"""GET /api/congress — recent congressional trades. Premium-only.

Pre-2026-05-16 this route was anonymous-readable, which leaked the
Premium-only Congress feed to anyone hitting the API directly even
though the frontend gates the /app/congress page. Fixed by requiring
auth + checking the canonical `congress.feed` flag from services/tier.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import CongressTrade, User
from app.services.auth import current_user_required
from app.services.tier import Tier, has_feature

router = APIRouter()


@router.get("")
async def list_congress(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    if not has_feature(Tier(user.tier), "congress.feed"):
        raise HTTPException(403, "Congressional trades are a Premium feature")
    stmt = (
        select(CongressTrade)
        .order_by(desc(CongressTrade.disclosed_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": r.id,
                "politician": r.politician,
                "chamber": r.chamber,
                "party": r.party,
                "symbol": r.symbol,
                "direction": r.direction,
                "amount_min": r.amount_min,
                "amount_max": r.amount_max,
                "trade_date": r.trade_date.isoformat(),
                "disclosed_at": r.disclosed_at.isoformat(),
            }
            for r in rows
        ],
    }
