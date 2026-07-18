"""Webhooks from Clerk (user sync) and Stripe (billing sync)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.config import get_settings
from app.db import get_session
from app.models import NewsletterSubscriber, StripeWebhookEvent, Subscription, User
from app.services.billing import parse_webhook, subscription_payload

logger = logging.getLogger(__name__)
router = APIRouter()
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
    try:
        payload = Webhook(settings.clerk_webhook_secret).verify(body, headers)
    except WebhookVerificationError as exc:
        raise HTTPException(400, f"Invalid signature: {exc}") from exc

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
    """Fire the server-side GA4 `purchase` event for a completed checkout.

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
        from app.services.analytics import is_configured, track_purchase

        if not is_configured():
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
        await track_purchase(
            user_id=user_id,
            transaction_id=str(checkout_session_id),
            value=value,
            currency=currency,
            tier=tier,
            billing_period=billing_period,
        )
    except Exception:
        # Analytics must never fail a money-path webhook.
        logger.exception("stripe.ga4_purchase_failed user=%s", user_id)


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
                                "Cancel + refund one of the two subscriptions in the "
                                "Stripe dashboard.",
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

        # Upsert subscription
        sub_result = await session.execute(select(Subscription).where(Subscription.id == p["id"]))
        existing = sub_result.scalar_one_or_none()
        if existing:
            existing.status = p["status"]
            existing.tier = p["tier"]
            existing.current_period_end = p["current_period_end"]
            existing.cancel_at_period_end = p["cancel_at_period_end"]
            existing.billing_period = p["billing_period"]
        else:
            session.add(Subscription(user_id=user.id, **p))

        # Update user tier if subscription is active/trialing
        if p["status"] in ("active", "trialing"):
            user.tier = p["tier"]
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
        elif p["status"] == "past_due":
            # Dunning grace window. A failed renewal flips the sub to
            # past_due while Stripe retries the card on its Smart Retries
            # schedule. Keep the customer on their paid tier the whole time
            # — yanking access mid-retry kills recovery and feels punitive
            # for what's usually an expired card or a bank fraud flag. Tier
            # only drops when retries exhaust and Stripe moves the sub to a
            # terminal status (unpaid / canceled), handled by the else below
            # and by customer.subscription.deleted.
            user.tier = p["tier"]
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

        # Welcome-to-paid email. Fires ONCE on the first time we ever see this
        # specific subscription (`existing` was None going into the upsert)
        # AND only on the .created event (not .updated, which fires on every
        # downstream change). Replay protection at the top of the handler
        # already covers duplicate webhook deliveries.
        # Fire-and-forget — a Resend outage must not fail the webhook.
        if (
            evt_type == "customer.subscription.created"
            and existing is None
            and p["status"] in ("active", "trialing")
            and user.email
        ):
            try:
                from app.services.email import (
                    render_subscription_started_email,
                    send_email,
                )
                # Pull amount + currency inline for the receipt line — these
                # aren't persisted on the Subscription row, so subscription_
                # payload() doesn't capture them. billing_period it does, so
                # reuse p["billing_period"] rather than re-deriving the interval.
                item = obj.get("items", {}).get("data", [{}])[0]
                price = item.get("price", {}) or {}
                amount_cents = price.get("unit_amount") or None
                currency = (price.get("currency") or "usd").lower()
                billing_period = p["billing_period"]
                next_charge_iso: str | None = None
                try:
                    from datetime import UTC, datetime
                    next_charge_iso = datetime.fromtimestamp(
                        obj["current_period_end"], UTC,
                    ).isoformat()
                except Exception:
                    next_charge_iso = None
                html = render_subscription_started_email(
                    user_name=(user.name or "trader"),
                    tier=p["tier"],
                    billing_period=billing_period,
                    amount_cents=amount_cents,
                    currency=currency,
                    next_charge_iso=next_charge_iso,
                )
                subject = f"You're in — welcome to Tapeline {p['tier'].capitalize()}"
                await send_email(user.email, subject, html, persona="billing")
                logger.info(
                    "stripe.welcome_to_paid_sent user=%s tier=%s billing=%s",
                    user.id, p["tier"], billing_period,
                )
            except Exception:
                logger.exception("stripe.welcome_to_paid_send_failed user=%s", user.id)

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
                cancelled_row.status = str(obj.get("status") or "canceled")
                cancelled_row.cancel_at_period_end = False

        result = await session.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
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
                    html = render_payment_failed_email(
                        user.name or "trader",
                        tier=user.tier or "Pro",
                        attempt_count=attempt_count,
                        final_attempt=final_attempt,
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

    elif evt_type == "customer.source.expiring":
        # The card on file expires at month-end. Proactively nudge an update
        # BEFORE the next renewal declines into dunning — cheaper to keep a
        # customer than to recover one. Replays are blocked by the
        # StripeWebhookEvent id-dedup at the top of this handler. The event's
        # data.object IS the card (top-level brand/last4/exp_*, with a nested
        # "card" fallback for source-shaped payloads).
        customer_id = obj.get("customer")
        result = await session.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
        if user and user.email:
            try:
                from app.services.email import render_card_expiring_email, send_email
                nested = obj.get("card") or {}
                brand = str(obj.get("brand") or nested.get("brand") or "Card")
                last4 = str(obj.get("last4") or nested.get("last4") or "")
                exp_month = obj.get("exp_month") or nested.get("exp_month")
                exp_year = obj.get("exp_year") or nested.get("exp_year")
                exp_label = (
                    f"{int(exp_month):02d}/{exp_year}" if exp_month and exp_year else "soon"
                )
                html = render_card_expiring_email(
                    user.name or "trader", brand=brand, last4=last4, exp_label=exp_label,
                )
                await send_email(
                    user.email,
                    "Your card on file is about to expire",
                    html,
                    persona="billing",
                )
                logger.info("stripe.card_expiring_email user=%s exp=%s", user.id, exp_label)
            except Exception:
                logger.exception("stripe.card_expiring_email_error user=%s", user.id)
        else:
            logger.warning("stripe.card_expiring_without_user customer=%s", customer_id)

    elif evt_type == "invoice.payment_succeeded":
        # A renewal charge cleared. Most of these are routine — every monthly
        # renewal lands here — so we act ONLY when the customer was mid-dunning
        # (carries one or more `dun{n}` tokens from prior failed attempts). In
        # that case the declined charge just recovered: send the all-clear and
        # wipe the dunning tokens so the next episode starts clean. No token =
        # ordinary renewal = stay silent (we don't email every successful
        # charge — Stripe's own receipt covers that).
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
                if user.email:
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
    Without `RESEND_WEBHOOK_SECRET` configured the endpoint returns 204
    No Content, which silently no-ops the webhook. The OLD behaviour
    raised a 503, which was correct on paper (the request couldn't be
    verified) but in practice Resend would retry with exponential
    backoff, each retry would 503, Sentry would log every one of them,
    and the operator would drown in spam from a config-not-set state
    rather than a real bug. 204 is the right hand-off: Resend marks the
    event delivered, no Sentry noise, and the only consequence is that
    we miss bounce/complaint events until the secret is configured —
    which is already the existing state when the secret is missing.

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
        # Silent no-op rather than 503. See docstring above for the why.
        # We log once per process at module load (further down) instead of
        # per-request so this doesn't fall off the operator's radar entirely.
        return {"ok": True, "skipped": "webhook_secret_not_configured"}

    body = await request.body()
    headers = {
        "svix-id": svix_id or "",
        "svix-timestamp": svix_timestamp or "",
        "svix-signature": svix_signature or "",
    }
    try:
        payload = Webhook(settings.resend_webhook_secret).verify(body, headers)
    except WebhookVerificationError as exc:
        raise HTTPException(400, f"Invalid signature: {exc}") from exc

    evt_type = payload.get("type", "")
    data = payload.get("data", {}) or {}
    # Resend payloads put recipient emails on data.to as a list.
    recipients = data.get("to") or []
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [str(r).lower().strip() for r in recipients if r]

    if not recipients:
        return {"ok": True, "noop": True}

    from datetime import UTC, datetime
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
