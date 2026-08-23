"""Trial-expiry save offer — the cancel-intercept 50%-off-3-months offer,
extended to expired card-less trialists (founder decision 2026-08-06).

Three legs, each pinned here:
  1. Eligibility (services/billing.trial_save_offer_eligible) — one shared
     server-side gate used by POST /checkout, GET /email-checkout, /api/me and
     the T+0 email, so every surface agrees and none can promise a discount
     checkout won't apply.
  2. The T+0 expired email states the offer ONLY when the caller verified
     eligibility — and states it as a standing fact (no countdown: rule 6).
  3. The subscription webhook marks save_offer_redeemed_at from the
     trial_save_offer metadata flag — at COMPLETION, not session-create, so an
     abandoned checkout can't burn the once-per-account offer.

Webhook harness mirrors test_dunning.py (parse_webhook patched, unique event
ids to dodge replay dedup, per-seeded-user assertions only).
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.routers import webhooks as webhooks_router
from app.services.billing import trial_save_offer_eligible
from app.services.email import render_trial_expired_email

_OFFER_PHRASE = "50% off your first 3 months"


# ── helpers ──────────────────────────────────────────────────────────────────

def _user(**over) -> SimpleNamespace:
    """A minimal user-shaped object for the pure eligibility gate."""
    base: dict = {
        "trial_ends_at": datetime.now(UTC) - timedelta(days=1),
        "stripe_customer_id": None,
        "canceled_at": None,
        "save_offer_redeemed_at": None,
    }
    base.update(over)
    return SimpleNamespace(**base)


def _evt(evt_type: str, obj: dict) -> dict:
    return {"id": f"evt_{_uuid.uuid4().hex}", "type": evt_type, "data": {"object": obj}}


async def _fire(monkeypatch, event: dict) -> httpx.Response:
    monkeypatch.setattr(webhooks_router.settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(webhooks_router, "parse_webhook", lambda body, sig: event)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.post(
            "/api/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "test-sig"},
        )


def _patch_sub_payload(monkeypatch, *, status: str = "active", tier: str = "premium") -> dict:
    payload = {
        "id": f"sub_{_uuid.uuid4().hex[:16]}",
        "status": status,
        "tier": tier,
        "current_period_end": datetime.now(UTC) + timedelta(days=30),
        "cancel_at_period_end": False,
    }
    monkeypatch.setattr(webhooks_router, "subscription_payload", lambda obj: payload)
    return payload


async def _seed_expired_trialist() -> tuple[str, str]:
    """A card-less user whose trial ended yesterday — the offer's cohort."""
    uid = f"tso_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=uid,
            email=email,
            name="SaveOfferTest",
            tier="free",
            password_hash="not-used",
            trial_ends_at=datetime.now(UTC) - timedelta(days=1),
        ))
        await s.commit()
    return uid, email


async def _row(uid: str) -> User:
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


# ── 1. Eligibility gate ──────────────────────────────────────────────────────

def test_expired_cardless_trialist_is_eligible():
    assert trial_save_offer_eligible(_user()) is True


def test_active_trial_is_not_eligible():
    # Still mid-trial — the offer is for AFTER expiry only.
    u = _user(trial_ends_at=datetime.now(UTC) + timedelta(days=3))
    assert trial_save_offer_eligible(u) is False


def test_no_trial_ever_is_not_eligible():
    assert trial_save_offer_eligible(_user(trial_ends_at=None)) is False


def test_stripe_customer_is_not_eligible():
    # Ever-subscribed users are the win-back's cohort, not this offer's.
    assert trial_save_offer_eligible(_user(stripe_customer_id="cus_x")) is False


def test_cancelled_user_is_not_eligible():
    # Churned paid users get the 40% win-back, never both offers.
    u = _user(canceled_at=datetime.now(UTC) - timedelta(days=10))
    assert trial_save_offer_eligible(u) is False


def test_already_redeemed_is_not_eligible():
    # Shares save_offer_redeemed_at with the cancel-intercept offer —
    # one redemption per account across BOTH mechanisms.
    u = _user(save_offer_redeemed_at=datetime.now(UTC) - timedelta(days=5))
    assert trial_save_offer_eligible(u) is False


# ── 2. T+0 email states the offer only when eligible ─────────────────────────

def test_expired_email_states_offer_when_eligible():
    html = render_trial_expired_email("Alex", None, save_offer=True)
    assert _OFFER_PHRASE in html
    assert "applied automatically at checkout" in html
    # Standing fact, not deadline theatre (rule 6).
    assert "expire" in html  # "It doesn't expire — it's simply once per account."


def test_expired_email_silent_without_eligibility():
    html = render_trial_expired_email("Alex", None)
    assert _OFFER_PHRASE not in html


# ── 3. Webhook marks redemption from the metadata flag ───────────────────────

@pytest.mark.asyncio
async def test_webhook_marks_save_offer_redeemed(monkeypatch):
    uid, _ = await _seed_expired_trialist()
    _patch_sub_payload(monkeypatch, status="active", tier="premium")
    # No stripe_customer_id on the user yet — resolved via the metadata
    # fallback, exactly like a first-time subscriber's out-of-order events.
    r = await _fire(monkeypatch, _evt(
        "customer.subscription.created",
        {
            "customer": f"cus_{_uuid.uuid4().hex[:18]}",
            "metadata": {"user_id": uid, "trial_save_offer": "1"},
        },
    ))
    assert r.status_code == 200
    row = await _row(uid)
    assert row.save_offer_redeemed_at is not None
    assert row.tier == "premium"


@pytest.mark.asyncio
async def test_webhook_without_flag_leaves_redemption_unset(monkeypatch):
    uid, _ = await _seed_expired_trialist()
    _patch_sub_payload(monkeypatch, status="active", tier="pro")
    r = await _fire(monkeypatch, _evt(
        "customer.subscription.created",
        {
            "customer": f"cus_{_uuid.uuid4().hex[:18]}",
            "metadata": {"user_id": uid},
        },
    ))
    assert r.status_code == 200
    row = await _row(uid)
    assert row.save_offer_redeemed_at is None
