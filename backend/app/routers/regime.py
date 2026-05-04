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

    # Look up SPY's 5-day change as the momentum input for Fear & Greed.
    # SPY is in every reasonable scoring universe; if missing we fall back
    # to None and the F&G calc treats that as neutral.
    from app.models import Ticker
    from app.services.fear_greed import compute_fear_greed
    spy_q = await session.execute(select(Ticker.change_pct_5d).where(Ticker.symbol == "SPY"))
    spy_5d = spy_q.scalar_one_or_none()

    fear_greed = compute_fear_greed(
        vix=row.vix,
        breadth_pct=row.breadth_pct,
        regime=row.regime,
        spy_change_5d_pct=spy_5d,
    )

    return {
        "regime": row.regime,
        "vix": row.vix,
        "dxy": row.dxy,
        "yield_10y": row.yield_10y,
        "rate_direction": row.rate_direction,
        "breadth_pct": row.breadth_pct,
        "sector_leaders": row.sector_leaders,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "fear_greed": fear_greed,
    }
