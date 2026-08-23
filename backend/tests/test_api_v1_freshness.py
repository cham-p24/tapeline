"""The public /api/v1 surface must apply the shared freshness floor.

Regression for the 2026-08-19 feed-coverage audit: the raw `tickers` table
carries "ghost" rows that dropped out of the active universe months ago but
kept their last score — including rows ABOVE 100 on a 0-100 scale, labelled
HIGH CONVICTION. Every other ranked surface already excludes them via
services/ticker_freshness.live_clauses(); /api/v1/signals and
/api/v1/ticker/{symbol} did not, so a paying Premium customer paging the
public API got APLS 129 / MCBS 126 / TPH 121 at the top of page 1.

Uses the same signup / tier / key helpers as test_api_keys.py.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.main import app
from app.models import ApiKey, Ticker, User
from app.services.api_keys import generate_key, new_key_id

pytestmark = pytest.mark.asyncio


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _premium_key(client: httpx.AsyncClient, monkeypatch) -> str:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"fresh-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "Fresh"},
    )
    assert r.status_code == 200, r.text
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.tier = "premium"
        u.stripe_customer_id = f"cus_{_uuid.uuid4().hex[:12]}"
        u.trial_ends_at = None
        await s.commit()
        uid = u.id

    raw, prefix, key_hash = generate_key()
    async with session_scope() as s:
        s.add(ApiKey(id=new_key_id(), user_id=uid, name="t", prefix=prefix, key_hash=key_hash))
        await s.commit()
    return raw


def _row(symbol: str, score: float, *, days_old: int, factors: int = 6) -> Ticker:
    """A Ticker row. `factors` populated sub-scores (the freshness floor needs >=2)."""
    subs = dict.fromkeys(
        ("sub_trend", "sub_rs", "sub_fundamentals", "sub_momentum", "sub_macro", "sub_smart_money"),
        None,
    )
    for k in list(subs)[:factors]:
        subs[k] = 55.0
    # The data-quality floor (ticker_freshness.valid_composite_clauses) also
    # requires change_pct_1d, confidence_pct and a clean asset_class, so a
    # "fresh" test row must carry them or it is correctly rejected as
    # incomplete — which is the floor doing its job, not a test bug.
    return Ticker(
        symbol=symbol,
        name=f"{symbol} Test Co",
        sector="Test",
        asset_class="equity",
        score=score,
        signal="HIGH CONVICTION" if score >= 85 else "NEUTRAL",
        price=10.0,
        volume=100_000,
        change_pct_1d=0.5,
        confidence_pct=70.0,
        updated_at=datetime.now(UTC) - timedelta(days=days_old),
        **subs,
    )


@pytest.fixture
async def seeded():
    """Two fresh, valid rows plus one 3-month-old ghost carrying an impossible
    129 score — the exact shape found in prod on 2026-08-19."""
    syms = ("ZZFRESH1", "ZZFRESH2", "ZZGHOST1")
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(syms)))
        s.add_all([
            _row("ZZFRESH1", 82.0, days_old=0),
            _row("ZZFRESH2", 71.0, days_old=0),
            _row("ZZGHOST1", 129.0, days_old=90, factors=1),
        ])
        await s.commit()
    yield syms
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(syms)))
        await s.commit()


async def test_signals_excludes_stale_ghosts(client, monkeypatch, seeded):
    async with client:
        key = await _premium_key(client, monkeypatch)
        r = await client.get("/api/v1/signals", params={"limit": 2000}, headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    syms = {i["symbol"] for i in r.json()["items"]}
    assert "ZZFRESH1" in syms and "ZZFRESH2" in syms
    # The ghost must never appear — it is 90 days stale, has one factor, and
    # carries a score that cannot exist on a 0-100 composite.
    assert "ZZGHOST1" not in syms
    # And nothing above 100 can ever be served by this endpoint.
    assert all(i["score"] <= 100 for i in r.json()["items"] if i["score"] is not None)


async def test_signals_ghost_does_not_lead_the_ranking(client, monkeypatch, seeded):
    """The specific customer-facing failure: a 129 ghost at the top of page 1."""
    async with client:
        key = await _premium_key(client, monkeypatch)
        r = await client.get("/api/v1/signals", params={"limit": 1}, headers={"X-API-Key": key})
    assert r.status_code == 200
    top = r.json()["items"][0]
    assert top["symbol"] != "ZZGHOST1"
    assert top["score"] <= 100


async def test_ticker_endpoint_404s_on_ghost(client, monkeypatch, seeded):
    async with client:
        key = await _premium_key(client, monkeypatch)
        fresh = await client.get("/api/v1/ticker/ZZFRESH1", headers={"X-API-Key": key})
        ghost = await client.get("/api/v1/ticker/ZZGHOST1", headers={"X-API-Key": key})
    assert fresh.status_code == 200
    assert fresh.json()["symbol"] == "ZZFRESH1"
    # A stale ghost must 404 (matching the in-app ticker page), not return a
    # months-old 129 as if it were today's score.
    assert ghost.status_code == 404
