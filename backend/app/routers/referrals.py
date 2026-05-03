"""Referral tracking — "Give a month, get a month" growth engine."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.services.auth import current_user_required

router = APIRouter()
settings = get_settings()


@router.get("/me")
async def my_referral_stats(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Referral code + who I've referred + conversion count."""
    # Who I've referred
    referred_q = await session.execute(
        select(User).where(User.referred_by == user.id)
    )
    referred = referred_q.scalars().all()
    signed_up = len(referred)
    converted = sum(1 for u in referred if u.tier in ("pro", "premium") and not u.trial_ends_at)

    # Build share URL — works even before domain is registered
    share_url = f"{settings.app_url}/signup?ref={user.referral_code}" if user.referral_code else None

    return {
        "referral_code": user.referral_code,
        "share_url": share_url,
        "signed_up": signed_up,
        "converted": converted,
        "months_earned": converted,  # 1 free month per paid conversion
        "referred_users": [
            {
                "email": u.email[:3] + "***" + u.email[u.email.index("@"):],  # privacy-preserving
                "tier": u.tier,
                "converted": u.tier in ("pro", "premium") and not u.trial_ends_at,
                "joined": u.created_at.isoformat() if u.created_at else None,
            }
            for u in referred[:20]
        ],
    }
