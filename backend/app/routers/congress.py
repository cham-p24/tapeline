"""GET /api/congress — recent congressional trades."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import CongressTrade

router = APIRouter()


@router.get("")
async def list_congress(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
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
