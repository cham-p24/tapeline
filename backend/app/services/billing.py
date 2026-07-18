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


# ── Tax posture: one switch, read by BOTH the session and the disclosure ────
#
# We do NOT enable Stripe Tax, so Stripe calculates and adds nothing on top of
# the sticker price — the advertised amount is the amount charged. The plan
# cards state that BEFORE the redirect (see get_charge_disclosure), and the
# only way that promise can stay true is if the disclosure and the Checkout
# session read the same constant. They do: this flag is forwarded as
# `automatic_tax` in create_checkout_session below AND reported as `tax_added`
# by get_charge_disclosure. Flip it here and both surfaces move together —
# there is no way to turn on tax collection and leave the copy claiming
# otherwise.
AUTOMATIC_TAX_ENABLED = False


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
    expires_in_minutes: int | None = None,
    trial_end: datetime | None = None,
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

    `expires_in_minutes` shortens the session's completable window from
    Stripe's ~24h default. The one-click email path passes 30 (Stripe's
    minimum) so a user who opens both tier links from one email can't come
    back a day later and complete BOTH — the concurrent-completable window
    shrinks from ~24h to minutes.

    `trial_end` preserves the remainder of an in-app no-card trial: the
    caller passes the user's trial_ends_at and we forward it as
    subscription_data.trial_end so a mid-trial "add a card" checkout starts
    billing when the trial was always going to end, instead of charging
    immediately and silently forfeiting the remaining free days. Skipped
    when under 48h remains (Stripe's documented minimum for trial_end).
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
        #
        # Wallet buttons render ABOVE the card form, so on a supported device
        # the whole card-entry step collapses into one biometric tap — the
        # single largest documented friction reduction available at this step.
        # This is checked by test_billing_checkout so a future refactor that
        # drops "card" (and with it the wallets) fails loudly instead of
        # silently reverting every mobile buyer to manual card entry.
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
            # Stated on the plan card before the redirect. Sending this
            # explicitly (rather than relying on the API default) is what makes
            # the "the amount shown is the amount charged" line verifiable
            # against the request we actually issue.
            "automatic_tax": {"enabled": AUTOMATIC_TAX_ENABLED},
        }
        if expires_in_minutes is not None:
            # Stripe clamps expires_at to [30 min, 24 h] from creation.
            import time as _time
            kwargs["expires_at"] = int(_time.time()) + max(expires_in_minutes, 30) * 60

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

        # Dunning prerequisite. Stripe's Smart Retries can only re-attempt a
        # failed renewal against a payment method stored ON THE SUBSCRIPTION;
        # without this the card collected at Checkout is attached to the
        # customer but is not the subscription's default, and a retry can find
        # nothing to charge. That turns a recoverable soft decline (expired
        # card, temporary insufficient funds) into silent involuntary churn —
        # roughly a quarter of all SaaS churn by vendor benchmark. The retry
        # SCHEDULE itself is dashboard config (see the runbook note in the PR);
        # this is the half that has to be set per-subscription in code.
        subscription_data: dict[str, Any] = {
            "metadata": sub_metadata,
            "payment_settings": {"save_default_payment_method": "on_subscription"},
        }
        if trial_end is not None:
            # Older rows can carry naive datetimes — stored values are UTC.
            if trial_end.tzinfo is None:
                trial_end = trial_end.replace(tzinfo=UTC)
            if trial_end >= datetime.now(UTC) + timedelta(hours=48):
                subscription_data["trial_end"] = int(trial_end.timestamp())
            # else: Stripe rejects subscription_data.trial_end closer than
            # 48h out (its documented minimum), so a nearly-finished trial
            # falls back to a normal charge-now checkout rather than 400ing
            # the whole purchase — the user gives up <48h of trial instead
            # of losing the checkout entirely.
        kwargs["subscription_data"] = subscription_data
        session = await asyncio.to_thread(stripe.checkout.Session.create, **kwargs)
        return session.url  # type: ignore[return-value]
    except stripe.error.StripeError as exc:
        logger.exception("stripe.checkout_create_failed")
        raise HTTPException(502, f"Stripe error: {exc}") from exc


# ── Charge disclosure: what Stripe will actually take, before the redirect ──
#
# Checkout research (Baymard) puts "unexpected cost at the payment step" at the
# top of the abandonment list, so the plan card has to state the real charge
# currency — and whether anything is added on top — BEFORE the user is thrown
# to checkout.stripe.com. Every field below is derived from live Stripe config
# or from the session kwargs this module actually sends. Nothing is guessed:
# when Stripe can't be reached, `currency` comes back None and the UI simply
# says less rather than inventing a claim.
#
# The tax half needs no network call at all: AUTOMATIC_TAX_ENABLED (top of this
# module) is the exact value forwarded as `automatic_tax` in the Checkout
# session, so reporting it here describes OUR OWN REQUEST rather than a guess
# about Stripe's account settings. That is what makes the "no tax is added"
# sentence a statement of fact instead of a promise we can't keep.

# Memoised: Price objects are immutable in Stripe (a price change means a new
# id), so one successful fetch per process is plenty.
_charge_disclosure_cache: dict[str, Any] | None = None


def _configured_price_ids() -> list[str]:
    """Every Stripe price id this deployment has configured, in preference
    order (the cheapest recurring plan first — any of them answers the
    currency question identically)."""
    return [
        p
        for p in (
            settings.stripe_price_pro_monthly,
            settings.stripe_price_pro_annual,
            settings.stripe_price_premium_monthly,
            settings.stripe_price_premium_annual,
        )
        if p
    ]


async def get_charge_disclosure() -> dict[str, Any]:
    """Describe the real charge: currency, and whether tax is added on top.

    Returns::

        {
          "currency": "USD" | None,     # None = couldn't determine, say nothing
          "tax_added": False | None,    # None = unknown, make NO tax claim
          "tax_behavior": "unspecified" | "inclusive" | "exclusive" | None,
          "source": "stripe" | "unavailable",
        }

    `currency` is only ever reported when a real Price object confirmed it.

    `tax_added` is deliberately three-valued. We only assert False — "nothing is
    added on top" — when BOTH halves agree: automatic tax is off in the session
    we send, AND the Price is not marked tax_behavior="exclusive". An exclusive
    price is one configured on the assumption that tax gets added on top, so
    even though our session adds none today, a dashboard-level tax rate could
    make the negative claim wrong. In that case we return None and the UI
    states the currency alone. A missing sentence is recoverable; a wrong tax
    claim at the payment step is not.
    """
    global _charge_disclosure_cache
    if _charge_disclosure_cache is not None:
        return dict(_charge_disclosure_cache)

    result: dict[str, Any] = {
        "currency": None,
        # No Price fetched yet, so the exclusive-price caveat above is
        # unverified — stay silent rather than assert.
        "tax_added": None,
        "tax_behavior": None,
        "source": "unavailable",
    }

    price_ids = _configured_price_ids()
    if settings.stripe_secret_key and price_ids:
        try:
            price = await asyncio.to_thread(stripe.Price.retrieve, price_ids[0])
            currency = price.get("currency") if isinstance(price, dict) else getattr(price, "currency", None)
            behavior = (
                price.get("tax_behavior") if isinstance(price, dict)
                else getattr(price, "tax_behavior", None)
            )
            if currency:
                result["currency"] = str(currency).upper()
                result["tax_behavior"] = behavior
                result["source"] = "stripe"
                if not AUTOMATIC_TAX_ENABLED and behavior != "exclusive":
                    result["tax_added"] = False
                elif AUTOMATIC_TAX_ENABLED:
                    result["tax_added"] = True
                # else: exclusive price — leave None, currency-only copy.
                # Cache only a genuine answer, so a transient Stripe blip
                # doesn't pin "unavailable" for the life of the process.
                _charge_disclosure_cache = dict(result)
        except stripe.error.StripeError:
            # Non-fatal: the disclosure degrades to currency-less rather than
            # failing the page or asserting something unverified.
            logger.warning("stripe.price_disclosure_failed", exc_info=True)
    return result


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
