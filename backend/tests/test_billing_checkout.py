"""Coverage for billing.create_checkout_session — the highest-value payment
path, previously only ever tested with the whole service mocked out
(test_retention_flow monkeypatches create_checkout_session away).

This validates that the function builds the right Stripe Checkout kwargs and
returns the hosted-checkout URL through the asyncio.to_thread offload added to
stop the sync Stripe SDK from stalling the event loop.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


async def test_create_checkout_session_returns_hosted_url(monkeypatch):
    from app.services import billing

    # Guarantee a price id resolves regardless of env config.
    monkeypatch.setattr(
        billing.settings, "stripe_price_pro_monthly", "price_test_pro_monthly",
        raising=False,
    )

    captured: dict = {}

    def _fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_test_123")

    # Patch the (to_thread-wrapped) blocking SDK call.
    monkeypatch.setattr(billing.stripe.checkout.Session, "create", _fake_session_create)

    url = await billing.create_checkout_session(
        user_id="u_test",
        user_email="buyer@example.com",
        tier="pro",
        billing_period="monthly",
        success_url="https://tapeline.io/app/billing?ok=1",
        cancel_url="https://tapeline.io/pricing",
    )

    assert url == "https://checkout.stripe.com/c/pay/cs_test_123"
    assert captured["mode"] == "subscription"
    assert captured["client_reference_id"] == "u_test"
    assert captured["customer_email"] == "buyer@example.com"
    assert captured["line_items"][0]["price"] == "price_test_pro_monthly"


async def test_create_checkout_session_preserves_remaining_trial(monkeypatch):
    """A mid-trial card-add forwards trial_end so Stripe starts billing when
    the trial was always going to end — no silent forfeit of free days."""
    from app.services import billing

    monkeypatch.setattr(
        billing.settings, "stripe_price_premium_monthly", "price_test_prem_monthly",
        raising=False,
    )

    captured: dict = {}

    def _fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_trial")

    monkeypatch.setattr(billing.stripe.checkout.Session, "create", _fake_session_create)

    trial_end = datetime.now(UTC) + timedelta(days=11)
    await billing.create_checkout_session(
        user_id="u_trial",
        user_email="trial@example.com",
        tier="premium",
        billing_period="monthly",
        success_url="https://x/s",
        cancel_url="https://x/c",
        trial_end=trial_end,
    )

    sub_data = captured["subscription_data"]
    assert sub_data["trial_end"] == int(trial_end.timestamp())
    # The metadata contract the webhooks rely on must survive the addition.
    assert sub_data["metadata"]["user_id"] == "u_trial"


async def test_create_checkout_session_short_trial_omits_trial_end(monkeypatch):
    """Stripe rejects trial_end closer than 48h out — a nearly-finished trial
    falls back to a normal charge-now checkout instead of a Stripe 400."""
    from app.services import billing

    monkeypatch.setattr(
        billing.settings, "stripe_price_premium_monthly", "price_test_prem_monthly",
        raising=False,
    )

    captured: dict = {}

    def _fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_short")

    monkeypatch.setattr(billing.stripe.checkout.Session, "create", _fake_session_create)

    await billing.create_checkout_session(
        user_id="u_short",
        user_email="short@example.com",
        tier="premium",
        billing_period="monthly",
        success_url="https://x/s",
        cancel_url="https://x/c",
        trial_end=datetime.now(UTC) + timedelta(hours=12),
    )

    sub_data = captured["subscription_data"]
    assert "trial_end" not in sub_data
    assert sub_data["metadata"]["user_id"] == "u_short"


async def test_create_checkout_session_naive_trial_end_treated_as_utc(monkeypatch):
    """Older rows can hold naive datetimes — they're stored UTC and must not
    crash the aware/naive comparison or get skipped."""
    from app.services import billing

    monkeypatch.setattr(
        billing.settings, "stripe_price_premium_monthly", "price_test_prem_monthly",
        raising=False,
    )

    captured: dict = {}

    def _fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_naive")

    monkeypatch.setattr(billing.stripe.checkout.Session, "create", _fake_session_create)

    naive = (datetime.now(UTC) + timedelta(days=7)).replace(tzinfo=None)
    await billing.create_checkout_session(
        user_id="u_naive",
        user_email="naive@example.com",
        tier="premium",
        billing_period="monthly",
        success_url="https://x/s",
        cancel_url="https://x/c",
        trial_end=naive,
    )

    expected = int(naive.replace(tzinfo=UTC).timestamp())
    assert captured["subscription_data"]["trial_end"] == expected


async def test_create_checkout_session_unconfigured_price_is_400(monkeypatch):
    from app.services import billing

    # No price id for this tier/period -> a clean 400, never an upstream call.
    monkeypatch.setattr(billing.settings, "stripe_price_premium_annual", "", raising=False)
    with pytest.raises(HTTPException) as exc:
        await billing.create_checkout_session(
            user_id="u",
            user_email="x@example.com",
            tier="premium",
            billing_period="annual",
            success_url="https://x/s",
            cancel_url="https://x/c",
        )
    assert exc.value.status_code == 400


# ── Checkout trust polish: wallets, tax posture, dunning prerequisite ────────
#
# These three assertions guard config that is invisible in the UI but decides
# whether a real customer can pay (wallets), whether the price we advertise is
# the price charged (automatic_tax), and whether a failed renewal is even
# recoverable (save_default_payment_method). All three are one-line kwargs that
# a refactor could silently drop, and none of them would fail loudly in prod —
# the failure mode is a quieter conversion rate and unexplained churn.

async def _capture_session_kwargs(monkeypatch, **overrides) -> dict:
    """Build a checkout session against a stubbed Stripe and return the kwargs."""
    from app.services import billing

    monkeypatch.setattr(
        billing.settings, "stripe_price_pro_monthly", "price_test_pro_monthly",
        raising=False,
    )
    captured: dict = {}

    def _fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_polish")

    monkeypatch.setattr(billing.stripe.checkout.Session, "create", _fake_session_create)

    params = {
        "user_id": "u_polish",
        "user_email": "polish@example.com",
        "tier": "pro",
        "billing_period": "monthly",
        "success_url": "https://x/s",
        "cancel_url": "https://x/c",
    }
    params.update(overrides)
    await billing.create_checkout_session(**params)
    return captured


async def test_checkout_enables_wallet_payments(monkeypatch):
    """Apple Pay / Google Pay ride on the "card" payment method type and render
    above the card form; Link is listed explicitly for its 1-click flow. Losing
    "card" here would silently drop every wallet button."""
    captured = await _capture_session_kwargs(monkeypatch)
    assert "card" in captured["payment_method_types"]
    assert "link" in captured["payment_method_types"]


async def test_checkout_tax_posture_matches_the_disclosed_copy(monkeypatch):
    """The plan card promises the sticker amount is the amount charged. That
    promise is only keepable if the session forwards the same constant the
    disclosure reports — assert they are literally the same value."""
    from app.services import billing

    captured = await _capture_session_kwargs(monkeypatch)
    assert captured["automatic_tax"] == {"enabled": billing.AUTOMATIC_TAX_ENABLED}


async def test_checkout_saves_default_payment_method_for_retries(monkeypatch):
    """Dunning prerequisite: Stripe Smart Retries can only re-attempt against a
    payment method stored on the SUBSCRIPTION. Without this the collected card
    is attached to the customer but not the subscription default, and a
    recoverable soft decline becomes involuntary churn."""
    captured = await _capture_session_kwargs(monkeypatch)
    settings_ = captured["subscription_data"]["payment_settings"]
    assert settings_["save_default_payment_method"] == "on_subscription"


# ── Charge disclosure ───────────────────────────────────────────────────────

async def test_charge_disclosure_reports_currency_and_no_tax(monkeypatch):
    """A normal (non-exclusive) price with automatic tax off yields the full
    two-part disclosure: real currency from Stripe, and an explicit False."""
    from app.services import billing

    monkeypatch.setattr(billing, "_charge_disclosure_cache", None, raising=False)
    monkeypatch.setattr(billing, "AUTOMATIC_TAX_ENABLED", False, raising=False)
    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test_x", raising=False)
    monkeypatch.setattr(
        billing.settings, "stripe_price_pro_monthly", "price_test_pro_monthly",
        raising=False,
    )
    monkeypatch.setattr(
        billing.stripe.Price, "retrieve",
        lambda *a, **k: {"currency": "usd", "tax_behavior": "unspecified"},
    )

    out = await billing.get_charge_disclosure()
    assert out["currency"] == "USD"
    assert out["tax_added"] is False
    assert out["source"] == "stripe"


async def test_charge_disclosure_makes_no_tax_claim_on_exclusive_price(monkeypatch):
    """An "exclusive" price is configured on the assumption tax gets added on
    top. Even though our session adds none today, a dashboard-level tax rate
    could make a "no tax" claim wrong — so the server declines to make one and
    the UI falls back to the currency sentence alone."""
    from app.services import billing

    monkeypatch.setattr(billing, "_charge_disclosure_cache", None, raising=False)
    monkeypatch.setattr(billing, "AUTOMATIC_TAX_ENABLED", False, raising=False)
    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test_x", raising=False)
    monkeypatch.setattr(
        billing.settings, "stripe_price_pro_monthly", "price_test_pro_monthly",
        raising=False,
    )
    monkeypatch.setattr(
        billing.stripe.Price, "retrieve",
        lambda *a, **k: {"currency": "usd", "tax_behavior": "exclusive"},
    )

    out = await billing.get_charge_disclosure()
    assert out["currency"] == "USD"
    assert out["tax_added"] is None  # "unknown" — say nothing about tax


async def test_charge_disclosure_degrades_silently_without_stripe(monkeypatch):
    """No Stripe key (CI, local dev, an outage): assert NOTHING. The UI keeps
    its currency constant and drops the tax sentence entirely."""
    from app.services import billing

    monkeypatch.setattr(billing, "_charge_disclosure_cache", None, raising=False)
    monkeypatch.setattr(billing.settings, "stripe_secret_key", "", raising=False)

    out = await billing.get_charge_disclosure()
    assert out["currency"] is None
    assert out["tax_added"] is None
    assert out["source"] == "unavailable"
