"""
Back-check job — populates next-day performance on yesterday's scorecard entries.

Runs once per day, ~1 hour after market close. For each entry logged yesterday
that doesn't yet have a next-day price, fetch today's close and compute:
    - change_pct_1d_after
    - spy_change_pct_1d
    - alpha_vs_spy
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyScorecardEntry, Ticker

logger = logging.getLogger(__name__)


async def backcheck_yesterday(session: AsyncSession, as_of_override: date | None = None) -> int:
    """Fill in next-day performance for a specific day (defaults to yesterday)."""
    target = as_of_override or (date.today() - timedelta(days=1))

    # Fetch SPY's current price as the "next day" reference
    spy_result = await session.execute(select(Ticker).where(Ticker.symbol == "SPY"))
    spy = spy_result.scalar_one_or_none()
    if spy is None or spy.price is None:
        logger.warning("backcheck.no_spy_price target=%s", target)
        return 0

    # Approximate yesterday's SPY price from change_pct_1d
    spy_yesterday = spy.price / (1 + (spy.change_pct_1d or 0) / 100) if spy.change_pct_1d else spy.price
    spy_move = ((spy.price / spy_yesterday) - 1) * 100 if spy_yesterday else 0.0

    # Find unscored entries for that date
    entries_result = await session.execute(
        select(DailyScorecardEntry)
        .where(DailyScorecardEntry.as_of == target, DailyScorecardEntry.price_next_day.is_(None))
    )
    entries = entries_result.scalars().all()
    if not entries:
        return 0

    # Load current prices for all those symbols in one query
    symbols = [e.symbol for e in entries]
    tickers_result = await session.execute(select(Ticker).where(Ticker.symbol.in_(symbols)))
    current_prices = {t.symbol: t.price for t in tickers_result.scalars().all() if t.price is not None}

    scored = 0
    for e in entries:
        now_price = current_prices.get(e.symbol)
        if now_price is None:
            continue
        pct = ((now_price / e.price_at_flag) - 1) * 100 if e.price_at_flag else 0.0
        e.price_next_day = now_price
        e.change_pct_1d_after = round(pct, 3)
        e.spy_change_pct_1d = round(spy_move, 3)
        e.alpha_vs_spy = round(pct - spy_move, 3)
        scored += 1

    await session.commit()
    logger.info("backcheck.done target=%s scored=%d", target, scored)
    return scored
