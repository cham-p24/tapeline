"""An anonymous caller must not be able to choose our Finnhub call volume.

`GET /api/ticker/{symbol}/financials` took no auth dependency, never ran
`clean_symbol()` (unlike its sibling `/{symbol}`), and never checked the symbol
against the Ticker table before calling `fetch_basic_financials(sym)`. On a
cache miss that is a live GET to Finnhub, and `_save_cache` then writes
`.cache/finnhub_metric_<SYM>.json` unconditionally — even for the empty blob
Finnhub returns for an unrecognised symbol.

So the cardinality of both the upstream call and the on-disk file was chosen
entirely by the URL path the caller typed. Every distinct symbol is a
guaranteed cache miss.

Finnhub is a shared, hard-capped dependency: the same key serves per-tick
fundamentals, the IPO/earnings calendars, insider Form 4, analyst ratings, the
daily sector backfill (deliberately budgeted at 200 calls/day) and half the news
feed. Looping `GET /api/ticker/ZZZQ0001/financials`, `…ZZZQ0002/…` exhausts the
free tier's 60 calls/min in about a second and degrades all of them for every
user, while growing `.cache/` by one inode per attacker-chosen symbol with no
bound and no eviction.

NOTE: this was deliberately NOT reproduced against production — running the
attack IS the harm (it would burn the live vendor quota). Verified by reading
the handler, and pinned here.
"""
from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import Ticker
from app.routers import ticker as ticker_router

_SYM = "ZFIN"


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def spy(monkeypatch):
    """Record every symbol that reaches the vendor adapter."""
    calls: list[str] = []

    async def _fake(sym: str):
        calls.append(sym)
        return {"pe": 12.3}

    monkeypatch.setattr(ticker_router, "fetch_basic_financials", _fake)
    return calls


async def _clear() -> None:
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol == _SYM))
        await s.commit()


async def _seed() -> None:
    from datetime import UTC, datetime

    async with session_scope() as s:
        s.add(
            Ticker(
                symbol=_SYM,
                name="Fin Test Corp",
                asset_class="equity",
                sector="Testonomicals",
                score=60.0,
                signal="CONSTRUCTIVE",
                updated_at=datetime.now(UTC),
                price=10.0,
                volume=100_000,
                change_pct_1d=0.1,
                confidence_pct=70,
                sub_trend=60,
                sub_rs=60,
                sub_momentum=60,
            )
        )
        await s.commit()


@pytest.mark.asyncio
async def test_unknown_symbol_never_reaches_the_vendor(client, spy):
    """THE regression. Each distinct junk symbol used to cost one Finnhub call
    and one cache file."""
    await _clear()
    try:
        async with client:
            for i in range(5):
                r = await client.get(f"/api/ticker/ZZZQ{i:04d}/financials")
                assert r.status_code == 404, (
                    f"expected 404 for an unknown symbol, got {r.status_code}"
                )
        assert spy == [], (
            f"an anonymous caller drove {len(spy)} Finnhub calls with invented "
            f"symbols: {spy} — that exhausts a shared 60/min budget in seconds"
        )
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_malformed_symbol_is_rejected_by_shape(client, spy):
    """clean_symbol() runs first, matching the sibling /{symbol} endpoint."""
    async with client:
        for bad in ["1BAD", "way-too-long-to-be-a-symbol"]:
            r = await client.get(f"/api/ticker/{bad}/financials")
            assert r.status_code == 404, f"{bad} → {r.status_code}"
    assert spy == [], f"a malformed symbol reached the vendor: {spy}"


@pytest.mark.asyncio
async def test_known_symbol_still_works(client, spy):
    """The guard must not break the real feature."""
    await _clear()
    await _seed()
    try:
        async with client:
            r = await client.get(f"/api/ticker/{_SYM}/financials")
            assert r.status_code == 200, r.text
            body = r.json()
        assert body["symbol"] == _SYM
        assert body["available"] is True
        assert body["metrics"] == {"pe": 12.3}
        assert spy == [_SYM], f"expected exactly one vendor call, got {spy}"
    finally:
        await _clear()


@pytest.mark.asyncio
async def test_lowercase_known_symbol_is_normalised(client, spy):
    await _clear()
    await _seed()
    try:
        async with client:
            r = await client.get(f"/api/ticker/{_SYM.lower()}/financials")
            assert r.status_code == 200, r.text
            assert r.json()["symbol"] == _SYM
        assert spy == [_SYM]
    finally:
        await _clear()
