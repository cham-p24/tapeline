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
        # Card declined on a renewal charge. Email the user with a fix-it link.
        # Idempotency is already enforced by the StripeWebhookEvent dedup at
        # the top of this handler — Stripe's auto-retries for the same event_id
        # will short-circuit before reaching this branch.
        customer_id = obj.get("customer")
        attempt_count = int(obj.get("attempt_count") or 1)
        result = await session.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
        if user and user.email:
            try:
                from app.services.email import render_payment_failed_email, send_email
                html = render_payment_failed_email(
                    user.name or "trader",
                    tier=user.tier or "Pro",
                    attempt_count=attempt_count,
                )
                await send_email(
                    user.email,
                    "Your Tapeline payment didn't go through",
                    html,
                    persona="billing",
                )
                logger.info(
                    "stripe.payment_failed_email_sent user=%s attempt=%d",
                    user.id, attempt_count,
                )
            except Exception:
                logger.exception("stripe.payment_failed_email_error user=%s", user.id)
        else:
            logger.warning("stripe.payment_failed_without_user customer=%s", customer_id)

    # Mark event as processed so the next delivery is treated as a replay
    if event_id:
        try:
            session.add(StripeWebhookEvent(id=event_id, event_type=evt_type))
            await session.commit()
        except Exception:
            # Concurrent delivery already inserted it — fine
            await session.rollback()

    return {"ok": True}
