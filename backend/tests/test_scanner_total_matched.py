"""Scanner total_matched — the "show don't hide" real count (routers/scanner.py).

A Free/anonymous caller is pinned to the top row_cap (10) rows of the ranked
universe. `total_matched` is the REAL count of ALL rows matching the current
filters, before that cap, so the client can state how many more tickers sit in
the full universe behind the wall — WITHOUT leaking any of the held-back
symbols or scores. Contract pinned here:

  1. Anonymous caller, more rows than the cap: total_matched is the true match
     count (> the returned row count), while `count` stays at the row_cap.
  2. Anonymous caller, fewer rows than the cap: total_matched == count (no
     hidden remainder to advertise).
  3. Premium caller: total_matched is null — the paginating tiers see the whole
     universe and have no cap to describe.

All test rows clear the full live_clauses() quality bar and sit in a unique
sector for isolation; deleted in each test's finally block.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import Ticker, User

_SECTOR_MANY = "TotalMatchedManySector"
_SECTOR_FEW = "TotalMatchedFewSector"
_MANY = 15  # more than the Free/anon row_cap (10)
_FEW = 4  # fewer than the row_cap
_SYMBOLS_MANY = [f"TMM{i:02d}" for i in range(_MANY)]
_SYMBOLS_FEW = [f"TMF{i:02d}" for i in range(_FEW)]


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _patch_signup_gates(monkeypatch) -> None:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


def _ticker_rows(sector: str, symbols: list[str]) -> list[dict]:
    now = datetime.now(UTC)
    common = dict(
        sector=sector,
        asset_class="stock",
        signal="HIGH CONVICTION",
        change_pct_1d=1.0,
        confidence_pct=80.0,
        sub_trend=70.0,
        sub_momentum=65.0,
        reason="Trend and momentum confirm the composite.",
        updated_at=now,
        price=50.0,
        volume=1_000_000,  # $50M dollar-volume, well above the liquidity floor
    )
    return [
        {"symbol": sym, "name": f"Total Matched Co {i}", "score": 95.0 - i, **common}
        for i, sym in enumerate(symbols)
    ]


async def _insert(sector: str, symbols: list[str]) -> None:
    async with SessionLocal() as s:
        for row in _ticker_rows(sector, symbols):
            await s.merge(Ticker(**row))
        await s.commit()


async def _delete(symbols: list[str]) -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(symbols)))
        await s.commit()


async def _signup(client: httpx.AsyncClient) -> tuple[dict, str]:
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": f"tm-{uuid.uuid4().hex[:10]}@example.com",
            "password": "TestPassword!2026",
            "name": "TM",
        },
    )
    assert r.status_code == 200, r.text
    return dict(r.cookies), r.json()["user"]["id"]


async def _set_tier(user_id: str, tier: str) -> None:
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        u.tier = tier
        await s.commit()


@pytest.mark.asyncio
async def test_anonymous_total_matched_reports_full_count(client):
    """Anon caller: count is capped at row_cap (10), but total_matched is the
    true 15 matching the filter — the held-back remainder is real and visible."""
    await _insert(_SECTOR_MANY, _SYMBOLS_MANY)
    try:
        async with client:
            r = await client.get(
                f"/api/scanner?sector={_SECTOR_MANY}&min_score=0&limit=200"
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["count"] == 10, "anon page is capped at row_cap"
            assert body["total_matched"] == _MANY, "total_matched must be the real count"
            assert body["total_matched"] > body["count"]
    finally:
        await _delete(_SYMBOLS_MANY)


@pytest.mark.asyncio
async def test_total_matched_equals_count_when_under_cap(client):
    """When fewer rows match than the cap allows, total_matched == count — there
    is no hidden remainder, so the client shows no locked band."""
    await _insert(_SECTOR_FEW, _SYMBOLS_FEW)
    try:
        async with client:
            r = await client.get(
                f"/api/scanner?sector={_SECTOR_FEW}&min_score=0&limit=200"
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["count"] == _FEW
            assert body["total_matched"] == _FEW
    finally:
        await _delete(_SYMBOLS_FEW)


@pytest.mark.asyncio
async def test_premium_total_matched_is_null(client, monkeypatch):
    """Premium pages the whole universe — no cap to describe, so total_matched
    is null rather than a redundant count."""
    _patch_signup_gates(monkeypatch)
    await _insert(_SECTOR_MANY, _SYMBOLS_MANY)
    try:
        async with client:
            cookies, uid = await _signup(client)
            await _set_tier(uid, "premium")
            r = await client.get(
                f"/api/scanner?sector={_SECTOR_MANY}&min_score=0&limit=200",
                cookies=cookies,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            # Premium sees all 15 rows unpaged, and total_matched is null.
            assert body["count"] == _MANY
            assert body["total_matched"] is None
    finally:
        await _delete(_SYMBOLS_MANY)
