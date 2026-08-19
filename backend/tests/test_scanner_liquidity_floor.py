"""Scanner liquidity floor (routers/scanner.py).

A high Tapeline Score on a near-untradeable instrument (a bond/strategy ETF
trading a few hundred dollars a day) was floating to the TOP of the ranked
scanner — the first thing a new visitor sees on the core surface. The floor
drops rows whose KNOWN dollar-volume (price*volume) is below the threshold,
while keeping rows with a null price/volume so it can only remove obvious
junk. Contract pinned here:

  1. Default view: an illiquid high-score name is excluded; a liquid one stays.
  2. min_dollar_volume=0 disables the floor (the illiquid name reappears).

Both test tickers clear the full live_clauses() quality bar and are deleted in
each test's finally block, leaving no high-score ghosts for other suites.
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


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _random_email() -> str:
    return f"liq-{uuid.uuid4().hex[:10]}@example.com"


def _patch_signup_gates(monkeypatch) -> None:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


# One liquid, one near-untradeable — both fresh, clean, high-scored so they
# rank at the very top of the score sort regardless of other rows.
_LIQ = "LIQVOLX"      # dollar-volume 50.0 * 1_000_000 = $50M — well above floor
_JUNK = "JUNKVOLX"    # dollar-volume 50.0 * 100      = $5k  — below the 50k floor
_SYMBOLS = [_LIQ, _JUNK]


def _ticker_rows() -> list[dict]:
    now = datetime.now(UTC)
    common = dict(
        sector="Information Technology",
        asset_class="stock",
        signal="HIGH CONVICTION",
        change_pct_1d=1.0,
        confidence_pct=80.0,
        sub_trend=70.0,
        sub_momentum=65.0,
        reason="Strong trend with momentum confirmation.",
        updated_at=now,
    )
    return [
        {"symbol": _LIQ, "name": "Liquid Test Co", "score": 98.0, "price": 50.0, "volume": 1_000_000, **common},
        {"symbol": _JUNK, "name": "Illiquid Test Co", "score": 99.0, "price": 50.0, "volume": 100, **common},
    ]


async def _insert_tickers() -> None:
    async with SessionLocal() as s:
        for row in _ticker_rows():
            await s.merge(Ticker(**row))
        await s.commit()


async def _delete_tickers() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMBOLS)))
        await s.commit()


async def _signup_premium(client: httpx.AsyncClient):
    r = await client.post(
        "/api/auth/signup",
        json={"email": _random_email(), "password": "TestPassword!2026", "name": "Liq"},
    )
    assert r.status_code == 200, r.text
    user_id = r.json()["user"]["id"]
    # Premium tier → full row cap, so ranking/cap can't hide our test rows.
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        u.tier = "premium"
        await s.commit()
    return r.cookies


@pytest.mark.asyncio
async def test_scanner_liquidity_floor_default_excludes_illiquid(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert_tickers()
    try:
        async with client:
            cookies = await _signup_premium(client)

            # Default floor (50k): liquid name present, illiquid junk excluded —
            # even though the junk row has the HIGHER score.
            r = await client.get(
                "/api/scanner?min_score=97&limit=200", cookies=cookies
            )
            assert r.status_code == 200, r.text
            syms = {i["symbol"] for i in r.json()["items"]}
            assert _LIQ in syms, "liquid name should survive the floor"
            assert _JUNK not in syms, "sub-floor dollar-volume name must be dropped"
    finally:
        await _delete_tickers()


@pytest.mark.asyncio
async def test_scanner_liquidity_floor_can_be_disabled(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert_tickers()
    try:
        async with client:
            cookies = await _signup_premium(client)

            # min_dollar_volume=0 disables the floor → the illiquid name returns.
            r = await client.get(
                "/api/scanner?min_score=97&limit=200&min_dollar_volume=0",
                cookies=cookies,
            )
            assert r.status_code == 200, r.text
            syms = {i["symbol"] for i in r.json()["items"]}
            assert _JUNK in syms, "floor disabled → illiquid name should reappear"
            assert _LIQ in syms
    finally:
        await _delete_tickers()
