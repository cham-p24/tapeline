"""/api/news — latest market news (cached) + per-ticker filter."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import NewsItem

router = APIRouter()

# Bound the per-ticker headline scan to recent news (mirrors
# routers/ticker.py::NEWS_LOOKBACK_DAYS). Defense-in-depth for the 2026-06-01
# death-spiral: `tickers LIKE '%SYM%'` is a leading-wildcard filter, so this
# caps the worst case INDEPENDENTLY of the pg_trgm index — a symbol rare in
# recent news can never trigger a full-table walk here, even if the index is
# ever absent. Unlike /api/ticker this endpoint had no such bound.
NEWS_LOOKBACK_DAYS = 90


@router.get("")
async def list_news(
    session: AsyncSession = Depends(get_session),
    symbol: str | None = None,
    limit: int = Query(30, ge=1, le=100),
) -> dict:
    stmt = select(NewsItem).order_by(desc(NewsItem.published_at)).limit(limit)
    if symbol:
        cutoff = datetime.now(UTC) - timedelta(days=NEWS_LOOKBACK_DAYS)
        stmt = (
            select(NewsItem)
            .where(
                NewsItem.tickers.like(f"%{symbol.upper()}%"),
                NewsItem.published_at >= cutoff,
            )
            .order_by(desc(NewsItem.published_at))
            .limit(limit)
        )
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
