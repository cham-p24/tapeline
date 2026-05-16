"""Tests for /api/public/signals.

The endpoint is the no-auth, no-tier-cap view of the full Tapeline-scored
universe — the data layer behind the public /signals page. It must:

  - return 200 for unauthenticated callers
  - never tier-gate (Free, anonymous, Premium all see the same payload)
  - never apply the 24h data delay that /api/scanner applies to Free
  - filter on min_score and signal when those params are provided
  - cap row count at 2000 to bound payload size
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import Ticker


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_public_signals_returns_200_unauth(client):
    """Anonymous caller hits /api/public/signals and gets a 200 + the
    standard envelope. No 401, no 403, no signin redirect."""
    async with client:
        r = await client.get("/api/public/signals?limit=10")
        assert r.status_code == 200
        body = r.json()
        assert "count" in body
        assert "items" in body
        assert "limit" in body
        assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_public_signals_no_tier_delay(client):
    """The /api/scanner endpoint adds `data_delayed_minutes` to its response
    so the Free-tier 24h delay is observable. /api/public/signals must NOT
    have that field — it serves live data to every visitor."""
    async with client:
        r = await client.get("/api/public/signals?limit=1")
        assert r.status_code == 200
        body = r.json()
        assert "data_delayed_minutes" not in body
        # Also: no `tier` echo (scanner has it; public endpoint doesn't
        # apply tier logic so it has nothing to report)
        assert "tier" not in body


@pytest.mark.asyncio
async def test_public_signals_caps_limit_at_2000(client):
    """Even if the caller asks for 10000 rows, the endpoint caps at 2000
    so the JSON payload stays bounded. Defensive against scrapers + clients
    that pass user input into the limit param without sanitising."""
    async with client:
        r = await client.get("/api/public/signals?limit=99999")
        assert r.status_code == 200
        body = r.json()
        assert body["limit"] == 2000


@pytest.mark.asyncio
async def test_public_signals_filters_by_signal_label(client):
    """signal=HIGH+CONVICTION returns only HIGH CONVICTION rows. Seeds a
    couple of rows with deterministic signals so the assertion is stable
    regardless of what's in the DB."""
    async with session_scope() as s:
        # Clean any prior seed leftovers
        existing = await s.execute(select(Ticker).where(Ticker.symbol.in_(("TEST_HIC", "TEST_NEU"))))
        for t in existing.scalars().all():
            await s.delete(t)
        await s.commit()

        s.add_all([
            Ticker(symbol="TEST_HIC", name="Hic Inc", asset_class="equity",
                   score=92.0, signal="HIGH CONVICTION"),
            Ticker(symbol="TEST_NEU", name="Neutral Inc", asset_class="equity",
                   score=45.0, signal="NEUTRAL"),
        ])
        await s.commit()

    async with client:
        r = await client.get("/api/public/signals?signal=HIGH+CONVICTION&limit=2000")
        assert r.status_code == 200
        body = r.json()
        symbols = {row["symbol"] for row in body["items"]}
        assert "TEST_HIC" in symbols
        assert "TEST_NEU" not in symbols

    # Cleanup so the next run isn't polluted
    async with session_scope() as s:
        for sym in ("TEST_HIC", "TEST_NEU"):
            row = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_public_signals_min_score_floor(client):
    """min_score=80 must drop everything below the threshold."""
    async with session_scope() as s:
        existing = await s.execute(select(Ticker).where(Ticker.symbol.in_(("TEST_HI", "TEST_LO"))))
        for t in existing.scalars().all():
            await s.delete(t)
        await s.commit()

        s.add_all([
            Ticker(symbol="TEST_HI", name="High Inc", asset_class="equity",
                   score=95.0, signal="HIGH CONVICTION"),
            Ticker(symbol="TEST_LO", name="Low Inc", asset_class="equity",
                   score=20.0, signal="WEAK"),
        ])
        await s.commit()

    async with client:
        r = await client.get("/api/public/signals?min_score=80&limit=2000")
        assert r.status_code == 200
        body = r.json()
        symbols = {row["symbol"] for row in body["items"]}
        assert "TEST_HI" in symbols
        assert "TEST_LO" not in symbols

    async with session_scope() as s:
        for sym in ("TEST_HI", "TEST_LO"):
            row = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
        await s.commit()
