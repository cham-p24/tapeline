"""Regression guards for the round-5 audit fixes.

  #1 alerts._fire re-checked only the delivery CHANNEL entitlement, never the
     rule TYPE's content feature — so a congress/squeeze/regime/news rule
     authored on a Premium trial kept delivering its Pro/Premium body after the
     trial lapsed to Free (most reachably via the Free web_push channel), and
     the full body was stored on the AlertEvent (readable at /api/alerts/events).
  #2 DELETE /api/alerts/rules/{id} did a bare session.delete(rule) with no
     child cleanup; alert_events.rule_id is a NOT-NULL FK with no ON DELETE, so
     on Postgres deleting a rule that had ever fired raised a ForeignKeyViolation
     (HTTP 500). Now deletes the events first.
  #4 customer.subscription.created never linked stripe_customer_id, so the
     trial-downgrade worker (keyed on stripe_customer_id IS NULL) could strand a
     brand-new paying subscriber at Free. Now links the customer when NULL.
  #8 Reddit dry-run marked Tier-2 auto-replies 'sent' though nothing was
     delivered. Now only marks sent on a real (non-dry-run) send.
  #9 _cost_for double-subtracted cache_read from input_tokens (they're separate
     additive buckets), so warm-cache classifications billed ~$0 and the daily
     spend cap under-enforced. Now bills each bucket at its own rate.
  #10 create_api_key check-then-insert wasn't atomic; now takes a per-user row
     lock before counting.
  #11 account erasure left the newsletter_subscribers row (email + UTM); now
     purged with the account.
"""
from __future__ import annotations

import secrets
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import func, select

from app.db import session_scope
from app.main import app
from app.models import AlertEvent, AlertRule, NewsletterSubscriber, User

# ── #1: content-tier re-check at send time ────────────────────────────────────

@pytest.mark.asyncio
async def test_downgraded_user_premium_alert_content_is_suppressed_and_redacted():
    from app.services import alerts

    uid = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(id=uid, email=f"{uid}@example.com", tier="free", password_hash="x"))
        # A congress (Premium) rule on the Free web_push channel — the exact
        # shape that survives a trial→Free downgrade and leaks premium content.
        rule = AlertRule(
            user_id=uid, name="Congress", rule_type="congress",
            channel="web_push", enabled=True,
        )
        s.add(rule)
        await s.commit()
        await s.refresh(rule)
        rule_id = rule.id

    premium_body = "Nancy Pelosi (House) BUY NVDA $1,000,000-$5,000,000"
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        r = (await s.execute(select(AlertRule).where(AlertRule.id == rule_id))).scalar_one()
        await alerts._fire(s, r, u, symbol="NVDA", message=premium_body, score=90.0)
        await s.commit()

    async with session_scope() as s:
        ev = (await s.execute(
            select(AlertEvent).where(AlertEvent.rule_id == rule_id)
        )).scalar_one()
    assert ev.delivered is False
    assert premium_body not in (ev.message or ""), "premium body must not be stored/leaked"
    assert "congress" in (ev.message or "").lower(), "redacted suppression message expected"


# ── #2: deleting a fired rule removes its events (no Postgres FK violation) ────

@pytest.mark.asyncio
async def test_deleting_a_fired_alert_rule_also_removes_its_events():
    from app.routers import alerts as alerts_router

    uid = f"u_{_uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(id=uid, email=f"{uid}@example.com", tier="premium", password_hash="x"))
        rule = AlertRule(user_id=uid, name="Score", rule_type="score",
                         channel="email", enabled=True)
        s.add(rule)
        await s.commit()
        await s.refresh(rule)
        rule_id = rule.id
        s.add(AlertEvent(user_id=uid, rule_id=rule_id, symbol="AAPL",
                         message="fired", channel="email", delivered=True))
        await s.commit()

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        out = await alerts_router.delete_rule(rule_id=rule_id, user=u, session=s)

    assert out["ok"] is True
    async with session_scope() as s:
        assert (await s.execute(
            select(AlertRule).where(AlertRule.id == rule_id)
        )).scalar_one_or_none() is None
        events = (await s.execute(
            select(AlertEvent).where(AlertEvent.rule_id == rule_id)
        )).scalars().all()
    assert events == [], "child alert_events must be deleted (else Postgres FK-violates)"


# ── #4: subscription.created links stripe_customer_id for a first-time sub ─────

@pytest.mark.asyncio
async def test_subscription_created_links_customer_for_first_time_subscriber(monkeypatch):
    from app.routers import webhooks as webhooks_router

    uid = f"u_{_uuid.uuid4().hex}"
    # A lapsed-trial user: Free, no Stripe customer, trial ended yesterday —
    # exactly what _downgrade_expired_trials keys on (stripe_customer_id IS NULL).
    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.com", tier="free", password_hash="x",
            stripe_customer_id=None,
            trial_ends_at=datetime.now(UTC) - timedelta(days=1),
        ))
        await s.commit()

    cust = f"cus_{_uuid.uuid4().hex[:18]}"
    payload = {
        "id": f"sub_{_uuid.uuid4().hex[:16]}",
        "status": "active",
        "tier": "premium",
        "current_period_end": datetime.now(UTC) + timedelta(days=20),
        "cancel_at_period_end": False,
    }
    monkeypatch.setattr(webhooks_router, "subscription_payload", lambda obj: payload)
    monkeypatch.setattr(webhooks_router.settings, "stripe_webhook_secret", "whsec_test")
    # Resolved via the metadata fallback (no user maps to the new customer yet).
    event = {
        "id": f"evt_{_uuid.uuid4().hex}",
        "type": "customer.subscription.created",
        "data": {"object": {"customer": cust, "metadata": {"user_id": uid}}},
    }
    monkeypatch.setattr(webhooks_router, "parse_webhook", lambda body, sig: event)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/webhooks/stripe", content=b"{}",
                         headers={"stripe-signature": "sig"})
    assert r.status_code == 200, r.text

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
    assert u.stripe_customer_id == cust, "first-time subscriber must be linked to close the downgrade race"
    assert u.tier == "premium"


# ── #8: Reddit dry-run must NOT mark a Tier-2 reply 'sent' ─────────────────────

@pytest.mark.asyncio
async def test_reddit_dry_run_does_not_mark_tier2_sent(monkeypatch):
    from app.services import inbox_kill_switch, reddit_inbox

    msg = SimpleNamespace(id=4242, status="auto_replied")
    result = SimpleNamespace(
        already_handled=False, tier=2, auto_reply_text="AAPL scores 80.", message=msg,
    )

    async def _fake_handle(*a, **k):
        return result

    async def _fake_send(_m, _t):
        return True  # dry-run send_reddit_reply also returns True — that's the trap

    marked: list[int] = []

    async def _fake_mark(_session, mid, when=None):
        marked.append(mid)

    monkeypatch.setattr(reddit_inbox, "handle_inbound", _fake_handle)
    monkeypatch.setattr(reddit_inbox, "find_prescriptive_phrase", lambda _t: None)
    monkeypatch.setattr(reddit_inbox, "send_reddit_reply", _fake_send)
    monkeypatch.setattr(reddit_inbox, "mark_sent", _fake_mark)

    session = AsyncMock()

    # Dry-run: nothing is actually posted, so the row must stay drafted.
    monkeypatch.setattr(inbox_kill_switch, "dry_run", lambda: True)
    await reddit_inbox._dispatch_inbound(
        session, channel="reddit_dm", channel_msg_id="t4_x",
        author="u/x", body="AAPL?", received_at=datetime.now(UTC),
    )
    assert marked == [], "dry-run must not record a phantom delivery as 'sent'"

    # Live: a real send DOES mark it sent.
    monkeypatch.setattr(inbox_kill_switch, "dry_run", lambda: False)
    await reddit_inbox._dispatch_inbound(
        session, channel="reddit_dm", channel_msg_id="t4_x",
        author="u/x", body="AAPL?", received_at=datetime.now(UTC),
    )
    assert marked == [4242], "a real (non-dry-run) send must mark the row sent"


# ── #9: warm-cache fresh input is billed, not zeroed ──────────────────────────

def test_cost_bills_uncached_input_not_zeroed_by_cache_read():
    from app.services.inbox_classifier import _cost_for

    # Warm cache: 60 fresh input tokens, 600 cache-read, 100 output.
    # Pre-fix uncached = max(0, 60 - 600) = 0 → the 60 fresh tokens billed at $0.
    # Post-fix: (60*1.00 + 600*0.10 + 100*5.00)/1e6 = 0.000620.
    cost = _cost_for("claude-haiku-4-5", 60, 600, 100)
    assert cost == Decimal("0.000620")
    # Strictly above the cache-read + output-only floor (the fresh input counts).
    floor = _cost_for("claude-haiku-4-5", 0, 600, 100)
    assert cost > floor


# ── #10: key-create takes a row lock before counting (race guard) ─────────────

def test_api_key_create_locks_the_user_row_before_counting():
    src = (
        Path(__file__).resolve().parent.parent / "app" / "routers" / "api_keys.py"
    ).read_text(encoding="utf-8")
    assert "with_for_update()" in src, (
        "create_api_key must serialise concurrent creates (per-user row lock) so "
        "a parallel burst can't exceed MAX_KEYS_PER_USER"
    )


# ── #11: account erasure purges the newsletter_subscribers row ────────────────

@pytest.mark.asyncio
async def test_account_deletion_purges_newsletter_subscriber_row():
    from app.routers import account as acct

    uid = f"u_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(id=uid, email=email, tier="premium", password_hash="x"))
        s.add(NewsletterSubscriber(
            email=email, status="confirmed", source="signup",
            unsubscribe_token=secrets.token_hex(32),
        ))
        await s.commit()

    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        await acct.delete_my_account(user=u, session=s)

    async with session_scope() as s:
        rows = (await s.execute(
            select(NewsletterSubscriber).where(
                func.lower(NewsletterSubscriber.email) == email.lower()
            )
        )).scalars().all()
    assert rows == [], "the erased user's newsletter row (email + UTM) must be gone"
