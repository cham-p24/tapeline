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


def is_trading_day(d: date) -> bool:
    """True if US equity markets are open on `d`."""
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return d not in _US_MARKET_HOLIDAYS_2026


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

    if not is_trading_day(target):
        logger.info("backcheck.skip_non_trading_day target=%s", target)
        return 0

    next_day = _next_trading_day(target)
    today = datetime.now(UTC).date()
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
    return scored
