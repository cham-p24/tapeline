"""Referral tracking — "Refer a friend, both get a free month" growth engine."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
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
        # Credits still unused — both parties earn 1 month on signup; the
        # credit is consumed at next paid checkout via a one-shot Stripe
        # coupon (see services/billing.create_checkout_session).
        "credit_months": user.referral_credit_months or 0,
        "months_earned": signed_up,  # one earned per friend who signed up
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


def _mask_referrer(u: User | None, *, is_caller: bool) -> str:
    """Privacy-preserving label for a leaderboard row.

    The caller always sees themselves as "You". Everyone else is masked —
    "Sam P." when a full name is on file, first name alone when it's a single
    token, otherwise a masked email local-part (mirrors the /me endpoint's
    masking). Never exposes a full name or address to another user.
    """
    if is_caller:
        return "You"
    if u is None:
        return "A Tapeline user"
    name = (u.name or "").strip()
    if name:
        parts = name.split()
        if len(parts) >= 2 and parts[-1]:
            return f"{parts[0]} {parts[-1][0]}."
        return parts[0]
    local = u.email.split("@")[0] if u.email else ""
    return (local[:2] + "***") if local else "A Tapeline user"


@router.get("/leaderboard")
async def referral_leaderboard(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Top referrers by confirmed signups — privacy-preserving social proof.

    Returns the top 10 (masked) plus the caller's own rank and count even when
    they're outside the top 10, so the page can always render "you're #N".
    Open to every logged-in user — referrals aren't tier-gated.
    """
    rows = (
        await session.execute(
            select(User.referred_by, func.count().label("n"))
            .where(User.referred_by.is_not(None))
            .group_by(User.referred_by)
            .order_by(func.count().desc())
        )
    ).all()
    ranked = [(rid, n) for rid, n in rows if rid]
    if not ranked:
        return {
            "leaderboard": [],
            "your_rank": None,
            "your_signups": 0,
            "total_referrers": 0,
        }

    top = ranked[:10]
    needed_ids = {rid for rid, _ in top} | {user.id}
    resolved = (
        await session.execute(select(User).where(User.id.in_(list(needed_ids))))
    ).scalars().all()
    users_by_id = {u.id: u for u in resolved}

    leaderboard = [
        {
            "rank": i,
            "display": _mask_referrer(users_by_id.get(rid), is_caller=(rid == user.id)),
            "is_you": rid == user.id,
            "signups": n,
        }
        for i, (rid, n) in enumerate(top, start=1)
    ]

    your_rank: int | None = None
    your_signups = 0
    for i, (rid, n) in enumerate(ranked, start=1):
        if rid == user.id:
            your_rank, your_signups = i, n
            break

    return {
        "leaderboard": leaderboard,
        "your_rank": your_rank,
        "your_signups": your_signups,
        "total_referrers": len(ranked),
    }
