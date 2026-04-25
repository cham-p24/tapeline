"""/api/news — latest market news (cached) + per-ticker filter."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import NewsItem

router = APIRouter()


@router.get("")
async def list_news(
    session: AsyncSession = Depends(get_session),
    symbol: str | None = None,
    limit: int = Query(30, ge=1, le=100),
) -> dict:
    stmt = select(NewsItem).order_by(desc(NewsItem.published_at)).limit(limit)
    if symbol:
        stmt = select(NewsItem).where(NewsItem.tickers.like(f"%{symbol.upper()}%")) \
            .order_by(desc(NewsItem.published_at)).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": n.id,
                "title": n.title,
                "publisher": n.publisher,
                "published_at": n.published_at.isoformat(),
                "url": n.url,
                "description": n.description,
                "tickers": n.tickers.split(",") if n.tickers else [],
                "sentiment": n.sentiment,
            }
            for n in rows
        ],
    }
