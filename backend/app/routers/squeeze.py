"""GET /api/squeeze — current BB squeeze setups. Pro+ only.

Pre-2026-05-16 this was anonymous-readable. Locked down to match
services/tier.FEATURES["squeeze.full"].
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import SqueezeSetup, User
from app.services.auth import current_user_required
from app.services.tier import Tier, has_feature

router = APIRouter()

# How many squeeze setups the FREE "taste" endpoint returns. Small on purpose:
# enough for a free user to find ONE name worth adding to their watchlist (the
# activation on-ramp), not enough to replace the paid Squeeze Watch feed.
FREE_SQUEEZE_PREVIEW_LIMIT = 3


@router.get("/preview")
async def squeeze_preview(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
) -> dict:
    """Read-only top-3 squeeze setups — a FREE discovery taste.

    Rationale (activation): Tapeline's #1 problem is that free users never add
    their OWN ticker. A hard 403 on every discovery tool leaves them with
    nothing to act on. This gives ANY logged-in user (Free included) a tiny,
    read-only slice of Squeeze Watch so they can find a name worth adding
    instead of bouncing. The full feed (GET /api/squeeze) stays Pro-gated.

    Requires login (not anonymous) so it never re-opens the anonymous scrape
    surface the main feed was locked down to close — the free taste is a
    logged-in activation nudge, not a public endpoint.
    """
    stmt = (
        select(SqueezeSetup)
        .order_by(desc(SqueezeSetup.spike_score))
        .limit(FREE_SQUEEZE_PREVIEW_LIMIT)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "preview": True,
        "limit": FREE_SQUEEZE_PREVIEW_LIMIT,
        "items": [
            {
                "symbol": r.symbol,
                "spike_score": r.spike_score,
                "squeeze_days": r.squeeze_days,
                "breakout_type": r.breakout_type,
                "reason": r.reason,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }


@router.get("")
async def list_squeezes(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
    min_score: float = Query(0, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    if not has_feature(Tier(user.tier), "squeeze.full"):
        raise HTTPException(403, "Squeeze scanner is a Pro feature")
    stmt = (
        select(SqueezeSetup)
        .where(SqueezeSetup.spike_score >= min_score)
        .order_by(desc(SqueezeSetup.spike_score))
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "symbol": r.symbol,
                "spike_score": r.spike_score,
                "squeeze_days": r.squeeze_days,
                "volume_multiple": r.volume_multiple,
                "obv_trend": r.obv_trend,
                "breakout_type": r.breakout_type,
                "suggested_window": r.suggested_window,
                "reason": r.reason,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }
