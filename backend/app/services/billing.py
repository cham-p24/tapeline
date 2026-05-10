"""Stripe billing — checkout sessions, customer portal, webhook handling."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import stripe
from fastapi import HTTPException

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key


def _tier_from_price(price_id: str) -> str:
    """Map Stripe price ID to Tapeline tier (handles both monthly + annual)."""
    if price_id in (settings.stripe_price_pro_monthly, settings.stripe_price_pro_annual):
        return "pro"
    if price_id in (settings.stripe_price_premium_monthly, settings.stripe_price_premium_annual):
        return "premium"
    return "free"


async def create_checkout_session(
    user_id: str,
    user_email: str,
    tier: str,
    billing_period: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout session and return the URL.

    `tier` is "pro" or "premium"; `billing_period` is "monthly" or "annual".
    """
    price_map = {
        ("pro", "monthly"):     settings.stripe_price_pro_monthly,
        ("pro", "annual"):      settings.stripe_price_pro_annual,
        ("premium", "monthly"): settings.stripe_price_premium_monthly,
        ("premium", "annual"):  settings.stripe_price_premium_annual,
    }
    price_id = price_map.get((tier, billing_period))
    if not price_id:
        raise HTTPException(
            400,
            f"No Stripe Price ID configured for {tier}/{billing_period}. "
            f"Set STRIPE_PRICE_{tier.upper()}_{billing_period.upper()} in .env.",
        )

    try:
        # automatic_payment_methods=True lets Stripe enable every wallet that's
        # turned on in the dashboard — card + Apple Pay + Google Pay + Link —
        # without us having to enumerate them. Apple/Google Pay show up as
        # express buttons on supported devices when the merchant account has
        # them enabled. No domain registration needed: hosted Checkout runs on
        # checkout.stripe.com, which Stripe pre-registers.
        session = stripe.checkout.Session.create(
            mode="subscription",
            automatic_payment_methods={"enabled": True},
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=user_email,
            client_reference_id=user_id,
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={"metadata": {"user_id": user_id, "tier": tier, "billing_period": billing_period}},
            allow_promotion_codes=True,
        )
        return session.url  # type: ignore[return-value]
    except stripe.error.StripeError as exc:
        logger.exception("stripe.checkout_create_failed")
        raise HTTPException(502, f"Stripe error: {exc}") from exc


async def create_portal_session(customer_id: str, return_url: str) -> str:
    """Create a customer portal session for self-serve billing management."""
    try:
        s = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
        return s.url  # type: ignore[return-value]
    except stripe.error.StripeError as exc:
        logger.exception("stripe.portal_create_failed")
        raise HTTPException(502, f"Stripe error: {exc}") from exc


def parse_webhook(payload: bytes, signature: str) -> stripe.Event:
    """Verify and parse a Stripe webhook."""
    try:
        return stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret,
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise HTTPException(400, f"Invalid webhook: {exc}") from exc


def subscription_payload(sub: Any) -> dict[str, Any]:
    """Extract the fields we persist from a Stripe subscription object."""
    item = sub["items"]["data"][0]
    return {
        "id": sub["id"],
        "status": sub["status"],
        "tier": _tier_from_price(item["price"]["id"]),
        "current_period_end": datetime.fromtimestamp(sub["current_period_end"], UTC),
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end", False)),
    }
