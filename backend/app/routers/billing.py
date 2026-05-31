"""Stripe billing endpoints."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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


@router.post("/checkout")
async def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(current_user_required),
) -> dict:
    if body.tier not in ("pro", "premium"):
        raise HTTPException(400, "tier must be 'pro' or 'premium'")
    if body.billing_period not in ("monthly", "annual"):
        raise HTTPException(400, "billing_period must be 'monthly' or 'annual'")
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
    )
    return {"url": url}


@router.post("/portal")
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


@router.post("/save-offer")
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
    return {
        "ok": True,
        "message": "Done — your next 3 months are 50% off. Same plan, half the price.",
    }


@router.post("/pause")
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


@router.post("/resume")
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


@router.post("/cancel")
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
