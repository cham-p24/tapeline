"""GET /api/regime — current market regime snapshot."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import RegimeState

router = APIRouter()


@router.get("")
async def get_regime(session: AsyncSession = Depends(get_session)) -> dict:
    result = await session.execute(select(RegimeState).where(RegimeState.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(503, "Regime not computed yet — worker may be starting up")
    return {
        "regime": row.regime,
        "vix": row.vix,
        "dxy": row.dxy,
        "yield_10y": row.yield_10y,
        "rate_direction": row.rate_direction,
        "breadth_pct": row.breadth_pct,
        "sector_leaders": row.sector_leaders,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
