"""Founder revenue dashboard (PR7).

Covers the three moving parts of the lever:

  1. mrr_contribution — the pure price-map function. Exact per tier x period,
     marketed rates (annual uses the advertised $8.25/$16.58 monthly-equiv,
     not lump/12); unknown tier -> 0; null/unknown period -> monthly.
  2. GET /api/admin/revenue — admin-gated aggregate endpoint. Exact MRR/ARR off
     ACTIVE subs only, the subscription book sliced by tier/period/status, churn
     + cancellation reasons, retention saves, dunning load, in-flight checkouts,
     the referral ledger, lifecycle-drip reach, and webhook volume.
  3. Subscription.billing_period — the new column that makes the MRR exact.

The conftest DB is session-scoped with NO per-test rollback, so the SQLite file
ACCUMULATES rows across the whole suite — aggregate counts are therefore non-
deterministic. Every endpoint assertion here is a DELTA (read baseline, seed a
known amount, read again, assert the difference), which is robust to whatever
other tests have already left in the DB.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.db import session_scope
from app.main import app
from app.models import StripeWebhookEvent, Subscription, User
from app.services.tier import mrr_contribution


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ── Admin auth + seed helpers ────────────────────────────────────────────────

async def _make_admin_cookies(client: httpx.AsyncClient, monkeypatch) -> dict:
    """Sign up a fresh user, then flip is_admin=True so admin endpoints accept
    them. Mirrors test_email_preview._make_admin_cookies."""
    from sqlalchemy import select

    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"admin-{_uuid.uuid4().hex[:8]}@example.com"
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


async def _seed_user(**kw) -> str:
    """Insert a minimal user; kwargs override defaults. Returns the user id."""
    uid = f"rev_{_uuid.uuid4().hex}"
    fields = {
        "id": uid,
        "email": f"{uid}@example.com",
        "name": "RevTest",
        "tier": "free",
        "password_hash": "not-used",
    }
    fields.update(kw)
    async with session_scope() as s:
        s.add(User(**fields))
        await s.commit()
    return uid


async def _seed_sub(
    user_id: str,
    *,
    tier: str,
    billing_period: str | None,
    status: str = "active",
    cancel_at_period_end: bool = False,
) -> None:
    async with session_scope() as s:
        s.add(Subscription(
            id=f"sub_{_uuid.uuid4().hex[:20]}",
            user_id=user_id,
            status=status,
            tier=tier,
            current_period_end=datetime.now(UTC) + timedelta(days=30),
            cancel_at_period_end=cancel_at_period_end,
            billing_period=billing_period,
        ))
        await s.commit()


async def _revenue(client: httpx.AsyncClient, cookies: dict) -> dict:
    r = await client.get("/api/admin/revenue", cookies=cookies)
    assert r.status_code == 200, r.text
    return r.json()


def _d(after: dict, before: dict, key: str) -> int:
    """Delta of a key across two snapshot dicts (missing => 0)."""
    return after.get(key, 0) - before.get(key, 0)


# ════════════════════════════════════════════════════════════════════════════
# Pure price map — mrr_contribution
# ════════════════════════════════════════════════════════════════════════════

def test_mrr_contribution_matches_marketed_rates():
    assert mrr_contribution("pro", "monthly") == 9.99
    assert mrr_contribution("pro", "annual") == 8.25
    assert mrr_contribution("premium", "monthly") == 19.99
    assert mrr_contribution("premium", "annual") == 16.58


def test_mrr_contribution_null_or_unknown_period_falls_back_to_monthly():
    assert mrr_contribution("pro", None) == 9.99
    assert mrr_contribution("premium", "weekly") == 19.99


def test_mrr_contribution_unknown_tier_is_zero():
    assert mrr_contribution("free", "monthly") == 0.0
    assert mrr_contribution(None, "monthly") == 0.0
    assert mrr_contribution("enterprise", "annual") == 0.0


# ════════════════════════════════════════════════════════════════════════════
# Endpoint — auth gate
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_revenue_requires_admin(client):
    """Anonymous -> 401 (admin endpoints return 401, not 403)."""
    async with client:
        r = await client.get("/api/admin/revenue")
        assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════════════
# Endpoint — exact MRR/ARR + subscription book
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_revenue_mrr_is_exact_per_tier_and_period(client, monkeypatch):
    """One active sub of each tier x period contributes its marketed monthly
    rate; trialing / canceled subs contribute $0. ARR = MRR x 12."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        before = await _revenue(client, cookies)

        users = [await _seed_user() for _ in range(6)]
        await _seed_sub(users[0], tier="pro", billing_period="monthly")
        await _seed_sub(users[1], tier="pro", billing_period="annual")
        await _seed_sub(users[2], tier="premium", billing_period="monthly")
        await _seed_sub(users[3], tier="premium", billing_period="annual")
        # Non-active => excluded from MRR and from the tier/period breakdowns.
        await _seed_sub(users[4], tier="premium", billing_period="monthly", status="trialing")
        await _seed_sub(users[5], tier="pro", billing_period="monthly", status="canceled")

        after = await _revenue(client, cookies)

        expected_mrr = 9.99 + 8.25 + 19.99 + 16.58  # 54.81
        assert after["mrr_usd"] - before["mrr_usd"] == pytest.approx(expected_mrr, abs=0.01)
        assert after["arr_usd"] - before["arr_usd"] == pytest.approx(expected_mrr * 12, abs=0.01)
        assert after["active_subscriptions"] - before["active_subscriptions"] == 4

        assert _d(after["subs_by_tier"], before["subs_by_tier"], "pro") == 2
        assert _d(after["subs_by_tier"], before["subs_by_tier"], "premium") == 2
        assert _d(after["subs_by_period"], before["subs_by_period"], "monthly") == 2
        assert _d(after["subs_by_period"], before["subs_by_period"], "annual") == 2
        # status breakdown covers the WHOLE book (incl. non-active)
        assert _d(after["subs_by_status"], before["subs_by_status"], "active") == 4
        assert _d(after["subs_by_status"], before["subs_by_status"], "trialing") == 1
        assert _d(after["subs_by_status"], before["subs_by_status"], "canceled") == 1


@pytest.mark.asyncio
async def test_revenue_null_billing_period_counts_as_monthly(client, monkeypatch):
    """A legacy sub synced before migration 0031 (billing_period NULL) must
    still contribute — at the monthly rate, not $0."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        before = await _revenue(client, cookies)

        uid = await _seed_user()
        await _seed_sub(uid, tier="pro", billing_period=None)

        after = await _revenue(client, cookies)
        assert after["mrr_usd"] - before["mrr_usd"] == pytest.approx(9.99, abs=0.01)
        assert _d(after["subs_by_period"], before["subs_by_period"], "monthly") == 1


# ════════════════════════════════════════════════════════════════════════════
# Endpoint — churn / retention / referral / dunning / checkout
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_revenue_churn_retention_referral_counts(client, monkeypatch):
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        before = await _revenue(client, cookies)

        now = datetime.now(UTC)
        u_cancel = await _seed_user(cancellation_reason="too_expensive")
        await _seed_sub(u_cancel, tier="pro", billing_period="monthly", cancel_at_period_end=True)
        await _seed_user(save_offer_redeemed_at=now)
        await _seed_user(subscription_paused_until=now + timedelta(days=20))
        await _seed_user(referred_by="someone-else", referral_credit_months=2)
        await _seed_user(checkout_started_at=now - timedelta(hours=2))
        await _seed_user(drip_state="dun2")

        after = await _revenue(client, cookies)
        assert after["cancellations_scheduled"] - before["cancellations_scheduled"] == 1
        assert _d(after["cancellation_reasons"], before["cancellation_reasons"], "too_expensive") == 1
        assert after["save_offers_redeemed"] - before["save_offers_redeemed"] == 1
        assert after["subscriptions_paused"] - before["subscriptions_paused"] == 1
        assert after["referred_users"] - before["referred_users"] == 1
        assert after["referral_credits_outstanding"] - before["referral_credits_outstanding"] == 2
        assert after["checkouts_in_flight"] - before["checkouts_in_flight"] == 1
        assert after["in_dunning"] - before["in_dunning"] == 1


# ════════════════════════════════════════════════════════════════════════════
# Endpoint — lifecycle-drip reach + webhook volume
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_revenue_drip_reach_counts_lever_tokens(client, monkeypatch):
    """Each automated email lever's token presence is counted once per user,
    across both drip_state and winback_state."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        before = await _revenue(client, cookies)

        await _seed_user(drip_state="abandon1,re14,annual_p")
        await _seed_user(drip_state="ref_m3,ref_m5")
        await _seed_user(winback_state="wb30,wb60")

        after = await _revenue(client, cookies)
        b, a = before["drip_reach"], after["drip_reach"]
        assert _d(a, b, "abandon1") == 1
        assert _d(a, b, "re14") == 1
        assert _d(a, b, "annual_p") == 1
        assert _d(a, b, "ref_m3") == 1
        assert _d(a, b, "ref_m5") == 1
        assert _d(a, b, "wb30") == 1
        assert _d(a, b, "wb60") == 1
        # tokens we didn't seed must not move
        assert _d(a, b, "ref_m25") == 0
        assert _d(a, b, "wb90") == 0


@pytest.mark.asyncio
async def test_revenue_webhook_volume_by_type(client, monkeypatch):
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        before = await _revenue(client, cookies)

        async with session_scope() as s:
            s.add(StripeWebhookEvent(
                id=f"evt_{_uuid.uuid4().hex}",
                event_type="invoice.payment_succeeded",
            ))
            await s.commit()

        after = await _revenue(client, cookies)
        assert _d(after["webhook_events"], before["webhook_events"], "invoice.payment_succeeded") == 1
