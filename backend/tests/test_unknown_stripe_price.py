"""An unrecognised Stripe price must never downgrade a paying subscriber.

`_tier_from_price` mapped ANY price id that is not one of the four configured
STRIPE_PRICE_* env values to "free", and the webhook wrote that straight onto
the user whenever the subscription was active/trialing. There was no
"unknown price" branch: the fallback silently meant FREE rather than
"leave the tier alone".

Two reachable triggers, both live:

  * Price rotation. Founding pricing is advertised as "locked in for early
    subscribers" and the STRIPE_PRICE_* env vars were already swapped once at
    the 2026-07 reprice. A subscriber who bought before a swap still carries
    the OLD price id on their Stripe subscription, so every renewal fires
    customer.subscription.updated with status="active" and that old price.
    They keep being charged $19.99/mo while locked out of every Premium
    surface.
  * Hand-sold anchor tiers. Team ($149/mo), Enterprise (from $2k/mo) and
    Trader ($59/mo) are created in the Stripe dashboard against price ids that
    are not in the four env vars. The first `.updated` event overwrites the
    admin's manual tier grant with "free".

It is also invisible: `_MRR_CONTRIBUTION` has no ("free", …) key, so the admin
revenue dashboard books them at $0 MRR.

`tier_from_price` now returns None for an unrecognised price, and the webhook
skips every tier write while logging `stripe.unknown_price` loudly.
"""
from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import StripeWebhookEvent, Subscription, User
from app.routers import webhooks as webhooks_router
from app.services.billing import _tier_from_price, tier_from_price


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _post(monkeypatch, event: dict) -> httpx.Response:
    monkeypatch.setattr(webhooks_router, "parse_webhook", lambda body, sig: event)
    monkeypatch.setattr(webhooks_router.settings, "stripe_webhook_secret", "whsec_test")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.post(
            "/api/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "sig"},
        )


def _sub_event(customer_id: str, event_id: str, price_id: str, status: str = "active") -> dict:
    return {
        "id": event_id,
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": f"sub_{uuid.uuid4().hex[:12]}",
                "customer": customer_id,
                "status": status,
                "current_period_end": 1788652800,
                "cancel_at_period_end": False,
                "items": {
                    "data": [
                        {
                            "price": {
                                "id": price_id,
                                "unit_amount": 1999,
                                "currency": "usd",
                                "recurring": {"interval": "month"},
                            }
                        }
                    ]
                },
            }
        },
    }


@pytest.fixture
async def premium_user():
    cid = f"cus_{uuid.uuid4().hex[:12]}"
    uid = str(uuid.uuid4())
    async with session_scope() as s:
        s.add(
            User(
                id=uid,
                email=f"px-{uuid.uuid4().hex[:8]}@example.com",
                tier="premium",
                stripe_customer_id=cid,
            )
        )
        await s.commit()
    yield uid, cid
    async with session_scope() as s:
        await s.execute(delete(Subscription).where(Subscription.user_id == uid))
        await s.execute(delete(User).where(User.id == uid))
        await s.commit()


def test_tier_from_price_returns_none_not_free_for_an_unknown_price():
    """None means 'we don't know'. 'free' means 'downgrade them'."""
    assert tier_from_price("price_rotated_out_2026_06") is None
    assert tier_from_price("price_team_149_handsold") is None
    assert tier_from_price("") is None


def test_lossy_helper_is_still_available_for_pricing_display():
    """The display-only path keeps its concrete fallback."""
    assert _tier_from_price("price_unknown_whatever") == "free"


@pytest.mark.parametrize("status", ["active", "trialing", "past_due"])
@pytest.mark.asyncio
async def test_unknown_price_does_not_downgrade_a_paying_subscriber(
    monkeypatch, premium_user, status
):
    """THE regression, across every branch that writes user.tier."""
    uid, cid = premium_user
    eid = f"evt_{uuid.uuid4().hex[:12]}"
    try:
        r = await _post(monkeypatch, _sub_event(cid, eid, "price_rotated_out", status))
        assert r.status_code == 200, r.text
        async with session_scope() as s:
            user = await s.get(User, uid)
            assert user.tier == "premium", (
                f"status={status}: an unrecognised price downgraded a paying "
                f"subscriber to {user.tier!r} — they keep being charged while "
                f"locked out of every paid surface"
            )
    finally:
        async with session_scope() as s:
            await s.execute(
                delete(StripeWebhookEvent).where(StripeWebhookEvent.id == eid)
            )
            await s.commit()


@pytest.mark.asyncio
async def test_a_known_price_still_sets_the_tier(monkeypatch, premium_user):
    """The guard must not freeze legitimate tier changes."""
    uid, cid = premium_user
    monkeypatch.setattr(
        webhooks_router.settings, "stripe_price_pro_monthly", "price_pro_m", raising=False
    )
    import app.services.billing as billing_mod

    monkeypatch.setattr(
        billing_mod.settings, "stripe_price_pro_monthly", "price_pro_m", raising=False
    )
    eid = f"evt_{uuid.uuid4().hex[:12]}"
    try:
        r = await _post(monkeypatch, _sub_event(cid, eid, "price_pro_m", "active"))
        assert r.status_code == 200, r.text
        async with session_scope() as s:
            user = await s.get(User, uid)
            assert user.tier == "pro", (
                "a RECOGNISED price failed to move the tier — the unknown-price "
                "guard is too broad"
            )
    finally:
        async with session_scope() as s:
            await s.execute(
                delete(StripeWebhookEvent).where(StripeWebhookEvent.id == eid)
            )
            await s.commit()


@pytest.mark.asyncio
async def test_unknown_price_stores_the_accounts_real_tier_on_the_subscription_row(
    monkeypatch, premium_user
):
    """Subscription.tier is NOT NULL, so a new row can't store None. It must
    record what the account actually holds — not 'free', which would book a
    hand-sold plan at $0 MRR in the admin dashboard."""
    uid, cid = premium_user
    eid = f"evt_{uuid.uuid4().hex[:12]}"
    try:
        r = await _post(monkeypatch, _sub_event(cid, eid, "price_team_handsold", "active"))
        assert r.status_code == 200, r.text
        async with session_scope() as s:
            rows = (
                await s.execute(select_sub(uid))
            ).scalars().all()
        assert rows, "no subscription row written"
        assert rows[0].tier == "premium", (
            f"subscription row booked at {rows[0].tier!r} — a hand-sold plan "
            f"recorded as free shows $0 MRR and hides the revenue"
        )
    finally:
        async with session_scope() as s:
            await s.execute(
                delete(StripeWebhookEvent).where(StripeWebhookEvent.id == eid)
            )
            await s.commit()


def select_sub(uid: str):
    from sqlalchemy import select

    return select(Subscription).where(Subscription.user_id == uid)
