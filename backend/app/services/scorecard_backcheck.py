"""
Back-check job — populates next-day performance on yesterday's scorecard entries.

Runs once per day, ~1 hour after market close. For each entry logged on a
prior trading day that doesn't yet have a next-day price, fetch the close
from the data feed and compute:
    - change_pct_1d_after
    - spy_change_pct_1d
    - alpha_vs_spy

Two design decisions worth knowing:

1. **Trading-day filter.** US markets close Sat/Sun and on ~9 federal
   holidays. The worker still ticks on those days (UTC time keeps moving),
   but a "next day" comparison across a non-trading day is meaningless —
   prices haven't moved because the market wasn't open. We skip non-trading
   targets entirely; the back-check will pick them up on the next run.

2. **Real next-day close, not live snapshot.** The previous version read
   `Ticker.price` as the "next day" price. That's the live current price,
   which on weekends or before the next session opens equals the price-at-
   flag → every row gets recorded as 0% return. Now we fetch the actual
   close from the Polygon/Massive aggregates endpoint when a vendor key is
   configured. When no key is configured (dev / mock mode), we fall through
   to `Ticker.price` ONLY when it differs meaningfully from `price_at_flag`
   — same-value snapshots are skipped and retried on the next run.

3. **Terminal skips vs. retries.** A pending date is either "not ready yet"
   (retry it) or "can never be scored" (stop). Non-trading days, dates whose
   remaining rows all have a zero/missing `price_at_flag`, and dates too old
   for the vendor to still serve history are terminal — see `_TERMINAL_DATES`.
   Everything else keeps retrying. Without that split the unscorable dates sat
   at the head of the oldest-first backlog forever and blocked newer ones.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyScorecardEntry, Ticker
from app.services.polygon_feed import _api_key as _polygon_key
from app.services.polygon_feed import fetch_aggregates

logger = logging.getLogger(__name__)


# Major US market holidays — federal holidays the NYSE / NASDAQ observe.
# Kept conservative; missing one means we'd back-check across a closed day
# and skip naturally because Polygon returns no aggregate. The list is
# refreshed annually; entries past their date stay harmless.
#
# NYSE observance rules baked into the dates below: a holiday falling on a
# Saturday is observed the preceding Friday, one falling on a Sunday the
# following Monday — EXCEPT New Year's Day, which is simply not observed when
# it lands on a Saturday (hence no New Year entry for 2028).
_US_MARKET_HOLIDAYS_2026: set[date] = {
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # MLK Day
    date(2026, 2, 16),   # Presidents Day
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # July 4 observed (4th is Saturday)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving
    date(2026, 12, 25),  # Christmas
}

_US_MARKET_HOLIDAYS_2027: set[date] = {
    date(2027, 1, 1),    # New Year's Day
    date(2027, 1, 18),   # MLK Day
    date(2027, 2, 15),   # Presidents Day
    date(2027, 3, 26),   # Good Friday
    date(2027, 5, 31),   # Memorial Day
    date(2027, 6, 18),   # Juneteenth observed (19th is Saturday)
    date(2027, 7, 5),    # July 4 observed (4th is Sunday)
    date(2027, 9, 6),    # Labor Day
    date(2027, 11, 25),  # Thanksgiving
    date(2027, 12, 24),  # Christmas observed (25th is Saturday)
}

_US_MARKET_HOLIDAYS_2028: set[date] = {
    # No New Year's Day entry — Jan 1 2028 is a Saturday and the NYSE does
    # not close the preceding Friday for it.
    date(2028, 1, 17),   # MLK Day
    date(2028, 2, 21),   # Presidents Day
    date(2028, 4, 14),   # Good Friday
    date(2028, 5, 29),   # Memorial Day
    date(2028, 6, 19),   # Juneteenth
    date(2028, 7, 4),    # Independence Day
    date(2028, 9, 4),    # Labor Day
    date(2028, 11, 23),  # Thanksgiving
    date(2028, 12, 25),  # Christmas
}

_US_MARKET_HOLIDAYS_2029: set[date] = {
    date(2029, 1, 1),    # New Year's Day
    date(2029, 1, 15),   # MLK Day
    date(2029, 2, 19),   # Presidents Day
    date(2029, 3, 30),   # Good Friday
    date(2029, 5, 28),   # Memorial Day
    date(2029, 6, 19),   # Juneteenth
    date(2029, 7, 4),    # Independence Day
    date(2029, 9, 3),    # Labor Day
    date(2029, 11, 22),  # Thanksgiving
    date(2029, 12, 25),  # Christmas
}

_US_MARKET_HOLIDAYS: set[date] = (
    _US_MARKET_HOLIDAYS_2026
    | _US_MARKET_HOLIDAYS_2027
    | _US_MARKET_HOLIDAYS_2028
    | _US_MARKET_HOLIDAYS_2029
)

# Years the table above actually covers. Anything outside this range is a
# silent-wrong-answer risk (we'd treat every closed session as a trading day),
# so `is_trading_day` logs loudly instead of quietly assuming "open".
_HOLIDAY_COVERAGE_YEARS: frozenset[int] = frozenset(
    d.year for d in _US_MARKET_HOLIDAYS
)

# Years we've already warned about — `_next_trading_day` calls `is_trading_day`
# in a loop, so warn once per year per process rather than per call.
_warned_uncovered_years: set[int] = set()


# ---------------------------------------------------------------------------
# Terminal skips — dates the back-check can never finish
# ---------------------------------------------------------------------------
# `backcheck_all_pending` replays every `as_of` that still has rows with
# `price_next_day IS NULL`, oldest first. Some of those dates can NEVER be
# completed: entries logged on a non-trading day, entries whose `price_at_flag`
# is zero/missing (no baseline to compute a return from), and long-past dates
# whose vendor history simply isn't retrievable any more. Retrying them every
# run kept them parked at the head of the oldest-first queue and starved newer,
# scorable dates — the backlog never drained. Those dates are recorded here
# with a reason and excluded from subsequent drains.
#
# Only structurally-unscorable dates land here. "Not ready yet" cases (the next
# session hasn't happened, a vendor fetch failed on a recent date) are left
# pending and retried as before.
#
# The registry is in-process only — `daily_scorecard` has no "skipped" column,
# and adding one is a migration this fix doesn't need. That also means a
# restart re-evaluates each date exactly once, so nothing is permanently
# written off on the strength of a single bad run.
_TERMINAL_DATES: dict[date, str] = {}

# How long a date stays retryable while its data is missing. Inside this window
# a failed fetch is "not ready yet" (vendor blip, key rotation, batch lag) and
# is retried. Past it, missing data is treated as never coming.
_MAX_BACKCHECK_AGE_DAYS = 90


def _mark_terminal(d: date, reason: str) -> None:
    """Record `d` as never-scorable so the drain stops re-attempting it."""
    if d in _TERMINAL_DATES:
        return
    _TERMINAL_DATES[d] = reason
    logger.warning(
        "backcheck.terminal_skip target=%s reason=%s - this date can never be "
        "back-checked; dropping it from the backlog so newer dates can drain.",
        d, reason,
    )


def terminal_skips() -> dict[date, str]:
    """Dates this process has given up on, mapped to the reason (observability)."""
    return dict(_TERMINAL_DATES)


def is_trading_day(d: date) -> bool:
    """True if US equity markets are open on `d`.

    Weekends are always closed. Holidays are looked up in `_US_MARKET_HOLIDAYS`,
    which is a hand-maintained table. For a date in a year the table does not
    cover we can only fall back to the weekday check — that is wrong on ~9 days
    a year, so we emit a warning (once per year per process) telling whoever
    reads the logs to extend the table.
    """
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    if d.year not in _HOLIDAY_COVERAGE_YEARS and d.year not in _warned_uncovered_years:
        _warned_uncovered_years.add(d.year)
        logger.warning(
            "backcheck.holiday_table_uncovered_year year=%d covered=%s - market "
            "holidays for this year are unknown, weekday-only fallback in use. "
            "Extend _US_MARKET_HOLIDAYS in app/services/scorecard_backcheck.py.",
            d.year, sorted(_HOLIDAY_COVERAGE_YEARS),
        )
    return d not in _US_MARKET_HOLIDAYS


def _next_trading_day(d: date) -> date:
    """First trading day strictly after `d`."""
    nxt = d + timedelta(days=1)
    while not is_trading_day(nxt):
        nxt = nxt + timedelta(days=1)
    return nxt


async def _fetch_close(symbol: str, on: date) -> float | None:
    """Real close on `on` for `symbol`, or None if unavailable.

    Uses Polygon/Massive aggregates when a vendor key is configured. Returns
    None on any failure or in dev/mock mode (no key) so the caller can fall
    back to other strategies.
    """
    if not _polygon_key():
        logger.warning("backcheck.fetch_close_no_key symbol=%s on=%s", symbol, on)
        return None
    try:
        bars = await fetch_aggregates(symbol, from_date=on, to_date=on)
        if not bars:
            logger.warning("backcheck.fetch_close_empty symbol=%s on=%s", symbol, on)
            return None
        # Aggregates schema: {"c": close, "h": high, "l": low, "o": open, ...}
        close = bars[0].get("c")
        return float(close) if close is not None else None
    except Exception:
        logger.exception("backcheck.fetch_close_failed symbol=%s on=%s", symbol, on)
        return None


async def _fetch_close_window(symbol: str, start: date, end: date) -> dict[date, float]:
    """Bulk fetch closes for a date range. {date: close} indexed by trading date.

    Single API call instead of one-per-date — Massive returns the whole
    range in one body. Used for SPY back-check so we don't hammer the
    aggregates endpoint per scorecard entry.
    """
    if not _polygon_key():
        return {}
    try:
        bars = await fetch_aggregates(symbol, from_date=start, to_date=end)
    except Exception:
        logger.exception("backcheck.window_fetch_failed symbol=%s start=%s end=%s", symbol, start, end)
        return {}
    out: dict[date, float] = {}
    for b in bars:
        ts_ms = b.get("t")
        close = b.get("c")
        if ts_ms is None or close is None:
            continue
        # `t` is the bar's start timestamp in ms — for daily bars this is
        # midnight of the trading day in US/Eastern (Massive normalises).
        bar_date = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).date()
        out[bar_date] = float(close)
    return out


async def backcheck_yesterday(session: AsyncSession, as_of_override: date | None = None) -> int:
    """Fill in next-day performance for entries logged on `as_of_override`
    (defaults to yesterday in UTC). Returns the number of entries updated.

    Skips entries when:
      - `as_of_override` is not a trading day (we'd be comparing across closed market)
      - the next trading day hasn't occurred yet (back-check too early)
      - `price_at_flag` is missing/zero (broken upstream data — would divide by zero)
      - we can't determine a real next-day close (no vendor key + live snapshot
        equals flag price → we skip and retry next run rather than write 0%)
    """
    target = as_of_override or (datetime.now(UTC).date() - timedelta(days=1))
    today = datetime.now(UTC).date()
    age_days = (today - target).days

    if not is_trading_day(target):
        # Structural: the market was shut on `target`, so there is no
        # flag-day close to measure from. No future run changes that.
        _mark_terminal(target, "non_trading_day")
        logger.info("backcheck.skip_non_trading_day target=%s", target)
        return 0

    next_day = _next_trading_day(target)
    if next_day > today:
        # Back-check fired before the next market session — nothing to compare yet.
        logger.info("backcheck.skip_too_early target=%s next=%s today=%s", target, next_day, today)
        return 0

    # Pull all entries for that target date that don't yet have a next-day price.
    entries_result = await session.execute(
        select(DailyScorecardEntry)
        .where(
            DailyScorecardEntry.as_of == target,
            DailyScorecardEntry.price_next_day.is_(None),
        )
    )
    entries = entries_result.scalars().all()
    if not entries:
        return 0

    if all(not e.price_at_flag or e.price_at_flag <= 0 for e in entries):
        # Structural: every remaining row has a missing/zero baseline price, so
        # there is no percentage to compute — and `price_at_flag` is written
        # once at flag time and never revisited. Bail before spending the SPY
        # fetch on a date that can't produce a single scored row.
        _mark_terminal(target, "no_baseline_price")
        return 0

    # SPY closes for both flag and next-day. Single bulk fetch — gives us
    # actual historical bars from Massive instead of the previous fallback
    # that "reconstructed" SPY from the live snapshot, which produced the
    # same wrong percent for every historical day. If neither real close is
    # available we skip and try again next run rather than write wrong data.
    spy_window = await _fetch_close_window("SPY", target, next_day)
    spy_at_flag = spy_window.get(target)
    spy_next = spy_window.get(next_day)
    if not spy_at_flag or not spy_next or spy_at_flag <= 0 or spy_next <= 0:
        logger.warning(
            "backcheck.spy_window_incomplete target=%s next=%s flag=%s next_close=%s "
            "(skipping back-check this run rather than write wrong values)",
            target, next_day, spy_at_flag, spy_next,
        )
        if age_days > _MAX_BACKCHECK_AGE_DAYS:
            # Old enough that "the vendor will have it next run" is no longer a
            # credible explanation — the history isn't coming.
            _mark_terminal(
                target,
                f"spy_history_unavailable_after_{_MAX_BACKCHECK_AGE_DAYS}d",
            )
        return 0
    spy_move = ((spy_next / spy_at_flag) - 1) * 100

    # Same fallback pattern for picks: prefer real fetch, fall back to live snapshot
    # only when it's *meaningfully different* from price_at_flag.
    symbols = [e.symbol for e in entries]
    snapshot_q = await session.execute(select(Ticker).where(Ticker.symbol.in_(symbols)))
    snapshots = {t.symbol: t.price for t in snapshot_q.scalars().all() if t.price is not None}

    scored = 0
    skipped_zero_flag = 0
    skipped_stale = 0

    for e in entries:
        if not e.price_at_flag or e.price_at_flag <= 0:
            # Garbage upstream — can't compute a return from a $0 flag price.
            skipped_zero_flag += 1
            continue

        next_close = await _fetch_close(e.symbol, next_day)
        if next_close is None or next_close <= 0:
            # Fallback: live snapshot, only if it's not the stale-equals-flag value.
            snap = snapshots.get(e.symbol)
            if snap is None or snap == e.price_at_flag:
                # Either no data at all, or the bug pattern (snapshot identical
                # to flag — back-check ran before any real next-session price
                # showed up). Skip; tomorrow's run will retry.
                skipped_stale += 1
                continue
            next_close = float(snap)

        pct = ((next_close / e.price_at_flag) - 1) * 100
        e.price_next_day = next_close
        e.change_pct_1d_after = round(pct, 3)
        e.spy_change_pct_1d = round(spy_move, 3)
        e.alpha_vs_spy = round(pct - spy_move, 3)
        scored += 1

    await session.commit()
    logger.info(
        "backcheck.done target=%s next=%s scored=%d skipped_zero_flag=%d skipped_stale=%d",
        target, next_day, scored, skipped_zero_flag, skipped_stale,
    )

    unresolved = skipped_zero_flag + skipped_stale
    if unresolved and age_days > _MAX_BACKCHECK_AGE_DAYS:
        # Whatever is left on this date (delisted symbols, zero baselines, a
        # close the vendor never returned) has had the full window to resolve.
        # Rows already scored above are committed; we just stop revisiting.
        _mark_terminal(
            target,
            f"unresolvable_rows_after_{_MAX_BACKCHECK_AGE_DAYS}d "
            f"(zero_flag={skipped_zero_flag} stale={skipped_stale})",
        )
    return scored


async def backcheck_all_pending(session: AsyncSession, max_dates: int = 60) -> int:
    """Drain the back-check backlog: score every prior date that still has
    entries without a next-day price.

    `backcheck_yesterday` only ever scores a single date (today-1 by default).
    That is fine on a worker that reboots daily, but on a stable deploy any day
    the single-date job didn't run is stranded forever — its rows keep
    `price_next_day IS NULL` and nothing ever revisits them. This function
    finds every distinct `as_of` that still has unscored rows and replays
    `backcheck_yesterday(as_of_override=...)` for each, oldest first, so the
    backlog self-heals on the next tick.

    `max_dates` caps the work per run (each date is its own SPY + per-symbol
    fetch) so a large backlog can't stall the worker loop; remaining dates are
    picked up on subsequent runs. Dates whose next trading day hasn't happened
    yet are skipped cheaply inside `backcheck_yesterday` (returns 0).

    Structurally-unscorable dates (see `_TERMINAL_DATES`) are the reason the
    candidate query is no longer `LIMIT max_dates`. Those dates sort oldest and
    can never complete, so they used to occupy every slot of the cap run after
    run and permanently starve the newer, scorable dates behind them. Now they
    are skipped outright once identified, the cap counts only dates that were
    genuinely scorable, and a second (looser) cap bounds the fetches spent
    discovering newly-terminal dates in any one run.
    """
    rows = await session.execute(
        select(DailyScorecardEntry.as_of)
        .where(DailyScorecardEntry.price_next_day.is_(None))
        .group_by(DailyScorecardEntry.as_of)
        .order_by(DailyScorecardEntry.as_of.asc())
    )
    pending_dates = [d for (d,) in rows.all()]
    if not pending_dates:
        return 0

    max_attempts = max_dates * 3
    total = 0
    attempts = 0
    scorable_attempts = 0
    skipped_terminal = 0
    newly_terminal = 0

    for d in pending_dates:
        if d in _TERMINAL_DATES:
            skipped_terminal += 1
            continue
        if scorable_attempts >= max_dates or attempts >= max_attempts:
            break
        attempts += 1
        total += await backcheck_yesterday(session, as_of_override=d)
        if d in _TERMINAL_DATES:
            # The attempt just wrote this date off — it shouldn't burn budget
            # that was meant for dates the back-check can actually finish.
            newly_terminal += 1
        else:
            scorable_attempts += 1

    logger.info(
        "backcheck.drain pending_dates=%d attempted=%d scored=%d "
        "skipped_terminal=%d newly_terminal=%d",
        len(pending_dates), attempts, total, skipped_terminal, newly_terminal,
    )
    return total
