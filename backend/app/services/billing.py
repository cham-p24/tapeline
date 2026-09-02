"""Stripe billing — checkout sessions, customer portal, webhook handling."""
from __future__ import annotations

import asyncio
import json
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


# ── Coupon names: Stripe's 40-char cap is a payment-path landmine ───────────
#
# stripe.Coupon.create rejects a `name` longer than 40 characters with a 400,
# and every coupon we mint sits INSIDE the try/except that turns a StripeError
# into `HTTPException(502)`. So an over-long discount label doesn't degrade the
# discount — it kills the whole checkout the customer just clicked. That is
# exactly how it failed in production on 2026-08-10 (Sentry TAPELINE-BACKEND-26,
# "Invalid string: Tape...ual); must be at most 40 characters"): the annual
# trial-save name was 52 chars, so the save offer 502'd instead of saving.
#
# Two defences, because the names live at eight call sites and are edited as
# copy:
#   1. Every name below is short by construction (the redundant "Tapeline "
#      prefix is gone — these render on a Tapeline invoice already).
#   2. _coupon_name clamps at runtime. Truncating a discount LABEL is a
#      cosmetic loss; 502ing a payment is a revenue loss. Never let a copy
#      edit take the checkout down again.
# test_stripe_coupon_names.py asserts (1) so the clamp in (2) stays unreachable.
STRIPE_COUPON_NAME_MAX = 40


def _coupon_name(name: str) -> str:
    """Clamp a coupon label to Stripe's 40-char limit (see note above)."""
    if len(name) <= STRIPE_COUPON_NAME_MAX:
        return name
    logger.warning("stripe.coupon_name_truncated len=%d name=%r", len(name), name)
    return name[:STRIPE_COUPON_NAME_MAX]


def tier_from_price(price_id: str) -> str | None:
    """Map a Stripe price ID to a Tapeline tier, or None if we don't know it.

    None means "unrecognised price", NOT "free". The distinction is the whole
    point: the caller must leave the tier alone rather than downgrade.

    Two reachable ways a live, paying subscription carries a price we don't
    recognise:

      * Price rotation. Founding pricing is advertised as "locked in for early
        subscribers" and the STRIPE_PRICE_* env vars were already swapped once
        at the 2026-07 reprice. A subscriber who bought before a swap still has
        the OLD price id on their Stripe subscription; every renewal fires
        customer.subscription.updated with status="active" and that old price.
      * Hand-sold anchor tiers. Team ($149/mo), Enterprise (from $2k/mo) and
        Trader ($59/mo) are created in the Stripe dashboard against price ids
        that are not in the four env vars.

    Resolving either to "free" meant the customer kept being charged while
    being locked out of every paid surface, and the admin revenue dashboard
    booked them at $0 MRR (_MRR_CONTRIBUTION has no "free" key), so the loss
    was invisible.
    """
    # An UNSET STRIPE_PRICE_* env var is the empty string, so a missing or
    # empty price id would otherwise `in`-match whichever tier is unconfigured
    # and grant it. Reject falsy ids before comparing.
    if not price_id:
        return None
    if price_id in (settings.stripe_price_pro_monthly, settings.stripe_price_pro_annual):
        return "pro"
    if price_id in (settings.stripe_price_premium_monthly, settings.stripe_price_premium_annual):
        return "premium"
    return None


def _tier_from_price(price_id: str) -> str:
    """Lossy variant for PRICING-DISPLAY paths that need a concrete tier.

    Only for computing an amount to quote (see the retention coupon path).
    Never use this to decide entitlement — use `tier_from_price` and handle
    None, or an unknown price silently becomes a downgrade.
    """
    return tier_from_price(price_id) or "free"


async def _monthly_unit_amount(tier: str) -> tuple[int, str]:
    """(unit_amount_in_minor_units, currency) for `tier`'s MONTHLY price.

    Used to value month-denominated discounts (referral credits, the win-back
    offer) in actual currency, so they can be applied as a `duration="once"`
    `amount_off` on an ANNUAL checkout. Without this, a repeating N-month
    coupon attached to a yearly price discounts the whole single annual invoice
    — Stripe applies a repeating coupon's full percent_off to every invoice
    inside its month window and never prorates within one invoice, so a
    1-month 100%-off referral credit zeroes an entire $199/yr subscription.

    Read from Stripe rather than a local constant so it can't drift from the
    real price. `unit_amount` is the plan's per-period charge in minor units
    (cents); it is populated for every standard recurring price Tapeline uses.
    """
    price_id = {
        "pro": settings.stripe_price_pro_monthly,
        "premium": settings.stripe_price_premium_monthly,
    }.get(tier)
    if not price_id:
        raise HTTPException(400, f"No monthly Stripe Price ID configured for {tier}.")
    price = await asyncio.to_thread(stripe.Price.retrieve, price_id)
    amount = getattr(price, "unit_amount", None)
    currency = getattr(price, "currency", None)
    if amount is None or currency is None:
        # Defensive: refuse rather than fall back to the exploitable repeating
        # coupon. A failed checkout the user can retry beats a free year.
        raise HTTPException(502, "Could not read the monthly price to value the discount.")
    return int(amount), str(currency)


def trial_save_offer_eligible(user: Any) -> bool:
    """Expired card-less trialist who never subscribed, never cancelled a paid
    sub (that cohort is the win-back's), and never redeemed the one-time save
    offer. Server-side gate shared by checkout, /api/me and the T+0 email so
    the offer can't be farmed and every surface agrees on who sees it.

    Deliberately NO tier check: at T+0 the hourly downgrade may not have
    flipped tier to "free" yet, but trial-expired + no Stripe customer is
    already exactly the cohort — a paying user always has a customer id.
    """
    from datetime import UTC as _UTC
    from datetime import datetime as _dt
    ends = user.trial_ends_at
    if ends is None:
        return False
    # SQLite (dev/tests) returns naive datetimes for tz-aware columns; treat
    # naive as UTC — same idiom as services/tier.is_on_trial.
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=_UTC)
    return (
        ends < _dt.now(_UTC)
        and user.stripe_customer_id is None
        and user.canceled_at is None
        and user.save_offer_redeemed_at is None
    )


async def create_checkout_session(
    user_id: str,
    user_email: str,
    tier: str,
    billing_period: str,
    success_url: str,
    cancel_url: str,
    referral_credit_months: int = 0,
    winback: bool = False,
    trial_save_offer: bool = False,
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
        # A repeating N-month coupon is only correct on a MONTHLY price, where
        # one invoice == one month. On an ANNUAL price the single yearly invoice
        # falls inside any N>=1-month window and Stripe discounts the WHOLE
        # invoice, so a 1-month referral credit would zero a $199/yr sub and the
        # win-back would take 40% off the entire year. For annual we translate
        # the month-denominated value into a fixed `amount_off` applied `once`.
        is_annual = billing_period == "annual"
        if referral_credit_months > 0:
            if is_annual:
                amount, currency = await _monthly_unit_amount(tier)
                coupon = await asyncio.to_thread(
                    stripe.Coupon.create,
                    amount_off=referral_credit_months * amount,
                    currency=currency,
                    duration="once",
                    name=_coupon_name(f"Referral credit ({referral_credit_months} mo, annual)"),
                    metadata={"user_id": user_id, "kind": "referral"},
                )
            else:
                coupon = await asyncio.to_thread(
                    stripe.Coupon.create,
                    percent_off=100,
                    duration="repeating",
                    duration_in_months=referral_credit_months,
                    name=_coupon_name(f"Referral credit ({referral_credit_months} mo)"),
                    metadata={"user_id": user_id, "kind": "referral"},
                )
            kwargs["discounts"] = [{"coupon": coupon.id}]
            sub_metadata["referral_credits_to_consume"] = str(referral_credit_months)
        elif winback:
            if is_annual:
                amount, currency = await _monthly_unit_amount(tier)
                # 40% off three months of value, applied once to the annual
                # invoice (not 40% off the whole year).
                coupon = await asyncio.to_thread(
                    stripe.Coupon.create,
                    amount_off=round(0.40 * 3 * amount),
                    currency=currency,
                    duration="once",
                    name=_coupon_name("Win-back (40% off 3 months, annual)"),
                    metadata={"user_id": user_id, "kind": "winback"},
                )
            else:
                coupon = await asyncio.to_thread(
                    stripe.Coupon.create,
                    percent_off=40,
                    duration="repeating",
                    duration_in_months=3,
                    name=_coupon_name("Win-back (40% off 3 months)"),
                    metadata={"user_id": user_id, "kind": "winback"},
                )
            kwargs["discounts"] = [{"coupon": coupon.id}]
            sub_metadata["winback"] = "1"
        elif trial_save_offer:
            # One-time trial-expiry save offer: 50% off 3 months. Extends the
            # cancel-intercept save offer (same % and duration, same
            # save_offer_redeemed_at once-per-account column) to the expired
            # card-less trialist — previously only paid cancels ever saw it.
            # Eligibility is the caller's job via trial_save_offer_eligible().
            # Redemption is marked in the subscription webhook (metadata flag
            # below), NOT here, so an abandoned checkout doesn't burn it.
            if is_annual:
                amount, currency = await _monthly_unit_amount(tier)
                # 50% off three months of value, applied once to the annual
                # invoice (not 50% off the whole year).
                coupon = await asyncio.to_thread(
                    stripe.Coupon.create,
                    amount_off=round(0.50 * 3 * amount),
                    currency=currency,
                    duration="once",
                    name=_coupon_name("Trial save (50% off 3 months, annual)"),
                    metadata={"user_id": user_id, "kind": "trial_save"},
                )
            else:
                coupon = await asyncio.to_thread(
                    stripe.Coupon.create,
                    percent_off=50,
                    duration="repeating",
                    duration_in_months=3,
                    name=_coupon_name("Trial save (50% off 3 months)"),
                    metadata={"user_id": user_id, "kind": "trial_save"},
                )
            kwargs["discounts"] = [{"coupon": coupon.id}]
            sub_metadata["trial_save_offer"] = "1"
        else:
            kwargs["allow_promotion_codes"] = True

        # Dunning prerequisite — already handled by Checkout, NOT by us.
        #
        # Smart Retries can only re-attempt a failed renewal against a payment
        # method stored ON THE SUBSCRIPTION. In mode="subscription" Checkout
        # does exactly that on its own: it attaches the collected card to the
        # customer and sets it as the subscription's default_payment_method.
        #
        # This dict used to also carry
        #   "payment_settings": {"save_default_payment_method": "on_subscription"}
        # which is a real field on Subscription.create/modify but is NOT a field
        # of a Checkout Session's subscription_data. Stripe therefore rejected
        # the ENTIRE request — "Received unknown parameter:
        # subscription_data[payment_settings]" — and the except-StripeError
        # below turned that 400 into a 502 on the customer's checkout. It
        # shipped 2026-07-18 (#363) and broke every single checkout until
        # 2026-08-24 (Sentry TAPELINE-BACKEND-20/21): no purchase, trial start,
        # or card-gate completion could succeed for 37 days.
        #
        # Do not re-add it. If a subscription ever needs non-default
        # payment_settings, apply them with Subscription.modify after the
        # customer.subscription.created webhook — never here.
        # test_checkout_subscription_data_keys.py pins the allowed key set.
        subscription_data: dict[str, Any] = {"metadata": sub_metadata}
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


def _nested(obj: Any, key: str) -> Any:
    """Read `key` off a value that may be a dict or a Stripe SDK object."""
    if obj is None:
        return None
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _sub_primary_price(sub: Any) -> Any:
    """The Price of the subscription's first line item (dict or SDK object)."""
    data = _nested(_sub_field(sub, "items"), "data")
    return _nested(data[0], "price") if data else None


def _sub_is_annual(sub: Any) -> bool:
    """True when the subscription bills on a yearly interval.

    A repeating N-month retention coupon must never be attached to a yearly
    sub: it either lands entirely outside the next annual invoice (does
    nothing) or, if the invoice is near, discounts the whole year — see
    _monthly_unit_amount for the mechanism.
    """
    return _nested(_sub_primary_price(sub), "recurring") is not None and \
        _nested(_nested(_sub_primary_price(sub), "recurring"), "interval") == "year"


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
        if _sub_is_annual(sub):
            # On a yearly sub, a repeating 3-month coupon either misses the
            # next (up to a year away) annual invoice entirely or discounts the
            # whole year — and burns the one-shot save_offer_redeemed_at flag
            # either way. Value it as 50% of three months, applied once.
            price_id = _nested(_sub_primary_price(sub), "id") or ""
            amount, currency = await _monthly_unit_amount(_tier_from_price(price_id))
            coupon = await asyncio.to_thread(
                stripe.Coupon.create,
                amount_off=round(0.50 * 3 * amount),
                currency=currency,
                duration="once",
                name=_coupon_name("Retention (50% off 3 months, annual)"),
                metadata={"customer_id": customer_id, "kind": "save_offer"},
            )
        else:
            coupon = await asyncio.to_thread(
                stripe.Coupon.create,
                percent_off=50,
                duration="repeating",
                duration_in_months=3,
                name=_coupon_name("Retention (50% off 3 months)"),
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
    # Same field move as subscription_payload: from API 2025-04-30.basil
    # `current_period_end` lives on the subscription ITEM, and the SDK pins
    # 2026-03-25.dahlia — so reading it off the Subscription returned None
    # every time and the cancellation confirmation silently dropped its
    # "access until X" date. Reuse the shared resolver.
    item = _nested(_sub_field(updated, "items"), "data") or [None]
    period_end = _period_end_ts(updated, item[0])
    if period_end:
        return datetime.fromtimestamp(period_end, UTC)
    return None


async def cancel_all_subscriptions_now(customer_id: str) -> int:
    """Immediately cancel EVERY live subscription for this customer.

    Used by account deletion (GDPR Art. 17 erasure): once the account is gone
    there is nobody to bill, so we stop charges NOW (not at period end), and we
    cover the duplicate-conversion case where a customer holds more than one
    subscription. Returns the number cancelled.

    Best-effort by design: a missing Stripe key, an unreachable Stripe, or a
    per-sub error is logged and never raised — an erasure request must complete
    regardless. The log line is the manual-follow-up hook if a cancel didn't
    land, so a deleted user is never left silently billed.
    """
    if not settings.stripe_secret_key:
        return 0
    try:
        subs = await asyncio.to_thread(
            stripe.Subscription.list, customer=customer_id, status="all", limit=100,
        )
    except stripe.error.StripeError:
        logger.exception("stripe.cancel_all_list_failed customer=%s", customer_id)
        return 0
    cancelled = 0
    for sub in list(getattr(subs, "data", None) or []):
        if _sub_field(sub, "status") in ("canceled", "incomplete_expired"):
            continue
        try:
            await asyncio.to_thread(stripe.Subscription.cancel, _sub_id(sub))
            cancelled += 1
        except stripe.error.StripeError:
            logger.exception(
                "stripe.cancel_all_failed customer=%s sub=%s",
                customer_id, _sub_id(sub),
            )
    return cancelled


def parse_webhook(payload: bytes, signature: str) -> dict[str, Any]:
    """Verify a Stripe webhook signature and return the event as a PLAIN DICT.

    Returning a dict rather than the `stripe.Event` is load-bearing, not a
    convenience. In stripe-python >= 12 (15.0.1 is installed, and
    pyproject pins only `stripe>=11.3.0` with no lock file) `StripeObject`
    is NOT a dict subclass — its MRO is literally ('StripeObject', 'object')
    and it defines no `get`, `keys`, `items` or `__iter__`. `__getitem__`
    works, so `event["type"]` reads fine, but `event.get("id")` falls through
    to `__getattr__("get")`, misses `_data`, and raises `AttributeError: get`.

    routers/webhooks.py uses `.get(...)` on the event and its nested objects in
    ~34 places, starting at the first statement after the signature check. So
    against REAL Stripe traffic the handler raised on every single delivery and
    the global handler turned it into a 500 — meaning Stripe charged the card
    and the customer was never granted their tier. Every webhook test hid this
    by monkeypatching this function to return a plain dict, which does have
    `.get()`; only the real vendor object does not. Same archetype as the
    #635 checkout outage: a mock accepting a shape the vendor rejects.

    `construct_event` still does the security-critical work — it verifies the
    HMAC over exactly these bytes and raises if it does not match — so parsing
    the same bytes with `json.loads` afterwards is verifying, then reading what
    was verified. Nothing is trusted that Stripe did not sign.
    """
    try:
        stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret,
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise HTTPException(400, f"Invalid webhook: {exc}") from exc
    # Signature verified above; re-read the same bytes as plain Python.
    parsed: dict[str, Any] = json.loads(payload)
    return parsed


def _period_end_ts(sub: Any, item: Any) -> int | None:
    """Unix timestamp for the end of the current billing period.

    Stripe MOVED this field. Up to API 2025-04-30.basil it sat on the
    Subscription; from that version on it lives on each subscription ITEM, and
    the Subscription object no longer carries it at all. The installed SDK
    (15.0.1) pins api_version 2026-03-25.dahlia — far past the move — and
    `stripe/_subscription.py` declares no `current_period_end`, while
    `stripe/_subscription_item.py` declares it at line 63.

    So `sub["current_period_end"]` raised KeyError on every real subscription
    webhook, which the global handler turned into a 500: the paid tier was
    never granted and Stripe eventually disabled the endpoint. Read the item
    first, fall back to the subscription for pre-basil payloads (and for the
    fixtures in older tests), and return None rather than raising if neither
    has it — a missing renewal date must degrade one email line, not kill the
    webhook that grants access.
    """
    for src in (item, sub):
        try:
            ts = src["current_period_end"]
        except (KeyError, TypeError):
            continue
        if ts is not None:
            return int(ts)
    return None


def subscription_payload(sub: Any) -> dict[str, Any]:
    """Extract the fields we persist from a Stripe subscription object."""
    item = sub["items"]["data"][0]
    # `_nested` on both hops: `item["price"]` and its "recurring" are plain
    # dicts when this is called from the webhook (parse_webhook coerces), but
    # StripeObjects when called with a live Subscription.retrieve result — and
    # those have no `.get()`. See parse_webhook's docstring.
    interval = _nested(_nested(item["price"], "recurring"), "interval") or "month"
    period_end_ts = _period_end_ts(sub, item)
    return {
        "id": sub["id"],
        "status": sub["status"],
        # May be None — an unrecognised price. The webhook MUST treat that as
        # "leave the tier alone", never as free. See tier_from_price.
        "tier": tier_from_price(item["price"]["id"]),
        "price_id": item["price"]["id"],
        # None when Stripe sent no period end; callers must handle it.
        "current_period_end": (
            datetime.fromtimestamp(period_end_ts, UTC) if period_end_ts else None
        ),
        "cancel_at_period_end": bool(_sub_field(sub, "cancel_at_period_end") or False),
        "billing_period": "annual" if interval == "year" else "monthly",
    }


# ── Card-expiry guard ───────────────────────────────────────────────────────
#
# WHY THIS IS NOT `customer.source.expiring`. That event was handled in
# webhooks.py from the retention work onward and could never once have fired.
# It is defined for legacy Card *Sources* attached to a Customer, and this
# account has none: on 2026-09-02 all four live customers returned
# `sources.total_count = 0` with `default_source = None`, one PaymentMethod
# each, and the single charge on the account carries `source=None`. Checkout in
# mode="subscription" mints PaymentMethods, and nothing in this codebase ever
# creates a Source. Subscribing the endpoint to the event would therefore have
# bought exactly nothing — a dead branch stays dead.
#
# `invoice.upcoming` is already subscribed, already fires before every renewal,
# and carries the renewal timestamp. That makes it the place to ask the
# question that actually matters: will the card on file still be valid on the
# day Stripe tries to charge it? The answer is knowable, and the failure it
# prevents — a silent decline twelve months after anyone last thought about
# billing — is the one that costs a paying customer.


def card_is_dead_by(card: Any, ts: int | float) -> bool:
    """True when `card` has expired by unix time `ts`.

    A card is valid through the LAST INSTANT of its expiry month — a card
    marked 09/2026 still works on 2026-09-30 — so the comparison is against
    the first instant of the following month, not against the expiry date.
    Off-by-one here means warning a customer whose card is fine, which trains
    them to ignore billing mail.

    Returns False on any card with no usable expiry rather than guessing;
    see card_on_file_for_invoice for why a payment method may have none.
    """
    month = _nested(card, "exp_month")
    year = _nested(card, "exp_year")
    if not month or not year:
        return False
    try:
        month, year = int(month), int(year)
    except (TypeError, ValueError):
        return False
    if not 1 <= month <= 12:
        return False
    dead_year, dead_month = (year + 1, 1) if month == 12 else (year, month + 1)
    dead_from = datetime(dead_year, dead_month, 1, tzinfo=UTC).timestamp()
    return ts >= dead_from


async def card_on_file_for_invoice(invoice: Any) -> dict[str, Any] | None:
    """The `card` block Stripe will actually charge for `invoice`, or None.

    Resolved in Stripe's own precedence order — the invoice's own default, then
    the subscription's, then the customer's. On a REAL upcoming invoice
    captured off this account, the first two of those are worth spelling out:

      * `invoice["default_payment_method"]` is null. It is populated only when
        someone has pinned a method to the invoice, which nothing here does.
      * `invoice["subscription"]` is ALSO null on API 2026-08-26.dahlia. The
        subscription id moved to `parent.subscription_details.subscription`,
        so reading the top-level key finds nothing and the resolution gives up
        one hop early — landing on the customer default, which is likewise
        null on all four live customers. The method that actually gets charged
        is the one on the SUBSCRIPTION, so missing this hop resolves every
        real invoice to None and the guard never fires.

    Returns None — never raises — when the method is not a card. That is not a
    hypothetical: one of the four live subscribers pays through Link, whose
    PaymentMethod has `card: null` and no expiry anywhere on it. Bank debits
    and wallets are the same. A payment method with no expiry cannot expire,
    so there is nothing to warn about and None is the correct answer.

    Any Stripe failure also yields None. This runs inside the renewal-notice
    path, and a card lookup that 500s must not take the renewal email with it.
    """
    if not settings.stripe_secret_key:
        return None

    pm_id = _nested(invoice, "default_payment_method")

    if not pm_id:
        parent = _nested(invoice, "parent") or {}
        sub_id = _nested(_nested(parent, "subscription_details"), "subscription")
        # Pre-dahlia payloads put it at the top level; read both so this keeps
        # working if the endpoint is ever pinned to an older version.
        sub_id = sub_id or _nested(invoice, "subscription")
        if sub_id:
            try:
                sub = await asyncio.to_thread(stripe.Subscription.retrieve, sub_id)
                pm_id = _sub_field(sub, "default_payment_method")
            except stripe.error.StripeError:
                logger.exception("stripe.card_lookup_subscription_failed sub=%s", sub_id)
                return None

    if not pm_id:
        customer_id = _nested(invoice, "customer")
        if customer_id:
            try:
                cust = await asyncio.to_thread(stripe.Customer.retrieve, customer_id)
                pm_id = _nested(
                    _sub_field(cust, "invoice_settings"), "default_payment_method"
                )
            except stripe.error.StripeError:
                logger.exception(
                    "stripe.card_lookup_customer_failed customer=%s", customer_id
                )
                return None

    # `default_source` is deliberately NOT consulted. It only ever holds a
    # legacy Source id, which PaymentMethod.retrieve cannot load, and this
    # account has never had one — chasing it would re-create the dead branch
    # this function exists to replace.
    if not isinstance(pm_id, str) or not pm_id.startswith("pm_"):
        if pm_id:
            logger.info("stripe.card_lookup_not_a_payment_method id=%s", pm_id)
        return None

    try:
        pm = await asyncio.to_thread(stripe.PaymentMethod.retrieve, pm_id)
    except stripe.error.StripeError:
        logger.exception("stripe.card_lookup_pm_failed pm=%s", pm_id)
        return None

    card = _sub_field(pm, "card")
    if card is None:
        logger.info(
            "stripe.card_lookup_no_card pm=%s type=%s", pm_id, _sub_field(pm, "type")
        )
        return None
    return {
        "brand": _nested(card, "display_brand") or _nested(card, "brand") or "Card",
        "last4": _nested(card, "last4") or "",
        "exp_month": _nested(card, "exp_month"),
        "exp_year": _nested(card, "exp_year"),
    }
