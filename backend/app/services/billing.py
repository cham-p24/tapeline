"""Stripe billing — checkout sessions, customer portal, webhook handling."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import stripe
from fastapi import HTTPException

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key
stripe.max_network_retries = 1


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
    winback: bool = False,
) -> str:
    """Create a Stripe Checkout session and return the URL.

    `tier` is "pro" or "premium"; `billing_period` is "monthly" or "annual".
    When `referral_credit_months > 0`, mint a one-shot 100%-off coupon for
    that many months and attach it to the session. The credit is consumed
    in the customer.subscription.created webhook so a cancelled checkout
    doesn't burn the balance.

    When `winback` is True (and there's no referral credit to spend), mint a
    one-shot 40%-off-for-3-months returning-customer coupon. The caller
    decides eligibility server-side (churned + dropped to free) so the
    `?winback=1` link in the day-90 email can't be farmed for a discount.
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

        # Stripe rejects allow_promotion_codes + discounts in the same session,
        # so the three paths below are mutually exclusive. Precedence:
        # referral credit (100% off, best deal) > win-back (40% off) > manual
        # promo codes. The customer can still apply a promo on a later checkout
        # once any auto-applied coupon is spent.
        if referral_credit_months > 0:
            coupon = await asyncio.to_thread(
                stripe.Coupon.create,
                percent_off=100,
                duration="repeating",
                duration_in_months=referral_credit_months,
                name=f"Tapeline referral credit ({referral_credit_months} mo)",
                metadata={"user_id": user_id, "kind": "referral"},
            )
            kwargs["discounts"] = [{"coupon": coupon.id}]
            sub_metadata["referral_credits_to_consume"] = str(referral_credit_months)
        elif winback:
            coupon = await asyncio.to_thread(
                stripe.Coupon.create,
                percent_off=40,
                duration="repeating",
                duration_in_months=3,
                name="Tapeline win-back (40% off 3 months)",
                metadata={"user_id": user_id, "kind": "winback"},
            )
            kwargs["discounts"] = [{"coupon": coupon.id}]
            sub_metadata["winback"] = "1"
        else:
            kwargs["allow_promotion_codes"] = True

        kwargs["subscription_data"] = {"metadata": sub_metadata}
        session = await asyncio.to_thread(stripe.checkout.Session.create, **kwargs)
        return session.url  # type: ignore[return-value]
    except stripe.error.StripeError as exc:
        logger.exception("stripe.checkout_create_failed")
        raise HTTPException(502, f"Stripe error: {exc}") from exc


async def create_portal_session(customer_id: str, return_url: str) -> str:
    """Create a customer portal session for self-serve billing management."""
    try:
        s = await asyncio.to_thread(
            stripe.billing_portal.Session.create,
            customer=customer_id,
            return_url=return_url,
        )
        return s.url  # type: ignore[return-value]
    except stripe.error.StripeError as exc:
        logger.exception("stripe.portal_create_failed")
        raise HTTPException(502, f"Stripe error: {exc}") from exc


# ── Retention: pause / save-offer / cancel ──────────────────────────────────
#
# All three operate on the customer's *primary* subscription — the one driving
# their paid tier. We resolve it live from Stripe (source of truth) rather than
# trusting the local Subscription row, which can lag a webhook. The cancel
# intercept (routers/billing.py) is the only caller; it persists the
# Tapeline-side state (paused_until, save_offer_redeemed_at, canceled_at).

# Status precedence when a customer somehow has multiple subscriptions — pick
# the most "live" one to act on.
_SUB_STATUS_PRIORITY = ("active", "trialing", "past_due", "unpaid", "paused")


def _require_stripe() -> None:
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Billing isn't configured (no Stripe key).")


async def _primary_subscription(customer_id: str) -> Any:
    """Return the customer's primary Stripe subscription object, or raise 404.

    Prefers active/trialing over past_due/paused. Raises HTTPException(404)
    when the customer has no subscription Stripe will let us act on.
    """
    try:
        subs = await asyncio.to_thread(
            stripe.Subscription.list, customer=customer_id, status="all", limit=20,
        )
    except stripe.error.StripeError as exc:
        logger.exception("stripe.subscription_list_failed customer=%s", customer_id)
        raise HTTPException(502, f"Stripe error: {exc}") from exc

    data = list(getattr(subs, "data", None) or [])
    if not data:
        raise HTTPException(404, "No subscription found for this account.")

    def _rank(sub: Any) -> int:
        status = sub.get("status") if isinstance(sub, dict) else getattr(sub, "status", None)
        try:
            return _SUB_STATUS_PRIORITY.index(status)
        except ValueError:
            return len(_SUB_STATUS_PRIORITY)

    data.sort(key=_rank)
    return data[0]


def _sub_id(sub: Any) -> str:
    return sub["id"] if isinstance(sub, dict) else sub.id


def _sub_field(sub: Any, key: str) -> Any:
    return sub.get(key) if isinstance(sub, dict) else getattr(sub, key, None)


async def pause_subscription(customer_id: str, months: int) -> datetime:
    """Pause billing for `months` (1-3) via Stripe pause_collection.

    Uses behaviour="void" — invoices generated during the pause are voided,
    so the customer isn't charged. Stripe keeps the subscription `active`
    (pause_collection doesn't change status), so our webhook leaves the
    user's tier intact: a pause is a retention win, not a downgrade. Stripe
    auto-resumes billing at `resumes_at`. Returns the resume datetime.
    """
    _require_stripe()
    if months < 1 or months > 3:
        raise HTTPException(400, "Pause length must be 1-3 months.")
    sub = await _primary_subscription(customer_id)
    resumes_at = datetime.now(UTC) + timedelta(days=30 * months)
    try:
        await asyncio.to_thread(
            stripe.Subscription.modify,
            _sub_id(sub),
            pause_collection={"behavior": "void", "resumes_at": int(resumes_at.timestamp())},
        )
    except stripe.error.StripeError as exc:
        logger.exception("stripe.pause_failed customer=%s", customer_id)
        raise HTTPException(502, f"Stripe error: {exc}") from exc
    return resumes_at


async def resume_subscription(customer_id: str) -> None:
    """Clear pause_collection so billing resumes immediately."""
    _require_stripe()
    sub = await _primary_subscription(customer_id)
    try:
        await asyncio.to_thread(stripe.Subscription.modify, _sub_id(sub), pause_collection="")
    except stripe.error.StripeError as exc:
        logger.exception("stripe.resume_failed customer=%s", customer_id)
        raise HTTPException(502, f"Stripe error: {exc}") from exc


async def apply_save_offer_coupon(customer_id: str) -> None:
    """Mint a one-time 50%-off-for-3-months coupon and apply it to the sub.

    The caller guards against repeat redemption via User.save_offer_redeemed_at;
    this function just does the Stripe side.
    """
    _require_stripe()
    sub = await _primary_subscription(customer_id)
    try:
        coupon = await asyncio.to_thread(
            stripe.Coupon.create,
            percent_off=50,
            duration="repeating",
            duration_in_months=3,
            name="Tapeline retention — 50% off 3 months",
            metadata={"customer_id": customer_id, "kind": "save_offer"},
        )
        # Apply the discount AND clear any scheduled cancellation in the same
        # call — accepting "keep my plan" should fully reactivate, not just
        # discount a sub that's still set to lapse. cancel_at_period_end=False
        # is a no-op when the sub wasn't scheduled to cancel (the common
        # pre-emptive-save path), so this is safe either way.
        await asyncio.to_thread(
            stripe.Subscription.modify,
            _sub_id(sub),
            discounts=[{"coupon": coupon.id}],
            cancel_at_period_end=False,
        )
    except stripe.error.StripeError as exc:
        logger.exception("stripe.save_offer_failed customer=%s", customer_id)
        raise HTTPException(502, f"Stripe error: {exc}") from exc


async def set_cancel_at_period_end(customer_id: str) -> datetime | None:
    """Schedule the subscription to cancel at period end (no immediate cut-off).

    The customer keeps access until the paid period ends; Stripe then fires
    customer.subscription.deleted and our webhook drops them to free. Returns
    the period-end datetime so the UI/email can show "access until X".
    """
    _require_stripe()
    sub = await _primary_subscription(customer_id)
    try:
        updated = await asyncio.to_thread(
            stripe.Subscription.modify, _sub_id(sub), cancel_at_period_end=True,
        )
    except stripe.error.StripeError as exc:
        logger.exception("stripe.cancel_failed customer=%s", customer_id)
        raise HTTPException(502, f"Stripe error: {exc}") from exc
    period_end = _sub_field(updated, "current_period_end")
    if period_end:
        return datetime.fromtimestamp(int(period_end), UTC)
    return None


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
    interval = (item["price"].get("recurring") or {}).get("interval", "month")
    return {
        "id": sub["id"],
        "status": sub["status"],
        "tier": _tier_from_price(item["price"]["id"]),
        "current_period_end": datetime.fromtimestamp(sub["current_period_end"], UTC),
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end", False)),
        "billing_period": "annual" if interval == "year" else "monthly",
    }
