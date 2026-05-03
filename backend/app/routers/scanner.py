"""GET /api/scanner — paginated ticker list with filters + tier gating."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticker, User
from app.services.auth import current_user_optional
from app.services.tier import Tier
from app.services.tier import limit as tier_limit

router = APIRouter()


@router.get("")
async def list_scanner(
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(current_user_optional),
    min_score: float = Query(0, ge=0, le=100),
    max_score: float = Query(100, ge=0, le=100),
    signal: str | None = None,
    sector: str | None = None,
    sort: str = Query("score", pattern="^(score|change_pct_1d|change_pct_5d|change_pct_1m|volume|symbol)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    # Tier gating — free users get a capped row count + stale timestamps
    tier = Tier(user.tier) if user else Tier.FREE
    row_cap = tier_limit(tier, "scanner_rows")  # free=10, pro/elite=1000
    if limit > row_cap:
        limit = row_cap
    stmt = select(Ticker).where(
        Ticker.score.isnot(None),
        Ticker.score >= min_score,
        Ticker.score <= max_score,
    )
    if signal:
        stmt = stmt.where(Ticker.signal == signal)
    if sector:
        stmt = stmt.where(Ticker.sector == sector)

    col = getattr(Ticker, sort)
    stmt = stmt.order_by(desc(col) if order == "desc" else col)
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Read the delay from tier.py (Free is 1440 = 24 hours; Pro/Premium = 0)
    # so the timestamp display matches what /how-it-works and /pricing advertise.
    delay_minutes = tier_limit(tier, "data_delay_minutes")
    return {
        "count": len(rows),
        "tier": tier.value,
        "row_cap": row_cap,
        "data_delayed_minutes": delay_minutes,
        "items": [
            {
                "symbol": r.symbol,
                "name": r.name,
                "sector": r.sector,
                "asset_class": r.asset_class,
                "score": r.score,
                "signal": r.signal,
                "price": r.price,
                "change_pct_1d": r.change_pct_1d,
                "change_pct_5d": r.change_pct_5d,
                "change_pct_1m": r.change_pct_1m,
                "volume": r.volume,
                "sub_trend": r.sub_trend,
                "sub_rs": r.sub_rs,
                "sub_fundamentals": r.sub_fundamentals,
                "sub_momentum": r.sub_momentum,
                "sub_macro": r.sub_macro,
                "sub_smart_money": r.sub_smart_money,
                "confidence_pct": r.confidence_pct,
                "reason": r.reason,
                "updated_at": (
                    (r.updated_at - timedelta(minutes=delay_minutes)).isoformat()
                    if r.updated_at and delay_minutes
                    else (r.updated_at.isoformat() if r.updated_at else None)
                ),
            }
            for r in rows
        ],
    }
