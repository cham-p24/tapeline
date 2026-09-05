"""Choosing the trial must mean handing over a card. And the trial is 30 days.

The product has exactly two front doors: sign up free with no card at all, or
take the Premium trial, which requires one. The whole design rests on the
second door actually asking. If it ever stopped asking, the trial would become
an unlimited free Premium plan and nobody would notice for months — the same
shape as the signup outage, where the failure was invisible because the thing
that broke was a thing nobody was watching.

Stripe collects the card because `mode="subscription"` defaults
`payment_method_collection` to `"always"`. That default is doing load-bearing
work, silently. Setting it to `"if_required"` — one plausible line, easy to add
while chasing a conversion win — makes Checkout skip the card entirely on a
trial, because nothing is owed today. The session still succeeds. The trial
still starts. Nothing errors anywhere. The customer simply never pays.

So it is pinned here rather than left to a vendor default nobody re-reads.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.routers.billing import MIN_TRIAL_DAYS, TRIAL_DAYS


def _install_stripe_fakes(monkeypatch, billing, captured: dict):
    for attr, value in [
        ("stripe_price_pro_monthly", "price_pro_monthly"),
        ("stripe_price_pro_annual", "price_pro_annual"),
        ("stripe_price_premium_monthly", "price_premium_monthly"),
        ("stripe_price_premium_annual", "price_premium_annual"),
    ]:
        monkeypatch.setattr(billing.settings, attr, value, raising=False)

    def _fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_test_123")

    monkeypatch.setattr(billing.stripe.checkout.Session, "create", _fake_session_create)
    monkeypatch.setattr(
        billing.stripe.Price, "retrieve",
        lambda price_id, **_: SimpleNamespace(unit_amount=1999, currency="usd"),
    )
    monkeypatch.setattr(
        billing.stripe.Coupon, "create",
        lambda **kw: SimpleNamespace(id="coupon_test_123"),
    )


async def _trial_session(monkeypatch, **overrides) -> dict:
    """Build the Checkout Session a trial start actually sends to Stripe."""
    from app.services import billing

    captured: dict = {}
    _install_stripe_fakes(monkeypatch, billing, captured)

    kwargs = {
        "user_id": "u_test",
        "user_email": "trialist@example.com",
        "tier": "premium",
        "billing_period": "monthly",
        "success_url": "https://tapeline.io/app/billing?ok=1",
        "cancel_url": "https://tapeline.io/app/start",
        # A REAL trial end, TRIAL_DAYS out. Passing `now` here silently drops
        # trial_end: services/billing omits it when under 48h remains, because
        # that is Stripe's documented minimum. The guard is correct — this
        # fixture just has to look like an actual trial start.
        "trial_end": (
            datetime.now(UTC) + timedelta(days=TRIAL_DAYS)
        ).replace(microsecond=0),
    }
    kwargs.update(overrides)
    await billing.create_checkout_session(**kwargs)
    return captured


@pytest.mark.asyncio
async def test_the_trial_checkout_never_makes_the_card_optional(monkeypatch):
    """`payment_method_collection="if_required"` would silently remove the wall.

    On a trial nothing is due today, so "if required" means "not required".
    Checkout would succeed, the trial would start, and no card would exist to
    charge on day 31.
    """
    captured = await _trial_session(monkeypatch)

    assert captured.get("payment_method_collection") != "if_required", (
        "the trial checkout tells Stripe the card is optional. Nothing is owed "
        "on day 0 of a trial, so Stripe will skip collection entirely and the "
        "trial becomes free Premium with no way to ever bill it."
    )


@pytest.mark.asyncio
async def test_the_trial_is_a_subscription_not_a_one_off(monkeypatch):
    """mode="subscription" is what makes Stripe demand a card by default.

    A payment-mode session with a $0 total would not collect one.
    """
    captured = await _trial_session(monkeypatch)
    assert captured.get("mode") == "subscription", (
        f"trial checkout mode is {captured.get('mode')!r}; only "
        f"mode='subscription' requires a payment method up front"
    )


@pytest.mark.asyncio
async def test_the_trial_carries_a_trial_end_so_day_one_is_not_billed(monkeypatch):
    """Without trial_end the customer is charged immediately.

    That is the opposite failure to the one above and just as bad: someone
    told "$0 today" is billed today.
    """
    captured = await _trial_session(monkeypatch)
    sub_data = captured.get("subscription_data", {})
    assert "trial_end" in sub_data, (
        "no trial_end on the trial checkout — the customer would be charged "
        "on the spot after being told the first charge is 30 days away"
    )
    # ...and it lands where the page said it would. A trial_end that is present
    # but wrong bills someone on a date they were never shown.
    days_out = (
        datetime.fromtimestamp(int(sub_data["trial_end"]), tz=UTC) - datetime.now(UTC)
    ).total_seconds() / 86400
    assert abs(days_out - TRIAL_DAYS) < 1, (
        f"the first charge is {days_out:.1f} days out, but the trial screen "
        f"quotes {TRIAL_DAYS} days and the customer agreed to that date"
    )


def test_the_trial_is_thirty_days():
    """The founder's decision, pinned so a refactor cannot quietly move it.

    Both halves of the product read one constant each (this one and
    frontend/lib/trial.ts), and a separate test pins those two together, so
    this is the only place the number itself is asserted.
    """
    assert TRIAL_DAYS == 30, (
        f"TRIAL_DAYS is {TRIAL_DAYS}, not 30. The trial length is quoted to "
        f"customers before they hand over a card and is the date their first "
        f"charge is calculated from; it is not an incidental tunable."
    )


def test_the_trial_still_clears_the_pre_charge_warning_window():
    """30 days is comfortably above the floor, but assert the relationship.

    The floor exists because Stripe's `trial_will_end` fires ~3 days out and
    /legal/refund promises that email in writing. A trial shorter than the
    warning window charges people without the notice they were promised.
    """
    assert TRIAL_DAYS >= MIN_TRIAL_DAYS, (
        f"TRIAL_DAYS={TRIAL_DAYS} is below MIN_TRIAL_DAYS={MIN_TRIAL_DAYS}"
    )
    assert TRIAL_DAYS - MIN_TRIAL_DAYS >= 7, (
        "the trial is close enough to the pre-charge warning window that a "
        "small future reduction would push it under; re-read the MIN_TRIAL_DAYS "
        "comment in routers/billing.py before shortening it"
    )
