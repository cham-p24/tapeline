"""GET /api/squeeze — current BB squeeze setups."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import SqueezeSetup

router = APIRouter()


@router.get("")
async def list_squeezes(
    session: AsyncSession = Depends(get_session),
    min_score: float = Query(0, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
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
