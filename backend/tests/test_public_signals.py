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

        # Factors populated so these read as real composites (the data-quality
        # floor drops rows with <2 of 6 factors); isolates the signal filter.
        s.add_all([
            Ticker(symbol="TEST_HIC", name="Hic Inc", asset_class="equity",
                   score=92.0, signal="HIGH CONVICTION",
                   sub_trend=90, sub_rs=88, sub_momentum=92),
            Ticker(symbol="TEST_NEU", name="Neutral Inc", asset_class="equity",
                   score=45.0, signal="NEUTRAL",
                   sub_trend=45, sub_rs=44, sub_momentum=46),
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

        # Factors populated so these read as real composites (the data-quality
        # floor drops rows with <2 of 6 factors); isolates the min_score filter.
        s.add_all([
            Ticker(symbol="TEST_HI", name="High Inc", asset_class="equity",
                   score=95.0, signal="HIGH CONVICTION",
                   sub_trend=95, sub_rs=93, sub_momentum=96),
            Ticker(symbol="TEST_LO", name="Low Inc", asset_class="equity",
                   score=20.0, signal="WEAK",
                   sub_trend=22, sub_rs=18, sub_momentum=20),
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


@pytest.mark.asyncio
async def test_public_signals_excludes_stale_ghost(client):
    """A stale 'ghost' row must NOT appear even when its score outranks every
    fresh row — the freshness floor (app.services.ticker_freshness) drops it.

    Regression guard for the ghost-row bug: tickers that drop out of the
    analyst's active sheet are not deleted; they linger carrying their last
    score. Pre-fix, a 12-day-stale ghost holding a raw >=98 momentum score
    outranked every fresh 6-factor composite (~45-90) and dominated the
    public ranking on a 'shows its work' product. The floor keeps only rows
    within STALE_WINDOW_DAYS of the latest refresh.
    """
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    async with session_scope() as s:
        existing = await s.execute(
            select(Ticker).where(Ticker.symbol.in_(("TEST_GHOST", "TEST_FRESH")))
        )
        for t in existing.scalars().all():
            await s.delete(t)
        await s.commit()

        # Both carry >=2 factors so they're valid composites — the ONLY reason
        # the ghost is dropped is staleness, which isolates the freshness floor.
        s.add_all([
            # Ghost: HIGHER score than anything fresh, but 60 days stale.
            Ticker(symbol="TEST_GHOST", name="Ghost Inc", asset_class="equity",
                   score=99.0, signal="STRONG SETUP",
                   updated_at=now - timedelta(days=60),
                   sub_trend=98, sub_rs=99, sub_momentum=99),
            # Fresh: lower score, current timestamp — anchors the window.
            Ticker(symbol="TEST_FRESH", name="Fresh Inc", asset_class="equity",
                   score=70.0, signal="STRONG SETUP",
                   updated_at=now,
                   sub_trend=68, sub_rs=72, sub_momentum=70),
        ])
        await s.commit()

    async with client:
        r = await client.get("/api/public/signals?limit=2000")
        assert r.status_code == 200
        symbols = {row["symbol"] for row in r.json()["items"]}
        # Fresh row present despite its LOWER score...
        assert "TEST_FRESH" in symbols
        # ...and the higher-scoring ghost is excluded by the freshness floor.
        assert "TEST_GHOST" not in symbols

    async with session_scope() as s:
        for sym in ("TEST_GHOST", "TEST_FRESH"):
            row = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_public_signals_excludes_corrupt_rows(client):
    """Deterministic data-quality floor (app.services.ticker_freshness): three
    corruption signatures must be dropped even when the row is perfectly FRESH,
    while two look-alike-but-legit rows must survive.

    All seeds carry a current ``updated_at`` so the freshness cutoff can't be
    what excludes them — this isolates the data-quality clauses:

      DROP  TEST_OVER   score=104  -> impossible for a clamped 0-100 composite
      DROP  'ZZ WSPACE' (a space)  -> sheet annotation ingested as a symbol
                                      (the '🏆 IVV' bug), would emit broken URLs
      DROP  TEST_THIN   1 factor   -> pre-composite ghost (<2 of 6 factors)
      KEEP  TESTOIL=F   3 factors  -> a real futures symbol ('=' but no space)
      KEEP  TEST_2F     2 factors  -> the >=2 threshold is inclusive
    """
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    seeds = ("TEST_OVER", "ZZ WSPACE", "TEST_THIN", "TESTOIL=F", "TEST_2F")
    async with session_scope() as s:
        existing = await s.execute(select(Ticker).where(Ticker.symbol.in_(seeds)))
        for t in existing.scalars().all():
            await s.delete(t)
        await s.commit()

        s.add_all([
            # Raw factor value leaked into score: > 100 is impossible for the
            # clamped composite. Otherwise pristine (fresh, full factors, no
            # space) so ONLY the score>100 clause can drop it.
            Ticker(symbol="TEST_OVER", name="Over Inc", asset_class="equity",
                   score=104.0, signal="STRONG SETUP", updated_at=now,
                   sub_trend=90, sub_rs=90, sub_fundamentals=90,
                   sub_momentum=90, sub_macro=90, sub_smart_money=90),
            # Space in the symbol = an annotation ("🏆 IVV") ingested as a ticker.
            # Valid score + full factors so ONLY notlike("% %") can drop it.
            Ticker(symbol="ZZ WSPACE", name="Annotation Inc", asset_class="equity",
                   score=88.0, signal="STRONG SETUP", updated_at=now,
                   sub_trend=80, sub_rs=80, sub_fundamentals=80,
                   sub_momentum=80, sub_macro=80, sub_smart_money=80),
            # Only one populated factor -> a pre-composite ghost. Valid score,
            # no space, so ONLY the <2-factor clause can drop it.
            Ticker(symbol="TEST_THIN", name="Thin Inc", asset_class="equity",
                   score=95.0, signal="STRONG SETUP", updated_at=now,
                   sub_rs=95.0),
            # Real commodity-future: contains '=' but NO space. Must survive —
            # proves the symbol filter is space-specific, not "any non-alnum".
            Ticker(symbol="TESTOIL=F", name="Test Oil Future", asset_class="future",
                   score=80.0, signal="STRONG SETUP", updated_at=now,
                   sub_trend=70, sub_rs=75, sub_macro=80),
            # Exactly two factors: the >=2 threshold is inclusive, so KEEP.
            Ticker(symbol="TEST_2F", name="Two Factor Inc", asset_class="equity",
                   score=70.0, signal="STRONG SETUP", updated_at=now,
                   sub_trend=65, sub_rs=75),
        ])
        await s.commit()

    async with client:
        r = await client.get("/api/public/signals?limit=2000")
        assert r.status_code == 200
        symbols = {row["symbol"] for row in r.json()["items"]}
        # Corrupt rows excluded despite being fresh...
        assert "TEST_OVER" not in symbols   # score > 100
        assert "ZZ WSPACE" not in symbols   # space in symbol
        assert "TEST_THIN" not in symbols   # < 2 factors
        # ...legit look-alikes preserved.
        assert "TESTOIL=F" in symbols       # futures '=F' kept
        assert "TEST_2F" in symbols         # exactly 2 factors kept

    async with session_scope() as s:
        for sym in seeds:
            row = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
        await s.commit()
