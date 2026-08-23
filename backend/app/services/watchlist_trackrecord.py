"""Personal watchlist track record — snapshot + next-day-vs-SPY back-check.

The per-user analogue of the public scorecard worker (workers/signal_publisher.py
:_ensure_daily_scorecard + services/scorecard_backcheck.py). Two jobs, both
driven from the scoring worker's tick:

- `ensure_watchlist_snapshot` freezes (score, price, signal) for every Premium
  user's watchlist ticker once per trading-day close. Unlike the public top-10 it
  applies NO sector cap / macro gate / liquidity floor — the user chose these
  names — but keeps the same zero-price skip and the same `min(score, 100)` clamp
  so a corrupt composite can't be frozen in.

- `backcheck_watchlist` fills next-day return, SPY's move, and alpha for pending
  rows, reusing the public back-check's helpers (trading-day calendar, real
  next-day closes, one bulk SPY fetch). It dedupes the per-symbol vendor fetch
  across users/rows so N users watching the same symbol costs ONE aggregate call
  per session, not N.

Read side (routers/watchlist.py:GET /track-record) is Premium-gated; the snapshot
is written only for Premium users so the table doesn't accrue rows for accounts
that can't see them. `summary_for_rows` mirrors routers/scorecard.py:_summary_stats
so the per-symbol numbers read the same as the public page.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from statistics import median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticker, User, WatchlistItem, WatchlistTrackRecordEntry
from app.services.scorecard_backcheck import (
    _fetch_close,
    _fetch_close_window,
    _next_trading_day,
    _session_is_complete,
    is_trading_day,
)

logger = logging.getLogger(__name__)

# A single session's absolute 1-day move above this is treated as a data
# artifact (split, bad tick, delisting) and excluded from the summary stats —
# same threshold + intent as routers/scorecard.py:_OUTLIER_PCT_THRESHOLD.
_OUTLIER_PCT_THRESHOLD = 50.0

# Cap on how many pending sessions a single back-check run drains, so a large
# backlog can't stall the worker loop. Each date is one SPY fetch + one fetch
# per distinct pending symbol on that date.
_MAX_BACKCHECK_DATES = 60


async def ensure_watchlist_snapshot(session: AsyncSession, today: date) -> int:
    """Freeze today's (score, price, signal) for every Premium user's watchlist
    ticker. Idempotent per (user, symbol, day). Returns rows written.

    Only runs on US trading days (the back-check assumes each row maps to a real
    next trading-day close). Must be called AFTER the US session close, same as
    the public freeze — `Ticker.price` is only today's close after the cash
    session ends.
    """
    if not is_trading_day(today):
        return 0

    # Premium users' watchlist symbols joined to the live Ticker snapshot.
    rows = await session.execute(
        select(WatchlistItem.user_id, Ticker)
        .join(User, User.id == WatchlistItem.user_id)
        .join(Ticker, Ticker.symbol == WatchlistItem.symbol)
        .where(User.tier == "premium")
    )
    candidates = rows.all()
    if not candidates:
        return 0

    # One query for everything already frozen today, so we don't do a per-row
    # existence check (idempotency without N round-trips).
    existing_rows = await session.execute(
        select(
            WatchlistTrackRecordEntry.user_id, WatchlistTrackRecordEntry.symbol
        ).where(WatchlistTrackRecordEntry.as_of == today)
    )
    already: set[tuple[str, str]] = {(u, s) for u, s in existing_rows.all()}

    written = 0
    skipped_zero_price = 0
    skipped_no_score = 0
    for user_id, t in candidates:
        if (user_id, t.symbol) in already:
            continue
        if not t.price or t.price <= 0:
            skipped_zero_price += 1
            continue
        if t.score is None:
            # No composite to freeze — skip; a later session will catch it.
            skipped_no_score += 1
            continue
        session.add(
            WatchlistTrackRecordEntry(
                user_id=user_id,
                as_of=today,
                symbol=t.symbol,
                # Defensive clamp, mirroring the public freeze — a corrupt >100
                # composite must never be frozen onto a track record.
                score_at_flag=min(t.score, 100.0),
                price_at_flag=float(t.price),
                signal_at_flag=t.signal,
            )
        )
        # Guard the unique (user, symbol, day) against the same symbol appearing
        # twice for a user across lists (shouldn't per the watchlist unique
        # constraint, but be safe against future multi-list dupes).
        already.add((user_id, t.symbol))
        written += 1

    await session.commit()
    logger.info(
        "watchlist_trackrecord.snapshot as_of=%s written=%d skipped_zero_price=%d "
        "skipped_no_score=%d",
        today, written, skipped_zero_price, skipped_no_score,
    )
    return written


async def backcheck_watchlist(
    session: AsyncSession, max_dates: int = _MAX_BACKCHECK_DATES
) -> int:
    """Fill next-day performance on pending watchlist track-record rows.

    Drains every prior session that still has rows without a next-day price,
    oldest first (self-healing after a worker gap). Per session it fetches SPY
    once and each distinct pending symbol's real next-day close once, then fans
    that close out to every user's row for that (symbol, session). Returns rows
    scored. Requires a vendor key (falls back to skip-and-retry without one).
    """
    pending = await session.execute(
        select(WatchlistTrackRecordEntry.as_of)
        .where(WatchlistTrackRecordEntry.price_next_day.is_(None))
        .group_by(WatchlistTrackRecordEntry.as_of)
        .order_by(WatchlistTrackRecordEntry.as_of.asc())
    )
    pending_dates = [d for (d,) in pending.all()]
    if not pending_dates:
        return 0

    today = datetime.now(UTC).date()
    total_scored = 0
    dates_done = 0

    for as_of in pending_dates:
        if dates_done >= max_dates:
            break
        if not is_trading_day(as_of):
            # A snapshot only ever writes on trading days, but guard anyway —
            # there is no next-day comparison across a closed session.
            continue
        next_day = _next_trading_day(as_of)
        if not _session_is_complete(next_day, today):
            # The next session hasn't FINISHED yet — nothing real to compare.
            # `next_day > today` alone accepted next_day == today, i.e. the
            # session still in progress, and the vendor's daily bar for an open
            # session carries the last trade so far rather than the close. Same
            # defect and same permanence as the public scorecard's back-check
            # (see services/scorecard_backcheck._session_is_complete): the row
            # gets a non-NULL price_next_day, so nothing revisits it.
            continue

        # SPY once for the whole date (the benchmark leg of every alpha).
        spy_window = await _fetch_close_window("SPY", as_of, next_day)
        spy_at_flag = spy_window.get(as_of)
        spy_next = spy_window.get(next_day)
        if not spy_at_flag or not spy_next or spy_at_flag <= 0 or spy_next <= 0:
            logger.warning(
                "watchlist_trackrecord.spy_window_incomplete as_of=%s next=%s",
                as_of, next_day,
            )
            continue
        spy_move = ((spy_next / spy_at_flag) - 1) * 100

        entries_result = await session.execute(
            select(WatchlistTrackRecordEntry).where(
                WatchlistTrackRecordEntry.as_of == as_of,
                WatchlistTrackRecordEntry.price_next_day.is_(None),
            )
        )
        entries = entries_result.scalars().all()

        # One vendor call per distinct symbol on this date, reused across users.
        close_cache: dict[str, float | None] = {}
        dates_done += 1
        for e in entries:
            if not e.price_at_flag or e.price_at_flag <= 0:
                continue
            if e.symbol not in close_cache:
                close_cache[e.symbol] = await _fetch_close(e.symbol, next_day)
            next_close = close_cache[e.symbol]
            if next_close is None or next_close <= 0:
                # No real close yet — leave pending, retry next run.
                continue
            pct = ((next_close / e.price_at_flag) - 1) * 100
            e.price_next_day = next_close
            e.change_pct_1d_after = round(pct, 3)
            e.spy_change_pct_1d = round(spy_move, 3)
            e.alpha_vs_spy = round(pct - spy_move, 3)
            total_scored += 1

    await session.commit()
    if total_scored:
        logger.info(
            "watchlist_trackrecord.backcheck scored=%d dates=%d",
            total_scored, dates_done,
        )
    return total_scored


def summary_for_rows(rows: list[WatchlistTrackRecordEntry]) -> dict:
    """Per-symbol summary stats over a symbol's back-checked rows.

    Mirrors routers/scorecard.py:_summary_stats — count only rows with a
    computed alpha, drop |1-day move| > threshold as data artifacts, then
    hit-rate = share with alpha > 0, plus median/avg alpha and 1-day return.
    `days_tracked` counts every frozen session (scored or not).
    """
    days_tracked = len({r.as_of for r in rows})
    scored = [
        r
        for r in rows
        if r.alpha_vs_spy is not None
        and r.change_pct_1d_after is not None
        and abs(r.change_pct_1d_after) <= _OUTLIER_PCT_THRESHOLD
    ]
    excluded = sum(
        1
        for r in rows
        if r.alpha_vs_spy is not None
        and r.change_pct_1d_after is not None
        and abs(r.change_pct_1d_after) > _OUTLIER_PCT_THRESHOLD
    )
    n = len(scored)
    if n == 0:
        return {
            "days_tracked": days_tracked,
            "entries_scored": 0,
            "entries_excluded_outliers": excluded,
            "avg_1d_return": None,
            "median_1d_return": None,
            "avg_alpha_vs_spy": None,
            "median_alpha_vs_spy": None,
            "hit_rate_beat_spy": None,
            "best_alpha": None,
            "worst_alpha": None,
        }
    alphas = [r.alpha_vs_spy for r in scored]
    returns = [r.change_pct_1d_after for r in scored]
    beats = sum(1 for a in alphas if a > 0)
    return {
        "days_tracked": days_tracked,
        "entries_scored": n,
        "entries_excluded_outliers": excluded,
        "avg_1d_return": round(sum(returns) / n, 3),
        "median_1d_return": round(median(returns), 3),
        "avg_alpha_vs_spy": round(sum(alphas) / n, 3),
        "median_alpha_vs_spy": round(median(alphas), 3),
        "hit_rate_beat_spy": round(beats / n * 100, 1),
        "best_alpha": round(max(alphas), 3),
        "worst_alpha": round(min(alphas), 3),
    }
