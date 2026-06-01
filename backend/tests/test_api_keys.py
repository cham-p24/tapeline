"""Premium public API keys (PR8).

Three moving parts, mirrored by three test groups:

  1. services/api_keys — the pure mint + shape helpers (generate_key /
     hash_key / looks_like_key).
  2. /api/api-keys — session-authed management CRUD. Premium-gated create,
     per-user key cap, list-never-leaks-secret, revoke.
  3. /api/v1 + authenticate_api_key — key-authenticated read surface with the
     Premium tier gate, the rolling daily quota (paid Premium = 1,000/day),
     usage accounting, and the UTC daily reset.

The conftest DB is session-scoped with NO per-test rollback, so global counts
accumulate — but every assertion here is scoped to a freshly-created user (keys
are filtered by user_id) or seeds an exact known key, so the suite's prior
state never perturbs these.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import ApiKey, User
from app.services.api_keys import (
    MAX_KEYS_PER_USER,
    generate_key,
    hash_key,
    looks_like_key,
    new_key_id,
)


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ── helpers ──────────────────────────────────────────────────────────────────

async def _signup(client: httpx.AsyncClient, monkeypatch) -> tuple[dict, str]:
    """Sign up a fresh user; return (cookies, user_id). Mirrors the auth-mock
    pattern in test_revenue_dashboard."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"apikey-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "ApiTest"},
    )
    assert r.status_code == 200, r.text
    async with session_scope() as s:
        uid = (await s.execute(select(User.id).where(User.email == email))).scalar_one()
    return dict(r.cookies), uid


async def _set_tier(user_id: str, tier: str, *, paying: bool = True) -> None:
    """Flip a user's tier. For a 'paying' Premium user we set a stripe customer
    id and clear the trial so effective_limit resolves to the full 1,000/day
    cap (not the 100/day trial throttle)."""
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        u.tier = tier
        if paying:
            u.stripe_customer_id = f"cus_{_uuid.uuid4().hex[:12]}"
            u.trial_ends_at = None
        await s.commit()


async def _premium(client, monkeypatch) -> tuple[dict, str]:
    cookies, uid = await _signup(client, monkeypatch)
    await _set_tier(uid, "premium", paying=True)
    return cookies, uid


async def _seed_key(
    user_id: str, *, requests_today: int = 0, requests_day: str | None = None
) -> str:
    """Insert an ApiKey directly and return its plaintext key."""
    raw, prefix, key_hash = generate_key()
    async with session_scope() as s:
        s.add(ApiKey(
            id=new_key_id(),
            user_id=user_id,
            name="seed",
            prefix=prefix,
            key_hash=key_hash,
            requests_today=requests_today,
            requests_day=requests_day,
        ))
        await s.commit()
    return raw


# ════════════════════════════════════════════════════════════════════════════
# 1. Pure helpers
# ════════════════════════════════════════════════════════════════════════════

def test_generate_key_shape_and_hash():
    raw, prefix, key_hash = generate_key()
    assert raw.startswith("tl_live_")
    assert len(raw) == 40            # "tl_live_" (8) + 32 hex
    assert prefix == raw[:16]
    assert len(key_hash) == 64       # sha256 hex
    assert hash_key(raw) == key_hash  # deterministic
    # Fresh entropy each call.
    raw2, _, hash2 = generate_key()
    assert raw2 != raw and hash2 != key_hash


def test_looks_like_key():
    raw, _, _ = generate_key()
    assert looks_like_key(raw)
    assert not looks_like_key(None)
    assert not looks_like_key("")
    assert not looks_like_key("nope")
    assert not looks_like_key("tl_live_tooshort")
    assert not looks_like_key("sk_live_" + "a" * 32)  # wrong prefix


# ════════════════════════════════════════════════════════════════════════════
# 2. Management CRUD — /api/api-keys
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_requires_premium(client, monkeypatch):
    async with client:
        cookies, uid = await _signup(client, monkeypatch)
        # Signup auto-starts a 14-day PREMIUM trial, so explicitly drop to free
        # to exercise the free-blocked path.
        await _set_tier(uid, "free", paying=False)

        r = await client.post("/api/api-keys", json={"name": "k"}, cookies=cookies)
        assert r.status_code == 403, r.text  # free → blocked

        await _set_tier(uid, "pro", paying=True)
        r = await client.post("/api/api-keys", json={"name": "k"}, cookies=cookies)
        assert r.status_code == 403, r.text  # pro → blocked (API is Premium-only)

        await _set_tier(uid, "premium", paying=True)
        r = await client.post("/api/api-keys", json={"name": "prod-bot"}, cookies=cookies)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["key"].startswith("tl_live_")
        assert body["prefix"] == body["key"][:16]
        assert body["name"] == "prod-bot"
        assert body["daily_limit"] == 1000


@pytest.mark.asyncio
async def test_list_never_leaks_secret(client, monkeypatch):
    async with client:
        cookies, uid = await _premium(client, monkeypatch)
        await client.post("/api/api-keys", json={"name": "one"}, cookies=cookies)

        r = await client.get("/api/api-keys", cookies=cookies)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] == 1
        assert body["max_keys"] == MAX_KEYS_PER_USER
        item = body["items"][0]
        assert item["prefix"].startswith("tl_live_")
        # The secret + its hash must NEVER appear in a list response.
        assert "key" not in item
        assert "key_hash" not in item


@pytest.mark.asyncio
async def test_max_keys_cap(client, monkeypatch):
    async with client:
        cookies, uid = await _premium(client, monkeypatch)
        for i in range(MAX_KEYS_PER_USER):
            r = await client.post("/api/api-keys", json={"name": f"k{i}"}, cookies=cookies)
            assert r.status_code == 200, r.text
        r = await client.post("/api/api-keys", json={"name": "one-too-many"}, cookies=cookies)
        assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_revoke_disables_key(client, monkeypatch):
    async with client:
        cookies, uid = await _premium(client, monkeypatch)
        created = (await client.post("/api/api-keys", json={"name": "temp"}, cookies=cookies)).json()
        raw, key_id = created["key"], created["id"]

        # Key works before revoke.
        r = await client.get("/api/v1/me", headers={"X-API-Key": raw})
        assert r.status_code == 200, r.text

        # Revoke.
        r = await client.delete(f"/api/api-keys/{key_id}", cookies=cookies)
        assert r.status_code == 200, r.text

        # Now rejected, and gone from the list.
        r = await client.get("/api/v1/me", headers={"X-API-Key": raw})
        assert r.status_code == 401
        listing = (await client.get("/api/api-keys", cookies=cookies)).json()
        assert all(k["id"] != key_id for k in listing["items"])


# ════════════════════════════════════════════════════════════════════════════
# 3. Key auth + quota — /api/v1
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_v1_requires_valid_key(client):
    async with client:
        assert (await client.get("/api/v1/signals")).status_code == 401  # no key
        r = await client.get("/api/v1/signals", headers={"X-API-Key": "tl_live_" + "0" * 32})
        assert r.status_code == 401  # unknown key


@pytest.mark.asyncio
async def test_v1_me_reports_quota_and_increments(client, monkeypatch):
    async with client:
        _, uid = await _premium(client, monkeypatch)
        raw = await _seed_key(uid)

        r = await client.get("/api/v1/me", headers={"X-API-Key": raw})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tier"] == "premium"
        assert body["quota"]["daily_limit"] == 1000
        assert body["quota"]["used_today"] == 1          # this call counted
        assert body["quota"]["remaining_today"] == 999

        # A second call advances usage.
        body2 = (await client.get("/api/v1/me", headers={"X-API-Key": raw})).json()
        assert body2["quota"]["used_today"] == 2


@pytest.mark.asyncio
async def test_v1_signals_via_bearer_key(client, monkeypatch):
    async with client:
        _, uid = await _premium(client, monkeypatch)
        raw = await _seed_key(uid)
        # Authorization: Bearer with the tl_live_ prefix also works.
        r = await client.get("/api/v1/signals", headers={"Authorization": f"Bearer {raw}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body and "count" in body


@pytest.mark.asyncio
async def test_quota_exhaustion_429(client, monkeypatch):
    async with client:
        _, uid = await _premium(client, monkeypatch)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        raw = await _seed_key(uid, requests_today=1000, requests_day=today)  # at cap
        r = await client.get("/api/v1/me", headers={"X-API-Key": raw})
        assert r.status_code == 429, r.text


@pytest.mark.asyncio
async def test_quota_resets_next_utc_day(client, monkeypatch):
    async with client:
        _, uid = await _premium(client, monkeypatch)
        yesterday = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")
        raw = await _seed_key(uid, requests_today=1000, requests_day=yesterday)  # yesterday at cap
        r = await client.get("/api/v1/me", headers={"X-API-Key": raw})
        assert r.status_code == 200, r.text
        # Counter rolled to a new day then counted this one call.
        assert r.json()["quota"]["used_today"] == 1


@pytest.mark.asyncio
async def test_downgraded_owner_loses_api_access(client, monkeypatch):
    async with client:
        _, uid = await _premium(client, monkeypatch)
        raw = await _seed_key(uid)
        await _set_tier(uid, "free", paying=False)
        r = await client.get("/api/v1/me", headers={"X-API-Key": raw})
        assert r.status_code == 403, r.text
