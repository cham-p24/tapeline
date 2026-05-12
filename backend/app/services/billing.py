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
    referral_credit_months: int = 0,
) -> str:
    """Create a Stripe Checkout session and return the URL.

    `tier` is "pro" or "premium"; `billing_period` is "monthly" or "annual".
    When `referral_credit_months > 0`, mint a one-shot 100%-off coupon for
    that many months and attach it to the session. The credit is consumed
    in the customer.subscription.created webhook so a cancelled checkout
    doesn't burn the balance.
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
        # Wallets — Apple Pay, Google Pay, and Link — show up automatically on
        # supported devices when "card" is in payment_method_types and they're
        # enabled in the Stripe dashboard. Hosted Checkout runs on
        # checkout.stripe.com which Stripe pre-registers for Apple Pay, so no
        # extra domain verification step is needed. We list "link" explicitly
        # so Stripe Link's 1-click flow gets surfaced as its own option.
        sub_metadata: dict[str, Any] = {
            "user_id": user_id, "tier": tier, "billing_period": billing_period,
        }
        kwargs: dict[str, Any] = {
            "mode": "subscription",
            "payment_method_types": ["card", "link"],
            "line_items": [{"price": price_id, "quantity": 1}],
            "customer_email": user_email,
            "client_reference_id": user_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
        }

        # Stripe rejects allow_promotion_codes + discounts in the same session.
        # Referral credit takes precedence; manual promo codes are disabled for
        # this one checkout. The customer can still apply a promo on a later
        # checkout once the referral credit is spent.
        if referral_credit_months > 0:
            coupon = stripe.Coupon.create(
                percent_off=100,
                duration="repeating",
                duration_in_months=referral_credit_months,
                name=f"Tapeline referral credit ({referral_credit_months} mo)",
                metadata={"user_id": user_id, "kind": "referral"},
            )
            kwargs["discounts"] = [{"coupon": coupon.id}]
            sub_metadata["referral_credits_to_consume"] = str(referral_credit_months)
        else:
            kwargs["allow_promotion_codes"] = True

        kwargs["subscription_data"] = {"metadata": sub_metadata}
        session = stripe.checkout.Session.create(**kwargs)
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
