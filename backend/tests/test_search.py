"""GET /api/search — ticker navigation search (symbol OR name), relevance-ranked.

Public + tier-agnostic (it's wayfinding to pages you can already visit). Seeds
fresh, valid Ticker rows (mirrors test_cap_hit_instrumentation's universe seed so
they pass the live_clauses freshness/quality floor) and asserts symbol matching,
name matching, exact-symbol-first ranking, and the empty-query short-circuit.
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.main import app
from app.models import Ticker


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _seed(symbol: str, name: str, score: float = 80.0) -> None:
    now = datetime.now(UTC)
    async with session_scope() as s:
        existing = (
            await s.execute(select(Ticker).where(Ticker.symbol == symbol))
        ).scalar_one_or_none()
        if existing is None:
            s.add(Ticker(
                symbol=symbol,
                name=name,
                asset_class="stock",
                score=score,
                change_pct_1d=1.0,
                confidence_pct=90.0,
                sub_trend=70.0,
                sub_rs=65.0,
                updated_at=now,
            ))
            await s.commit()


async def _cleanup(symbols: list[str]) -> None:
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(symbols)))
        await s.commit()


@pytest.mark.asyncio
async def test_empty_query_returns_empty(client):
    async with client:
        r = await client.get("/api/search?q=")
        assert r.status_code == 200, r.text
        assert r.json()["results"] == []


@pytest.mark.asyncio
async def test_matches_symbol_and_name(client):
    syms = ["ZZSRCHA", "ZZSRCHB"]
    try:
        await _seed("ZZSRCHA", "Zeta Searchable Alpha Corp", 88.0)
        await _seed("ZZSRCHB", "Beta Unrelated Holdings Inc", 80.0)
        async with client:
            # Symbol substring hits both.
            r = await client.get("/api/search?q=ZZSRCH")
            assert r.status_code == 200, r.text
            got = {x["symbol"] for x in r.json()["results"]}
            assert {"ZZSRCHA", "ZZSRCHB"} <= got

            # Name substring hits only the one whose NAME contains it.
            r2 = await client.get("/api/search?q=Zeta Searchable")
            got2 = [x["symbol"] for x in r2.json()["results"]]
            assert "ZZSRCHA" in got2
            assert "ZZSRCHB" not in got2
    finally:
        await _cleanup(syms)


@pytest.mark.asyncio
async def test_exact_symbol_ranks_first_over_higher_score(client):
    """An exact symbol match beats a higher-scoring prefix match — relevance,
    not score, wins the top slot for a navigation query."""
    syms = ["ABXX", "ABXXTRAIL"]
    try:
        await _seed("ABXXTRAIL", "Trailing Prefix Co", 99.0)  # higher score
        await _seed("ABXX", "Exact Symbol Co", 40.0)          # exact, lower score
        async with client:
            r = await client.get("/api/search?q=ABXX")
            results = r.json()["results"]
            assert results, "expected at least one match"
            assert results[0]["symbol"] == "ABXX"
    finally:
        await _cleanup(syms)
