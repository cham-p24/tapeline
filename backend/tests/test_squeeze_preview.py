"""Free squeeze taste — GET /api/squeeze/preview (routers/squeeze.py).

Activation lever: Tapeline's #1 problem is that Free users never add their OWN
ticker. The full Squeeze Watch feed (GET /api/squeeze) is Pro-gated, which left
Free users with a hard 403 and nothing to discover. /api/squeeze/preview gives
ANY logged-in user (Free included) a read-only top-3 slice so they can find a
name worth adding. Contract pinned here:

  1. A FREE user gets 200 with at most 3 items (the taste).
  2. Anonymous callers get 401 — the taste is a logged-in nudge, NOT a re-opened
     public/scrapeable surface (the full feed was locked down to close exactly
     that hole).
  3. The full feed (GET /api/squeeze) stays Pro-gated: a Free user still 403s.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import SqueezeSetup, User

_SYMBOLS = [f"SQZ{i:02d}" for i in range(5)]  # 5 setups → proves the top-3 cap


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


async def _insert_setups() -> None:
    now = datetime.now(UTC)
    async with SessionLocal() as s:
        for i, sym in enumerate(_SYMBOLS):
            await s.merge(SqueezeSetup(
                symbol=sym,
                spike_score=90.0 - i,  # distinct, descending → deterministic top-3
                squeeze_days=5,
                volume_multiple=2.5,
                obv_trend="rising",
                breakout_type="bullish",
                suggested_window="1-2 weeks",
                reason="Bollinger squeeze with rising OBV.",
                updated_at=now,
            ))
        await s.commit()


async def _delete_setups() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(SqueezeSetup).where(SqueezeSetup.symbol.in_(_SYMBOLS)))
        await s.commit()


async def _free_user(client: httpx.AsyncClient) -> dict:
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": f"sqz-{uuid.uuid4().hex[:10]}@example.com",
            "password": "TestPassword!2026",
            "name": "Sqz",
        },
    )
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    async with SessionLocal() as s:  # drop the auto-started trial to FREE
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        u.tier = "free"
        u.trial_ends_at = None
        await s.commit()
    return dict(r.cookies)


@pytest.mark.asyncio
async def test_free_user_gets_top3_preview(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert_setups()
    try:
        async with client:
            cookies = await _free_user(client)
            r = await client.get("/api/squeeze/preview", cookies=cookies)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["preview"] is True
            assert body["limit"] == 3
            assert len(body["items"]) <= 3
            # Highest spike_score comes first (SQZ00 = 90.0).
            assert body["items"][0]["symbol"] == "SQZ00"
    finally:
        await _delete_setups()


@pytest.mark.asyncio
async def test_preview_requires_login(client):
    """Anonymous callers get 401 — the taste must not re-open a public feed."""
    async with client:
        r = await client.get("/api/squeeze/preview")
        assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_full_squeeze_feed_still_pro_gated_for_free(client, monkeypatch):
    """The full feed stays Pro-only — a Free user still 403s on /api/squeeze."""
    _patch_signup_gates(monkeypatch)
    async with client:
        cookies = await _free_user(client)
        r = await client.get("/api/squeeze", cookies=cookies)
        assert r.status_code == 403, r.text
