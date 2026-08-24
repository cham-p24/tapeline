"""Every key we send in a Checkout Session's `subscription_data` must be a
field Stripe actually accepts there.

Why this file exists: PR #363 (2026-07-18) added
`payment_settings={"save_default_payment_method": "on_subscription"}` to
`subscription_data`. That IS a real field — on `Subscription.create/modify`.
It is NOT a field of a Checkout Session's `subscription_data`, so Stripe
rejected the whole request with "Received unknown parameter:
subscription_data[payment_settings]", and create_checkout_session's
`except stripe.error.StripeError` turned that 400 into a 502 on the
customer's checkout.

Blast radius: `subscription_data` is built unconditionally, so this broke
EVERY checkout — new subscriptions, trial starts, and (from 2026-08-22) the
card gate that a new account must clear before it can use the product. It ran
for 37 days (Sentry TAPELINE-BACKEND-20/21) and the failure was invisible
from inside the app: the code looked correct, the tests passed, and only
Stripe knew the parameter was bogus.

The lesson this test encodes: a wrong-but-plausible Stripe field is not
caught by "does the code run" — it is only caught by checking the key names
against Stripe's actual contract for THIS endpoint. So we pin the allowlist
and walk every branch that builds a session.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

# Fields Stripe documents on Checkout Session `subscription_data`.
# https://docs.stripe.com/api/checkout/sessions/create (subscription_data)
# Deliberately a strict allowlist, not a denylist of things we got wrong once:
# the next bad key will be a different plausible-sounding one.
ALLOWED_SUBSCRIPTION_DATA_KEYS = frozenset({
    "application_fee_percent",
    "billing_cycle_anchor",
    "default_tax_rates",
    "description",
    "invoice_settings",
    "metadata",
    "on_behalf_of",
    "proration_behavior",
    "transfer_data",
    "trial_end",
    "trial_period_days",
    "trial_settings",
})

# Every way a checkout can be built. Each tuple is (label, kwargs).
CHECKOUT_VARIANTS = [
    ("plain_monthly", {"billing_period": "monthly"}),
    ("plain_annual", {"billing_period": "annual"}),
    ("referral_monthly", {"billing_period": "monthly", "referral_credit_months": 1}),
    ("referral_annual", {"billing_period": "annual", "referral_credit_months": 1}),
    ("winback_monthly", {"billing_period": "monthly", "winback": True}),
    ("winback_annual", {"billing_period": "annual", "winback": True}),
    ("trial_save_monthly", {"billing_period": "monthly", "trial_save_offer": True}),
    ("trial_save_annual", {"billing_period": "annual", "trial_save_offer": True}),
]


def _install_stripe_fakes(monkeypatch, billing, captured: dict):
    """Stand in for every Stripe call create_checkout_session can make."""
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

    def _fake_price_retrieve(price_id, **_):
        return SimpleNamespace(unit_amount=999, currency="usd")

    def _fake_coupon_create(**kwargs):
        captured.setdefault("_coupons", []).append(kwargs)
        return SimpleNamespace(id="coupon_test_123")

    monkeypatch.setattr(billing.stripe.checkout.Session, "create", _fake_session_create)
    monkeypatch.setattr(billing.stripe.Price, "retrieve", _fake_price_retrieve)
    monkeypatch.setattr(billing.stripe.Coupon, "create", _fake_coupon_create)


async def _run(monkeypatch, **overrides) -> dict:
    from app.services import billing

    captured: dict = {}
    _install_stripe_fakes(monkeypatch, billing, captured)

    kwargs = {
        "user_id": "u_test",
        "user_email": "buyer@example.com",
        "tier": "pro",
        "billing_period": "monthly",
        "success_url": "https://tapeline.io/app/billing?ok=1",
        "cancel_url": "https://tapeline.io/pricing",
    }
    kwargs.update(overrides)
    await billing.create_checkout_session(**kwargs)
    return captured


@pytest.mark.parametrize("label,overrides", CHECKOUT_VARIANTS, ids=[c[0] for c in CHECKOUT_VARIANTS])
async def test_subscription_data_keys_are_valid_for_checkout(monkeypatch, label, overrides):
    captured = await _run(monkeypatch, **overrides)

    sub_data = captured.get("subscription_data", {})
    unknown = set(sub_data) - ALLOWED_SUBSCRIPTION_DATA_KEYS
    assert not unknown, (
        f"[{label}] subscription_data carries key(s) Stripe does not accept on a "
        f"Checkout Session: {sorted(unknown)}. Stripe rejects the ENTIRE request "
        "with 'Received unknown parameter', which surfaces as a 502 on the "
        "customer's checkout. If the field belongs on the Subscription, set it "
        "via Subscription.modify after the webhook instead."
    )


@pytest.mark.parametrize("label,overrides", CHECKOUT_VARIANTS, ids=[c[0] for c in CHECKOUT_VARIANTS])
async def test_payment_settings_never_returns(monkeypatch, label, overrides):
    """Named pin for the specific 37-day outage, so a revert is loud."""
    captured = await _run(monkeypatch, **overrides)
    assert "payment_settings" not in captured.get("subscription_data", {}), (
        f"[{label}] payment_settings is back in subscription_data. This exact key "
        "broke every Tapeline checkout from 2026-07-18 to 2026-08-24. Checkout "
        "already sets the collected card as the subscription's default payment "
        "method in mode='subscription' — this key buys nothing and costs everything."
    )


async def test_metadata_still_travels(monkeypatch):
    """Removing payment_settings must not take the metadata with it.

    The subscription webhook reads these keys to consume referral credits and
    mark save-offer redemption, so an empty metadata dict would silently break
    accounting rather than checkout.
    """
    captured = await _run(monkeypatch, referral_credit_months=2)
    metadata = captured["subscription_data"]["metadata"]
    assert metadata.get("referral_credits_to_consume") == "2"
    assert metadata.get("user_id") == "u_test"


async def test_trial_end_still_forwarded(monkeypatch):
    """trial_end IS a valid subscription_data field — it must survive."""
    trial_end = datetime.now(UTC) + timedelta(days=10)
    captured = await _run(monkeypatch, trial_end=trial_end)
    assert captured["subscription_data"]["trial_end"] == int(trial_end.timestamp())


async def test_a_checkout_actually_succeeds(monkeypatch):
    """End-to-end sanity: the happy path returns a URL rather than raising.

    With the bad key present this test fails at the Stripe layer in production
    but PASSES against a permissive mock — which is precisely why the key-name
    allowlist above, not this test, is the real guard.
    """
    from app.services import billing

    captured: dict = {}
    _install_stripe_fakes(monkeypatch, billing, captured)
    url = await billing.create_checkout_session(
        user_id="u_test",
        user_email="buyer@example.com",
        tier="pro",
        billing_period="monthly",
        success_url="https://tapeline.io/app/billing?ok=1",
        cancel_url="https://tapeline.io/pricing",
    )
    assert url.startswith("https://checkout.stripe.com/")
