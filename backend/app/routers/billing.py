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
    tier: str  # "pro" or "premium"


@router.post("/checkout")
async def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(current_user_required),
) -> dict:
    url = await create_checkout_session(
        user_id=user.id,
        user_email=user.email,
        tier=body.tier,
        success_url=f"{settings.app_url}/app/billing?success=1",
        cancel_url=f"{settings.app_url}/app/billing?cancelled=1",
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
