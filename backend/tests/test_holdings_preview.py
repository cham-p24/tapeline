"""Free insider taste — GET /api/holdings/preview (routers/holdings.py).

Conversion fix (2026-07-18): /app/holdings wrapped its whole body in <Paywall>,
which BLURS its children. But the Premium-gated GET /api/holdings 403s before
anything renders, so the blur sat over a literally empty table — a free user saw
an upgrade card floating over nothing. The preview endpoint gives any logged-in
tier the 3 most recent REAL Form 4 filings plus the REAL feed size so the page
can render populated rows and state the true held-back number.

Contract pinned here:
  1. A FREE user gets 200 with at most 3 items (the taste), newest-dated first.
  2. `feed_size` is the REAL total row count of the DB-backed feed, not the
     3-row slice — the frontend's locked copy must never invent a number.
  3. Anonymous callers get 401 — a logged-in nudge, not a public surface.
  4. The full feed (GET /api/holdings) stays Premium-gated: Free AND Pro 403.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal, session_scope
from app.main import app
from app.models import InsiderTransaction, User

_SYMBOLS = [f"INS{i:02d}" for i in range(5)]  # 5 filings → proves the top-3 cap


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


async def _insert_filings() -> None:
    async with session_scope() as s:
        for i, sym in enumerate(_SYMBOLS):
            # Descending transaction_date → deterministic "newest 3". All well
            # inside the 30-day preview window.
            s.add(InsiderTransaction(
                symbol=sym,
                insider_name=f"TESTER INSIDER {i}",
                transaction_date=(date.today() - timedelta(days=i)).isoformat(),
                share_change=1_000 + i,
                transaction_price=100.0,
                transaction_value=round((1_000 + i) * 100.0, 2),
                code="P",
            ))
        await s.commit()


async def _delete_filings() -> None:
    async with session_scope() as s:
        await s.execute(delete(InsiderTransaction).where(InsiderTransaction.symbol.in_(_SYMBOLS)))
        await s.commit()


async def _signup(client: httpx.AsyncClient, tier: str) -> dict:
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": f"ins-{uuid.uuid4().hex[:10]}@example.com",
            "password": "TestPassword!2026",
            "name": "Ins",
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
async def test_free_user_gets_top3_preview_with_real_feed_size(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert_filings()
    try:
        async with client:
            cookies = await _signup(client, "free")
            r = await client.get("/api/holdings/preview", cookies=cookies)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["preview"] is True
            assert body["limit"] == 3
            assert body["days"] == 30
            assert len(body["items"]) == 3
            # Rows carry real, renderable fields — not a stub payload.
            first = body["items"][0]
            for field in ("symbol", "insider_name", "transaction_date",
                          "share_change", "transaction_price", "transaction_value"):
                assert first[field] is not None, field
            # feed_size counts the WHOLE table, not the 3-row slice. We inserted
            # 5 rows; the shared test DB may hold others, so pin a lower bound.
            assert body["feed_size"] >= 5
            assert body["feed_size"] >= len(body["items"])
    finally:
        await _delete_filings()


@pytest.mark.asyncio
async def test_preview_requires_login(client):
    """Anonymous callers get 401 — the taste must not re-open a public feed."""
    async with client:
        r = await client.get("/api/holdings/preview")
        assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_full_holdings_feed_still_premium_gated(client, monkeypatch):
    """The full feed stays Premium-only — Free AND Pro still 403."""
    _patch_signup_gates(monkeypatch)
    async with client:
        for tier in ("free", "pro"):
            cookies = await _signup(client, tier)
            r = await client.get("/api/holdings", cookies=cookies)
            assert r.status_code == 403, f"{tier}: {r.text}"


@pytest.mark.asyncio
async def test_premium_full_feed_unchanged(client, monkeypatch):
    """Premium path is untouched: 200, filterable, with the real feed_size."""
    _patch_signup_gates(monkeypatch)
    await _insert_filings()
    try:
        async with client:
            cookies = await _signup(client, "premium")
            r = await client.get("/api/holdings?limit=200", cookies=cookies)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["count"] == len(body["items"])
            assert body["feed_size"] >= 5
            # The full feed does NOT carry the preview envelope.
            assert "preview" not in body
            # Symbol filter still works.
            r2 = await client.get(f"/api/holdings?symbol={_SYMBOLS[0]}", cookies=cookies)
            assert r2.status_code == 200, r2.text
            assert {i["symbol"] for i in r2.json()["items"]} == {_SYMBOLS[0]}
    finally:
        await _delete_filings()
