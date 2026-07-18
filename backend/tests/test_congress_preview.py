"""Free Congress taste — GET /api/congress/preview (routers/congress.py).

Conversion fix (2026-07-18): /app/congress wrapped its whole body in <Paywall>,
which BLURS its children. But the Premium-gated GET /api/congress 403s before
anything renders, so the blur sat over a literally empty table — a free user saw
an upgrade card floating over nothing and therefore zero evidence the feed had
any content. The preview endpoint gives any logged-in tier the 3 most recently
disclosed REAL trades plus the REAL total row count so the page can render
populated rows and state the true held-back number.

Contract pinned here:
  1. A FREE user gets 200 with at most 3 items (the taste), newest-disclosed
     first.
  2. `total_disclosures` counts the WHOLE table, not the 3-row slice — the
     frontend's locked copy must never invent a number.
  3. Anonymous callers get 401 — the taste is a logged-in nudge, NOT a
     re-opened public/scrapeable surface (the full feed was locked down in
     2026-05 to close exactly that hole).
  4. The full feed (GET /api/congress) stays Premium-gated: a Free user — and
     a PRO user — still 403s.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import CongressTrade, User

_SYMBOLS = [f"CNG{i:02d}" for i in range(5)]  # 5 disclosures → proves the top-3 cap


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


async def _insert_trades() -> None:
    now = datetime.now(UTC)
    async with SessionLocal() as s:
        for i, sym in enumerate(_SYMBOLS):
            s.add(CongressTrade(
                politician=f"Rep Test {i}",
                chamber="House",
                party="D",
                symbol=sym,
                direction="BUY",
                amount_min=1_001.0,
                amount_max=15_000.0,
                trade_date=date(2026, 6, 1),
                # Descending disclosure times → deterministic "newest 3".
                # Far enough in the future that any pre-existing rows in the
                # shared test DB can't outrank them.
                disclosed_at=now + timedelta(days=365, minutes=-i),
            ))
        await s.commit()


async def _delete_trades() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(CongressTrade).where(CongressTrade.symbol.in_(_SYMBOLS)))
        await s.commit()


async def _signup(client: httpx.AsyncClient, tier: str) -> dict:
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": f"cng-{uuid.uuid4().hex[:10]}@example.com",
            "password": "TestPassword!2026",
            "name": "Cng",
        },
    )
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    async with SessionLocal() as s:  # drop the auto-started trial to `tier`
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        u.tier = tier
        u.trial_ends_at = None
        await s.commit()
    return dict(r.cookies)


@pytest.mark.asyncio
async def test_free_user_gets_top3_preview_with_real_total(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert_trades()
    try:
        async with client:
            cookies = await _signup(client, "free")
            r = await client.get("/api/congress/preview", cookies=cookies)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["preview"] is True
            assert body["limit"] == 3
            assert len(body["items"]) == 3
            # Newest disclosure first (CNG00 has the latest disclosed_at).
            assert body["items"][0]["symbol"] == "CNG00"
            # Rows carry real, renderable fields — not a stub payload.
            first = body["items"][0]
            for field in ("politician", "chamber", "party", "direction",
                          "amount_min", "amount_max", "trade_date", "disclosed_at"):
                assert first[field] is not None, field
            # total_disclosures counts the WHOLE table, not the 3-row slice. We
            # inserted 5 rows; the shared test DB may hold others, so pin a
            # lower bound rather than an exact count.
            assert body["total_disclosures"] >= 5
            assert body["total_disclosures"] >= len(body["items"])
    finally:
        await _delete_trades()


@pytest.mark.asyncio
async def test_preview_requires_login(client):
    """Anonymous callers get 401 — the taste must not re-open a public feed."""
    async with client:
        r = await client.get("/api/congress/preview")
        assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_full_congress_feed_still_premium_gated(client, monkeypatch):
    """The full feed stays Premium-only — Free AND Pro still 403."""
    _patch_signup_gates(monkeypatch)
    async with client:
        for tier in ("free", "pro"):
            cookies = await _signup(client, tier)
            r = await client.get("/api/congress", cookies=cookies)
            assert r.status_code == 403, f"{tier}: {r.text}"


@pytest.mark.asyncio
async def test_premium_full_feed_unchanged(client, monkeypatch):
    """Pro path (Premium here) is untouched: 200 with the full item shape."""
    _patch_signup_gates(monkeypatch)
    await _insert_trades()
    try:
        async with client:
            cookies = await _signup(client, "premium")
            r = await client.get("/api/congress", cookies=cookies)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["count"] == len(body["items"])
            symbols = {i["symbol"] for i in body["items"]}
            assert symbols & set(_SYMBOLS)
            # The full feed does NOT carry the preview envelope.
            assert "preview" not in body
            assert "total_disclosures" not in body
    finally:
        await _delete_trades()
