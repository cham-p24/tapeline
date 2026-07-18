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
