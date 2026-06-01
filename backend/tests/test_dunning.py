"""Dunning sequence — failed-payment recovery (PR4).

Covers the four moving parts of the dunning loop:

  1. Renderers (pure): the `final_attempt` last-chance variant of
     render_payment_failed_email, and render_payment_recovered_email.
  2. Subscription status → tier: a `past_due` sub keeps the customer on their
     paid tier (the Stripe-retry grace window); a terminal `unpaid` drops to
     Free. This is the grace-window behaviour the whole sequence depends on —
     emailing a fix-it link is pointless if access was already yanked.
  3. invoice.payment_failed: sends an escalating email, stamps a `dun{n}`
     dedup token per attempt, dedupes a re-fired attempt, flips subject +
     copy on the final attempt, and does NOT stamp when the send is skipped.
  4. invoice.payment_succeeded: a mid-dunning recovery (user carries dun
     tokens) clears them and sends the all-clear; a routine renewal (no dun
     tokens) stays silent.
  5. /api/me surfaces billing.past_due so the DunningBanner can render.

Webhook tests drive the real endpoint with parse_webhook + subscription_payload
monkeypatched (there's no Stripe key in CI) and a unique event id per call so
the StripeWebhookEvent replay-dedup never false-fires against the shared
session-scoped SQLite DB. Assertions are per-seeded-user (fresh uuid id each
time), never on aggregate counts, so leftover rows from other tests can't
perturb them.
"""
from __future__ import annotations

import re
import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, select

import app.services.email as email_module
from app.db import session_scope
from app.main import app
from app.models import Subscription, User
from app.routers import webhooks as webhooks_router
from app.services.email import (
    render_payment_failed_email,
    render_payment_recovered_email,
)

_AUTH = {"Authorization": "Bearer dev-bypass"}
# A far-future unix ts so next_payment_attempt reads as "Stripe will retry".
_FUTURE_TS = int((datetime.now(UTC) + timedelta(days=3)).timestamp())


# ── helpers ──────────────────────────────────────────────────────────────────

def _evt(evt_type: str, obj: dict) -> dict:
    """A parsed-webhook stand-in with a unique id (dodges replay dedup)."""
    return {"id": f"evt_{_uuid.uuid4().hex}", "type": evt_type, "data": {"object": obj}}


async def _fire(monkeypatch, event: dict) -> httpx.Response:
    """POST a fake Stripe event through the real /api/webhooks/stripe handler.

    parse_webhook is patched to return `event` verbatim, so the signature +
    body are irrelevant; the secret is patched truthy so the handler doesn't
    503 before it gets there.
    """
    monkeypatch.setattr(webhooks_router.settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(webhooks_router, "parse_webhook", lambda body, sig: event)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.post(
            "/api/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "test-sig"},
        )


def _patch_sub_payload(monkeypatch, *, status: str, tier: str = "premium") -> dict:
    """Patch subscription_payload to a controlled dict so the test doesn't need
    to know the configured Stripe price→tier mapping."""
    payload = {
        "id": f"sub_{_uuid.uuid4().hex[:16]}",
        "status": status,
        "tier": tier,
        "current_period_end": datetime.now(UTC) + timedelta(days=20),
        "cancel_at_period_end": False,
    }
    monkeypatch.setattr(webhooks_router, "subscription_payload", lambda obj: payload)
    return payload


async def _seed_user(
    *, tier: str = "premium", drip_state: str = "", customer_id: str | None = None,
) -> tuple[str, str, str]:
    """Insert a fresh paid user with a Stripe customer id. Returns
    (user_id, email, customer_id)."""
    uid = f"dun_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    cust = customer_id or f"cus_{_uuid.uuid4().hex[:18]}"
    async with session_scope() as s:
        s.add(User(
            id=uid,
            email=email,
            name="DunTest",
            tier=tier,
            password_hash="not-used",
            stripe_customer_id=cust,
            drip_state=drip_state,
        ))
        await s.commit()
    return uid, email, cust


async def _user_row(uid: str) -> dict:
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        return {"tier": u.tier, "drip_state": u.drip_state or ""}


class _Capture:
    """A delivered send_email — records each call, returns no 'skipped' key so
    the handler stamps its dedup token."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, to, subject, html, persona=None, **_kw):
        self.calls.append({"to": to, "subject": subject, "html": html, "persona": persona})
        return {"id": "test-msg"}


# ════════════════════════════════════════════════════════════════════════════
# Subscription status → tier (the grace window)
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_subscription_past_due_keeps_paid_tier(monkeypatch):
    """A past_due sub (Stripe mid-retry) must KEEP the customer on their paid
    tier — yanking access mid-dunning kills recovery."""
    uid, _, cust = await _seed_user(tier="premium")
    _patch_sub_payload(monkeypatch, status="past_due", tier="premium")
    r = await _fire(monkeypatch, _evt("customer.subscription.updated", {"customer": cust}))
    assert r.status_code == 200
    assert (await _user_row(uid))["tier"] == "premium"


@pytest.mark.asyncio
async def test_subscription_unpaid_drops_to_free(monkeypatch):
    """A terminal `unpaid` sub (retries exhausted) drops the account to Free."""
    uid, _, cust = await _seed_user(tier="premium")
    _patch_sub_payload(monkeypatch, status="unpaid", tier="premium")
    r = await _fire(monkeypatch, _evt("customer.subscription.updated", {"customer": cust}))
    assert r.status_code == 200
    assert (await _user_row(uid))["tier"] == "free"


# ════════════════════════════════════════════════════════════════════════════
# invoice.payment_failed — escalating dunning emails
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_payment_failed_first_attempt_sends_and_stamps(monkeypatch):
    """First failed attempt → soft email, billing persona, dun1 stamped."""
    uid, email, cust = await _seed_user(tier="pro", drip_state="")
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    obj = {"customer": cust, "attempt_count": 1, "next_payment_attempt": _FUTURE_TS}
    r = await _fire(monkeypatch, _evt("invoice.payment_failed", obj))
    assert r.status_code == 200
    assert "dun1" in (await _user_row(uid))["drip_state"].split(",")
    assert len(cap.calls) == 1
    call = cap.calls[0]
    assert call["to"] == email
    assert call["persona"] == "billing"
    assert call["subject"] == "Your Tapeline payment didn't go through"
    assert "Stripe will retry automatically" in call["html"]


@pytest.mark.asyncio
async def test_payment_failed_escalates_across_attempts(monkeypatch):
    """Successive attempts stamp distinct tokens and escalate the copy."""
    uid, _, cust = await _seed_user(tier="pro")
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    await _fire(monkeypatch, _evt(
        "invoice.payment_failed",
        {"customer": cust, "attempt_count": 1, "next_payment_attempt": _FUTURE_TS},
    ))
    await _fire(monkeypatch, _evt(
        "invoice.payment_failed",
        {"customer": cust, "attempt_count": 2, "next_payment_attempt": _FUTURE_TS},
    ))
    tokens = (await _user_row(uid))["drip_state"].split(",")
    assert "dun1" in tokens and "dun2" in tokens
    assert len(cap.calls) == 2
    # 2nd-attempt copy is the escalated variant.
    assert "2nd attempt" in cap.calls[1]["html"]


@pytest.mark.asyncio
async def test_payment_failed_dedupes_same_attempt(monkeypatch):
    """A re-fired event for the same attempt (distinct event id) must NOT
    re-send — the dun{n} token guards against double-touching one attempt."""
    uid, _, cust = await _seed_user(tier="pro")
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    obj = {"customer": cust, "attempt_count": 2, "next_payment_attempt": _FUTURE_TS}
    await _fire(monkeypatch, _evt("invoice.payment_failed", obj))
    await _fire(monkeypatch, _evt("invoice.payment_failed", dict(obj)))
    assert len(cap.calls) == 1
    assert (await _user_row(uid))["drip_state"].split(",").count("dun2") == 1


@pytest.mark.asyncio
async def test_payment_failed_final_attempt_escalated_subject(monkeypatch):
    """next_payment_attempt=None → last-chance: escalated subject + copy."""
    uid, _, cust = await _seed_user(tier="premium")
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    obj = {"customer": cust, "attempt_count": 4, "next_payment_attempt": None}
    r = await _fire(monkeypatch, _evt("invoice.payment_failed", obj))
    assert r.status_code == 200
    assert len(cap.calls) == 1
    call = cap.calls[0]
    assert call["subject"] == "Action needed: your Tapeline access is about to lapse"
    assert "last automatic retry" in call["html"]
    assert "dun4" in (await _user_row(uid))["drip_state"].split(",")


@pytest.mark.asyncio
async def test_payment_failed_skipped_send_does_not_stamp(monkeypatch):
    """Without RESEND_API_KEY the real send_email returns skipped:True — the
    dun token must NOT be stamped, so a later genuine event can still try.
    No send_email patch here, mirroring CI's real behaviour."""
    uid, _, cust = await _seed_user(tier="pro")
    obj = {"customer": cust, "attempt_count": 1, "next_payment_attempt": _FUTURE_TS}
    r = await _fire(monkeypatch, _evt("invoice.payment_failed", obj))
    assert r.status_code == 200
    assert "dun1" not in (await _user_row(uid))["drip_state"].split(",")


# ════════════════════════════════════════════════════════════════════════════
# invoice.payment_succeeded — recovery / all-clear
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_payment_succeeded_recovery_clears_and_sends(monkeypatch):
    """A success while the user carries dun tokens = recovery: clear the
    tokens and send the all-clear."""
    uid, email, cust = await _seed_user(tier="premium", drip_state="dun1,dun2")
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    r = await _fire(monkeypatch, _evt("invoice.payment_succeeded", {"customer": cust}))
    assert r.status_code == 200
    assert (await _user_row(uid))["drip_state"] == ""
    assert len(cap.calls) == 1
    assert cap.calls[0]["to"] == email
    assert cap.calls[0]["subject"] == "Payment received — you're all set"
    assert cap.calls[0]["persona"] == "billing"


@pytest.mark.asyncio
async def test_payment_succeeded_recovery_preserves_other_tokens(monkeypatch):
    """Recovery wipes only dun* tokens — unrelated drip state survives."""
    uid, _, cust = await _seed_user(tier="premium", drip_state="re14,dun1,wk3")
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    await _fire(monkeypatch, _evt("invoice.payment_succeeded", {"customer": cust}))
    tokens = (await _user_row(uid))["drip_state"].split(",")
    assert "dun1" not in tokens
    assert "re14" in tokens and "wk3" in tokens


@pytest.mark.asyncio
async def test_payment_succeeded_routine_renewal_silent(monkeypatch):
    """A success with no dun tokens is an ordinary renewal — no email, no
    state change. Stripe's own receipt covers the charge."""
    uid, _, cust = await _seed_user(tier="premium", drip_state="re14")

    async def _guard(*_a, **_k):
        raise AssertionError("recovery email sent on a routine renewal")

    monkeypatch.setattr(email_module, "send_email", _guard)
    r = await _fire(monkeypatch, _evt("invoice.payment_succeeded", {"customer": cust}))
    assert r.status_code == 200
    assert (await _user_row(uid))["drip_state"] == "re14"


# ════════════════════════════════════════════════════════════════════════════
# /api/me billing.past_due
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_me_reports_past_due_billing():
    """A paid user with a past_due subscription surfaces billing.past_due on
    /api/me so the DunningBanner can render."""
    sub_id = f"sub_me_{_uuid.uuid4().hex[:12]}"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await c.get("/api/me", headers=_AUTH)  # ensure dev_user row exists
        async with session_scope() as s:
            u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one()
            u.tier = "premium"
            s.add(Subscription(
                id=sub_id,
                user_id="dev_user",
                status="past_due",
                tier="premium",
                current_period_end=datetime.now(UTC) + timedelta(days=30),
            ))
            await s.commit()
        try:
            body = (await c.get("/api/me", headers=_AUTH)).json()
            assert body["billing"]["past_due"] is True
            assert body["billing"]["status"] == "past_due"
        finally:
            async with session_scope() as s:
                await s.execute(delete(Subscription).where(Subscription.id == sub_id))
                await s.commit()


@pytest.mark.asyncio
async def test_me_healthy_billing_not_past_due():
    """No past_due subscription → billing.past_due is False."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await c.get("/api/me", headers=_AUTH)
        async with session_scope() as s:
            await s.execute(delete(Subscription).where(Subscription.user_id == "dev_user"))
            u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one_or_none()
            if u is not None:
                u.tier = "premium"
            await s.commit()
        body = (await c.get("/api/me", headers=_AUTH)).json()
        assert body["billing"]["past_due"] is False


# ════════════════════════════════════════════════════════════════════════════
# Renderers (pure)
# ════════════════════════════════════════════════════════════════════════════

def test_payment_failed_final_attempt_renderer():
    html = render_payment_failed_email("Alex", "premium", 4, final_attempt=True)
    assert "Alex," in html
    assert "last automatic retry" in html
    assert "drops to Free" in html
    assert "Premium" in html
    # The soft first-attempt line must NOT appear in the last-chance variant.
    assert "Stripe will retry automatically" not in html


def test_payment_recovered_renderer():
    html = render_payment_recovered_email("Sam", tier="premium")
    assert "Sam" in html
    assert "all set" in html
    assert "Premium" in html
    # CTA points at the app, not the billing page (nothing to fix anymore).
    assert 'href="https://tapeline.io/app"' in html
    # No unresolved template placeholders leaked (ignore the CSS in <style>).
    html_no_style = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    leaked = re.findall(r"\{[a-z_][a-z0-9_]*\}", html_no_style)
    assert not leaked, f"unresolved template placeholders: {leaked[:5]}"
