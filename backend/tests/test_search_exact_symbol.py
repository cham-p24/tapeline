"""An exact symbol match must always be findable.

`search()` built a broad OR predicate (`symbol LIKE '%q%' OR name ILIKE '%q%'`)
and then truncated the candidate set with `ORDER BY score DESC LIMIT 60` BEFORE
the Python relevance ranking ran. The ranking that is supposed to float an exact
symbol to rank 0 only ever saw rows that had already survived a score-ordered
cut — so for any query whose match set exceeds 60 rows, the exact match was
silently discarded and could never be returned.

It bit every short query with wide name overlap, because `name ILIKE '%t%'`
alone matches nearly the entire universe. Verified against PRODUCTION before
the fix — each of these returned 10 rows with no exact match, while the ticker
endpoint served the symbol perfectly well:

    /api/search?q=T   → no AT&T        /api/ticker/T   → "AT&T Inc."
    /api/search?q=F   → no Ford        /api/ticker/F   → "Ford Motor Company"
    /api/search?q=A   → no Agilent     /api/ticker/A   → "Agilent Technologies"
    /api/search?q=AI  → no C3.ai       /api/ticker/AI  → "C3.ai, Inc."
    /api/search?q=C   → no Citigroup   /api/ticker/C   → "Citigroup Inc."

This endpoint backs the ⌘K palette, the public search box, and the public MCP
`search_tickers` tool that an AI assistant calls to resolve a company name to a
symbol before every other tool call — so the assistant concluded Tapeline does
not cover Ford and told the user so.

The relevance tiers now live in the ORDER BY, evaluated by the database before
the limit.
"""
from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import Ticker

_PREFIX = "ZSRCH"
# Comfortably more than the old `_MAX_LIMIT * 3` = 60 candidate cut.
_NOISE = 90


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _clear() -> None:
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.like(f"{_PREFIX}%")))
        await s.execute(delete(Ticker).where(Ticker.symbol == "ZQ"))
        await s.commit()


async def _seed() -> None:
    """One low-scoring EXACT match, buried under many high-scoring rows whose
    NAME contains the query — exactly the production shape."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    rows = [
        Ticker(
            symbol="ZQ",  # the exact match
            name="Zed Quality Corp",
            asset_class="equity",
            sector="Testonomicals",
            score=31.0,  # deliberately LOW, so a score-ordered cut drops it
            signal="CAUTION",
            updated_at=now,
            price=10.0,
            volume=100_000,
            change_pct_1d=0.1,
            confidence_pct=60,
            sub_trend=30,
            sub_rs=30,
            sub_momentum=30,
        )
    ]
    for i in range(_NOISE):
        rows.append(
            Ticker(
                symbol=f"{_PREFIX}{i:03d}",
                # Name contains "ZQ" so it matches the same OR predicate.
                name=f"Noise ZQ Holdings {i}",
                asset_class="equity",
                sector="Testonomicals",
                score=95.0 - (i * 0.1),  # all HIGHER than the exact match
                signal="HIGH CONVICTION",
                updated_at=now,
                price=20.0 + i,
                volume=200_000,
                change_pct_1d=0.1,
                confidence_pct=80,
                sub_trend=80,
                sub_rs=80,
                sub_momentum=80,
            )
        )
    async with session_scope() as s:
        s.add_all(rows)
        await s.commit()


@pytest.mark.asyncio
async def test_exact_symbol_is_returned_even_when_buried_under_higher_scores(client):
    """THE regression. 90 higher-scoring name-matches used to evict the exact
    symbol before relevance ranking ever ran."""
    await _clear()
    await _seed()
    try:
        async with client:
            r = await client.get("/api/search?q=ZQ&limit=10")
            assert r.status_code == 200, r.text
            results = r.json()["results"]
        symbols = [x["symbol"] for x in results]
        assert "ZQ" in symbols, (
            f"exact symbol ZQ missing from {symbols} — it was cut by the "
            f"score-ordered candidate truncation before relevance ranking"
        )
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_exact_symbol_ranks_first(client):
    """Not just present — first. It is what the user typed."""
    await _clear()
    await _seed()
    try:
        async with client:
            r = await client.get("/api/search?q=ZQ&limit=10")
            results = r.json()["results"]
        assert results, "no results at all"
        assert results[0]["symbol"] == "ZQ", (
            f"exact match ranked {[x['symbol'] for x in results].index('ZQ')} "
            f"instead of 0"
        )
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_lowercase_query_still_finds_the_exact_symbol(client):
    """The ⌘K palette sends whatever the user typed."""
    await _clear()
    await _seed()
    try:
        async with client:
            r = await client.get("/api/search?q=zq&limit=10")
            results = r.json()["results"]
        assert results and results[0]["symbol"] == "ZQ"
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_relevance_tiers_are_preserved(client):
    """exact → symbol-prefix → symbol-contains → name-only, unchanged."""
    from datetime import UTC, datetime

    await _clear()
    now = datetime.now(UTC)
    async with session_scope() as s:
        s.add_all([
            # name-only match, highest score
            Ticker(symbol=f"{_PREFIX}NAME", name="Something ZQ Inc", asset_class="equity",
                   sector="Testonomicals", score=99.0, signal="HIGH CONVICTION",
                   updated_at=now, price=10.0, volume=1_000, change_pct_1d=0.1, confidence_pct=70,
                   sub_trend=70, sub_rs=70, sub_momentum=70),
            # symbol-contains
            Ticker(symbol=f"{_PREFIX}ZQ", name="Contains", asset_class="equity",
                   sector="Testonomicals", score=90.0, signal="HIGH CONVICTION",
                   updated_at=now, price=10.0, volume=1_000, change_pct_1d=0.1, confidence_pct=70,
                   sub_trend=70, sub_rs=70, sub_momentum=70),
            # symbol-prefix
            Ticker(symbol="ZQPREFIX", name="Prefix", asset_class="equity",
                   sector="Testonomicals", score=80.0, signal="STRONG SETUP",
                   updated_at=now, price=10.0, volume=1_000, change_pct_1d=0.1, confidence_pct=70,
                   sub_trend=70, sub_rs=70, sub_momentum=70),
            # exact, lowest score
            Ticker(symbol="ZQ", name="Exact", asset_class="equity",
                   sector="Testonomicals", score=10.0, signal="WEAK",
                   updated_at=now, price=10.0, volume=1_000, change_pct_1d=0.1, confidence_pct=70,
                   sub_trend=10, sub_rs=10, sub_momentum=10),
        ])
        await s.commit()
    try:
        async with client:
            r = await client.get("/api/search?q=ZQ&limit=10")
            got = [x["symbol"] for x in r.json()["results"]]
        assert got[0] == "ZQ", f"exact not first: {got}"
        assert got[1] == "ZQPREFIX", f"prefix not second: {got}"
        assert got.index(f"{_PREFIX}ZQ") < got.index(f"{_PREFIX}NAME"), (
            f"symbol-contains must outrank name-only: {got}"
        )
    finally:
        await _clear()
        async with session_scope() as s:
            await s.execute(delete(Ticker).where(Ticker.symbol == "ZQPREFIX"))
            await s.commit()


@pytest.mark.asyncio
async def test_limit_is_respected(client):
    await _clear()
    await _seed()
    try:
        async with client:
            r = await client.get("/api/search?q=ZQ&limit=5")
            assert len(r.json()["results"]) == 5
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_like_metacharacters_are_still_escaped(client):
    """`_` and `%` must stay literal — the escaping guard is unchanged."""
    await _clear()
    await _seed()
    try:
        async with client:
            r = await client.get("/api/search?q=%25&limit=10")
            assert r.status_code == 200
            # '%' matches nothing literally in the seeded set.
            syms = [x["symbol"] for x in r.json()["results"]]
            assert not any(s.startswith(_PREFIX) or s == "ZQ" for s in syms), syms
    finally:
        await _clear()
