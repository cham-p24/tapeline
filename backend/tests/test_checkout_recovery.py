"""Checkout abandonment recovery (PR6).

Covers the three moving parts of the lever:

  1. run_checkout_abandonment_recovery — selects users whose
     checkout_started_at sits in the 1-24h window, dedups on the "abandon1"
     drip_state token, respects the RE_ENGAGEMENT opt-out (marketing-class
     nudge), and only stamps on a NON-skipped send (no RESEND key = no-op).
  2. checkout.session.completed webhook clears checkout_started_at (+ tier /
     period), so a customer who actually converted drops out of the
     recovery population and is never nudged.
  3. render_checkout_abandoned_email — copy carries the name, tier label,
     sticker price, and the /app/billing resume link with tier + period
     pre-selected; no leaked template placeholders.

Mirrors test_lifecycle_emails.py (orchestrator + renderer; per-user drip_state
assertions on the shared session-scoped DB, never aggregate counts) and
test_dunning.py (_fire drives the real webhook with parse_webhook monkeypatched
so the signature + body are irrelevant and CI needs no Stripe key).
"""
from __future__ import annotations

import re
import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

import app.services.email as email_module
from app.db import session_scope
from app.main import app
from app.models import User
from app.routers import webhooks as webhooks_router
from app.services.email import (
    render_checkout_abandoned_email,
    run_checkout_abandonment_recovery,
)
from app.services.email_prefs import DEFAULT_PREFS, EmailPref


async def _fake_send_ok(*_a, **_k):
    """A delivered send — no 'skipped' key, so the orchestrator stamps state."""
    return {"id": "test-msg"}


# ── Seed helpers ─────────────────────────────────────────────────────────────

async def _seed_user(
    *,
    started_ago: timedelta | None,
    tier: str = "free",
    checkout_tier: str = "pro",
    checkout_period: str = "monthly",
    re_engagement: bool = True,
    drip_state: str = "",
) -> tuple[str, str]:
    """Insert a user with checkout_started_at = now - started_ago (or None for
    'no in-flight checkout'). Returns (user_id, email)."""
    uid = f"ckr_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    prefs = DEFAULT_PREFS
    if not re_engagement:
        prefs &= ~int(EmailPref.RE_ENGAGEMENT)
    started = None if started_ago is None else datetime.now(UTC) - started_ago
    async with session_scope() as s:
        s.add(User(
            id=uid,
            email=email,
            name="CkrTest",
            tier=tier,
            password_hash="not-used",
            email_prefs=prefs,
            drip_state=drip_state,
            checkout_started_at=started,
            checkout_tier=checkout_tier,
            checkout_billing_period=checkout_period,
        ))
        await s.commit()
    return uid, email


async def _row(uid: str) -> dict:
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        return {
            "drip_state": u.drip_state or "",
            "checkout_started_at": u.checkout_started_at,
            "checkout_tier": u.checkout_tier,
            "stripe_customer_id": u.stripe_customer_id,
        }


def _evt(evt_type: str, obj: dict) -> dict:
    """A parsed-webhook stand-in with a unique id (dodges replay dedup)."""
    return {"id": f"evt_{_uuid.uuid4().hex}", "type": evt_type, "data": {"object": obj}}


async def _fire(monkeypatch, event: dict) -> httpx.Response:
    """POST a fake Stripe event through the real /api/webhooks/stripe handler."""
    monkeypatch.setattr(webhooks_router.settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(webhooks_router, "parse_webhook", lambda body, sig: event)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.post(
            "/api/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "test-sig"},
        )


# ════════════════════════════════════════════════════════════════════════════
# Orchestrator — selection window + dedup + opt-out + skipped-no-stamp
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_recovery_fires_for_abandoned_checkout(monkeypatch):
    """checkout_started_at 2h ago → squarely in the 1-24h window → abandon1."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(started_ago=timedelta(hours=2))
    async with session_scope() as s:
        await run_checkout_abandonment_recovery(s)
    assert "abandon1" in (await _row(uid))["drip_state"].split(",")


@pytest.mark.asyncio
async def test_recovery_skips_too_new(monkeypatch):
    """Started 30 min ago → below the 1h floor (could still be mid-checkout)."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(started_ago=timedelta(minutes=30))
    async with session_scope() as s:
        await run_checkout_abandonment_recovery(s)
    assert (await _row(uid))["drip_state"] == ""


@pytest.mark.asyncio
async def test_recovery_skips_too_old(monkeypatch):
    """Started 30h ago → past the 24h ceiling (stale; feels creepy)."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(started_ago=timedelta(hours=30))
    async with session_scope() as s:
        await run_checkout_abandonment_recovery(s)
    assert (await _row(uid))["drip_state"] == ""


@pytest.mark.asyncio
async def test_recovery_skips_when_never_started(monkeypatch):
    """checkout_started_at None (completed or never started) → not a target."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(started_ago=None)
    async with session_scope() as s:
        await run_checkout_abandonment_recovery(s)
    assert (await _row(uid))["drip_state"] == ""


@pytest.mark.asyncio
async def test_recovery_dedupes(monkeypatch):
    """Already stamped abandon1 → one email per attempt; the second pass must
    not re-send (assert on the captured send list, not a swallowed raise)."""
    uid, email = await _seed_user(
        started_ago=timedelta(hours=2), drip_state="abandon1",
    )
    sends: list[str] = []

    async def _track(to, *_a, **_k):
        sends.append(to)
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _track)
    async with session_scope() as s:
        await run_checkout_abandonment_recovery(s)
    assert email not in sends
    assert (await _row(uid))["drip_state"] == "abandon1"


@pytest.mark.asyncio
async def test_recovery_respects_re_engagement_optout(monkeypatch):
    """In-window, but RE_ENGAGEMENT bit cleared → no send. Delivered fake
    proves '' means 'gated', not 'skipped'."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(started_ago=timedelta(hours=2), re_engagement=False)
    async with session_scope() as s:
        await run_checkout_abandonment_recovery(s)
    assert (await _row(uid))["drip_state"] == ""


@pytest.mark.asyncio
async def test_recovery_preserves_other_drip_tokens(monkeypatch):
    """Stamping abandon1 must not clobber unrelated drip state."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(started_ago=timedelta(hours=2), drip_state="re14,day3")
    async with session_scope() as s:
        await run_checkout_abandonment_recovery(s)
    tokens = (await _row(uid))["drip_state"].split(",")
    assert "abandon1" in tokens
    assert "re14" in tokens and "day3" in tokens


@pytest.mark.asyncio
async def test_recovery_skipped_send_does_not_stamp():
    """Without RESEND_API_KEY the real send_email returns skipped:True — the
    abandon1 token must NOT be stamped, so a later run still retries. No
    send_email patch here, mirroring CI's real no-key behaviour."""
    uid, _ = await _seed_user(started_ago=timedelta(hours=2))
    async with session_scope() as s:
        await run_checkout_abandonment_recovery(s)
    assert (await _row(uid))["drip_state"] == ""


# ════════════════════════════════════════════════════════════════════════════
# Webhook — checkout.session.completed clears the in-flight markers
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_completed_checkout_clears_in_flight_markers(monkeypatch):
    """A converted customer drops out of the recovery population: the
    completed webhook nulls checkout_started_at / tier / period (and links the
    Stripe customer)."""
    uid, _ = await _seed_user(started_ago=timedelta(hours=2))
    cust = f"cus_{_uuid.uuid4().hex[:18]}"
    r = await _fire(monkeypatch, _evt(
        "checkout.session.completed",
        {"client_reference_id": uid, "customer": cust},
    ))
    assert r.status_code == 200
    row = await _row(uid)
    assert row["checkout_started_at"] is None
    assert row["checkout_tier"] is None
    assert row["stripe_customer_id"] == cust


@pytest.mark.asyncio
async def test_completed_then_recovery_is_noop(monkeypatch):
    """End-to-end: a checkout that completes is never nudged on the next
    worker pass (checkout_started_at was cleared)."""
    uid, email = await _seed_user(started_ago=timedelta(hours=2))
    cust = f"cus_{_uuid.uuid4().hex[:18]}"
    await _fire(monkeypatch, _evt(
        "checkout.session.completed",
        {"client_reference_id": uid, "customer": cust},
    ))

    sends: list[str] = []

    async def _track(to, *_a, **_k):
        sends.append(to)
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _track)
    async with session_scope() as s:
        await run_checkout_abandonment_recovery(s)
    assert email not in sends
    assert (await _row(uid))["drip_state"] == ""


# ════════════════════════════════════════════════════════════════════════════
# Renderer (pure)
# ════════════════════════════════════════════════════════════════════════════

def test_checkout_abandoned_renderer_pro_monthly():
    html = render_checkout_abandoned_email("Alex", tier="pro", billing_period="monthly")
    assert "Alex" in html
    assert "Pro" in html
    assert "$29.99/mo" in html
    # Resume link lands on /app/billing with the plan pre-selected.
    assert "/app/billing?resume=1" in html
    assert "tier=pro" in html
    assert "billing_period=monthly" in html
    # Conversion nudge, not market advice — no prescriptive directives in the
    # body. The shared shell footer carries a "...not a recommendation. Trade
    # your own thesis." disclaimer, so scan for prescriptive *verbs*, not the
    # bare "recommend" substring (which the disclaimer noun legitimately holds).
    low = html.lower()
    assert "we recommend" not in low
    assert "you should" not in low
    assert "buy now" not in low
    # No unresolved template placeholders leaked (ignore the CSS in <style>).
    html_no_style = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    leaked = re.findall(r"\{[a-z_][a-z0-9_]*\}", html_no_style)
    assert not leaked, f"unresolved template placeholders: {leaked[:5]}"


def test_checkout_abandoned_renderer_premium_annual():
    html = render_checkout_abandoned_email("Sam", tier="premium", billing_period="annual")
    assert "Sam" in html
    assert "Premium" in html
    assert "$479.99/yr" in html
    assert "tier=premium" in html
    assert "billing_period=annual" in html


def test_checkout_abandoned_renderer_unknown_period_falls_back():
    """An unexpected period string must not render blank or crash — it falls
    back to monthly in the link + price."""
    html = render_checkout_abandoned_email("Alex", tier="pro", billing_period="weekly")
    assert "Alex" in html
    assert "billing_period=monthly" in html
    assert "$29.99/mo" in html
