"""Stripe billing endpoints."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.services.auth import current_user_required
from app.services.billing import (
    apply_save_offer_coupon,
    create_checkout_session,
    create_portal_session,
    pause_subscription,
    resume_subscription,
    set_cancel_at_period_end,
)
from app.services.email_checkout import verify_checkout_token
from app.services.rate_limit import limit_strict
from app.services.tier import is_on_trial

router = APIRouter()
settings = get_settings()

# Exit-survey reason codes accepted by POST /cancel. Anything else is coerced
# to "other" so a stale frontend can't 422 a user out of cancelling.
_CANCEL_REASONS = frozenset(
    {
        "too_expensive",
        "not_using",
        "missing_feature",
        "found_alternative",
        "trial_only",
        "technical_issues",
        "other",
    }
)


class CheckoutRequest(BaseModel):
    tier: str = "pro"                     # "pro" or "premium"
    billing_period: str = "monthly"        # "monthly" or "annual"


@router.post("/checkout", dependencies=[Depends(limit_strict)])
async def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if body.tier not in ("pro", "premium"):
        raise HTTPException(400, "tier must be 'pro' or 'premium'")
    if body.billing_period not in ("monthly", "annual"):
        raise HTTPException(400, "billing_period must be 'monthly' or 'annual'")
    # Double-billing guard (mirrors the email-checkout guard below): a user
    # whose paid tier is live on Stripe already has a subscription — Checkout
    # always mints a NEW Stripe Customer + subscription, so letting a
    # subscriber through here double-bills them and the webhook can only page
    # the founder to refund it after the money moved. Keyed on paid tier AND
    # linked customer, NOT bare stripe_customer_id: churned users keep their
    # customer id (tier already dropped to "free") and must still be able to
    # check out again — the win-back path below depends on it. Trial users
    # have no stripe_customer_id, so they pass through untouched.
    if user.stripe_customer_id and user.tier in ("pro", "premium"):
        raise HTTPException(
            409,
            "You already have an active subscription — contact support to switch plans.",
        )
    url = await create_checkout_session(
        user_id=user.id,
        user_email=user.email,
        tier=body.tier,
        billing_period=body.billing_period,
        # Params are read by the frontend trial_converted Vercel Analytics event
        # in /app/billing — keep `checkout=success` + tier + billing_period in
        # sync with app/app/billing/page.tsx.
        success_url=f"{settings.app_url}/app/billing?checkout=success&tier={body.tier}&billing_period={body.billing_period}",
        cancel_url=f"{settings.app_url}/app/billing?checkout=cancelled",
        # Pass the user's unspent referral credits; the billing service mints
        # a one-shot 100%-off coupon for that many months when > 0.
        referral_credit_months=user.referral_credit_months or 0,
        # Returning-customer 40%-off offer (day-90 win-back email). Gated
        # server-side on "actually churned" — cancelled AND already dropped to
        # free — so the ?winback=1 link can't be farmed by an active user, and
        # it mirrors exactly who receives the wb90 email. Referral credit, if
        # any, takes precedence inside create_checkout_session.
        winback=(user.tier == "free" and user.canceled_at is not None),
        # Mid-trial card-add: forward the user's remaining trial so Stripe
        # starts billing when the trial was always going to end, instead of
        # charging today and silently forfeiting the free days the "Keep
        # Premium — add a card" emails promised. The service drops it when
        # under Stripe's 48h trial_end minimum.
        trial_end=user.trial_ends_at
        if is_on_trial(user.tier, user.trial_ends_at, user.stripe_customer_id)
        else None,
    )
    # Mark the checkout as in-flight for abandonment recovery. If the user
    # never completes, the hourly worker (run_checkout_abandonment_recovery)
    # emails a one-shot resume nudge ~1-24h later; checkout.session.completed
    # clears checkout_started_at, so a converted user is never nudged. Stripping
    # the "abandon1" token re-arms the nudge for this fresh attempt even if a
    # prior abandoned checkout already consumed it. Stamped only after the
    # session minted successfully (a Stripe error above raises before this).
    user.checkout_started_at = datetime.now(UTC)
    user.checkout_tier = body.tier
    user.checkout_billing_period = body.billing_period
    user.drip_state = ",".join(
        t for t in (user.drip_state or "").split(",") if t and t != "abandon1"
    )
    await session.commit()
    return {"url": url}


@router.get("/email-checkout", dependencies=[Depends(limit_strict)])
async def email_checkout(
    # Deliberately tolerant params: mail clients line-wrap and rewrite long
    # URLs, and FastAPI validation failures return raw 422 JSON BEFORE the
    # handler's graceful fallback can run. So no required params, no pattern
    # constraints — bad values are coerced/redirected inside the handler.
    token: str = Query(""),
    tier: str = Query("premium"),
    period: str = Query("monthly"),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """One-click checkout from a conversion email — no login required.

    The trial-drip emails are the only touchpoint that reaches a bounced trial
    user, and their CTA used to land behind the login wall (a password the
    user forgot two weeks ago). This endpoint verifies the signed token from
    the email and 303s straight into Stripe Checkout for that user's account.

    The token grants NO session — it can only open a checkout page bound to
    its own user (worst case for a forwarded email: someone pays FOR the
    user). Every failure path degrades to a marketing page, never an error.

    Deliberately side-effect-free besides the Stripe session: email scanners
    (Outlook SafeLinks, Gmail) prefetch GET links, so this path must NOT stamp
    checkout_started_at / re-arm the abandonment nudge the way POST /checkout
    does — a scanner prefetch would otherwise queue a spurious "finish
    checking out" email at every send.
    """
    fallback = f"{settings.app_url}/pricing?src=email_link"
    # Coerce (not reject) mangled tier/period — the token is what proves
    # identity; a truncated tier param shouldn't cost the conversion.
    if tier not in ("pro", "premium"):
        tier = "premium"
    if period not in ("monthly", "annual"):
        period = "monthly"
    user_id = verify_checkout_token(token)
    if user_id is None:
        # Missing/expired/tampered link — somewhere they can still convert.
        return RedirectResponse(fallback, status_code=303)

    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        return RedirectResponse(fallback, status_code=303)
    if user.stripe_customer_id:
        # Already has billing set up (subscribed after the email went out, or
        # an old link) — the in-app billing page is the right surface; a fresh
        # checkout here could double-subscribe them.
        return RedirectResponse(f"{settings.app_url}/app/billing", status_code=303)

    try:
        url = await create_checkout_session(
            user_id=user.id,
            user_email=user.email,
            tier=tier,
            billing_period=period,
            # PUBLIC success/cancel pages — this flow's whole premise is a
            # user with no session (forgot password), and /app/* sits behind
            # the login-wall middleware. Bouncing a PAYING customer to /signin
            # (success) or dead-ending a hesitant one (cancel) recreates the
            # exact friction this endpoint exists to remove. /checkout/success
            # fires the trial_converted + subscribe analytics events that
            # /app/billing fires for the authed flow.
            success_url=f"{settings.app_url}/checkout/success?tier={tier}&billing_period={period}&src=email",
            cancel_url=f"{settings.app_url}/pricing?src=email_checkout_cancelled",
            referral_credit_months=user.referral_credit_months or 0,
            winback=(user.tier == "free" and user.canceled_at is not None),
            # Same mid-trial preservation as POST /checkout — this endpoint
            # IS the "Keep Premium — add a card" email CTA, so it's the path
            # a day-3 trial user most likely arrives through.
            trial_end=user.trial_ends_at
            if is_on_trial(user.tier, user.trial_ends_at, user.stripe_customer_id)
            else None,
            # Shrink the completable window from ~24h to Stripe's 30-min
            # minimum: each email carries TWO tier links, and the double-
            # subscribe guard above only runs at session-CREATE time — a
            # long-lived second tab must not be able to complete a second
            # subscription a day later.
            expires_in_minutes=30,
        )
    except Exception:
        # Stripe hiccup — degrade to the pricing page, never a raw 500 from an
        # email click.
        import logging

        logging.getLogger(__name__).exception(
            "billing.email_checkout_session_failed user=%s", user.id
        )
        return RedirectResponse(fallback, status_code=303)
    return RedirectResponse(url, status_code=303)


@router.post("/portal", dependencies=[Depends(limit_strict)])
async def open_portal(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not user.stripe_customer_id:
        raise HTTPException(400, "No billing account yet — subscribe first")
    url = await create_portal_session(
        customer_id=user.stripe_customer_id,
        return_url=f"{settings.app_url}/app/billing",
    )
    return {"url": url}


# ── Retention: cancel intercept (save offer → pause → exit survey) ──────────


class PauseRequest(BaseModel):
    months: int = 1  # 1, 2, or 3


class CancelRequest(BaseModel):
    reason: str = "other"
    feedback: str | None = None


def _require_paid(user: User) -> None:
    """Cancel/pause/save only apply to a real Stripe subscription. Trial users
    (no customer id) just let the trial lapse — surface a clear 400 instead."""
    if not user.stripe_customer_id:
        raise HTTPException(400, "No paid subscription to manage yet.")


@router.get("/retention-options")
async def retention_options(user: User = Depends(current_user_required)) -> dict:
    """State the cancel-intercept modal needs to decide what to offer.

    `save_offer_available` gates the one-time 50%-off-3-months card.
    `paused_until` / `canceled_at` let the modal reflect an in-flight pause
    or scheduled cancellation rather than re-offering the same actions.
    """
    return {
        "has_subscription": bool(user.stripe_customer_id),
        "tier": user.tier,
        "save_offer_available": user.save_offer_redeemed_at is None,
        "paused_until": user.subscription_paused_until.isoformat()
        if user.subscription_paused_until
        else None,
        "canceled_at": user.canceled_at.isoformat() if user.canceled_at else None,
    }


@router.post("/save-offer", dependencies=[Depends(limit_strict)])
async def accept_save_offer(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Accept the one-time 50%-off-for-3-months retention coupon."""
    _require_paid(user)
    if user.save_offer_redeemed_at is not None:
        raise HTTPException(409, "You've already used this offer.")
    await apply_save_offer_coupon(user.stripe_customer_id)
    now = datetime.now(UTC)
    user.save_offer_redeemed_at = now
    # They're staying — wipe any in-flight cancellation + winback bookkeeping.
    user.canceled_at = None
    user.winback_state = ""
    await session.commit()

    # Transactional confirmation — fire-and-forget so a Resend hiccup never
    # 500s the save-offer accept. No List-Unsubscribe header: it's account
    # state (a billing change the user just made), not marketing.
    if user.email:
        try:
            from app.services.email import render_save_offer_accepted_email, send_email

            html = render_save_offer_accepted_email(
                user.name or "trader",
                tier=user.tier,
            )
            await send_email(
                user.email,
                "Your Tapeline discount is applied — 50% off for 3 months",
                html,
                persona="billing",
            )
        except Exception:  # email must never block the save-offer accept
            import logging

            logging.getLogger(__name__).exception(
                "billing.save_offer_email_failed user=%s", user.id
            )

    return {
        "ok": True,
        "message": "Done — your next 3 months are 50% off. Same plan, half the price.",
    }


@router.post("/pause", dependencies=[Depends(limit_strict)])
async def pause(
    body: PauseRequest,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Pause billing for 1-3 months instead of cancelling."""
    _require_paid(user)
    resumes_at = await pause_subscription(user.stripe_customer_id, body.months)
    user.subscription_paused_until = resumes_at
    user.canceled_at = None
    user.winback_state = ""
    await session.commit()
    return {"ok": True, "resumes_at": resumes_at.isoformat()}


@router.post("/resume", dependencies=[Depends(limit_strict)])
async def resume(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Resume a paused subscription immediately."""
    _require_paid(user)
    await resume_subscription(user.stripe_customer_id)
    user.subscription_paused_until = None
    await session.commit()
    return {"ok": True}


@router.post("/cancel", dependencies=[Depends(limit_strict)])
async def cancel(
    body: CancelRequest,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Schedule cancellation at period end + capture the exit survey.

    We keep the customer on their tier until the paid period ends (Stripe
    cancel_at_period_end). canceled_at drives the 30/60/90-day winback drip;
    reason/feedback feed the churn dashboard.
    """
    _require_paid(user)
    period_end = await set_cancel_at_period_end(user.stripe_customer_id)
    now = datetime.now(UTC)
    user.canceled_at = now
    user.winback_state = ""  # fresh cancellation → eligible for winback again
    reason = body.reason if body.reason in _CANCEL_REASONS else "other"
    user.cancellation_reason = reason
    feedback = (body.feedback or "").strip()
    user.cancellation_feedback = feedback[:1000] or None
    await session.commit()

    # Transactional confirmation — fire-and-forget so a Resend hiccup never
    # 500s the cancel. No List-Unsubscribe header: it's account state, not
    # marketing.
    if user.email:
        try:
            from app.services.email import render_subscription_canceled_email, send_email

            html = render_subscription_canceled_email(
                user.name or "trader",
                tier=user.tier,
                period_end_iso=period_end.isoformat() if period_end else None,
            )
            await send_email(
                user.email,
                "Your Tapeline plan is set to cancel",
                html,
                persona="billing",
            )
        except Exception:  # email must never block the cancel
            import logging

            logging.getLogger(__name__).exception(
                "billing.cancel_email_failed user=%s", user.id
            )

    return {
        "ok": True,
        "period_end": period_end.isoformat() if period_end else None,
    }
