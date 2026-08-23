"""A carded trialist is NOT a paying customer.

THE BUG THIS PINS
-----------------
Before the #548 card gate, `stripe_customer_id IS NOT NULL` was a fair proxy
for "this person pays us" — you only got a Stripe customer by checking out.
The card gate inverted that: every card-required trial creates a Stripe
customer on day 0, while charging $0.

Both the growth funnel and the revenue dashboard still used that column, so:

  * `paying` / `paid_customers` counted trialists as payers, and
  * `trial_to_paid_pct = paying / trials_started` read ~100% — for a product
    with zero payers, ever.

`PAID_ADS_METRICS_BIBLE.md` §2.4 calls trial→paid "THE gate metric" and the
whole paid-ads decision rests on it. A dashboard reporting the broken step as
solved is worse than one reporting nothing: it would license spend that the
real number forbids.

The same query also made `trials_active` structurally zero, because it
required `stripe_customer_id IS NULL` — true of no card-required trial.

These tests fail loudly if any of that comes back.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import Subscription, User
from app.services.growth_funnel import summarize_growth_funnel


def _email() -> str:
    return f"funnel-{secrets.token_hex(6)}@example.com"


async def _mk_user(session, *, email: str, trial: bool, stripe: bool) -> User:
    now = datetime.now(UTC)
    u = User(
        id=f"u_{secrets.token_hex(8)}",
        email=email,
        password_hash="x",
        tier="premium" if trial else "free",
        created_at=now - timedelta(days=1),
        # A card-required trial: trial stamps AND a Stripe customer, $0 paid.
        trial_started_at=now - timedelta(days=1) if trial else None,
        trial_ends_at=now + timedelta(days=13) if trial else None,
        stripe_customer_id=f"cus_{secrets.token_hex(6)}" if stripe else None,
    )
    session.add(u)
    await session.flush()
    return u


@pytest.mark.asyncio
async def test_carded_trialist_is_not_counted_as_paying():
    """The exact #548 fact pattern: trial stamps + a Stripe customer + $0 paid."""
    email = _email()
    async with session_scope() as s:
        await _mk_user(s, email=email, trial=True, stripe=True)
        await s.commit()

    async with session_scope() as s2:
        out = await summarize_growth_funnel(s2, days=30)
    assert out["available"] is True

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        # The trial IS counted as started...
        assert out["trials_started"] >= 1
        # ...and as currently active. The old query required
        # stripe_customer_id IS NULL, making this structurally 0 post-#548.
        assert out["trials_active"] >= 1, (
            "a card-required trial in its window must count as an ACTIVE trial; "
            "requiring stripe_customer_id IS NULL makes this permanently zero"
        )
        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_paying_requires_an_active_subscription_not_a_stripe_customer():
    """Only an active Subscription row makes someone a payer."""
    trialist, payer = _email(), _email()
    async with session_scope() as s:
        await _mk_user(s, email=trialist, trial=True, stripe=True)
        p = await _mk_user(s, email=payer, trial=True, stripe=True)
        s.add(Subscription(id=f"sub_{secrets.token_hex(6)}", user_id=p.id, status="active", tier="premium", current_period_end=datetime.now(UTC) + timedelta(days=30)))
        await s.commit()

    async with session_scope() as s2:
        out = await summarize_growth_funnel(s2, days=30)

    # Exactly one of the two is paying, though BOTH have a stripe_customer_id.
    assert out["paying"] >= 1
    assert out["trials_started"] >= 2
    assert out["paying"] < out["trials_started"], (
        "paying must not equal trials_started — that is the ~100% "
        "trial_to_paid_pct artefact this test exists to prevent"
    )
    assert out["trial_to_paid_pct"] < 100.0

    async with session_scope() as s:
        for e in (trialist, payer):
            u = (await s.execute(select(User).where(User.email == e))).scalar_one()
            await s.execute(delete(Subscription).where(Subscription.user_id == u.id))
            await s.delete(u)
        await s.commit()


@pytest.mark.asyncio
async def test_trialing_and_canceled_subscriptions_do_not_count_as_paying():
    """`status == "active"` only — trialing/canceled are not revenue."""
    emails = [_email(), _email()]
    async with session_scope() as s:
        for e, status in zip(emails, ("trialing", "canceled"), strict=True):
            u = await _mk_user(s, email=e, trial=True, stripe=True)
            s.add(Subscription(id=f"sub_{secrets.token_hex(6)}", user_id=u.id, status=status, tier="premium", current_period_end=datetime.now(UTC) + timedelta(days=30)))
        await s.commit()

    async with session_scope() as s2:
        out = await summarize_growth_funnel(s2, days=30)
    assert out["paying"] == 0, (
        "a `trialing` or `canceled` subscription is not a paying customer"
    )

    async with session_scope() as s:
        for e in emails:
            u = (await s.execute(select(User).where(User.email == e))).scalar_one()
            await s.execute(delete(Subscription).where(Subscription.user_id == u.id))
            await s.delete(u)
        await s.commit()
