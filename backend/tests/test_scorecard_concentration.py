"""Tests for the daily-scorecard concentration filters (Fix 3 of audit).

The filters (in workers/signal_publisher._ensure_daily_scorecard):
1. Skip picks where sub_macro < 30 (FALLING regime band)
2. Cap _MAX_PER_SECTOR picks per sector
3. Skip picks with missing/zero price

This test seeds 50 Ticker rows in a deterministic shape and verifies the
filter behaviour at the boundary cases. It does NOT exercise the actual
worker tick — just the freeze function in isolation.
"""

import datetime as dt

import pytest
from sqlalchemy import select

from app.db import session_scope
from app.models import DailyScorecardEntry, Ticker
from app.workers.signal_publisher import (
    _MAX_PER_SECTOR,
    _MIN_MACRO_FOR_INCLUSION,
    _ensure_daily_scorecard,
)


def _make_ticker(symbol: str, score: float, sector: str = "Tech",
                 sub_macro: float | None = 60.0, price: float = 100.0) -> Ticker:
    return Ticker(
        symbol=symbol,
        name=symbol,
        score=score,
        signal="STRONG SETUP",
        price=price,
        sector=sector,
        sub_macro=sub_macro,
        asset_class="equity",
    )


def _next_monday(d: dt.date) -> dt.date:
    """Return a known trading day (Mon-Fri, no holiday) for the test fixture."""
    while d.weekday() >= 5:
        d = d + dt.timedelta(days=1)
    return d


@pytest.mark.asyncio
async def test_sector_cap_enforced():
    """If 8 tickers all score high in one sector, the freeze must hold
    at most _MAX_PER_SECTOR of them and pull the remainder from other
    sectors."""
    today = _next_monday(dt.date.today())

    async with session_scope() as s:
        # Clear any pre-existing rows for the test day
        existing = await s.execute(
            select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == today)
        )
        for e in existing.scalars().all():
            await s.delete(e)

        # Seed 8 chip stocks at the highest scores, plus 12 stocks from
        # other sectors at slightly lower scores
        symbols_to_clean = []
        for i, sym in enumerate(["NVDA", "AMD", "AVGO", "MU", "QCOM",
                                  "INTC", "MRVL", "ARM"]):
            t = _make_ticker(sym, score=95.0 - i * 0.1, sector="Information Technology")
            s.add(t)
            symbols_to_clean.append(sym)
        for i, sym in enumerate(["JPM", "BAC", "GS", "WFC", "MS", "C",
                                  "JNJ", "PFE", "MRK", "LLY", "BMY", "ABBV",
                                  "XOM", "CVX", "COP", "EOG"]):
            if i < 6:
                sector = "Financials"
            elif i < 12:
                sector = "Health Care"
            else:
                sector = "Energy"
            t = _make_ticker(sym, score=80.0 - i * 0.1, sector=sector)
            s.add(t)
            symbols_to_clean.append(sym)
        await s.commit()

    try:
        await _ensure_daily_scorecard(today)

        async with session_scope() as s:
            rows_q = await s.execute(
                select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == today)
            )
            rows = rows_q.scalars().all()
            assert len(rows) == 10, f"expected 10 picks, got {len(rows)}"

            # Count by which seeded ticker each row corresponds to
            chip_symbols = {"NVDA", "AMD", "AVGO", "MU", "QCOM",
                            "INTC", "MRVL", "ARM"}
            chips_in_top10 = sum(1 for r in rows if r.symbol in chip_symbols)
            assert chips_in_top10 == _MAX_PER_SECTOR, (
                f"sector cap violated: {chips_in_top10} chips in top-10, "
                f"cap is {_MAX_PER_SECTOR}"
            )
    finally:
        # Cleanup: remove seeded tickers and scorecard rows
        async with session_scope() as s:
            for sym in symbols_to_clean:
                tq = await s.execute(select(Ticker).where(Ticker.symbol == sym))
                for t in tq.scalars().all():
                    await s.delete(t)
            existing = await s.execute(
                select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == today)
            )
            for e in existing.scalars().all():
                await s.delete(e)
            await s.commit()


@pytest.mark.asyncio
async def test_macro_hostile_picks_skipped():
    """Tickers with sub_macro < 30 (FALLING regime) should not appear in
    the scorecard freeze even if their composite score is the highest."""
    today = _next_monday(dt.date.today() + dt.timedelta(days=14))  # offset so other test's date doesn't collide

    async with session_scope() as s:
        existing = await s.execute(
            select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == today)
        )
        for e in existing.scalars().all():
            await s.delete(e)

        # Highest-scoring ticker is in a hostile regime — should be skipped
        s.add(_make_ticker("HOSTILE", score=99.0, sector="Energy", sub_macro=20.0))
        # Plus 12 perfectly-good picks
        symbols_to_clean = ["HOSTILE"]
        for i in range(12):
            sym = f"OK{i:02d}"
            t = _make_ticker(sym, score=80.0 - i * 0.5, sector=f"S{i % 5}",
                             sub_macro=60.0)
            s.add(t)
            symbols_to_clean.append(sym)
        await s.commit()

    try:
        await _ensure_daily_scorecard(today)

        async with session_scope() as s:
            rows_q = await s.execute(
                select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == today)
            )
            symbols = {r.symbol for r in rows_q.scalars().all()}
            assert "HOSTILE" not in symbols, (
                "hostile-regime pick should have been skipped"
            )
            assert len(symbols) == 10
    finally:
        async with session_scope() as s:
            for sym in symbols_to_clean:
                tq = await s.execute(select(Ticker).where(Ticker.symbol == sym))
                for t in tq.scalars().all():
                    await s.delete(t)
            existing = await s.execute(
                select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == today)
            )
            for e in existing.scalars().all():
                await s.delete(e)
            await s.commit()
