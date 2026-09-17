"""Webhooks from Clerk (user sync) and Stripe (billing sync)."""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.config import get_settings
from app.db import get_session
from app.models import NewsletterSubscriber, StripeWebhookEvent, Subscription, User
from app.services.billing import (
    card_is_dead_by,
    card_on_file_for_invoice,
    parse_webhook,
    subscription_has_other_paid_invoice,
    subscription_payload,
    tier_from_price,
)
from app.services.stripe_compat import stripe_field

logger = logging.getLogger(__name__)
router = APIRouter()

#: Latch for the Resend bounce/complaint webhook's missing-secret warning.
#
# Once per process, not per request. Per-request is the log spam that got the
# old 503 removed; never is what we had until 2026-09-05, when the docstring
# on `resend_webhook` was found promising a module-load warning that had never
# been written. Module scope rather than a function attribute so a test can
# reset it explicitly.
_resend_secret_warned = False


def _warn_resend_secret_missing() -> None:
    """Warn once per process that bounce/complaint handling is inert.

    This endpoint is the only thing that marks an address undeliverable. With
    no secret configured we keep mailing addresses that bounce, which quietly
    burns the sending domain's reputation — a symptom that looks nothing like
    its cause. The log names the fix so it is actionable from the line alone.
    """
    global _resend_secret_warned
    if _resend_secret_warned:
        return
    _resend_secret_warned = True
    logger.warning(
        "resend.webhook_secret_missing — bounce/complaint events are being "
        "accepted and DISCARDED. No address will be marked undeliverable "
        "while this is unset, so hard-bouncing addresses keep receiving mail "
        "and the sending domain's reputation degrades silently. "
        "Fix: fly secrets set RESEND_WEBHOOK_SECRET=<signing secret> "
        "-a tapeline-backend (Resend dashboard → Webhooks → signing secret). "
        "Logged once per process.",
    )
settings = get_settings()

# Tier precedence, mirroring services/tier.py:_ORDER. Used to pick which tier
# a user keeps when a cancelled subscription leaves other live ones behind.
_TIER_RANK = {"free": 0, "pro": 1, "premium": 2}


@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    svix_id: str | None = Header(None, alias="svix-id"),
    svix_timestamp: str | None = Header(None, alias="svix-timestamp"),
    svix_signature: str | None = Header(None, alias="svix-signature"),
) -> dict:
    """Clerk posts user.created / user.updated / user.deleted events here."""
    if not settings.clerk_webhook_secret:
        raise HTTPException(503, "CLERK_WEBHOOK_SECRET not configured")

    body = await request.body()
    headers = {
        "svix-id": svix_id or "",
        "svix-timestamp": svix_timestamp or "",
        "svix-signature": svix_signature or "",
    }
    # verify() checks the signature only; the body is parsed explicitly. See
    # the same block in resend_webhook for why its return value is not used.
    try:
        Webhook(settings.clerk_webhook_secret).verify(body, headers)
    except WebhookVerificationError as exc:
        raise HTTPException(400, f"Invalid signature: {exc}") from exc
    payload = json.loads(body)

    evt_type = payload.get("type")
    data = payload.get("data", {})

    if evt_type in ("user.created", "user.updated"):
        user_id = data["id"]
        email = (data.get("email_addresses") or [{}])[0].get("email_address", "")
        name = " ".join(filter(None, [data.get("first_name"), data.get("last_name")])) or None

        result = await session.execute(select(User).where(User.id == user_id))
        existing = result.scalar_one_or_none()
        if existing:
            existing.email = email
            existing.name = name
        else:
            session.add(User(id=user_id, email=email, name=name, tier="free"))
        await session.commit()
        logger.info("clerk.user_synced id=%s", user_id)

    elif evt_type == "user.deleted":
        user_id = data["id"]
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()
        logger.info("clerk.user_deleted id=%s", user_id)

    return {"ok": True}


async def _send_purchase_conversion(
    session: AsyncSession,
    *,
    user_id: str,
    obj: dict,
    tier: str | None = None,
    billing_period: str | None = None,
) -> None:
    """Fire the server-side `purchase` conversion for a completed checkout.

    Two destinations, each independently env-gated: GA4 Measurement Protocol
    (`services/analytics`) and the Meta Conversions API (`services/meta_capi`).
    Either, both, or neither may be configured; the shared latch below means a
    subscription is reported once per platform, and turning Meta on later
    cannot replay historical purchases.

    Once per SUBSCRIPTION, not once per event. The event-id dedup at the top
    of the webhook already blocks Stripe redelivering the *same* event, but a
    subscription can legitimately produce more than one
    `checkout.session.completed` (e.g. the duplicate-tab case handled above),
    and a conversion must not be counted twice. The latch is a synthetic row
    in `stripe_webhook_events` keyed `ga4_purchase:{subscription_id}` — the
    insert is the claim, so two concurrent deliveries can't both win. Reusing
    that table keeps this schema-free; the id column is String(80) and Stripe
    subscription ids are ~28 chars.

    `transaction_id` is the Stripe **checkout session** id — the identifier of
    this purchase, and the one a client-side beacon would carry via Stripe's
    `{CHECKOUT_SESSION_ID}` success_url template. GA4 de-duplicates purchase
    events sharing a transaction_id, so server and client can both report the
    same sale without double-counting.

    Entirely best-effort: never raises, and a no-op unless GA4_MEASUREMENT_ID
    + GA4_API_SECRET are set.
    """
    try:
        from app.services import meta_capi
        from app.services.analytics import is_configured, track_purchase

        # Two independent destinations, each separately env-gated. The latch
        # below is shared so a subscription is reported once per platform, and
        # so enabling Meta later cannot replay historical purchases.
        ga4_on = is_configured()
        meta_on = meta_capi.is_configured()
        if not ga4_on and not meta_on:
            return

        checkout_session_id = obj.get("id")
        if not checkout_session_id:
            return
        # `subscription` is an id string on the raw event, but an expanded
        # object if the API version/expansion ever changes — handle both.
        sub_raw = obj.get("subscription")
        if isinstance(sub_raw, dict):
            sub_raw = sub_raw.get("id")
        subscription_id = sub_raw or checkout_session_id

        # Claim the conversion. If the row already exists this subscription
        # has already been reported — bail without sending.
        latch_id = f"ga4_purchase:{subscription_id}"[:80]
        claimed = await session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.id == latch_id)
        )
        if claimed.scalar_one_or_none() is not None:
            logger.info("stripe.ga4_purchase_already_sent sub=%s", subscription_id)
            return
        try:
            session.add(StripeWebhookEvent(id=latch_id, event_type="ga4_purchase"))
            await session.commit()
        except Exception:
            # Concurrent delivery claimed it first — it will do the send.
            await session.rollback()
            logger.info("stripe.ga4_purchase_claim_lost sub=%s", subscription_id)
            return

        # amount_total is in the currency's minor unit (cents for USD).
        amount_total = obj.get("amount_total")
        value = (
            round(amount_total / 100, 2)
            if isinstance(amount_total, (int, float)) and not isinstance(amount_total, bool)
            else None
        )
        currency = str(obj.get("currency") or "usd").upper()
        if ga4_on:
            await track_purchase(
                user_id=user_id,
                transaction_id=str(checkout_session_id),
                value=value,
                currency=currency,
                tier=tier,
                billing_period=billing_period,
            )
        if meta_on:
            # Meta needs a hashed email for match quality; the webhook has the
            # user id, so read the address here rather than threading it
            # through every call site. Hashing happens inside meta_capi — the
            # raw address never leaves this process.
            #
            # The stored Meta click id comes along in the same read. A purchase
            # lands ~30 days after the click with no browser present, so `fbc`
            # can only be rebuilt server-side from the persisted fbclid — and
            # without it the fbclid → User → Stripe join that is the only
            # honest Meta payer count has nothing to key on.
            row = (
                await session.execute(
                    select(User.email, User.signup_fbclid, User.created_at)
                    .where(User.id == user_id)
                )
            ).one_or_none()
            email = row[0] if row else None
            purchase_fbc = meta_capi.fbc_value(row[1], row[2]) if row else None
            await meta_capi.track_purchase(
                user_id=user_id,
                transaction_id=str(checkout_session_id),
                email=email,
                value=value,
                currency=currency,
                event_source_url=meta_capi.source_url("/app/billing"),
                tier=tier,
                billing_period=billing_period,
                fbc=purchase_fbc,
            )
    except Exception:
        # Analytics must never fail a money-path webhook.
        logger.exception("stripe.ga4_purchase_failed user=%s", user_id)


_PAID_TIERS = ("pro", "premium")
_BILLING_PERIODS = ("monthly", "annual")


def _invoice_subscription_details(inv: dict) -> dict:
    """The invoice's `subscription_details` block, wherever this API version
    puts it.

    A webhook event arrives on the ENDPOINT's API version, which is not the
    version the SDK pins for the calls this app makes. The live endpoint's
    invoice events carry `api_version` 2026-04-22.dahlia (read 2026-09-14 and
    again 2026-09-15); production's stripe-python 15.6.1 makes its own API
    calls on 2026-08-26.dahlia. Both are dahlia and agree on every field read
    here: an invoice has NO top-level `subscription`; the id and the checkout
    metadata live at `parent.subscription_details.{subscription, metadata}`.
    Pre-basil payloads carried a top-level `subscription` id and
    `subscription_details.metadata`.
    """
    parent = inv.get("parent")
    if isinstance(parent, dict):
        details = parent.get("subscription_details")
        if isinstance(details, dict):
            return details
    legacy = inv.get("subscription_details")
    return legacy if isinstance(legacy, dict) else {}


def _invoice_subscription_id(inv: dict) -> str | None:
    sub = _invoice_subscription_details(inv).get("subscription") or inv.get("subscription")
    if isinstance(sub, dict):
        sub = sub.get("id")
    return sub if isinstance(sub, str) and sub else None


def _invoice_lines(inv: dict) -> list[dict]:
    data = (inv.get("lines") or {}).get("data") or []
    return [line for line in data if isinstance(line, dict)]


def _invoice_subscription_metadata(inv: dict) -> dict:
    """The metadata stamped on the subscription at checkout-session create
    (`user_id`, `tier`, `billing_period`). Falls back to the first line's copy,
    which Stripe also carries.

    Stamped ONCE, at checkout. A plan changed after that (Premium -> Pro in the
    portal, monthly -> annual) leaves it stale, so it is a fallback for the
    plan name and period, never the first source."""
    meta = _invoice_subscription_details(inv).get("metadata")
    if isinstance(meta, dict) and meta:
        return meta
    for line in _invoice_lines(inv):
        line_meta = line.get("metadata")
        if isinstance(line_meta, dict) and line_meta:
            return line_meta
    return {}


def _line_period(line: Any) -> tuple[int, int] | None:
    per = stripe_field(line, "period")
    start_ts, end_ts = stripe_field(per, "start"), stripe_field(per, "end")
    if (
        isinstance(start_ts, int)
        and isinstance(end_ts, int)
        and not isinstance(start_ts, bool)
        and not isinstance(end_ts, bool)
        and end_ts > start_ts
    ):
        return start_ts, end_ts
    return None


def _line_price_id(line: Any) -> str | None:
    """The price id an invoice line bills, in either payload shape.

    dahlia lines have NO `price` key: the id is `pricing.price_details.price`.
    Pre-basil lines carried an expanded `price` object (or a bare id)."""
    pid = stripe_field(
        stripe_field(stripe_field(line, "pricing"), "price_details"), "price"
    )
    if not pid:
        legacy = stripe_field(line, "price")
        pid = legacy if isinstance(legacy, str) else stripe_field(legacy, "id")
    return pid if isinstance(pid, str) and pid else None


def _line_plan_price_cents(line: Any) -> int | None:
    """The plan's price for one billing period on this line, in minor units:
    unit amount times quantity, BEFORE any discount. None when unknown.

    dahlia lines carry the unit amount as `pricing.unit_amount_decimal` — a
    decimal string of minor units in the webhook JSON ("1999"), a Decimal on an
    SDK object. Pre-basil lines carried `price.unit_amount_decimal` or
    `price.unit_amount`. A trial line reads "0" (live events, 2026-09-15), so
    zero means "not a price we can quote", never "free"."""
    raw = stripe_field(stripe_field(line, "pricing"), "unit_amount_decimal")
    if raw is None:
        legacy = stripe_field(line, "price")
        if legacy is not None and not isinstance(legacy, str):
            raw = stripe_field(legacy, "unit_amount_decimal")
            if raw is None:
                raw = stripe_field(legacy, "unit_amount")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        unit = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    if not unit.is_finite():
        return None
    qty = stripe_field(line, "quantity", 1)
    if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1:
        qty = 1
    cents = int((unit * qty).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return cents if cents > 0 else None


def _plan_line(lines: list[dict]) -> dict | None:
    """The line that bills the plan itself: one with a quotable unit price,
    over the longest period. Proration lines ride along as shorter extras."""
    best: dict | None = None
    best_key: tuple[bool, int] | None = None
    for line in lines:
        per = _line_period(line)
        key = (_line_plan_price_cents(line) is not None, (per[1] - per[0]) if per else 0)
        if best_key is None or key > best_key:
            best, best_key = line, key
    return best


def _billing_period_from_price(price_id: str | None) -> str | None:
    """"annual" / "monthly" for one of the four configured plan prices, else
    None (a hand-sold or rotated price). Falsy ids never match, so an unset
    STRIPE_PRICE_* env var (the empty string) can't claim one."""
    if not price_id:
        return None
    if price_id in (settings.stripe_price_pro_annual, settings.stripe_price_premium_annual):
        return "annual"
    if price_id in (settings.stripe_price_pro_monthly, settings.stripe_price_premium_monthly):
        return "monthly"
    return None


async def _resolve_invoice_account(
    session: AsyncSession, inv: dict, sub_id: str,
) -> tuple[User | None, Subscription | None]:
    """The account and Subscription row a paid invoice belongs to.

    `invoice.payment_succeeded` can land before `checkout.session.completed`
    has linked the customer, so this resolves the way the subscription branch
    does — customer id, then the `user_id` stamped into subscription metadata
    — plus the Subscription row."""
    meta = _invoice_subscription_metadata(inv)
    customer_id = inv.get("customer")
    user = None
    if customer_id:
        user = (
            await session.execute(
                select(User).where(User.stripe_customer_id == customer_id)
            )
        ).scalar_one_or_none()
    sub_row = (
        await session.execute(select(Subscription).where(Subscription.id == sub_id))
    ).scalar_one_or_none()
    if user is None and meta.get("user_id"):
        user = (
            await session.execute(select(User).where(User.id == meta["user_id"]))
        ).scalar_one_or_none()
    if user is None and sub_row is not None:
        user = (
            await session.execute(select(User).where(User.id == sub_row.user_id))
        ).scalar_one_or_none()
    return user, sub_row


async def _tell_founder_paid_invoice_unannounced(
    *,
    reason: str,
    inv: dict,
    amount_paid: int,
    currency: str,
    sub_id: str,
    user: User | None,
) -> None:
    """Founder-only: money arrived and nothing announced it. Never raises."""
    try:
        from app.services.telegram import notify_founder_paid_invoice_unannounced

        await notify_founder_paid_invoice_unannounced(
            reason=reason,
            amount=amount_paid / 100,
            currency=currency,
            email=user.email if user is not None else None,
            customer=inv.get("customer"),
            subscription=sub_id,
        )
    except Exception:
        logger.exception("stripe.founder_unannounced_alert_failed sub=%s", sub_id)


async def _welcome_on_first_paid_invoice(session: AsyncSession, inv: dict) -> bool:
    """Welcome-to-paid email + founder revenue alert, once per subscription,
    when the subscription's FIRST invoice with money on it succeeds.

    Returns True when THIS invoice was taken as the subscription's first
    payment (the latch was claimed here for it), whether or not the email was
    then delivered. The caller uses that to hold back the dunning all-clear,
    so a first charge that clears on a retry gets one billing email, not two.

    WHY HERE AND NOT ON `status == "active"`. At the end of a card-required
    trial Stripe flips the subscription to active roughly an hour before it
    attempts the first invoice. Latching the welcome on that status told two
    trial customers (2026-09-12 and 2026-09-14) "You're in — welcome to
    Tapeline Premium" and told the founder about a sale — and then both first
    charges were declined. The only event that means money arrived is a paid
    invoice with `amount_paid > 0`, and `invoice.payment_succeeded` is the one
    this account's webhook endpoint is subscribed to (enabled_events, read
    2026-09-14; `invoice.paid` is not).

    The rules, each one a case the old trigger got wrong or could get wrong:

    * $0 invoices never count. A trial start and a 100%-off referral month
      both produce a paid invoice for $0, and neither claims the latch — so
      the first real charge after them still gets its welcome.
    * Once per subscription, via the same `paid_start:{subscription}` row in
      stripe_webhook_events the status trigger used. Keeping the key is
      deliberate: subscriptions already welcomed under the old trigger stay
      welcomed, so nobody gets a second "You're in" when their first charge
      finally clears through dunning. The event-id dedup at the top of the
      handler stops a redelivery; the latch stops a later distinct invoice.
    * A paid invoice on a subscription with no latch is not automatically a
      first charge. A subscription paid for before the latch existed (one live
      Pro subscription on 2026-09-14) would be welcomed at its renewal. A
      `subscription_create` invoice is by definition the first; for any other
      billing_reason Stripe's paid-invoice history decides, and an
      already-paid subscription has the latch claimed silently. If Stripe
      cannot be asked, nothing is sent to the customer and nothing is claimed
      — a missing welcome is recoverable, a false one is not.
    * Refusing to send is not the same as staying silent. When the history is
      unavailable, or no account matches the invoice, no latch is claimed —
      and at the next renewal the history shows a paid invoice, so the latch
      is then claimed with no alert and the first sale is never announced.
      So the founder is told at once, with the amount charged, that a paid
      invoice went unannounced and why.
    * TWO AMOUNTS. The welcome states `amount_paid` as "Charged today" and the
      plan's price per period (the paid line's unit amount) separately. A
      discounted first charge (a win-back or trial-save coupon, a founder
      promo code, a referral credit) is a one-off figure: rendering it "per
      month" promised a price the next undiscounted invoice would break. The
      founder alert labels the two the same way.
    * The plan name and period come from the price the invoice actually
      bills, then the Subscription row, then the checkout metadata, then the
      account. Metadata is stamped once at checkout, so after a plan change it
      names the plan the customer left.

    Never raises: this runs inside the webhook that has to acknowledge Stripe.
    """
    first_charge = False
    try:
        amount_paid = inv.get("amount_paid")
        if (
            not isinstance(amount_paid, int)
            or isinstance(amount_paid, bool)
            or amount_paid <= 0
        ):
            return False
        sub_id = _invoice_subscription_id(inv)
        if not sub_id:
            # A one-off invoice is not a subscription starting.
            return False

        latch_id = f"paid_start:{sub_id}"[:80]
        claimed = await session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.id == latch_id)
        )
        if claimed.scalar_one_or_none() is not None:
            return False
        currency = str(inv.get("currency") or "usd").lower()

        if (inv.get("billing_reason") or "") != "subscription_create":
            prior_paid = await subscription_has_other_paid_invoice(sub_id, inv.get("id"))
            if prior_paid is None:
                logger.error(
                    "stripe.paid_welcome_undecided sub=%s invoice=%s — Stripe's "
                    "invoice history was unavailable; welcome NOT sent, founder told",
                    sub_id, inv.get("id"),
                )
                user, _ = await _resolve_invoice_account(session, inv, sub_id)
                await _tell_founder_paid_invoice_unannounced(
                    reason=(
                        "Stripe's invoice history could not be read, so this "
                        "was not confirmed as the subscription's first payment"
                    ),
                    inv=inv, amount_paid=amount_paid, currency=currency,
                    sub_id=sub_id, user=user,
                )
                return False
            if prior_paid:
                # Already a paying subscription: this is a renewal (or an
                # upgrade), not a first charge. Claim the latch so the history
                # is never consulted again for it.
                try:
                    session.add(StripeWebhookEvent(id=latch_id, event_type="paid_start"))
                    await session.commit()
                except Exception:
                    await session.rollback()
                logger.info("stripe.paid_welcome_skipped_established sub=%s", sub_id)
                return False

        user, sub_row = await _resolve_invoice_account(session, inv, sub_id)
        if user is None:
            logger.warning(
                "stripe.paid_welcome_without_user customer=%s sub=%s — founder told",
                inv.get("customer"), sub_id,
            )
            await _tell_founder_paid_invoice_unannounced(
                reason=(
                    "no Tapeline account matches this Stripe customer or the "
                    "subscription's metadata"
                ),
                inv=inv, amount_paid=amount_paid, currency=currency,
                sub_id=sub_id, user=None,
            )
            return False

        # Claim before sending: at most once, never twice.
        try:
            session.add(StripeWebhookEvent(id=latch_id, event_type="paid_start"))
            await session.commit()
        except Exception:
            await session.rollback()
            logger.info("stripe.paid_start_claim_lost sub=%s", sub_id)
            return False
        first_charge = True

        meta = _invoice_subscription_metadata(inv)
        lines = _invoice_lines(inv)
        plan_line = _plan_line(lines)
        price_id = _line_price_id(plan_line) if plan_line is not None else None

        tier = tier_from_price(price_id) if price_id else None
        if tier is None and sub_row is not None and sub_row.tier in _PAID_TIERS:
            tier = sub_row.tier
        if tier is None and meta.get("tier") in _PAID_TIERS:
            tier = meta["tier"]
        if tier is None and user.tier in _PAID_TIERS:
            # A hand-sold price: the admin grant set the account's tier.
            tier = user.tier
        # Never invent a plan name. "Welcome to Tapeline Free" after a charge
        # is false, so an unresolvable tier still alerts the founder (money
        # arrived) but does not send the customer a welcome naming a plan.
        tier_label = tier or "unknown"

        period_start = period_end = None
        for line in lines:
            per = _line_period(line)
            if per is not None and (period_end is None or per[1] > period_end):
                period_start, period_end = per
        billing_period = _billing_period_from_price(price_id)
        if (
            billing_period is None
            and sub_row is not None
            and sub_row.billing_period in _BILLING_PERIODS
        ):
            billing_period = sub_row.billing_period
        if billing_period is None and meta.get("billing_period") in _BILLING_PERIODS:
            billing_period = meta["billing_period"]
        if billing_period is None:
            long_period = (
                period_start is not None
                and period_end is not None
                and (period_end - period_start) >= 180 * 86400
            )
            billing_period = "annual" if long_period else "monthly"

        if period_end is not None:
            next_charge_iso: str | None = datetime.fromtimestamp(period_end, UTC).isoformat()
        elif sub_row is not None and sub_row.current_period_end is not None:
            next_charge_iso = sub_row.current_period_end.isoformat()
        else:
            next_charge_iso = None
        plan_price_cents = (
            _line_plan_price_cents(plan_line) if plan_line is not None else None
        )

        if tier is None:
            logger.error(
                "stripe.paid_welcome_unknown_tier user=%s sub=%s — customer "
                "welcome not sent; founder alerted",
                user.id, sub_id,
            )
        elif user.email:
            try:
                from app.services.email import (
                    render_subscription_started_email,
                    send_email,
                )

                html = render_subscription_started_email(
                    user_name=(user.name or "trader"),
                    tier=tier_label,
                    billing_period=billing_period,
                    plan_price_cents=plan_price_cents,
                    currency=currency,
                    next_charge_iso=next_charge_iso,
                    charged_today_cents=amount_paid,
                )
                subject = f"You're in — welcome to Tapeline {tier_label.capitalize()}"
                await send_email(user.email, subject, html, persona="billing")
                logger.info(
                    "stripe.welcome_to_paid_sent user=%s tier=%s billing=%s "
                    "charged=%d plan_price=%s",
                    user.id, tier_label, billing_period, amount_paid, plan_price_cents,
                )
            except Exception:
                logger.exception("stripe.welcome_to_paid_send_failed user=%s", user.id)

        # A separate try so a Resend outage on the customer's welcome email
        # can't also swallow the revenue notification — these are the two
        # things that must not share a failure mode.
        try:
            from app.services.telegram import notify_founder_new_subscription

            await notify_founder_new_subscription(
                email=user.email,
                tier=tier_label,
                billing_period=billing_period,
                amount=amount_paid / 100,
                currency=currency,
                plan_price=(
                    plan_price_cents / 100 if plan_price_cents is not None else None
                ),
            )
        except Exception:
            logger.exception("stripe.founder_alert_failed user=%s", user.id)
        return True
    except Exception:
        logger.exception("stripe.paid_welcome_failed invoice=%s", inv.get("id"))
        return first_charge


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="stripe-signature"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Stripe billing events: checkout completion, subscription changes."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(503, "STRIPE_WEBHOOK_SECRET not configured")
    if not stripe_signature:
        raise HTTPException(400, "Missing stripe-signature header")

    body = await request.body()
    event = parse_webhook(body, stripe_signature)
    evt_type = event["type"]
    obj = event["data"]["object"]

    # Idempotency: Stripe redelivers events on our 5xx, and a leaked signing
    # secret would let attackers replay events. Both are blocked by checking
    # the event id against our processed-events log.
    event_id = event.get("id")
    if event_id:
        existing = await session.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.id == event_id)
        )
        if existing.scalar_one_or_none() is not None:
            logger.info("stripe.webhook_replay event=%s type=%s", event_id, evt_type)
            return {"ok": True, "replay": True}

    if evt_type == "checkout.session.completed":
        user_id = obj.get("client_reference_id")
        customer_id = obj.get("customer")
        if user_id and customer_id:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                # A DIFFERENT customer id is not by itself a duplicate. A
                # legitimate win-back (churned to free, re-subscribes months
                # later) always mints a fresh Stripe Customer, so comparing ids
                # alone paged the founder to "cancel + refund one of the two"
                # on every single returning customer — advice that would refund
                # a valid new subscription. Only alarm when the OLD customer
                # still has a live subscription, i.e. the user really is
                # double-billed right now.
                still_live = False
                if user.stripe_customer_id and user.stripe_customer_id != customer_id:
                    live_rows = await session.execute(
                        select(Subscription).where(
                            Subscription.user_id == user.id,
                            Subscription.status.in_(("active", "trialing", "past_due")),
                        )
                    )
                    still_live = live_rows.scalars().first() is not None
                if user.stripe_customer_id and user.stripe_customer_id != customer_id:
                    # DUPLICATE CONVERSION: a second checkout completed while a
                    # different Stripe customer is already linked (two checkout
                    # tabs — each session mints its own Customer). The user is
                    # now double-subscribed on live Stripe. We adopt the newer
                    # customer (portal/cancel operate on it) — the older sub
                    # keeps flowing via the metadata fallback below so nothing
                    # is silently orphaned — and page the founder to refund/
                    # cancel the loser in the Stripe dashboard. Deliberately
                    # NOT auto-cancelling: unwinding a paid invoice is a
                    # money-path judgement call, not webhook code.
                    logger.error(
                        "stripe.duplicate_checkout user=%s old_customer=%s new_customer=%s",
                        user_id, user.stripe_customer_id, customer_id,
                    )
                    try:
                        from app.services import telegram as tg
                        chat_id = settings.inbox_founder_telegram_chat_id
                        if chat_id and settings.telegram_bot_token:
                            await tg.send_message_with_id(
                                chat_id,
                                "🚨 <b>Duplicate Stripe subscription</b>\n\n"
                                f"User <code>{user_id}</code> ({user.email}) completed a "
                                f"second checkout.\nOld customer: <code>{user.stripe_customer_id}</code>\n"
                                f"New customer: <code>{customer_id}</code>\n\n"
                                + (
                                    "A LIVE subscription is recorded on the old customer, "
                                    "so this is a real double-billing. Cancel + refund one "
                                    "of the two subscriptions in the Stripe dashboard."
                                    if still_live else
                                    "No live subscription is recorded against the old "
                                    "customer — this is also what a normal returning "
                                    "(win-back) customer looks like. Confirm in Stripe that "
                                    "only ONE subscription is active; cancel + refund the "
                                    "other only if both are."
                                ),
                                parse_mode="HTML",
                            )
                    except Exception:  # alert must never fail the webhook
                        logger.exception("stripe.duplicate_checkout_alert_failed")
                user.stripe_customer_id = customer_id
                # Snapshot the in-flight checkout intent before it's cleared
                # below — it's the only place the session object carries the
                # tier/period (Stripe puts those in subscription_data.metadata,
                # which is NOT echoed on checkout.session.completed).
                bought_tier = user.checkout_tier
                bought_period = user.checkout_billing_period
                # Checkout completed — clear the in-flight markers so the
                # abandonment-recovery worker never nudges a customer who
                # actually converted. (drip_state's "abandon1" token is left
                # as-is; it's inert once checkout_started_at is None.)
                user.checkout_started_at = None
                user.checkout_tier = None
                user.checkout_billing_period = None
                await session.commit()
                logger.info("stripe.customer_linked user=%s customer=%s", user_id, customer_id)

                # Server-side `purchase` conversion (GA4 Measurement Protocol).
                # The client-side beacon on /app/billing?checkout=success only
                # fires if that redirect-return page actually executes — a
                # closed tab, a failed redirect or an ad-blocker (high
                # prevalence in a trader audience) silently loses the
                # conversion. The webhook, by contrast, sees every charge.
                # Fire-and-forget and fully env-gated; see services/analytics.
                await _send_purchase_conversion(
                    session, user_id=user_id, obj=obj,
                    tier=bought_tier, billing_period=bought_period,
                )

    elif evt_type in ("customer.subscription.created", "customer.subscription.updated"):
        p = subscription_payload(obj)
        # Find user by stripe_customer_id
        customer_id = obj["customer"]
        result = await session.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
        if not user:
            # Fallback: resolve via the user_id we stamp into subscription
            # metadata at checkout-session create. Covers the duplicate-
            # conversion case where a second completed checkout overwrote
            # user.stripe_customer_id — the first subscription's customer no
            # longer maps to any user by column, but its metadata still names
            # the owner. Without this, that subscription's events are silently
            # dropped and it becomes unmanageable from our side.
            meta_user_id = (obj.get("metadata") or {}).get("user_id")
            if meta_user_id:
                result = await session.execute(
                    select(User).where(User.id == meta_user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    logger.warning(
                        "stripe.subscription_resolved_via_metadata customer=%s user=%s",
                        customer_id, meta_user_id,
                    )
        if not user:
            logger.warning("stripe.subscription_without_user customer=%s", customer_id)
            return {"ok": True}

        # One-time trial-expiry save offer: consumed by the subscription that
        # carries the metadata flag (stamped at checkout-session create in
        # services/billing.create_checkout_session). Marked HERE — not at
        # session create — so an abandoned checkout doesn't burn the
        # once-per-account offer. Idempotent via the None check; shares the
        # save_offer_redeemed_at column with the cancel-intercept offer so an
        # account can only ever redeem ONE of the two.
        if (
            (obj.get("metadata") or {}).get("trial_save_offer") == "1"
            and user.save_offer_redeemed_at is None
        ):
            user.save_offer_redeemed_at = datetime.now(UTC)

        # An unrecognised price resolves to tier=None, which means "we don't
        # know", NOT "free". Downgrading here would lock a still-paying
        # customer out of every paid surface (price rotation leaves old price
        # ids on live subscriptions; hand-sold Team/Enterprise/Trader prices
        # are never in the four STRIPE_PRICE_* env vars) and book them at $0
        # MRR, so the loss would be invisible. Log loudly and leave the tier
        # untouched — the founder can add the price id or set the tier by hand.
        unknown_price = p["tier"] is None
        price_id = p.pop("price_id", None)
        # For customer-facing copy and the founder notification, fall back to
        # the tier the ACCOUNT actually holds. Never render "None" at a
        # customer, and never call .capitalize() on it.
        tier_label = p["tier"] or user.tier
        if unknown_price:
            logger.error(
                "stripe.unknown_price price=%s sub=%s user=%s status=%s — tier "
                "left unchanged (add this price to STRIPE_PRICE_* or set the "
                "tier manually)",
                price_id, p["id"], user.id, p["status"],
            )

        # Upsert subscription
        sub_result = await session.execute(select(Subscription).where(Subscription.id == p["id"]))
        existing = sub_result.scalar_one_or_none()
        # No prior-status snapshot here any more. It used to exist so the paid
        # receipt could fire on a trialing -> active transition, but that misses
        # a trial whose first charge is declined (trialing -> past_due ->
        # active) and misfires on ordinary dunning recovery. The receipt and
        # the founder's revenue alert are not sent from this branch at all:
        # they wait for money, in `_welcome_on_first_paid_invoice`
        # (invoice.payment_succeeded).
        if existing:
            existing.status = p["status"]
            # Skip the tier write on an unknown price — keep what we last knew.
            if not unknown_price:
                existing.tier = p["tier"]
            # Never clobber a known-good renewal date with None. p[...] is
            # None only for a malformed event missing current_period_end on
            # both the item and the subscription; the previously stored value
            # is strictly better information than nothing.
            if p["current_period_end"] is not None:
                existing.current_period_end = p["current_period_end"]
            existing.cancel_at_period_end = p["cancel_at_period_end"]
            existing.billing_period = p["billing_period"]
        else:
            # Subscription.tier is NOT NULL, so a brand-new row for an unknown
            # price stores the user's CURRENT tier rather than inventing one.
            # That keeps a hand-sold plan (mapped to premium by an admin grant)
            # booked at its real tier instead of $0.
            new_sub = dict(p)
            if unknown_price:
                new_sub["tier"] = user.tier
            if new_sub["current_period_end"] is None:
                # Subscription.current_period_end is NOT NULL. A malformed
                # event that omits it must not become an IntegrityError — that
                # would 500 the webhook and strand a PAYING customer on free,
                # which is the exact failure this whole change removes. Store a
                # conservative placeholder and log loudly; the next renewal
                # webhook overwrites it with the real date.
                span = timedelta(days=365 if p["billing_period"] == "annual" else 31)
                new_sub["current_period_end"] = datetime.now(UTC) + span
                logger.error(
                    "stripe.missing_current_period_end sub=%s user=%s — stored placeholder",
                    p["id"], user.id,
                )
            session.add(Subscription(user_id=user.id, **new_sub))

        # Update user tier if subscription is active/trialing
        if p["status"] in ("active", "trialing"):
            # ONLY the tier write is skipped for an unrecognised price —
            # everything below (customer linking, retention bookkeeping) must
            # still run, or an unknown price would strand the account in a
            # worse state than the downgrade it replaced.
            if not unknown_price:
                user.tier = p["tier"]
            # Link the Stripe customer if we resolved this user via the metadata
            # fallback (stripe_customer_id still NULL — a first-time subscriber
            # whose checkout.session.completed hasn't been processed yet). Stripe
            # does NOT guarantee event ordering, and _downgrade_expired_trials
            # (signal_publisher.py) treats stripe_customer_id IS NULL as "never
            # paid": without this, the hourly downgrade task can drop a brand-new
            # paying subscriber back to Free in the window before checkout.session
            # .completed lands (which sets stripe_customer_id but NOT tier),
            # stranding a paying customer at Free. Only set when NULL so the
            # deliberate duplicate-conversion path (which adopts a *different*
            # already-linked customer at checkout.session.completed) is untouched.
            if user.stripe_customer_id is None:
                user.stripe_customer_id = customer_id
            # Clear stale retention bookkeeping so the cancel-intercept modal
            # and winback drip never act on dead state. Two independent flips:
            #   • un-cancel — if the sub is no longer scheduled to cancel at
            #     period end (e.g. they hit "Renew" in the Stripe portal),
            #     wipe canceled_at + winback_state. Keep them when it IS still
            #     scheduled to cancel: that's the state our /cancel endpoint
            #     just wrote and the winback clock legitimately starts from.
            #   • auto-resume — Stripe ends a pause by clearing pause_collection
            #     and firing .updated; mirror that so "Paused until X" doesn't
            #     stick around past the resume date.
            if not p["cancel_at_period_end"]:
                user.canceled_at = None
                user.winback_state = ""
            if not obj.get("pause_collection"):
                user.subscription_paused_until = None

            if p["status"] == "trialing":
                # ── Card-required trial: this is where the trial is GRANTED ──
                #
                # Signup no longer hands out a trial (routers/auth.py); a card
                # completed through Checkout does, and Stripe reports it back
                # as a `trialing` subscription. `user.tier` was already set to
                # the subscription's tier above, so all that remains is to
                # anchor the DATES to Stripe rather than to a local clock.
                #
                # trial_ends_at is copied from the SUBSCRIPTION's own
                # trial_end, which is the instant Stripe will raise the first
                # invoice. Anything in-app that states "your first charge is
                # on ..." reads this column, so the promised date and the
                # billed date are the same value by construction — even if the
                # user (or support) later shifts the trial in the dashboard,
                # because .updated lands here too.
                #
                # trial_started_at is the never-cleared "has this account ever
                # trialled" marker that gates the one-per-account check in
                # routers/billing.py. Written only when null so the mid-trial
                # card-add and every subsequent .updated leave the original
                # start instant intact.
                #
                # Replay-safe on both counts: the event-id dedupe at the top of
                # this handler drops redelivered events outright, and these two
                # writes are idempotent anyway — the same trial_end re-lands on
                # the same column, and trial_started_at is write-once.

                raw_trial_end = obj.get("trial_end")
                if raw_trial_end:
                    user.trial_ends_at = datetime.fromtimestamp(
                        int(raw_trial_end), UTC,
                    )
                first_trial = user.trial_started_at is None
                if first_trial:
                    raw_trial_start = obj.get("trial_start") or obj.get("start_date")
                    user.trial_started_at = (
                        datetime.fromtimestamp(int(raw_trial_start), UTC)
                        if raw_trial_start
                        else datetime.now(UTC)
                    )
                logger.info(
                    "stripe.trial_started user=%s sub=%s trial_ends_at=%s",
                    user.id, p["id"], user.trial_ends_at,
                )
                # Meta CAPI `StartTrial` — the event a paid campaign should
                # OPTIMISE toward. It is the earliest high-intent signal (a
                # card was entered) and the only one with any chance of
                # reaching the ~50 events/ad-set/week smart bidding needs;
                # `Purchase` is for reporting and value, not optimisation.
                #
                # Gated on `first_trial` so the write-once trial_started_at
                # column doubles as the dedupe key — every subsequent
                # `.updated` on the same subscription leaves it set and sends
                # nothing. Fire-and-forget, env-gated, never raises.
                if first_trial:
                    try:
                        from app.services import meta_capi

                        # fbc carries the Meta click id captured at signup.
                        # This event fires from a Stripe webhook days after
                        # the click with no browser present, so the value is
                        # rebuilt server-side from the stored fbclid — that is
                        # the whole reason meta_capi.fbc_value() exists.
                        # Unhashed by contract; hashing it zeroes its value.
                        await meta_capi.track_start_trial(
                            user_id=user.id, email=user.email,
                            fbc=meta_capi.fbc_value(
                                user.signup_fbclid, user.created_at,
                            ),
                            # No browser on a Stripe webhook. The checkout was
                            # started from the billing page, which is the
                            # closest true source URL available.
                            event_source_url=meta_capi.source_url("/app/billing"),
                        )
                    except Exception:
                        logger.exception("stripe.meta_start_trial_failed user=%s", user.id)
        elif p["status"] == "past_due":
            # Dunning grace window. A failed renewal flips the sub to
            # past_due while Stripe retries the card on its Smart Retries
            # schedule. Keep the customer on their paid tier the whole time
            # — yanking access mid-retry kills recovery and feels punitive
            # for what's usually an expired card or a bank fraud flag. Tier
            # only drops when retries exhaust and Stripe moves the sub to a
            # terminal status (unpaid / canceled), handled by the else below
            # and by customer.subscription.deleted.
            #
            # Same unknown-price rule as the active/trialing branch: an
            # unrecognised price means "leave the tier alone", so a dunning
            # event on a rotated or hand-sold price can't quietly downgrade a
            # customer Stripe is still trying to charge.
            if not unknown_price:
                user.tier = p["tier"]
        else:
            # Mirror the customer.subscription.deleted guard: only drop to free
            # if NO other subscription of theirs is still live. A duplicate-
            # conversion user can hold two subs; if one goes unpaid/canceled
            # (this else branch) while the other is still active and charging,
            # dropping to free strands a paying customer at Free tier. The
            # current sub was just upserted to its non-live status above, so it
            # won't match this query; excluding p["id"] is belt-and-suspenders.
            other_live = (await session.execute(
                select(Subscription).where(
                    Subscription.user_id == user.id,
                    Subscription.status.in_(("active", "trialing", "past_due")),
                    Subscription.id != p["id"],
                )
            )).scalars().all()
            if other_live:
                best = max(other_live, key=lambda s: _TIER_RANK.get(s.tier, 0))
                user.tier = best.tier
                logger.warning(
                    "stripe.subscription_downgraded_but_still_subscribed "
                    "user=%s sub=%s kept_tier=%s remaining=%d",
                    user.id, p["id"], best.tier, len(other_live),
                )
            else:
                user.tier = "free"

        # Consume referral credits ONLY on the initial .created event —
        # .updated also lands here and would otherwise double-consume from
        # the same subscription. Replay protection at the top of this
        # handler guards against duplicate deliveries of the same event_id.
        if evt_type == "customer.subscription.created":
            sub_metadata = obj.get("metadata") or {}
            try:
                to_consume = int(sub_metadata.get("referral_credits_to_consume") or 0)
            except (TypeError, ValueError):
                to_consume = 0
            if to_consume > 0 and (user.referral_credit_months or 0) > 0:
                consumed = min(to_consume, user.referral_credit_months)
                user.referral_credit_months -= consumed
                logger.info(
                    "stripe.referral_credits_consumed user=%s consumed=%d remaining=%d",
                    user.id, consumed, user.referral_credit_months,
                )

        await session.commit()
        logger.info("stripe.subscription_synced user=%s tier=%s status=%s", user.id, p["tier"], p["status"])

        # The welcome-to-paid email and the founder's revenue alert are NOT sent
        # from this branch. They wait for money: see
        # `_welcome_on_first_paid_invoice`, called from invoice.payment_succeeded.
        # A subscription's status turning "active" is not a charge — at the end
        # of a card-required trial Stripe sets it active about an hour BEFORE it
        # attempts the first invoice, and on 2026-09-12 and 2026-09-14 a trial
        # customer was told "You're in" (and the founder told of a sale) before
        # a first charge that was then declined.
        #
        # A trial START is not a purchase either. `customer.subscription.created`
        # fires with status "trialing" the moment a card-required trial begins.
        # Trials get the terms restated instead; the receipt waits for real money.
        # Latched on `existing is None` — the row insert — NOT on the event
        # type. Stripe does not guarantee ordering, and when .updated arrived
        # before .created it created the row itself, so .created then saw
        # existing != None and BOTH events declined to send: the customer got
        # no trial disclosure and no receipt, and the founder got no revenue
        # alert. The insert happens exactly once per subscription id, which is
        # precisely the "first time we ever saw this subscription" condition
        # the trial disclosure wants.
        is_trial_start = (existing is None and p["status"] == "trialing")

        if is_trial_start and user.email:
            try:
                from app.services.email import (
                    render_trial_started_email,
                    send_email,
                )
                item = obj.get("items", {}).get("data", [{}])[0]
                price = item.get("price", {}) or {}
                unit_amount = price.get("unit_amount")
                currency = (price.get("currency") or "usd").upper()
                interval = ((price.get("recurring") or {}).get("interval")) or "month"
                amount_label = (
                    f"${unit_amount / 100:.2f} {currency}/{interval}"
                    if unit_amount else "your plan's price"
                )
                trial_end_ts = obj.get("trial_end")
                if trial_end_ts:
                    from datetime import UTC as _UTC
                    from datetime import datetime as _dt
                    _end = _dt.fromtimestamp(int(trial_end_ts), tz=_UTC)
                    charge_date_label = f"{_end:%A, %B} {_end.day}"
                else:
                    charge_date_label = "when your trial ends"
                html = render_trial_started_email(
                    (user.name or "trader"),
                    tier=tier_label,
                    amount_label=amount_label,
                    charge_date_label=charge_date_label,
                )
                await send_email(
                    user.email,
                    # tier_label, NOT p["tier"]: tier_from_price returns None
                    # for an unrecognised price (a rotated/hand-sold price id),
                    # and None.capitalize() would raise here — killing the
                    # first-charge disclosure email that a card-required trial
                    # is legally required to send. tier_label is already the
                    # resolved, non-None label used everywhere else in this
                    # branch.
                    f"Your Tapeline {tier_label.capitalize()} trial has started",
                    html,
                    persona="billing",
                    skip_if_undeliverable=False,
                )
                logger.info(
                    "stripe.trial_started_email user=%s tier=%s first_charge=%s",
                    user.id, tier_label, charge_date_label,
                )
            except Exception:
                logger.exception("stripe.trial_started_email_failed user=%s", user.id)

    elif evt_type == "customer.subscription.deleted":
        customer_id = obj["customer"]
        sub_id = obj.get("id")

        # Record the cancellation on the Subscription row itself. Without
        # this the row stays "active" forever: the admin revenue dashboard
        # (routers/admin.py counts Subscription.status in active/trialing)
        # keeps billing a dead sub into MRR, and the remaining-subscription
        # check below would see a phantom live sub.
        cancelled_row: Subscription | None = None
        if sub_id:
            sub_result = await session.execute(
                select(Subscription).where(Subscription.id == sub_id)
            )
            cancelled_row = sub_result.scalar_one_or_none()
            if cancelled_row is not None:
                # Was this cancelled DURING the trial, i.e. before any money
                # moved? That changes the only thing the person actually wants
                # to know right now, so capture it before we overwrite status.
                cancelled_before_any_charge = cancelled_row.status == "trialing"
                cancelled_tier = cancelled_row.tier
                cancelled_row.status = str(obj.get("status") or "canceled")
                cancelled_row.cancel_at_period_end = False
            else:
                cancelled_before_any_charge = False
                cancelled_tier = "premium"

        result = await session.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
        if user and user.email and cancelled_before_any_charge:
            # Cancelled mid-trial: no charge was ever taken. Confirming that in
            # writing, immediately, is the difference between a person who might
            # come back and one who watches their statement expecting a charge.
            try:
                from app.services.email import (
                    render_trial_canceled_email,
                    send_email,
                )
                await send_email(
                    user.email,
                    "Your trial is cancelled — nothing was charged",
                    render_trial_canceled_email(
                        (user.name or "trader"), tier=cancelled_tier,
                    ),
                    persona="billing",
                    skip_if_undeliverable=False,
                )
                logger.info("stripe.trial_canceled_email user=%s", user.id)
            except Exception:
                logger.exception("stripe.trial_canceled_email_failed user=%s", user.id)
        if not user:
            # Same metadata fallback as the created/updated branch above: in
            # the duplicate-checkout case the older subscription's customer no
            # longer maps to any user by column, so its cancellation would be
            # dropped entirely. Fall back to the user_id we stamp into
            # subscription metadata at checkout-session create.
            meta_user_id = (obj.get("metadata") or {}).get("user_id")
            if meta_user_id:
                result = await session.execute(select(User).where(User.id == meta_user_id))
                user = result.scalar_one_or_none()
            if not user and cancelled_row is not None:
                result = await session.execute(
                    select(User).where(User.id == cancelled_row.user_id)
                )
                user = result.scalar_one_or_none()
            if user:
                logger.warning(
                    "stripe.deleted_resolved_via_fallback customer=%s user=%s sub=%s",
                    customer_id, user.id, sub_id,
                )

        if user:
            # Only drop to free if NO other subscription of theirs is still
            # live. A duplicate-conversion user holds two subs; cancelling one
            # must not strand the other (still-charging) one at Free tier.
            # past_due counts as live — the dunning branch above deliberately
            # keeps those customers on their paid tier while Stripe retries.
            conditions = [
                Subscription.user_id == user.id,
                Subscription.status.in_(("active", "trialing", "past_due")),
            ]
            if sub_id:
                conditions.append(Subscription.id != sub_id)
            remaining = await session.execute(select(Subscription).where(*conditions))
            live_subs = remaining.scalars().all()
            if live_subs:
                best = max(live_subs, key=lambda s: _TIER_RANK.get(s.tier, 0))
                user.tier = best.tier
                logger.warning(
                    "stripe.subscription_cancelled_but_still_subscribed "
                    "user=%s cancelled=%s kept_tier=%s remaining=%d",
                    user.id, sub_id, best.tier, len(live_subs),
                )
            else:
                user.tier = "free"
                logger.info("stripe.subscription_cancelled user=%s sub=%s", user.id, sub_id)

        await session.commit()

    elif evt_type == "invoice.payment_failed":
        # Card declined on a renewal charge — dunning. Email the customer a
        # fix-it link, escalating per Stripe retry attempt. Exact event
        # redeliveries are blocked by the StripeWebhookEvent dedup at the top
        # of this handler; the per-attempt `dun{n}` token in drip_state guards
        # against double-touching the same attempt across *distinct* events
        # and is wiped on recovery (invoice.payment_succeeded below).
        customer_id = obj.get("customer")
        attempt_count = int(obj.get("attempt_count") or 1)
        # Stripe nulls next_payment_attempt once it has exhausted its automatic
        # Smart Retries — that makes this the last-chance touch before the sub
        # goes terminal and the account drops to Free.
        final_attempt = obj.get("next_payment_attempt") is None
        result = await session.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
        if user and user.email:
            token = f"dun{attempt_count}"
            tokens = [t for t in (user.drip_state or "").split(",") if t]
            if token in tokens:
                logger.info(
                    "stripe.payment_failed_deduped user=%s attempt=%d",
                    user.id, attempt_count,
                )
            else:
                try:
                    from app.services.email import render_payment_failed_email, send_email

                    # Is this the charge at the END OF A TRIAL rather than a
                    # renewal? Stripe cannot tell us directly — the invoice for
                    # a trial converting carries billing_reason
                    # "subscription_cycle", exactly like an ordinary renewal.
                    # But the first charge lands ON trial_ends_at by
                    # construction, so a trial that ended within the retry
                    # window is a reliable local signal.
                    #
                    # The window is generous because Stripe retries over
                    # several days and this email is sent per attempt; the cost
                    # of being slightly wide is calling a genuine renewal a
                    # first charge for one account that started paying days
                    # ago, which is far cheaper than telling someone who has
                    # never paid that their "renewal" failed.
                    first_charge = False
                    ends = getattr(user, "trial_ends_at", None)
                    if ends is not None:
                        if ends.tzinfo is None:
                            ends = ends.replace(tzinfo=UTC)
                        age = datetime.now(UTC) - ends
                        first_charge = timedelta(0) <= age <= timedelta(days=14)

                    html = render_payment_failed_email(
                        user.name or "trader",
                        tier=user.tier or "Pro",
                        attempt_count=attempt_count,
                        final_attempt=final_attempt,
                        first_charge=first_charge,
                    )
                    subject = (
                        "Action needed: your Tapeline access is about to lapse"
                        if final_attempt
                        else "Your Tapeline payment didn't go through"
                    )
                    res = await send_email(user.email, subject, html, persona="billing")
                    # Stamp the dedup token only on a real send, mirroring the
                    # drip orchestrators — a skipped send (no RESEND key /
                    # undeliverable) leaves the token unset so a later genuine
                    # event can still try.
                    if not res.get("skipped", False):
                        user.drip_state = ",".join([*tokens, token])
                        await session.commit()
                    logger.info(
                        "stripe.payment_failed_email user=%s attempt=%d final=%s skipped=%s",
                        user.id, attempt_count, final_attempt, res.get("skipped", False),
                    )
                except Exception:
                    logger.exception("stripe.payment_failed_email_error user=%s", user.id)
        else:
            logger.warning("stripe.payment_failed_without_user customer=%s", customer_id)

    elif evt_type == "customer.subscription.trial_will_end":
        # Stripe fires this ~3 days before a trial converts to a paid charge.
        # It is the ONLY pre-charge notice a card-required trialist gets:
        # run_daily_drip is filtered to `stripe_customer_id IS NULL` (its
        # day-11/13 CTAs are signed Stripe *Checkout* links, which would open a
        # SECOND subscription for someone who already has one), so a trialist
        # with a card on file is invisible to it by design. Without this branch
        # we would collect a card and charge it with zero warning — the pattern
        # that produces chargebacks, and one this product cannot defend.
        #
        # The date and amount are read off Stripe's own subscription object, so
        # what we quote is exactly what will be charged. Replays are already
        # blocked by the StripeWebhookEvent id-dedup at the top of the handler.
        #
        # A CANCELLED TRIAL IS NOT ABOUT TO BE CHARGED. Stripe schedules this
        # event off `trial_end` and sends it regardless of
        # `cancel_at_period_end`, because a subscription set to cancel is
        # still `trialing` right up to the date. The copy below states, as
        # fact, that "the card you added is charged <amount> and Premium
        # continues" — so without this guard we tell someone who already
        # cancelled that we are about to take $199 off them. That is false, it
        # is alarming, and it is the single most likely way to convert a
        # polite non-customer into a chargeback or a complaint.
        #
        # Not hypothetical: an account created 2026-09-03 13:04 added a card
        # for the $199/year trial and cancelled at 13:07, three minutes later.
        # Its trial runs to 09-17, so this event fires on 09-14.
        #
        # Nothing is sent instead. They asked to stop, they already have the
        # cancellation confirmation, and the one thing this email exists to
        # prevent — an unexpected charge — cannot happen to them.
        # Skipped by falling through, NOT by returning early: the event-id
        # idempotency row is written at the very END of this handler, and a
        # `return` here would leave the delivery unrecorded.
        # BACKSTOP ONLY. The compliant notice now goes at SEVEN days from
        # services/email.run_trial_precharge_drip, because Visa requires "at
        # least 7 days before" and this event fires at a fixed ~3. If that drip
        # already sent for this trial it left a `pc7<YYMMDD>` token, and
        # re-sending here would be two emails about one charge. If the drip did
        # NOT run, this still fires and the customer is warned - late by Visa's
        # rule, but warned, which is the outcome that matters to them.
        already_warned = False
        trial_end_ts = obj.get("trial_end")
        if trial_end_ts:
            _tok = "pc7" + datetime.fromtimestamp(
                int(trial_end_ts), tz=UTC
            ).strftime("%y%m%d")
            _res = await session.execute(
                select(User).where(User.stripe_customer_id == obj.get("customer"))
            )
            _u = _res.scalar_one_or_none()
            if _u is not None and _tok in set((_u.drip_state or "").split(",")):
                already_warned = True
                logger.info(
                    "stripe.trial_will_end_skipped_already_warned sub=%s",
                    obj.get("id"),
                )

        cancelled = bool(obj.get("cancel_at_period_end") or obj.get("canceled_at"))
        if cancelled:
            logger.info(
                "stripe.trial_will_end_skipped_cancelled sub=%s customer=%s",
                obj.get("id"), obj.get("customer"),
            )

        customer_id = obj.get("customer")
        result = await session.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        if user and user.email and not cancelled and not already_warned:
            try:
                from datetime import datetime as _dt

                from app.services.email import (
                    render_trial_precharge_reminder_email,
                    send_email,
                )

                trial_end_ts = obj.get("trial_end")
                if trial_end_ts:
                    end_dt = _dt.fromtimestamp(int(trial_end_ts), tz=UTC)
                    charge_date_label = f"{end_dt:%A, %B} {end_dt.day}"
                else:
                    charge_date_label = "when your trial ends"

                # Price/currency off the subscription item; fall back to a
                # non-committal phrase rather than inventing a number.
                items = ((obj.get("items") or {}).get("data") or [])
                price = (items[0].get("price") or {}) if items else {}
                unit_amount = price.get("unit_amount")
                currency = str(price.get("currency") or "usd").upper()
                interval = ((price.get("recurring") or {}).get("interval")) or "month"
                if unit_amount:
                    amount_label = f"${unit_amount / 100:.2f} {currency}/{interval}"
                else:
                    amount_label = "your plan's price"

                html = render_trial_precharge_reminder_email(
                    user.name or "trader",
                    tier=(user.tier or "premium"),
                    amount_label=amount_label,
                    charge_date_label=charge_date_label,
                )
                await send_email(
                    user.email,
                    f"Your Tapeline trial ends {charge_date_label}",
                    html,
                    persona="billing",
                    skip_if_undeliverable=False,
                )
                logger.info(
                    "stripe.trial_will_end_email user=%s ends=%s amount=%s",
                    user.id, charge_date_label, amount_label,
                )
            except Exception:
                logger.exception("stripe.trial_will_end_email_error user=%s", user.id)
        else:
            logger.warning(
                "stripe.trial_will_end_without_user customer=%s", customer_id,
            )

    elif evt_type == "invoice.upcoming":
        # PRE-RENEWAL NOTICE. Stripe fires this before it creates a renewal
        # invoice, and it carries the amount it is actually about to charge.
        #
        # `customer.subscription.trial_will_end` above covers only the FIRST
        # charge. Nothing covered the ones after it — including the annual
        # renewal a year later, which is the charge most likely to be a
        # surprise and the one that produces "I forgot I ever signed up"
        # disputes. render_annual_renewal_reminder_email has existed since the
        # retention work but was reachable only from the admin preview: the
        # template was written and never given a trigger. This is the trigger.
        #
        # AMOUNT FROM THE INVOICE, never the sticker price. A grandfathered,
        # discounted or proration-adjusted subscription renews at a different
        # figure, and quoting the wrong one is worse than quoting none — the
        # renderer takes None and points at billing instead.
        customer_id = obj.get("customer")
        result = await session.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        if user and user.email:
            try:
                from app.services.email import (
                    render_annual_renewal_reminder_email,
                    send_email,
                )

                lines = (obj.get("lines") or {}).get("data") or []

                # THE INTERVAL COMES FROM THE BILLED PERIOD, not from a price
                # object. On the API version this account actually sends
                # (2026-08-26.dahlia) an invoice line has NO `price` key at
                # all: it carries `pricing.price_details.price`, a bare price
                # ID with no `recurring` block to read an interval out of.
                # Reading `line["price"]["recurring"]["interval"]` yields None
                # on every real delivery, which silently skips every email —
                # a handler that passes its tests and never sends anything.
                # `period` is on the line in every API version, is the thing
                # the customer is actually being billed for, and needs no
                # second API call to interpret. Prorations ride along as short
                # extra lines, so take the LONGEST period on the invoice.
                period_days = 0.0
                for line in lines:
                    per = line.get("period") or {}
                    start_ts, end_ts = per.get("start"), per.get("end")
                    if (
                        isinstance(start_ts, int)
                        and isinstance(end_ts, int)
                        and end_ts > start_ts
                    ):
                        period_days = max(period_days, (end_ts - start_ts) / 86400)

                ts = obj.get("next_payment_attempt") or obj.get("period_end")

                amount_due = obj.get("amount_due")
                currency = (obj.get("currency") or "usd").upper()
                amount_label = (
                    f"${amount_due / 100:.2f} {currency}"
                    if isinstance(amount_due, (int, float)) and amount_due
                    else None
                )
                renew_label = (
                    datetime.fromtimestamp(ts, tz=UTC).strftime("%d %B %Y")
                    if ts else "your next renewal date"
                )

                # ── WILL THE CARD STILL BE ALIVE ON THE DAY? ────────────────
                #
                # This replaces the `customer.source.expiring` branch that used
                # to sit further down. That event is defined for legacy Card
                # Sources; every customer on this account pays with a
                # PaymentMethod minted by Checkout, so it could never fire and
                # the branch had never once executed. The risk it was meant to
                # cover is real all the same, and worst for annual plans: one
                # charge every twelve months, a card that quietly expired in
                # between, and a decline nobody saw coming.
                #
                # Asked here because `invoice.upcoming` is already subscribed,
                # already fires ahead of every renewal, and carries the date of
                # the charge. The lead time is Stripe's, set in Billing
                # settings and measured in days rather than months, so this is
                # a last clear chance rather than an early warning — the
                # dunning ladder in invoice.payment_failed still backs it up.
                # It could not be measured from the event log: invoice.upcoming
                # was only subscribed on 2026-08-30 (#705) and had fired zero
                # times as of 2026-09-02, the first renewals being 09-12.
                #
                # Deliberately OUTSIDE the annual-only gate below. A monthly
                # subscriber's renewal reminder is suppressed as noise because
                # it says nothing they did not expect; "your card is about to
                # be declined" is not noise at any interval.
                card_warned = False
                card = await card_on_file_for_invoice(obj)
                if card and ts and card_is_dead_by(card, ts):
                    exp_label = f"{int(card['exp_month']):02d}/{card['exp_year']}"
                    # One warning per CARD, not per renewal: re-sending every
                    # cycle to someone who has chosen not to act is nagging,
                    # and the token changes the moment they put a new card on
                    # file. Guards distinct events; exact redeliveries are
                    # already stopped by the StripeWebhookEvent id-dedup above.
                    token = f"cardexp{card['exp_month']}{card['exp_year']}{card['last4']}"
                    tokens = [t for t in (user.drip_state or "").split(",") if t]
                    card_warned = True
                    if token in tokens:
                        logger.info(
                            "stripe.card_expiring_deduped user=%s exp=%s",
                            user.id, exp_label,
                        )
                    else:
                        from app.services.email import render_card_expiring_email

                        html = render_card_expiring_email(
                            user.name or "trader",
                            brand=str(card["brand"]).title(),
                            last4=str(card["last4"]),
                            exp_label=exp_label,
                            renew_date_label=renew_label,
                            amount_label=amount_label,
                        )
                        res = await send_email(
                            user.email,
                            "Your card expires before your next Tapeline renewal",
                            html,
                            persona="billing",
                            skip_if_undeliverable=False,
                        )
                        # Stamp only on a real send, mirroring the dunning
                        # branch: a skipped send must leave the token unset so
                        # a later genuine event can still try.
                        if not res.get("skipped", False):
                            user.drip_state = ",".join([*tokens, token])
                            await session.commit()
                        logger.info(
                            "stripe.card_expiring_sent user=%s exp=%s on=%s skipped=%s",
                            user.id, exp_label, renew_label,
                            res.get("skipped", False),
                        )

                # Does trial_will_end already own this charge? That branch
                # fires ~3 days before a trial converts and states the same
                # date and amount, so warning again here is two emails for one
                # payment. Decided from OUR record of the trial end rather
                # than the invoice's billing_reason: an upcoming invoice for a
                # converting trial does not reliably carry
                # `subscription_create`, and trial_ends_at is written from the
                # subscription's own trial_end, so the two refer to the same
                # instant. A year later, at the real renewal, this is long past
                # and the notice goes out normally.
                trial_end = user.trial_ends_at
                covered_by_trial_notice = bool(
                    trial_end
                    and ts
                    and abs(trial_end.timestamp() - ts) <= 2 * 86400
                )

                # MONTHLY IS DELIBERATELY SKIPPED. A monthly subscriber is
                # charged a small amount they saw twelve times a year and gets
                # a receipt every time; a reminder before each one is noise
                # that trains people to ignore billing mail — the opposite of
                # the goal. The surprise risk lives in the long intervals, and
                # so does the regulatory expectation. To include monthly,
                # lower this threshold: everything below already works for it.
                if card_warned:
                    # The card email carries this renewal's date and amount
                    # already, so the routine reminder would be a second email
                    # about one charge — and the weaker of the two.
                    logger.info(
                        "stripe.upcoming_superseded_by_card_warning user=%s", user.id
                    )
                elif period_days < 180:
                    logger.info(
                        "stripe.upcoming_skipped_short_period user=%s days=%.1f",
                        user.id, period_days,
                    )
                elif covered_by_trial_notice or (
                    (obj.get("billing_reason") or "") == "subscription_create"
                ):
                    logger.info("stripe.upcoming_skipped_trial_first user=%s", user.id)
                else:
                    html = render_annual_renewal_reminder_email(
                        user.name or "there",
                        tier=str(user.tier),
                        amount_label=amount_label,
                        renew_date_label=renew_label,
                    )
                    await send_email(
                        user.email,
                        f"Your Tapeline plan renews on {renew_label}",
                        html,
                        persona="billing",
                        skip_if_undeliverable=False,
                    )
                    logger.info(
                        "stripe.renewal_reminder_sent user=%s amount=%s on=%s",
                        user.id, amount_label, renew_label,
                    )
            except Exception:
                logger.exception("stripe.renewal_reminder_error user=%s", user.id)
        else:
            logger.warning(
                "stripe.upcoming_invoice_without_user customer=%s", customer_id
            )

    elif evt_type == "invoice.payment_succeeded":
        # A charge cleared. Most of these are routine — every monthly renewal
        # lands here — and stay silent (we don't email every successful charge;
        # Stripe's own receipt covers that). Two exceptions:
        #
        # 1. The subscription's FIRST invoice with money on it: welcome-to-paid
        #    + the founder revenue alert (`_welcome_on_first_paid_invoice`).
        # 2. A customer mid-dunning (one or more `dun{n}` tokens from failed
        #    attempts): the declined charge just recovered, so wipe the tokens
        #    and send the all-clear.
        #
        # Both can be true of one invoice — a trial whose first charge was
        # declined and then clears on a retry. The welcome is decided FIRST so
        # that case gets one email, not two. The dunning tokens are still
        # cleared either way. A trial already latched as welcomed (by the old
        # status trigger) gets the all-clear instead, so the all-clear must be
        # true for someone who has never paid before — see
        # render_payment_recovered_email.
        welcomed = await _welcome_on_first_paid_invoice(session, obj)

        customer_id = obj.get("customer")
        result = await session.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
        if user:
            tokens = [t for t in (user.drip_state or "").split(",") if t]
            dun_tokens = [t for t in tokens if t.startswith("dun")]
            if dun_tokens:
                # Clear dunning state first and commit — the state change is the
                # source of truth; the recovery email is best-effort and must
                # not be able to strand the tokens if Resend hiccups.
                user.drip_state = ",".join(t for t in tokens if not t.startswith("dun"))
                await session.commit()
                if welcomed:
                    logger.info(
                        "stripe.payment_recovered_email_skipped_first_charge "
                        "user=%s cleared=%d",
                        user.id, len(dun_tokens),
                    )
                elif user.email:
                    try:
                        from app.services.email import (
                            render_payment_recovered_email,
                            send_email,
                        )
                        html = render_payment_recovered_email(
                            user.name or "trader", tier=user.tier or "Pro",
                        )
                        await send_email(
                            user.email,
                            "Payment received — you're all set",
                            html,
                            persona="billing",
                        )
                        logger.info(
                            "stripe.payment_recovered_email user=%s cleared=%d",
                            user.id, len(dun_tokens),
                        )
                    except Exception:
                        logger.exception(
                            "stripe.payment_recovered_email_error user=%s", user.id,
                        )

    # Mark event as processed so the next delivery is treated as a replay
    if event_id:
        try:
            session.add(StripeWebhookEvent(id=event_id, event_type=evt_type))
            await session.commit()
        except Exception:
            # Concurrent delivery already inserted it — fine
            await session.rollback()

    return {"ok": True}


# ── Resend (deliverability feedback) ──────────────────────────────────────

@router.post("/resend")
async def resend_webhook(
    request: Request,
    svix_id: str | None = Header(None, alias="svix-id"),
    svix_timestamp: str | None = Header(None, alias="svix-timestamp"),
    svix_signature: str | None = Header(None, alias="svix-signature"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Handle email.bounced + email.complained from Resend.

    A hard bounce or spam complaint means the recipient address can't
    or won't receive our mail. Continuing to send eats the domain's
    sender reputation fast. We stamp `User.email_undeliverable_at` and
    `send_email` short-circuits future sends to that address.

    Newsletter subscribers live in their OWN table (most never create a
    `users` row), so the User stamp alone doesn't stop the daily Top 10
    digest — it selects on `NewsletterSubscriber.status == "confirmed"`.
    We therefore flip the subscriber row to `unsubscribed` as well, which
    is the same terminal state the one-click unsubscribe link writes.

    Resend uses Svix for webhook signing — same library as Clerk above.
    Without `RESEND_WEBHOOK_SECRET` configured the endpoint returns 200
    with `{"ok": true, "skipped": ...}`, which no-ops the webhook. The OLD
    behaviour raised a 503, which was correct on paper (the request
    couldn't be verified) but in practice Resend would retry with
    exponential backoff, each retry would 503, Sentry would log every one
    of them, and the operator would drown in spam from a config-not-set
    state rather than a real bug. A 200 is the right hand-off: Resend
    marks the event delivered, no Sentry noise, and the only consequence
    is that we miss bounce/complaint events until the secret is
    configured — which is already the state when the secret is missing.

    CORRECTED 2026-09-05. This paragraph previously claimed a 204 (it is a
    200 with a body) and, more importantly, promised: "We log once per
    process at module load (further down) instead of per-request so this
    doesn't fall off the operator's radar entirely." **There was no such
    log, anywhere in the file.** The no-op was completely silent, which is
    the failure mode the sentence was written to prevent — and the
    docstring was the only thing standing between that and someone
    noticing. `_warn_resend_secret_missing()` below now actually does it.

    Why it matters: this endpoint is the only thing that marks an address
    undeliverable. Silently skipping it means we keep mailing addresses
    that bounce, which is how a sending domain's reputation dies — and the
    symptom (delivery quietly degrading) looks nothing like the cause.

    Events we handle:
      email.bounced     — set email_undeliverable_at to now(); unsubscribe
                          any matching newsletter subscriber
      email.complained  — set email_undeliverable_at + clear all email_prefs
                          + clear marketing_opt_in (spam-flag IS opt-out);
                          unsubscribe any matching newsletter subscriber

    Other events (delivered, opened, clicked, sent, delivery_delayed)
    are ignored — they're useful for analytics later but not for this
    reputation-protection job.
    """
    if not settings.resend_webhook_secret:
        # No-op rather than 503 — see the docstring for why. But NOT silent:
        # once per process, at WARNING, naming the fix. Per-request would be
        # the log spam the 503 was removed to avoid.
        _warn_resend_secret_missing()
        return {"ok": True, "skipped": "webhook_secret_not_configured"}

    body = await request.body()
    headers = {
        "svix-id": svix_id or "",
        "svix-timestamp": svix_timestamp or "",
        "svix-signature": svix_signature or "",
    }
    # verify() checks the SIGNATURE ONLY. The body is parsed explicitly below,
    # and verify()'s return value is deliberately ignored.
    #
    # svix 2.x changed verify() to return None; 1.x returned the parsed
    # payload. pyproject pins only `svix>=1.40.0`, so production resolved
    # 2.4.0 while the local venv still had 1.91.1, and `payload.get(...)`
    # raised AttributeError on every correctly signed event. Found on
    # 2026-09-13, the day RESEND_WEBHOOK_SECRET was first set: every real
    # bounce and complaint 500'd, Resend retried and gave up, and nothing
    # was ever marked undeliverable. It hid because no test had ever sent a
    # correctly signed request. Guard:
    # tests/test_svix_webhooks_ignore_verify_return.py
    try:
        Webhook(settings.resend_webhook_secret).verify(body, headers)
    except WebhookVerificationError as exc:
        raise HTTPException(400, f"Invalid signature: {exc}") from exc
    payload = json.loads(body)

    evt_type = payload.get("type", "")
    data = payload.get("data", {}) or {}
    # Resend payloads put recipient emails on data.to as a list.
    recipients = data.get("to") or []
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [str(r).lower().strip() for r in recipients if r]

    if not recipients:
        return {"ok": True, "noop": True}

    now = datetime.now(UTC)

    affected = 0
    for addr in recipients:
        if evt_type in ("email.bounced", "email.complained"):
            # Suppress the newsletter list independently of `users` — the
            # two tables overlap only for subscribers who later signed up.
            sub_r = await session.execute(
                select(NewsletterSubscriber).where(NewsletterSubscriber.email == addr)
            )
            subscriber = sub_r.scalar_one_or_none()
            if subscriber is not None and subscriber.status != "unsubscribed":
                subscriber.status = "unsubscribed"
                subscriber.unsubscribed_at = now
                affected += 1
                logger.warning(
                    "resend.newsletter_suppressed addr=%s reason=%s", addr, evt_type,
                )

        r = await session.execute(select(User).where(User.email == addr))
        user = r.scalar_one_or_none()
        if user is None:
            continue
        if evt_type == "email.bounced":
            # Hard bounce. Address won't accept our mail again — mark
            # undeliverable so send_email short-circuits.
            if user.email_undeliverable_at is None:
                user.email_undeliverable_at = now
                affected += 1
                logger.info("resend.bounce_marked user=%s addr=%s", user.id, addr)
        elif evt_type == "email.complained":
            # User clicked "Mark as spam" in their inbox. Treat as a
            # full opt-out: kill every email_prefs bit and clear the
            # marketing-consent flag. Also stamp undeliverable so the
            # rare transactional we'd otherwise send (e.g. payment_failed)
            # also short-circuits — better to lose a transactional than
            # earn another spam complaint.
            if user.email_undeliverable_at is None:
                user.email_undeliverable_at = now
            user.email_prefs = 0
            user.marketing_opt_in = False
            affected += 1
            logger.warning(
                "resend.spam_complaint user=%s addr=%s — all prefs cleared",
                user.id, addr,
            )

    if affected:
        await session.commit()
    return {"ok": True, "type": evt_type, "affected": affected}
