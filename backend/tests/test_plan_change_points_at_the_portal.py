"""An existing subscriber is sent to the portal, not to a human.

The double-billing guard itself is correct and stays: Stripe Checkout always
mints a NEW customer and a NEW subscription, so letting an active subscriber
through it charges them twice and the webhook can only page the founder to
refund after the money has moved.

What was wrong was the message. It said "contact support to switch plans" — on
a product with a fully wired self-serve billing portal (POST /api/billing/portal,
with buttons already on /app/billing). That sent a paying customer down a slower
path that already existed, and read as "we can't do this" rather than "here is
where you do it".

Whether the portal exposes plan SWITCHING specifically is a Stripe dashboard
setting rather than anything in this repo, which is why the copy names the
portal generally: cancellation and payment-method updates live there regardless.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import User
from app.routers.billing import CheckoutRequest, create_checkout


async def _user(tier: str, customer: str | None) -> User:
    uid = f"u_{uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.test", name="Plan probe",
            tier=tier, password_hash="x", drip_state="",
            stripe_customer_id=customer,
        ))
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


async def _cleanup(user: User) -> None:
    async with session_scope() as s:
        await s.execute(delete(User).where(User.id == user.id))


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["pro", "premium"])
async def test_an_active_subscriber_is_pointed_at_the_portal(tier):
    user = await _user(tier, f"cus_{uuid.uuid4().hex[:18]}")
    try:
        async with session_scope() as s:
            with pytest.raises(HTTPException) as exc:
                await create_checkout(
                    CheckoutRequest(tier="premium", billing_period="monthly"),
                    user=user, session=s,
                )
        detail = str(exc.value.detail)

        # The guard still fires — this is the double-billing protection.
        assert exc.value.status_code == 409

        # ...but it routes to the self-serve path that exists.
        assert "portal" in detail.lower(), (
            f"an active subscriber was told {detail!r}; the billing portal is "
            f"wired end to end and is where they should be sent"
        )
        assert "contact support" not in detail.lower(), (
            "still directing paying customers to a human for something they "
            "can do themselves"
        )
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_the_guard_still_lets_churned_and_trial_users_through():
    """The message changed; the guard's shape must not have.

    A churned user KEEPS their stripe_customer_id (tier drops to "free"), and
    the win-back flow depends on them being able to check out again. A trial
    user has no customer id at all. Neither may be caught by a guard keyed on
    the customer id alone.
    """
    churned = await _user("free", f"cus_{uuid.uuid4().hex[:18]}")
    trialling = await _user("premium", None)
    try:
        for user in (churned, trialling):
            async with session_scope() as s:
                try:
                    await create_checkout(
                        CheckoutRequest(tier="pro", billing_period="monthly"),
                        user=user, session=s,
                    )
                except HTTPException as e:
                    assert e.status_code != 409, (
                        f"{user.tier} user with customer_id="
                        f"{user.stripe_customer_id!r} was blocked as an active "
                        f"subscriber; the double-billing guard has widened"
                    )
                except Exception:
                    # Reaching Stripe (or failing to) means the guard passed,
                    # which is all this test is about.
                    pass
    finally:
        await _cleanup(churned)
        await _cleanup(trialling)
