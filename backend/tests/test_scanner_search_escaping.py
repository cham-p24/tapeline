"""Scanner symbol-search must treat `q` as a LITERAL substring.

routers/scanner.py built `Ticker.symbol.like(f"%{q}%")` without escaping LIKE
metacharacters. Unescaped, `_` matches any single character (so q="B_C"
wrongly returned "BAC") and `%` matches everything (so q="%" returned the whole
capped result set instead of narrowing). The same bug sat in routers/export.py,
so the CSV export and the on-screen scanner drifted apart. These pin the fix.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.main import app
from app.models import Ticker

_SECTOR = "ScanEscapeSector_" + uuid.uuid4().hex[:6]
# None of these contain the LITERAL substring "B_C".
_SYMBOLS = ["BAC", "BXC", "ZZBOND"]


def _rows() -> list[dict]:
    now = datetime.now(UTC)
    common = {
        "sector": _SECTOR,
        "asset_class": "stock",
        "signal": "HIGH CONVICTION",
        "change_pct_1d": 1.0,
        "confidence_pct": 80.0,
        "sub_trend": 70.0,
        "sub_momentum": 65.0,
        "reason": "Trend and momentum confirm the composite.",
        "updated_at": now,
        "price": 50.0,
        "volume": 1_000_000,  # clears the liquidity floor
    }
    return [{"symbol": s, "name": f"Co {s}", "score": 90.0, **common} for s in _SYMBOLS]


async def _insert() -> None:
    async with SessionLocal() as s:
        for row in _rows():
            await s.merge(Ticker(**row))
        await s.commit()


async def _delete() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMBOLS)))
        await s.commit()


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_underscore_in_q_is_literal_not_a_wildcard(client):
    """q='B_C' must NOT return 'BAC' — '_' is a literal, not a single-char
    wildcard. This is the exact wrong-rows case the escape fixes."""
    await _insert()
    try:
        async with client:
            r = await client.get(
                "/api/scanner", params={"q": "B_C", "min_score": 0, "limit": 200}
            )
            assert r.status_code == 200, r.text
            syms = [row["symbol"] for row in r.json()["items"]]
            assert "BAC" not in syms, "'_' leaked as a wildcard and matched BAC"
    finally:
        await _delete()


@pytest.mark.asyncio
async def test_percent_in_q_matches_nothing(client):
    """q='%' pre-fix matched every row; escaped it's a literal '%' that no
    symbol contains, so it narrows to nothing."""
    await _insert()
    try:
        async with client:
            r = await client.get(
                "/api/scanner", params={"q": "%", "min_score": 0, "limit": 200}
            )
            assert r.status_code == 200, r.text
            syms = [row["symbol"] for row in r.json()["items"]]
            assert not any(s in syms for s in _SYMBOLS), "'%' matched everything"
    finally:
        await _delete()


@pytest.mark.asyncio
async def test_plain_substring_search_still_narrows(client):
    """Sanity: escaping must not break ordinary substring search."""
    await _insert()
    try:
        async with client:
            r = await client.get(
                "/api/scanner", params={"q": "BAC", "min_score": 0, "limit": 200}
            )
            assert r.status_code == 200, r.text
            syms = [row["symbol"] for row in r.json()["items"]]
            assert "BAC" in syms
            assert "ZZBOND" not in syms
    finally:
        await _delete()
