"""The daily look-up meter must be VISIBLE, not just enforced.

Before this, the meter (used / limit / remaining) was computed on every free
look-up and thrown away: the 200 carried no meter, /api/usage omitted daily
look-ups entirely, and the free user's first contact with metering was the
hard 402 at the cap — no warning at 9, 10 or 11.

Contract pinned here:

  1. GET /api/ticker/{symbol} 200 carries `lookups`
     (used / limit / remaining / resets_at) for a metered FREE caller, and the
     numbers advance with each look-up.
  2. Unmetered callers (paid tier, active no-card trial, first-session grace)
     get `lookups.limit is None` — the UNLIMITED sentinel — so a client can
     tell "no cap" apart from "cap not yet reached".
  3. Anonymous callers get `lookups: null` (they aren't metered on this
     endpoint — see test_freemium_lookups for why).
  4. GET /api/usage carries metrics.ticker_lookups_today, agreeing with the
     ticker response, and reading it never CONSUMES a look-up.

Reuses the signup / tier / seed helpers' shape from test_freemium_lookups.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import Ticker, User
from app.services.tier import FREE_DAILY_LOOKUPS


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


SEEDED = "METERSYM"


async def _signup(client: httpx.AsyncClient, monkeypatch) -> tuple[dict, str]:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"meter-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "MeterTest"},
    )
    assert r.status_code == 200, r.text
    async with session_scope() as s:
        uid = (await s.execute(select(User.id).where(User.email == email))).scalar_one()
    return dict(r.cookies), uid


async def _free(client, monkeypatch) -> tuple[dict, str]:
    """A logged-in FREE user PAST the first-session grace window, so the daily
    meter actually applies (a brand-new account is unmetered for 24h)."""
    cookies, uid = await _signup(client, monkeypatch)
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        u.tier = "free"
        u.stripe_customer_id = None
        u.trial_ends_at = None
        u.created_at = datetime.now(UTC) - timedelta(days=2)
        await s.commit()
    return cookies, uid


async def _seed_ticker(symbol: str = SEEDED) -> None:
    async with session_scope() as s:
        existing = (
            await s.execute(select(Ticker).where(Ticker.symbol == symbol))
        ).scalar_one_or_none()
        if existing is None:
            s.add(Ticker(symbol=symbol, name="Meter Test Co", score=64.0))
            await s.commit()


# ════════════════════════════════════════════════════════════════════════════
# 1. The ticker 200 carries the meter
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ticker_response_carries_lookup_meter_for_free_user(client, monkeypatch):
    async with client:
        await _seed_ticker()
        cookies, _uid = await _free(client, monkeypatch)

        r = await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
        assert r.status_code == 200, r.text
        meter = r.json()["lookups"]
        assert meter is not None, "free callers must be told where they stand"
        assert meter["limit"] == FREE_DAILY_LOOKUPS
        assert meter["used"] == 1
        assert meter["remaining"] == FREE_DAILY_LOOKUPS - 1
        # Reset time is the next UTC midnight — a real timestamp, not a hint.
        assert meter["resets_at"] is not None
        resets = datetime.fromisoformat(meter["resets_at"])
        assert resets > datetime.now(UTC)
        assert (resets.hour, resets.minute, resets.second) == (0, 0, 0)

        # And it advances on the next look-up.
        r2 = await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
        assert r2.status_code == 200, r2.text
        meter2 = r2.json()["lookups"]
        assert meter2["used"] == 2
        assert meter2["remaining"] == FREE_DAILY_LOOKUPS - 2


@pytest.mark.asyncio
async def test_meter_is_present_on_the_lookup_before_the_wall(client, monkeypatch):
    """The whole point: the caller can see the cap coming. On the LAST allowed
    look-up the meter reads used == limit, remaining == 0 — and only the call
    AFTER that is the 402."""
    async with client:
        await _seed_ticker()
        cookies, _uid = await _free(client, monkeypatch)

        last = None
        for _ in range(FREE_DAILY_LOOKUPS):
            r = await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
            assert r.status_code == 200, r.text
            last = r.json()["lookups"]

        assert last["used"] == FREE_DAILY_LOOKUPS
        assert last["remaining"] == 0

        over = await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
        assert over.status_code == 402, over.text


# ════════════════════════════════════════════════════════════════════════════
# 2 + 3. Unmetered callers and anonymous callers
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["pro", "premium"])
async def test_paid_user_meter_reports_unlimited(client, monkeypatch, tier):
    async with client:
        await _seed_ticker()
        cookies, uid = await _signup(client, monkeypatch)
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            u.tier = tier
            u.stripe_customer_id = f"cus_{_uuid.uuid4().hex[:12]}"
            u.trial_ends_at = None
            await s.commit()

        r = await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
        assert r.status_code == 200, r.text
        meter = r.json()["lookups"]
        assert meter["limit"] is None, "UNLIMITED sentinel for paid tiers"
        assert meter["remaining"] is None
        assert meter["resets_at"] is None


@pytest.mark.asyncio
async def test_anonymous_caller_gets_null_meter(client):
    """Anon isn't metered on this endpoint, so there is no meter to report —
    null, not a fabricated zero-usage block."""
    async with client:
        await _seed_ticker()
        r = await client.get(f"/api/ticker/{SEEDED}")
        assert r.status_code == 200, r.text
        assert r.json()["lookups"] is None


# ════════════════════════════════════════════════════════════════════════════
# 4. /api/usage exposes the same counter
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_usage_endpoint_includes_daily_lookups(client, monkeypatch):
    async with client:
        await _seed_ticker()
        cookies, _uid = await _free(client, monkeypatch)

        for _ in range(3):
            r = await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
            assert r.status_code == 200, r.text

        u = await client.get("/api/usage", cookies=cookies)
        assert u.status_code == 200, u.text
        block = u.json()["metrics"]["ticker_lookups_today"]
        assert block["cap"] == FREE_DAILY_LOOKUPS
        assert block["used"] == 3
        assert block["remaining"] == FREE_DAILY_LOOKUPS - 3
        assert block["resets_at"] is not None


@pytest.mark.asyncio
async def test_reading_usage_does_not_consume_a_lookup(client, monkeypatch):
    """The page that shows you your usage must not cost you any of it."""
    async with client:
        await _seed_ticker()
        cookies, _uid = await _free(client, monkeypatch)

        await client.get(f"/api/ticker/{SEEDED}", cookies=cookies)
        for _ in range(4):
            r = await client.get("/api/usage", cookies=cookies)
            assert r.status_code == 200, r.text

        block = (await client.get("/api/usage", cookies=cookies)).json()[
            "metrics"
        ]["ticker_lookups_today"]
        assert block["used"] == 1


@pytest.mark.asyncio
async def test_usage_reports_no_cap_for_paid_user(client, monkeypatch):
    async with client:
        cookies, uid = await _signup(client, monkeypatch)
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            u.tier = "pro"
            u.stripe_customer_id = f"cus_{_uuid.uuid4().hex[:12]}"
            u.trial_ends_at = None
            await s.commit()

        block = (await client.get("/api/usage", cookies=cookies)).json()[
            "metrics"
        ]["ticker_lookups_today"]
        assert block["cap"] is None
        assert block["remaining"] is None
        assert block["resets_at"] is None


@pytest.mark.asyncio
async def test_usage_reports_zero_after_utc_day_rollover(client, monkeypatch):
    """A counter still stamped with YESTERDAY has logically rolled over. The
    read surface must show 0, matching what the next look-up would reset it to
    — not a stale count that makes the user think they're nearly capped."""
    async with client:
        cookies, uid = await _free(client, monkeypatch)
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            u.lookups_today = FREE_DAILY_LOOKUPS
            u.lookups_reset_on = yesterday
            await s.commit()

        block = (await client.get("/api/usage", cookies=cookies)).json()[
            "metrics"
        ]["ticker_lookups_today"]
        assert block["used"] == 0
        assert block["remaining"] == FREE_DAILY_LOOKUPS
