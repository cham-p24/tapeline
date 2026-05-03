"""/api/ipos and /api/earnings — calendar endpoints."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import EarningsEvent, IPOEvent

ipo_router = APIRouter()
earnings_router = APIRouter()


@ipo_router.get("")
async def list_ipos(
    session: AsyncSession = Depends(get_session),
    days: int = Query(90, ge=1, le=365),
    status: str | None = None,
) -> dict:
    cutoff = date.today() + timedelta(days=days)
    stmt = select(IPOEvent).where(IPOEvent.expected_date <= cutoff).order_by(IPOEvent.expected_date)
    if status:
        stmt = stmt.where(IPOEvent.status == status)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": r.id,
                "symbol": r.symbol,
                "company_name": r.company_name,
                "sector": r.sector,
                "exchange": r.exchange,
                "expected_date": r.expected_date.isoformat(),
                "price_low": r.price_low,
                "price_high": r.price_high,
                "shares_offered": r.shares_offered,
                "status": r.status,
                "lead_underwriter": r.lead_underwriter,
                "description": r.description,
            }
            for r in rows
        ],
    }


@earnings_router.get("")
async def list_earnings(
    session: AsyncSession = Depends(get_session),
    days: int = Query(14, ge=1, le=90),
    symbol: str | None = None,
) -> dict:
    today = date.today()
    cutoff = today + timedelta(days=days)
    stmt = (
        select(EarningsEvent)
        .where(EarningsEvent.report_date >= today, EarningsEvent.report_date <= cutoff)
        .order_by(EarningsEvent.report_date)
    )
    if symbol:
        stmt = stmt.where(EarningsEvent.symbol == symbol.upper())
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": r.id,
                "symbol": r.symbol,
                "report_date": r.report_date.isoformat(),
                "report_time": r.report_time,
                "fiscal_quarter": r.fiscal_quarter,
                "eps_estimate": r.eps_estimate,
                "eps_actual": r.eps_actual,
                "revenue_estimate_m": r.revenue_estimate_m,
                "revenue_actual_m": r.revenue_actual_m,
                "surprise_pct": r.surprise_pct,
            }
            for r in rows
        ],
    }
