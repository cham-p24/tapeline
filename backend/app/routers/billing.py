"""Stripe billing endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.services.auth import current_user_required
from app.services.billing import create_checkout_session, create_portal_session

router = APIRouter()
settings = get_settings()


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
