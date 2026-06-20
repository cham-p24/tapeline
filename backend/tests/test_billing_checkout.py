"""Coverage for billing.create_checkout_session — the highest-value payment
path, previously only ever tested with the whole service mocked out
(test_retention_flow monkeypatches create_checkout_session away).

This validates that the function builds the right Stripe Checkout kwargs and
returns the hosted-checkout URL through the asyncio.to_thread offload added to
stop the sync Stripe SDK from stalling the event loop.
"""
from __future__ import annotations

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
