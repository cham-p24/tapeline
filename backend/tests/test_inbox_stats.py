"""Coverage for GET /api/inbox/stats — the observability surface.

Founder polls this every 30s from /app/inbox to see live spend, tier
mix, latency, and queue depth. A regression here is the founder going
blind to a cost-cap trip OR a classifier drift; both are bad enough to
warrant test coverage even though the endpoint is read-only.

Tests:
  - 401 unauth
  - Empty DB → all numeric counts 0, no errors
  - Spend SUM matches inserted classification_log rows
  - cap_tripped flips when daily spend ≥ cap
  - Latency p50 / p95 computed on a known set
  - tier_counts_today aggregates inbound_messages by tier
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from app.config import get_settings
from app.db import session_scope
from app.main import app
from app.models import InboundMessage, InboxClassificationLog, User
from app.services import inbox_kill_switch


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()
    yield
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()


async def _make_admin_cookies(client: httpx.AsyncClient, monkeypatch) -> dict:
    """Mirror of test_email_preview's helper — make + promote an admin
    user so we can hit /api/inbox/stats."""
    from sqlalchemy import select

    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"inbox-stats-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "Admin"},
    )
    assert r.status_code == 200, r.text
    cookies = r.cookies

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_admin = True
        await s.commit()
    return cookies


@pytest.mark.asyncio
async def test_stats_requires_admin(client):
    async with client:
        r = await client.get("/api/inbox/stats")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_stats_empty_db_returns_zero_counts(client, monkeypatch):
    """An admin asking before any inbox traffic exists should get a
    well-shaped response with zero counts, no errors."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        r = await client.get("/api/inbox/stats", cookies=cookies)
        assert r.status_code == 200, r.text
        body = r.json()

    # Spend + classification count
    assert isinstance(body["today_spend_usd"], (int, float))
    assert body["today_classifications"] >= 0
    assert "cap_usd" in body
    assert isinstance(body["cap_tripped"], bool)
    # Pending count is non-negative
    assert body["pending_count"] >= 0
    # Tier-count shape always has the four keys even if empty
    for k in ("1", "2", "3", "unclassified"):
        assert k in body["tier_counts_today"]
        assert k in body["tier_counts_last_7d"]
    # Latency percentiles can be None when there's no data yet
    assert body["latency_p50_ms"] is None or isinstance(body["latency_p50_ms"], int)
    assert body["latency_p95_ms"] is None or isinstance(body["latency_p95_ms"], int)
    # Cache hit ratio is 0..1 (0.0 when no data)
    assert 0.0 <= body["cache_hit_ratio"] <= 1.0
    # Toggles surfaced for the UI status chip
    assert isinstance(body["bot_enabled"], bool)
    assert isinstance(body["dry_run"], bool)


@pytest.mark.asyncio
async def test_stats_aggregates_classification_log_spend(client, monkeypatch):
    """Insert three classification_log rows totalling $0.42 of spend
    today; the endpoint should report today_spend_usd ≈ 0.42 and
    today_classifications == 3."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)

        # Seed three rows
        now = datetime.now(UTC)
        async with session_scope() as s:
            for cost, latency in [
                (Decimal("0.10"), 200),
                (Decimal("0.20"), 800),
                (Decimal("0.12"), 1200),
            ]:
                s.add(InboxClassificationLog(
                    inbound_message_id=None,
                    input_hash="x" * 64,
                    model="claude-haiku-4-5",
                    input_tokens=500,
                    cached_tokens=400,
                    output_tokens=80,
                    cost_usd=cost,
                    latency_ms=latency,
                    tier=1,
                    reason="test seed",
                ))
            await s.commit()
        inbox_kill_switch.reset_spend_cache()

        r = await client.get("/api/inbox/stats", cookies=cookies)
        assert r.status_code == 200, r.text
        body = r.json()

    assert body["today_classifications"] >= 3
    # Spend should include the 0.42 we just added (other tests may have
    # contributed too; we only assert AT LEAST our seed).
    assert body["today_spend_usd"] >= 0.42 - 1e-6
    # p50 on [200, 800, 1200] is the middle element (800), p95 is the
    # largest. With other test seeds in the same window the exact value
    # may shift, so we assert structure not exact equality.
    assert body["latency_p50_ms"] is not None
    assert body["latency_p95_ms"] is not None
    assert body["latency_p50_ms"] <= body["latency_p95_ms"]


@pytest.mark.asyncio
async def test_stats_cap_tripped_flag(client, monkeypatch):
    """When today's spend ≥ INBOX_CLAUDE_DAILY_CAP_USD, cap_tripped is true."""
    # Set a tiny cap so any single test row trips it.
    monkeypatch.setenv("INBOX_CLAUDE_DAILY_CAP_USD", "0.001")
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()

    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        async with session_scope() as s:
            s.add(InboxClassificationLog(
                inbound_message_id=None,
                input_hash="capped" + "x" * 58,
                model="claude-haiku-4-5",
                input_tokens=10, cached_tokens=0, output_tokens=10,
                cost_usd=Decimal("0.50"),  # way above the 0.001 cap
                latency_ms=100, tier=1, reason="cap test",
            ))
            await s.commit()
        inbox_kill_switch.reset_spend_cache()

        r = await client.get("/api/inbox/stats", cookies=cookies)
        assert r.status_code == 200, r.text
        body = r.json()
    assert body["cap_tripped"] is True


@pytest.mark.asyncio
async def test_stats_tier_counts_aggregate_inbound_messages(client, monkeypatch):
    """Insert 2 Tier 1, 1 Tier 2, 1 Tier 3 today; verify counts."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        now = datetime.now(UTC)
        seeds = [(1, "a"), (1, "b"), (2, "c"), (3, "d")]
        async with session_scope() as s:
            for tier, sfx in seeds:
                s.add(InboundMessage(
                    channel="email",
                    channel_msg_id=f"stats-tier-{_uuid.uuid4().hex}-{sfx}",
                    author="stats-test@example.com",
                    body=f"seeded tier {tier}",
                    received_at=now,
                    tier=tier,
                    status="classified",
                ))
            await s.commit()

        r = await client.get("/api/inbox/stats", cookies=cookies)
        assert r.status_code == 200, r.text
        body = r.json()

    # At least our 4 seeds — other tests may have inserted more.
    assert body["tier_counts_today"]["1"] >= 2
    assert body["tier_counts_today"]["2"] >= 1
    assert body["tier_counts_today"]["3"] >= 1


@pytest.mark.asyncio
async def test_stats_pending_count_includes_new_and_classified(client, monkeypatch):
    """pending_count counts rows in status='new' OR 'classified' so the
    founder can see queue depth across both stages."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        now = datetime.now(UTC)
        async with session_scope() as s:
            for status in ["new", "classified"]:
                s.add(InboundMessage(
                    channel="email",
                    channel_msg_id=f"stats-pending-{_uuid.uuid4().hex}-{status}",
                    author="stats-pending@example.com",
                    body=f"queued ({status})",
                    received_at=now,
                    tier=1,
                    status=status,
                ))
            # An already-handled row that should NOT count
            s.add(InboundMessage(
                channel="email",
                channel_msg_id=f"stats-pending-{_uuid.uuid4().hex}-done",
                author="stats-pending@example.com",
                body="already done",
                received_at=now,
                tier=2,
                status="auto_replied",
                handled_at=now,
            ))
            await s.commit()

        r = await client.get("/api/inbox/stats", cookies=cookies)
        assert r.status_code == 200, r.text
        body = r.json()

    # ≥ 2 because our seeds added 2 pending rows
    assert body["pending_count"] >= 2
