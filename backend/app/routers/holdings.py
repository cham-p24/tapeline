"""GET /api/holdings — elite-fund 13F institutional holdings (Premium-only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import InstitutionalHolding, User
from app.services.auth import current_user_required
from app.services.tier import Tier, has_feature

router = APIRouter()


@router.get("")
async def list_holdings(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
    symbol: str | None = Query(None, description="Filter to one ticker"),
    fund: str | None = Query(None, description="Filter to one fund (substring match)"),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """
    Latest 13F holdings for the eight tracked elite funds.
    Refreshed every 24h via Quiver (mock fallback when no API key).
    Premium-only.
    """
    if not has_feature(Tier(user.tier), "holdings.elite"):
        raise HTTPException(403, "Elite institutional holdings require Premium tier")

    stmt = select(InstitutionalHolding).order_by(desc(InstitutionalHolding.value_usd))
    if symbol:
        stmt = stmt.where(InstitutionalHolding.symbol == symbol.upper())
    if fund:
        stmt = stmt.where(InstitutionalHolding.fund_name.ilike(f"%{fund}%"))
    stmt = stmt.limit(limit)

    rows = (await session.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": h.id,
                "fund_name": h.fund_name,
                "manager": h.manager,
                "cik": h.cik,
                "symbol": h.symbol,
                "value_usd": h.value_usd,
                "shares": h.shares,
                "percent_portfolio": h.percent_portfolio,
                "fetched_at": h.fetched_at.isoformat(),
            }
            for h in rows
        ],
    }


@router.get("/funds")
async def list_funds(
    user: User = Depends(current_user_required),
) -> dict:
    """List the elite funds being tracked. Premium-only."""
    if not has_feature(Tier(user.tier), "holdings.elite"):
        raise HTTPException(403, "Elite institutional holdings require Premium tier")
    from app.services.quiver_feed import get_tracked_funds
    return {"items": get_tracked_funds()}
