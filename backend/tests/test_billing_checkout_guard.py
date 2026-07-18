"""POST /api/billing/checkout — double-billing guard + mid-trial preservation.

Two money-path contracts pinned here:

  1. An existing subscriber (paid tier live on Stripe) gets a 409 — Checkout
     always mints a NEW Stripe Customer + subscription, so letting a
     subscriber through double-bills them and the webhook can only page the
     founder to refund it after the money moved. The guard must NOT block
     churned users (tier already dropped to free, customer id retained) —
     the win-back re-subscribe path depends on them checking out again.
  2. A user on an unexpired no-card trial has their trial_ends_at forwarded
     as trial_end so adding a card doesn't charge immediately and silently
     forfeit the remaining free days (the <48h Stripe-minimum fallback is
     covered service-side in test_billing_checkout.py).

Mirrors test_retention_flow.py: endpoints authenticate via `Bearer
dev-bypass` → the shared dev_user row; the Stripe-touching service function
(create_checkout_session) is monkeypatched at the router import site; and
assertions read the SPECIFIC dev_user row, never aggregates.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.routers import billing as billing_router

_AUTH = {"Authorization": "Bearer dev-bypass"}


async def _prep_dev_user(client: httpx.AsyncClient, **fields) -> None:
    """Reset the shared dev_user row to a known baseline + the given fields,
    so each test is independent of leftover state from earlier tests."""
    # GET /api/me ensures the dev_user row exists before we mutate it.
    await client.get("/api/me", headers=_AUTH)
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one()
        u.tier = fields.get("tier", "premium")
        u.stripe_customer_id = fields.get("stripe_customer_id")
        u.canceled_at = fields.get("canceled_at")
        u.trial_ends_at = fields.get("trial_ends_at")
        u.checkout_started_at = None
        u.checkout_tier = None
        u.checkout_billing_period = None
        await s.commit()


async def _dev_user_snapshot() -> dict:
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one()
        return {
            "tier": u.tier,
            "stripe_customer_id": u.stripe_customer_id,
            "checkout_started_at": u.checkout_started_at,
        }


@pytest.fixture(autouse=True)
async def _restore_dev_user_baseline():
    """Leave dev_user clean for other suites (the DB is session-scoped and
    never truncated): premium tier, no Stripe customer, no trial."""
    yield
    async with session_scope() as s:
        u = (
            await s.execute(select(User).where(User.id == "dev_user"))
        ).scalar_one_or_none()
        if u is None:
            return
        u.tier = "premium"
        u.stripe_customer_id = None
        u.canceled_at = None
        u.trial_ends_at = None
        u.checkout_started_at = None
        u.checkout_tier = None
        u.checkout_billing_period = None
        await s.commit()


def _capture_checkout(monkeypatch) -> dict:
    """Patch billing_router.create_checkout_session with a kwargs recorder."""
    captured: dict = {}

    async def _fake(**kwargs):
        captured.clear()
        captured.update(kwargs)
        return "https://stripe.test/session"

    monkeypatch.setattr(billing_router, "create_checkout_session", _fake)
    return captured


async def test_checkout_409_for_active_subscriber(monkeypatch):
    """A live subscriber (paid tier + linked Stripe customer) must never mint
    a second checkout session — 409 before any Stripe call, and the
    abandonment-recovery marker must NOT be armed."""
    captured = _capture_checkout(monkeypatch)
    transport = httpx.ASGITransport(app=app)
    for tier in ("pro", "premium"):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await _prep_dev_user(c, tier=tier, stripe_customer_id="cus_guard_live")
            r = await c.post(
                "/api/billing/checkout",
                json={"tier": "premium", "billing_period": "monthly"},
                headers=_AUTH,
            )
        assert r.status_code == 409, tier
        assert "already have an active subscription" in r.json()["detail"]
        assert captured == {}, "create_checkout_session must not be called"

    snap = await _dev_user_snapshot()
    assert snap["checkout_started_at"] is None


async def test_checkout_allows_churned_resubscribe(monkeypatch):
    """A churned user keeps their stripe_customer_id but their tier already
    dropped to free — they MUST still be able to check out again (the day-90
    win-back email depends on it), with the win-back flag intact."""
    captured = _capture_checkout(monkeypatch)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(
            c,
            tier="free",
            stripe_customer_id="cus_guard_churned",
            canceled_at=datetime.now(UTC),
        )
        r = await c.post(
            "/api/billing/checkout",
            json={"tier": "pro", "billing_period": "monthly"},
            headers=_AUTH,
        )
    assert r.status_code == 200
    assert captured["winback"] is True
    assert captured["trial_end"] is None  # churned, not on trial


async def test_checkout_forwards_trial_end_for_trial_user(monkeypatch):
    """Mid-trial card-add: the user's unexpired trial_ends_at is forwarded so
    Stripe starts billing at trial end instead of charging immediately."""
    captured = _capture_checkout(monkeypatch)
    trial_ends = datetime.now(UTC) + timedelta(days=11)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(c, tier="premium", trial_ends_at=trial_ends)
        r = await c.post(
            "/api/billing/checkout",
            json={"tier": "premium", "billing_period": "monthly"},
            headers=_AUTH,
        )
    assert r.status_code == 200
    forwarded = captured["trial_end"]
    assert forwarded is not None
    # SQLite round-trips DateTime(timezone=True) as naive UTC — normalise
    # before comparing instants.
    if forwarded.tzinfo is None:
        forwarded = forwarded.replace(tzinfo=UTC)
    assert abs((forwarded - trial_ends).total_seconds()) < 5


async def test_checkout_no_trial_end_when_not_on_trial(monkeypatch):
    """No trial (comped premium) or an EXPIRED trial must not forward a
    trial_end — only an unexpired no-card trial earns preservation."""
    captured = _capture_checkout(monkeypatch)
    transport = httpx.ASGITransport(app=app)
    for trial_ends in (None, datetime.now(UTC) - timedelta(days=1)):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            await _prep_dev_user(c, tier="premium", trial_ends_at=trial_ends)
            r = await c.post(
                "/api/billing/checkout",
                json={"tier": "premium", "billing_period": "monthly"},
                headers=_AUTH,
            )
        assert r.status_code == 200
        assert captured["trial_end"] is None, trial_ends


# ── Cancelled-checkout return path ──────────────────────────────────────────

async def test_cancel_url_carries_tier_and_period_for_resume(monkeypatch):
    """Stripe's "back" link must name the plan the user was part-way through.

    /app/billing reads these params to render the "nothing was charged"
    recovery panel with ONE resume button. Without them the page can still
    reassure, but it has to fall back to the whole plan grid — so the params
    are the difference between one click and a re-decision.
    """
    captured = _capture_checkout(monkeypatch)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(c, tier="free", stripe_customer_id=None)
        r = await c.post(
            "/api/billing/checkout",
            json={"tier": "premium", "billing_period": "annual"},
            headers=_AUTH,
        )
    assert r.status_code == 200
    cancel_url = captured["cancel_url"]
    assert "checkout=cancelled" in cancel_url
    assert "tier=premium" in cancel_url
    assert "billing_period=annual" in cancel_url


# ── Dunning state on the endpoint the billing page already calls ────────────

async def test_retention_options_reports_past_due():
    """A failed renewal surfaces on /api/billing/retention-options so the
    billing page can render its recovery panel — and stop quoting a "next
    charge" price — without a second round-trip."""
    from sqlalchemy import delete

    from app.models import Subscription

    sub_id = f"sub_ro_{uuid4().hex[:12]}"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(c, tier="premium", stripe_customer_id="cus_ro_pastdue")
        async with session_scope() as s:
            s.add(Subscription(
                id=sub_id,
                user_id="dev_user",
                status="past_due",
                tier="premium",
                current_period_end=datetime.now(UTC) + timedelta(days=30),
            ))
            await s.commit()
        try:
            body = (
                await c.get("/api/billing/retention-options", headers=_AUTH)
            ).json()
            assert body["past_due"] is True
            assert body["subscription_status"] == "past_due"
        finally:
            async with session_scope() as s:
                await s.execute(delete(Subscription).where(Subscription.id == sub_id))
                await s.commit()


async def test_retention_options_healthy_subscription_not_past_due():
    """An active subscription must never trip the dunning panel."""
    from sqlalchemy import delete

    from app.models import Subscription

    sub_id = f"sub_ok_{uuid4().hex[:12]}"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await _prep_dev_user(c, tier="premium", stripe_customer_id="cus_ro_active")
        async with session_scope() as s:
            s.add(Subscription(
                id=sub_id,
                user_id="dev_user",
                status="active",
                tier="premium",
                current_period_end=datetime.now(UTC) + timedelta(days=30),
            ))
            await s.commit()
        try:
            body = (
                await c.get("/api/billing/retention-options", headers=_AUTH)
            ).json()
            assert body["past_due"] is False
            assert body["subscription_status"] == "active"
        finally:
            async with session_scope() as s:
                await s.execute(delete(Subscription).where(Subscription.id == sub_id))
                await s.commit()
