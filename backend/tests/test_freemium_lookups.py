"""Freemium daily ticker-lookup metering on GET /api/ticker/{symbol}.

Contract under test (services/usage + routers/ticker):

  - FREE (logged-in) user : tier.FREE_DAILY_LOOKUPS successful lookups per UTC
    day, then HTTP 402 {"error":"free_lookup_limit", tier:"free"}.
  - PRO / PREMIUM / active-trial : unlimited, never 402, counter never moves.
  - ANONYMOUS (no account) : NOT metered on this endpoint. The public
    /t/{symbol} SEO pages are server-rendered from one frontend IP, so a per-IP
    anon cap here 402'd our own SSR and took down the /t/ surface.
    consume_anon_lookup stays a dormant utility (unit-tested below) for a future
    client-side anon gate.
  - The counter rolls over on the UTC day boundary (simulated by stamping
    lookups_reset_on = yesterday).
  - A 404 (invalid / unknown symbol) never burns budget.

Mirrors the auth-mock + _set_tier helpers from test_api_keys. The conftest DB
is session-scoped with no per-test rollback, but every assertion is scoped to a
freshly-created user (durable counter is per-user) or resets the per-process
anon meter (conftest autouse fixture clears usage._anon_lookups each test).
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import Ticker, User
from app.services.tier import ANON_DAILY_LOOKUPS, FREE_DAILY_LOOKUPS


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ── helpers ──────────────────────────────────────────────────────────────────

async def _signup(client: httpx.AsyncClient, monkeypatch) -> tuple[dict, str]:
    """Sign up a fresh user; return (cookies, user_id)."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"lookup-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "LookupTest"},
    )
    assert r.status_code == 200, r.text
    async with session_scope() as s:
        uid = (await s.execute(select(User.id).where(User.email == email))).scalar_one()
    return dict(r.cookies), uid


async def _set_tier(user_id: str, tier: str, *, paying: bool = True) -> None:
    """Flip a user's tier. A 'paying' user gets a stripe customer id and a
    cleared trial so the freemium meter treats them as fully unmetered."""
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        u.tier = tier
        if paying:
            u.stripe_customer_id = f"cus_{_uuid.uuid4().hex[:12]}"
            u.trial_ends_at = None
        await s.commit()


async def _free(client, monkeypatch) -> tuple[dict, str]:
    """A logged-in FREE user PAST the first-session grace window.

    Signup auto-starts a Premium trial, so drop to free. Then age created_at
    beyond tier.FREE_FIRST_SESSION_GRACE_HOURS so the daily look-up meter
    actually applies — a brand-new account is unmetered for its first session
    (see test_free_user_within_grace_window_is_unmetered), which would
    otherwise mask the cap the metering tests assert on.
    """
    cookies, uid = await _signup(client, monkeypatch)
    await _set_tier(uid, "free", paying=False)
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        u.created_at = datetime.now(UTC) - timedelta(days=2)
        await s.commit()
    return cookies, uid


SEEDED = "FREESYM"  # a single shared, validly-shaped ticker for lookup tests


async def _seed_ticker(symbol: str = SEEDED) -> None:
    """Idempotently insert a real, servable ticker row (score in-range so the
    >100 corruption guard never trips)."""
    async with session_scope() as s:
        existing = (
            await s.execute(select(Ticker).where(Ticker.symbol == symbol))
        ).scalar_one_or_none()
        if existing is None:
            s.add(Ticker(symbol=symbol, name="Freemium Test Co", score=72.0))
            await s.commit()


async def _get_lookups_today(user_id: str) -> tuple[int, date | None]:
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        return u.lookups_today, u.lookups_reset_on


# ════════════════════════════════════════════════════════════════════════════
# FREE user — N lookups then 402 free_lookup_limit
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_free_user_gets_cap_then_402(client, monkeypatch):
    async with client:
        await _seed_ticker()
        cookies, _uid = await _free(client, monkeypatch)

        # FREE_DAILY_LOOKUPS successful 200s.
        for i in range(FREE_DAILY_LOOKUPS):
            r = await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
            assert r.status_code == 200, f"lookup {i + 1}: {r.text}"
            assert r.json()["symbol"] == SEEDED

        # The next one is over the cap → 402 with the free contract body.
        r = await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
        assert r.status_code == 402, r.text
        detail = r.json()["detail"]
        assert detail["error"] == "free_lookup_limit"
        assert detail["tier"] == "free"
        assert detail["limit"] == FREE_DAILY_LOOKUPS
        assert detail["used"] == FREE_DAILY_LOOKUPS


@pytest.mark.asyncio
async def test_free_user_within_grace_window_is_unmetered(client, monkeypatch):
    """First-session wall-free: a brand-new FREE account (created_at ~now, i.e.
    inside tier.FREE_FIRST_SESSION_GRACE_HOURS) is NEVER metered, even well past
    the daily cap, and the durable counter never advances. This is the
    activation guarantee — a new user's first exploratory session can't hit the
    look-up wall before they've found a ticker worth saving."""
    async with client:
        await _seed_ticker()
        cookies, uid = await _signup(client, monkeypatch)
        # Drop to free but leave created_at fresh → inside the grace window.
        await _set_tier(uid, "free", paying=False)

        for _ in range(FREE_DAILY_LOOKUPS + 5):
            r = await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
            assert r.status_code == 200, r.text

        used, _reset = await _get_lookups_today(uid)
        assert used == 0, "a grace-window free user must not be metered"


@pytest.mark.asyncio
async def test_free_user_404_does_not_burn_budget(client, monkeypatch):
    """An invalid / unknown symbol 404s BEFORE metering, so it costs nothing."""
    async with client:
        cookies, uid = await _free(client, monkeypatch)

        # Several misses — all 404, none should advance the counter.
        for _ in range(FREE_DAILY_LOOKUPS + 3):
            r = await client.get("/api/ticker/ZZZQXNONE", cookies=cookies)
            assert r.status_code == 404, r.text

        used, _reset = await _get_lookups_today(uid)
        assert used == 0, "404s must not consume the daily lookup budget"


@pytest.mark.asyncio
async def test_free_counter_resets_across_utc_day_boundary(client, monkeypatch):
    """Stamp the counter as yesterday-at-cap; the next lookup rolls it over and
    succeeds (counts as 1 for the new day)."""
    async with client:
        await _seed_ticker()
        cookies, uid = await _free(client, monkeypatch)

        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            u.lookups_today = FREE_DAILY_LOOKUPS  # at cap...
            u.lookups_reset_on = yesterday        # ...but for YESTERDAY
            await s.commit()

        r = await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
        assert r.status_code == 200, r.text

        used, reset = await _get_lookups_today(uid)
        assert used == 1, "counter should have rolled to 0 then counted this call"
        assert reset == datetime.now(UTC).date()


# ════════════════════════════════════════════════════════════════════════════
# PRO / PREMIUM — unlimited, never metered
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["pro", "premium"])
async def test_paid_user_unlimited(client, monkeypatch, tier):
    async with client:
        await _seed_ticker()
        cookies, uid = await _signup(client, monkeypatch)
        await _set_tier(uid, tier, paying=True)

        # Well past the free cap — every call 200s.
        for _ in range(FREE_DAILY_LOOKUPS + 5):
            r = await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
            assert r.status_code == 200, r.text

        # And the durable counter never moved for a paid user.
        used, _reset = await _get_lookups_today(uid)
        assert used == 0


@pytest.mark.asyncio
async def test_active_trial_user_unlimited(client, monkeypatch):
    """A signup auto-starts a 14-day Premium trial (tier=premium, no stripe
    customer, future trial_ends_at). That user must be unmetered."""
    async with client:
        await _seed_ticker()
        cookies, uid = await _signup(client, monkeypatch)
        # Leave the auto-started trial intact (premium + future trial_ends_at,
        # no stripe customer) — this is the active-trial state.
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            assert u.tier == "premium"
            assert u.trial_ends_at is not None
            assert u.stripe_customer_id is None

        for _ in range(FREE_DAILY_LOOKUPS + 5):
            r = await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
            assert r.status_code == 200, r.text


# ════════════════════════════════════════════════════════════════════════════
# ANONYMOUS — NOT metered on this endpoint (public SSR/SEO must stay open)
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_anon_is_not_capped_on_endpoint(client):
    """Anonymous callers must NOT be metered here: the public /t/{symbol} pages
    are server-rendered from one frontend IP, so a per-IP cap would 402 our own
    SSR and take down the whole /t/ surface. Anon gets unlimited 200s well past
    the (dormant) ANON_DAILY_LOOKUPS value, even from a single IP."""
    async with client:
        await _seed_ticker()
        headers = {"X-Forwarded-For": "203.0.113.42"}
        for i in range(ANON_DAILY_LOOKUPS + 5):
            r = await client.get(f"/api/ticker/{SEEDED}", headers=headers)
            assert r.status_code == 200, f"anon lookup {i + 1}: {r.text}"
            assert r.json()["symbol"] == SEEDED


# ════════════════════════════════════════════════════════════════════════════
# Pure service-level unit checks (no HTTP) — usage.consume_anon_lookup
# ════════════════════════════════════════════════════════════════════════════

def test_consume_anon_lookup_caps_and_resets():
    from app.services import usage

    usage._anon_lookups.clear()
    ip = "192.0.2.7"

    seen = []
    for _ in range(ANON_DAILY_LOOKUPS):
        res = usage.consume_anon_lookup(ip)
        assert res["allowed"] is True
        seen.append(res["used"])
    assert seen == list(range(1, ANON_DAILY_LOOKUPS + 1))

    # Over cap — rejected, count does not advance.
    over = usage.consume_anon_lookup(ip)
    assert over["allowed"] is False
    assert over["used"] == ANON_DAILY_LOOKUPS
    assert over["limit"] == ANON_DAILY_LOOKUPS

    # Simulate a new UTC day: stamp yesterday → next call rolls to 1.
    yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
    usage._anon_lookups[ip] = (yesterday, ANON_DAILY_LOOKUPS)
    rolled = usage.consume_anon_lookup(ip)
    assert rolled["allowed"] is True
    assert rolled["used"] == 1
