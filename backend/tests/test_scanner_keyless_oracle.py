"""/api/scanner refuses a price oracle to a keyless caller (2026-09-19).

The anonymous scanner answers at most 10 rows, but `min_price` / `max_price`
let anyone bisect a ticker's vendor price from whether it appears, and a sort
on a daily move or on volume publishes the ranking of those vendor numbers
across the universe, 10 rows at a time. /api/public/signals already refuses
both to a keyless caller (#889); this is the same rule on the scanner.

Signed-in users and our own SSR (INTERNAL_SSR_TOKEN) are unchanged, and the
default anonymous top 10 is unchanged.
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import Ticker

TOKEN = "scanner-oracle-test-token"
SSR = {"x-tapeline-internal": TOKEN}
SIGNED_IN = {"Authorization": "Bearer dev-bypass"}
SYM = "ZSOQ"

ORACLES = [
    "max_price=50",
    "min_price=10",
    "sort=change_pct_1d",
    "sort=change_pct_5d",
    "sort=change_pct_1m",
    "sort=volume",
]


@pytest.fixture
async def seeded(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "internal_ssr_token", TOKEN)
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol == SYM))
        s.add(Ticker(
            symbol=SYM, name="Oracle Corp", asset_class="equity",
            sector="Information Technology", score=80.0, signal="STRONG SETUP",
            price=42.0, change_pct_1d=1.0, change_pct_5d=2.0, change_pct_1m=3.0,
            volume=5_000_000, confidence_pct=90.0, sub_trend=80.0, sub_rs=80.0,
            sub_fundamentals=80.0, sub_smart_money=80.0, sub_macro=50.0,
            sub_momentum=80.0, reason="seeded", updated_at=datetime.now(UTC),
        ))
        await s.commit()
    yield
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol == SYM))
        await s.commit()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ORACLES)
async def test_a_keyless_caller_gets_no_price_oracle(seeded, query):
    """Mutation: drop the gate, and each of these answers 200."""
    async with _client() as c:
        r = await c.get(f"/api/scanner?{query}")
    assert r.status_code == 403, (query, r.status_code, r.text[:200])


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", [SSR, SIGNED_IN], ids=["ssr", "signed-in"])
@pytest.mark.parametrize("query", ORACLES)
async def test_ssr_and_signed_in_keep_every_filter_and_sort(seeded, headers, query):
    async with _client() as c:
        r = await c.get(f"/api/scanner?{query}", headers=headers)
    assert r.status_code == 200, (query, r.status_code, r.text[:200])


@pytest.mark.asyncio
async def test_the_default_anonymous_top_ten_is_unchanged(seeded):
    async with _client() as c:
        r = await c.get("/api/scanner?sector=Information%20Technology")
    assert r.status_code == 200
    assert any(i["symbol"] == SYM for i in r.json()["items"])


@pytest.mark.asyncio
async def test_a_wrong_token_is_keyless(seeded):
    async with _client() as c:
        r = await c.get("/api/scanner?sort=volume", headers={"x-tapeline-internal": "nope"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_the_mcp_daily_picks_still_answer(seeded):
    """routers/mcp.py calls list_scanner as a plain function and passes
    keyless=True; with no price filter or sort it must still answer."""
    from app.routers import mcp as mcp_module

    async with session_scope() as s:
        out = await mcp_module._tool_daily_picks({"limit": 10}, s)
    assert "picks" in out and isinstance(out["picks"], list)
