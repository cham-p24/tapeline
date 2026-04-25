"""Admin-only endpoints: tier adjustments, user lookup."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import AlertEvent, Subscription, User

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


async def require_admin(request: Request, session: AsyncSession = Depends(get_session)):
    """
    Admin auth: either (a) logged-in user with is_admin=True, or (b) legacy
    X-Admin-Key header. Returns the admin User object when available.
    """
    from app.services.auth import current_user_optional

    user = await current_user_optional(request, session)
    if user and user.is_admin:
        return user

    admin_key = getattr(settings, "admin_api_key", None) or ""
    if admin_key and request.headers.get("X-Admin-Key") == admin_key:
        return None

    raise HTTPException(401, "Admin access required")


class TierPatch(BaseModel):
    tier: str  # "free" | "pro" | "premium"


@router.get("/users")
async def list_users(
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
) -> dict:
    result = await session.execute(select(User).limit(limit))
    users = result.scalars().all()
    return {
        "count": len(users),
        "items": [{"id": u.id, "email": u.email, "tier": u.tier, "created_at": u.created_at.isoformat()} for u in users],
    }


@router.patch("/users/{user_id}/tier")
async def set_user_tier(
    user_id: str,
    body: TierPatch,
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "User not found")
    if body.tier not in ("free", "pro", "premium"):
        raise HTTPException(400, "Invalid tier")
    user.tier = body.tier
    await session.commit()
    logger.info("admin.tier_set user=%s tier=%s", user_id, body.tier)
    return {"ok": True, "user_id": user_id, "tier": body.tier}


@router.get("/stats")
async def platform_stats(
    _: None = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    users_total = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
    pro_count = (await session.execute(select(func.count()).select_from(User).where(User.tier == "pro"))).scalar() or 0
    premium_count = (await session.execute(select(func.count()).select_from(User).where(User.tier == "premium"))).scalar() or 0
    active_subs = (await session.execute(
        select(func.count()).select_from(Subscription).where(Subscription.status.in_(("active", "trialing")))
    )).scalar() or 0
    alerts_delivered = (await session.execute(
        select(func.count()).select_from(AlertEvent).where(AlertEvent.delivered.is_(True))
    )).scalar() or 0
    return {
        "users_total": users_total,
        "users_pro": pro_count,
        "users_premium": premium_count,
        "active_subscriptions": active_subs,
        "alerts_delivered": alerts_delivered,
        "mrr_usd": pro_count * 29 + premium_count * 49,
    }
