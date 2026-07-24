"""cap_events instrumentation — the free→paid micro-funnel's ground truth.

Contract under test (services/cap_events + the five enforcement points):

  1. record_cap_hit(session, user_id, cap, tier)
       - persists ONE cap_events row for a FREE user,
       - is a NO-OP for pro/premium (paid ceilings aren't a conversion signal),
       - drops an unknown cap name instead of writing it,
       - NEVER raises: a write failure is swallowed so the caller's 402/403
         still returns cleanly.

  2. Each of the five server-side enforcement points writes a cap_events row at
     the exact moment a FREE user is refused MORE:
       - daily_lookups     GET /api/ticker/{sym}     (402 free_lookup_limit)
       - watchlist_tickers POST /api/watchlist       (403 watchlist full)
       - web_push_alerts   POST /api/alerts/rules    (403 free web-push cap)
       - squeeze_preview   GET /api/squeeze/preview  (free preview shows N of many)
       - scanner_rows      GET /api/scanner          (free row cap filled the page)

  3. A paid user sailing past (or never reaching) those branches writes NOTHING.

  4. A logging failure inside record_cap_hit does not break the endpoint.

Mirrors the signup + _set_tier helpers from test_freemium_lookups: the conftest
DB is session-scoped with no per-test rollback, so every assertion is scoped to
a freshly-created user (a unique uuid id), and cap_events rows are queried by
that user_id.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.db import session_scope
from app.main import app
from app.models import CapEvent, SqueezeSetup, Ticker, User
from app.routers.squeeze import FREE_SQUEEZE_PREVIEW_LIMIT
from app.services import cap_events as cap_events_module
from app.services.cap_events import record_cap_hit
from app.services.tier import (
    FREE_DAILY_LOOKUPS,
    FREE_SCANNER_ROWS,
    FREE_WATCHLIST_TICKERS,
    FREE_WEB_PUSH_ALERTS,
    Tier,
)


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

    email = f"caphit-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "CapHitTest"},
    )
    assert r.status_code == 200, r.text
    async with session_scope() as s:
        uid = (await s.execute(select(User.id).where(User.email == email))).scalar_one()
    return dict(r.cookies), uid


async def _set_tier(user_id: str, tier: str, *, paying: bool = True) -> None:
    """Flip a user's tier. A 'paying' user gets a stripe customer id + cleared
    trial so the freemium logic treats them as fully paid (never metered)."""
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        u.tier = tier
        if paying:
            u.stripe_customer_id = f"cus_{_uuid.uuid4().hex[:12]}"
            u.trial_ends_at = None
        else:
            u.stripe_customer_id = None
            u.trial_ends_at = None
        await s.commit()


async def _free(client, monkeypatch) -> tuple[dict, str]:
    """A logged-in FREE user PAST the first-session look-up grace window."""
    cookies, uid = await _signup(client, monkeypatch)
    await _set_tier(uid, "free", paying=False)
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        u.created_at = datetime.now(UTC) - timedelta(days=2)
        await s.commit()
    return cookies, uid


async def _cap_rows(user_id: str, cap: str | None = None) -> int:
    async with session_scope() as s:
        stmt = select(func.count()).select_from(CapEvent).where(CapEvent.user_id == user_id)
        if cap is not None:
            stmt = stmt.where(CapEvent.cap == cap)
        return (await s.execute(stmt)).scalar_one()


# ════════════════════════════════════════════════════════════════════════════
# 1. record_cap_hit unit contract (no HTTP)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_record_cap_hit_persists_free_row():
    uid = f"u-{_uuid.uuid4().hex[:12]}"
    async with session_scope() as s:
        await record_cap_hit(s, uid, "daily_lookups", Tier.FREE)

    async with session_scope() as s:
        rows = (
            await s.execute(select(CapEvent).where(CapEvent.user_id == uid))
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].cap == "daily_lookups"
    assert rows[0].tier == "free"
    assert rows[0].created_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["pro", "premium", Tier.PRO, Tier.PREMIUM])
async def test_record_cap_hit_noop_for_paid(tier):
    """Paid ceilings are not a free→paid signal — nothing is written, whether
    the tier is passed as a string or the Tier enum."""
    uid = f"u-{_uuid.uuid4().hex[:12]}"
    async with session_scope() as s:
        await record_cap_hit(s, uid, "watchlist_tickers", tier)
    assert await _cap_rows(uid) == 0


@pytest.mark.asyncio
async def test_record_cap_hit_drops_unknown_cap():
    """A typo'd cap name must not poison the dataset — dropped, not written,
    and never raised."""
    uid = f"u-{_uuid.uuid4().hex[:12]}"
    async with session_scope() as s:
        await record_cap_hit(s, uid, "not_a_real_cap", Tier.FREE)
    assert await _cap_rows(uid) == 0


@pytest.mark.asyncio
async def test_record_cap_hit_swallows_write_error():
    """A commit failure must be swallowed (fire-and-forget) so the caller's
    reject branch still returns cleanly — record_cap_hit never propagates."""
    uid = f"u-{_uuid.uuid4().hex[:12]}"

    async with session_scope() as s:
        async def _boom():
            raise RuntimeError("db down")

        s.commit = _boom  # type: ignore[method-assign]
        # Must NOT raise despite the commit blowing up.
        await record_cap_hit(s, uid, "scanner_rows", Tier.FREE)

    assert await _cap_rows(uid) == 0


# ════════════════════════════════════════════════════════════════════════════
# 2. Enforcement points persist a row for a FREE user
# ════════════════════════════════════════════════════════════════════════════


async def _seed_ticker(symbol: str) -> None:
    async with session_scope() as s:
        existing = (
            await s.execute(select(Ticker).where(Ticker.symbol == symbol))
        ).scalar_one_or_none()
        if existing is None:
            s.add(Ticker(symbol=symbol, name="Cap Hit Co", score=72.0))
            await s.commit()


@pytest.mark.asyncio
async def test_daily_lookups_cap_hit_persists(client, monkeypatch):
    sym = "CAPLOOK"
    async with client:
        await _seed_ticker(sym)
        cookies, uid = await _free(client, monkeypatch)
        # Jump straight to the wall: stamp the durable counter at-cap for today.
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            u.lookups_today = FREE_DAILY_LOOKUPS
            u.lookups_reset_on = datetime.now(UTC).date()
            await s.commit()

        r = await client.get(f"/api/ticker/{sym}", cookies=cookies)
        assert r.status_code == 402, r.text

    assert await _cap_rows(uid, "daily_lookups") == 1


@pytest.mark.asyncio
async def test_watchlist_cap_hit_persists(client, monkeypatch):
    async with client:
        cookies, uid = await _free(client, monkeypatch)
        # Fill to the free watchlist cap.
        for i in range(FREE_WATCHLIST_TICKERS):
            r = await client.post(
                "/api/watchlist", json={"symbol": f"WL{i}"}, cookies=cookies
            )
            assert r.status_code == 200, r.text
        # One past the cap → 403.
        over = await client.post(
            "/api/watchlist", json={"symbol": "WLOVER"}, cookies=cookies
        )
        assert over.status_code == 403, over.text

    assert await _cap_rows(uid, "watchlist_tickers") == 1


@pytest.mark.asyncio
async def test_web_push_cap_hit_persists(client, monkeypatch):
    def _wp(i: int) -> dict:
        return {
            "name": f"WP {i}",
            "rule_type": "score",
            "symbol": "AAPL",
            "threshold": 70,
            "channel": "web_push",
        }

    async with client:
        cookies, uid = await _free(client, monkeypatch)
        for i in range(FREE_WEB_PUSH_ALERTS):
            r = await client.post("/api/alerts/rules", json=_wp(i), cookies=cookies)
            assert r.status_code == 200, r.text
        over = await client.post("/api/alerts/rules", json=_wp(99), cookies=cookies)
        assert over.status_code == 403, over.text

    assert await _cap_rows(uid, "web_push_alerts") == 1


async def _seed_squeeze(n: int) -> None:
    async with session_scope() as s:
        for i in range(n):
            sym = f"SQZ{i}"
            existing = (
                await s.execute(select(SqueezeSetup).where(SqueezeSetup.symbol == sym))
            ).scalar_one_or_none()
            if existing is None:
                s.add(
                    SqueezeSetup(
                        symbol=sym,
                        spike_score=90.0 - i,
                        squeeze_days=5,
                        volume_multiple=2.0,
                        obv_trend="up",
                        breakout_type="bull",
                        suggested_window="5-10d",
                        reason="test",
                    )
                )
        await s.commit()


@pytest.mark.asyncio
async def test_squeeze_preview_cap_hit_persists(client, monkeypatch):
    async with client:
        # More setups than the preview shows → the free user is refused the rest.
        await _seed_squeeze(FREE_SQUEEZE_PREVIEW_LIMIT + 2)
        cookies, uid = await _free(client, monkeypatch)

        r = await client.get("/api/squeeze/preview", cookies=cookies)
        assert r.status_code == 200, r.text

    assert await _cap_rows(uid, "squeeze_preview") == 1


async def _seed_scanner_universe(n: int) -> None:
    """Seed n tickers that PASS live_clauses (fresh + valid composite) so a free
    user's capped scanner page fills to FREE_SCANNER_ROWS."""
    now = datetime.now(UTC)
    async with session_scope() as s:
        for i in range(n):
            sym = f"SCAN{i:02d}"
            existing = (
                await s.execute(select(Ticker).where(Ticker.symbol == sym))
            ).scalar_one_or_none()
            if existing is None:
                s.add(
                    Ticker(
                        symbol=sym,
                        name=f"Scan Co {i}",
                        asset_class="stock",
                        score=80.0 - (i * 0.1),
                        change_pct_1d=1.0,
                        confidence_pct=90.0,
                        sub_trend=70.0,
                        sub_rs=65.0,
                        updated_at=now,
                    )
                )
        await s.commit()


@pytest.mark.asyncio
async def test_scanner_rows_cap_hit_persists(client, monkeypatch):
    async with client:
        # Comfortably more valid rows than the free cap so the page fills.
        await _seed_scanner_universe(FREE_SCANNER_ROWS + 3)
        cookies, uid = await _free(client, monkeypatch)

        r = await client.get("/api/scanner?limit=100", cookies=cookies)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tier"] == "free"
        assert body["count"] == FREE_SCANNER_ROWS

    assert await _cap_rows(uid, "scanner_rows") >= 1


# ════════════════════════════════════════════════════════════════════════════
# 3. Paid users write NOTHING
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_paid_user_lookups_write_no_cap_event(client, monkeypatch):
    sym = "CAPLOOKPRO"
    async with client:
        await _seed_ticker(sym)
        cookies, uid = await _signup(client, monkeypatch)
        await _set_tier(uid, "pro", paying=True)
        # Well past the free cap — all 200 (unmetered), never a 402.
        for _ in range(FREE_DAILY_LOOKUPS + 3):
            r = await client.get(f"/api/ticker/{sym}", cookies=cookies)
            assert r.status_code == 200, r.text

    assert await _cap_rows(uid) == 0


@pytest.mark.asyncio
async def test_premium_user_squeeze_preview_writes_no_cap_event(client, monkeypatch):
    """A premium user has squeeze.full, so the preview endpoint's cap-hit guard
    is false AND record_cap_hit refuses paid tiers — belt and braces, no row."""
    async with client:
        await _seed_squeeze(FREE_SQUEEZE_PREVIEW_LIMIT + 2)
        cookies, uid = await _signup(client, monkeypatch)
        await _set_tier(uid, "premium", paying=True)

        r = await client.get("/api/squeeze/preview", cookies=cookies)
        assert r.status_code == 200, r.text

    assert await _cap_rows(uid) == 0


# ════════════════════════════════════════════════════════════════════════════
# 4. A logging failure does not break the endpoint
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_logging_failure_does_not_break_endpoint(client, monkeypatch):
    """Force the cap-event write to blow up and prove the 402 still returns —
    instrumentation must never turn a clean reject into a 500."""
    sym = "CAPLOOKFAIL"

    class _BrokenCapEvent:
        def __init__(self, *a, **k):
            raise RuntimeError("simulated insert failure")

    # record_cap_hit references the module-global CapEvent; swap it for one that
    # raises on construction, inside the helper's try/except.
    monkeypatch.setattr(cap_events_module, "CapEvent", _BrokenCapEvent)

    async with client:
        await _seed_ticker(sym)
        cookies, uid = await _free(client, monkeypatch)
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            u.lookups_today = FREE_DAILY_LOOKUPS
            u.lookups_reset_on = datetime.now(UTC).date()
            await s.commit()

        r = await client.get(f"/api/ticker/{sym}", cookies=cookies)
        # The endpoint still rejects cleanly despite the logging blow-up.
        assert r.status_code == 402, r.text

    # And nothing was written for this user.
    assert await _cap_rows(uid) == 0
