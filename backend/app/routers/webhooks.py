"""Webhooks from Clerk (user sync) and Stripe (billing sync)."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

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
    subscription_payload,
)

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
            # lands ~14 days after the click with no browser present, so `fbc`
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
        # active) and misfires on ordinary dunning recovery. `is_paid_start`
        # below latches "has this subscription ever been active" instead.
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

        # Welcome-to-paid email. Fires ONCE on the first time we ever see this
        # specific subscription (`existing` was None going into the upsert)
        # AND only on the .created event (not .updated, which fires on every
        # downstream change). Replay protection at the top of the handler
        # already covers duplicate webhook deliveries.
        # Fire-and-forget — a Resend outage must not fail the webhook.
        # A trial START is not a purchase. `customer.subscription.created` fires
        # with status "trialing" the moment a card-required trial begins, and the
        # welcome-to-paid receipt below would tell someone who has paid nothing
        # that they are "in" on a paid plan — a receipt for a charge that never
        # happened, and the shortest path to an "I never agreed to pay" dispute.
        # Trials get the terms restated instead; the receipt waits for real money.
        # Latched on `existing is None` — the row insert — NOT on the event
        # type. Stripe does not guarantee ordering, and when .updated arrived
        # before .created it created the row itself, so .created then saw
        # existing != None and BOTH events declined to send: the customer got
        # no trial disclosure and no receipt, and the founder got no revenue
        # alert. The insert happens exactly once per subscription id, which is
        # precisely the "first time we ever saw this subscription" condition
        # these emails want.
        is_trial_start = (existing is None and p["status"] == "trialing")
        # The first REAL charge on this subscription.
        #
        # NOT `prior_status == "trialing"`. That reads the IMMEDIATELY PRIOR
        # status, and a trial whose first charge is declined converts as
        #     trialing -> past_due -> active
        # so by the time it reaches active the prior status is past_due and the
        # customer got no receipt while the founder got no revenue alert — for
        # a sale that did complete, just not on the first card attempt. Stripe
        # retries for days, so this is an ordinary outcome, not an edge case.
        #
        # The honest question is "has this subscription EVER been active
        # before", which the row cannot answer: it stores only the last status.
        # So latch it, reusing the stripe_webhook_events idempotency table the
        # ga4_purchase claim already uses — same mechanism, no migration.
        #
        # This also fixes the reverse error. `past_due -> active` on an
        # established subscription is ordinary dunning RECOVERY, not a new
        # sale; it already has its own email (render_payment_recovered_email).
        # A naive "prior_status in (trialing, past_due)" would have sent a
        # fresh receipt and pinged the founder about new revenue every time a
        # long-standing subscriber's card recovered.
        is_paid_start = False
        if p["status"] == "active":
            paid_latch = f"paid_start:{p['id']}"[:80]
            already = await session.execute(
                select(StripeWebhookEvent).where(StripeWebhookEvent.id == paid_latch)
            )
            if already.scalar_one_or_none() is None:
                try:
                    session.add(
                        StripeWebhookEvent(id=paid_latch, event_type="paid_start")
                    )
                    await session.flush()
                    is_paid_start = True
                except Exception:
                    # A concurrent delivery claimed it; that one sends.
                    await session.rollback()
                    logger.info("stripe.paid_start_claim_lost sub=%s", p["id"])

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
                    # branch (see the paid-start subject below).
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

        if is_paid_start and user.email:
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
                # p["current_period_end"] already resolved the basil field move
                # (item first, subscription second). Reading obj[...] directly
                # here raised KeyError on every real event, and the bare except
                # turned that into a silently missing next-charge date on the
                # customer's receipt.
                next_charge_iso = (
                    p["current_period_end"].isoformat()
                    if p["current_period_end"] is not None
                    else None
                )
                html = render_subscription_started_email(
                    user_name=(user.name or "trader"),
                    tier=tier_label,
                    billing_period=billing_period,
                    amount_cents=amount_cents,
                    currency=currency,
                    next_charge_iso=next_charge_iso,
                )
                subject = f"You're in — welcome to Tapeline {tier_label.capitalize()}"
                await send_email(user.email, subject, html, persona="billing")
                logger.info(
                    "stripe.welcome_to_paid_sent user=%s tier=%s billing=%s",
                    user.id, tier_label, billing_period,
                )
            except Exception:
                logger.exception("stripe.welcome_to_paid_send_failed user=%s", user.id)

            # Tell the founder, on the same once-per-subscription branch. A
            # separate try so a Resend outage on the customer's welcome email
            # can't also swallow the revenue notification — these are the two
            # things that must not share a failure mode.
            try:
                from app.services.telegram import notify_founder_new_subscription

                sub_item = (obj.get("items", {}).get("data") or [{}])[0]
                sub_price = sub_item.get("price", {}) or {}
                unit_amount = sub_price.get("unit_amount")
                await notify_founder_new_subscription(
                    email=user.email,
                    tier=tier_label,
                    billing_period=p["billing_period"],
                    amount=(unit_amount / 100) if unit_amount else None,
                    currency=sub_price.get("currency") or "usd",
                )
            except Exception:
                logger.exception("stripe.founder_alert_failed user=%s", user.id)

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
        if user and user.email and not cancelled:
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
