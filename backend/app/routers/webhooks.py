"""Webhooks from Clerk (user sync) and Stripe (billing sync)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.config import get_settings
from app.db import get_session
from app.models import StripeWebhookEvent, Subscription, User
from app.services.billing import parse_webhook, subscription_payload

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


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
                user.stripe_customer_id = customer_id
                # Checkout completed — clear the in-flight markers so the
                # abandonment-recovery worker never nudges a customer who
                # actually converted. (drip_state's "abandon1" token is left
                # as-is; it's inert once checkout_started_at is None.)
                user.checkout_started_at = None
                user.checkout_tier = None
                user.checkout_billing_period = None
                await session.commit()
                logger.info("stripe.customer_linked user=%s customer=%s", user_id, customer_id)

    elif evt_type in ("customer.subscription.created", "customer.subscription.updated"):
        p = subscription_payload(obj)
        # Find user by stripe_customer_id
        customer_id = obj["customer"]
        result = await session.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
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
                # Pull amount + billing period inline from the Stripe payload.
                # subscription_payload() doesn't capture them — they're only
                # needed for the receipt line in the email, not the DB row.
                item = obj.get("items", {}).get("data", [{}])[0]
                price = item.get("price", {}) or {}
                amount_cents = price.get("unit_amount") or None
                currency = (price.get("currency") or "usd").lower()
                interval = (price.get("recurring") or {}).get("interval", "month")
                billing_period = "annual" if interval == "year" else "monthly"
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
        result = await session.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
        if user:
            user.tier = "free"
            await session.commit()
            logger.info("stripe.subscription_cancelled user=%s", user.id)

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
      email.bounced     — set email_undeliverable_at to now()
      email.complained  — set email_undeliverable_at + clear all email_prefs
                          + clear marketing_opt_in (spam-flag IS opt-out)

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
