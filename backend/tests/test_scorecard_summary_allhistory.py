"""The /api/scorecard summary must reflect ALL back-checked history.

routers/scorecard.get_scorecard computed its summary (days_tracked, hit-rate,
alpha) from the same trailing `days` display window it used for the per-day
picks. Its own docstring promised the summary "always reflect[s] ALL
back-checked data", the JSON-LD Dataset markup + marketing lean on it, and the
CSV/JSON export computes it over the full archive — so a windowed summary
understated the public track record (days_tracked=30 no matter how long the
record actually was) and disagreed with the export. This pins the fix.
"""
from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.main import app
from app.models import DailyScorecardEntry

_N = 35  # more than the default days=30 display window
_BASE = date(2024, 6, 1)
_DATES = [_BASE - timedelta(days=i) for i in range(_N)]
_SYMS = [f"SCHIST{i:02d}" for i in range(_N)]


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _seed() -> None:
    await _cleanup()
    async with SessionLocal() as s:
        for d, sym in zip(_DATES, _SYMS, strict=True):
            s.add(DailyScorecardEntry(
                as_of=d, symbol=sym, rank=1,
                score_at_flag=90.0, price_at_flag=100.0, price_next_day=101.0,
                change_pct_1d_after=1.0, spy_change_pct_1d=0.5, alpha_vs_spy=0.5,
            ))
        await s.commit()


async def _cleanup() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(DailyScorecardEntry).where(DailyScorecardEntry.symbol.in_(_SYMS)))
        await s.commit()


@pytest.mark.asyncio
async def test_summary_days_tracked_counts_all_history_not_the_window(client):
    """35 distinct back-checked sessions on record → days_tracked must be >= 35
    even though the caller asks for the default 30-day picks window. Pre-fix it
    was capped at the window (30)."""
    await _seed()
    try:
        async with client:
            r = await client.get("/api/scorecard", params={"days": 30})
            assert r.status_code == 200, r.text
            summary = r.json()["summary"]
            assert summary["days_tracked"] >= _N, (
                f"days_tracked={summary['days_tracked']} was capped to the "
                f"display window instead of counting all {_N}+ sessions"
            )
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_summary_is_stable_across_display_windows(client):
    """The headline trust stats must not move when the caller changes the picks
    window — days_tracked at days=5 must equal days_tracked at days=30, because
    the summary is all-history and only the picks list is windowed."""
    await _seed()
    try:
        async with client:
            small = (await client.get("/api/scorecard", params={"days": 5})).json()
            big = (await client.get("/api/scorecard", params={"days": 30})).json()
            assert small["summary"]["days_tracked"] == big["summary"]["days_tracked"]
            assert small["summary"]["days_tracked"] >= _N
    finally:
        await _cleanup()
