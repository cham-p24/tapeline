"""GET /api/ticker/{symbol} — detailed single-ticker view with breakdown + news."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import NewsItem, SqueezeSetup, Ticker
from app.services.news_feed import fetch_news_for_ticker

router = APIRouter()


@router.get("/{symbol}")
async def ticker_detail(
    symbol: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Complete view of a single ticker — score breakdown, squeeze status, news."""
    symbol = symbol.upper()

    # Core ticker
    result = await session.execute(select(Ticker).where(Ticker.symbol == symbol))
    t = result.scalar_one_or_none()
    if t is None:
        raise HTTPException(404, f"Ticker {symbol} not in scanner universe")

    # Squeeze setup if present
    sq_result = await session.execute(select(SqueezeSetup).where(SqueezeSetup.symbol == symbol))
    sq = sq_result.scalar_one_or_none()

    # News — prefer cached, fall back to live fetch
    news_result = await session.execute(
        select(NewsItem)
        .where(NewsItem.tickers.like(f"%{symbol}%"))
        .order_by(desc(NewsItem.published_at))
        .limit(8)
    )
    news_rows = news_result.scalars().all()
    if not news_rows:
        try:
            live = await fetch_news_for_ticker(symbol, limit=8)
            news_rows = [_DictNews(**n) for n in live]  # type: ignore[arg-type]
        except Exception:
            news_rows = []

    return {
        "symbol": t.symbol,
        "name": t.name,
        "sector": t.sector,
        "asset_class": t.asset_class,
        "price": t.price,
        "score": t.score,
        "signal": t.signal,
        "change_pct_1d": t.change_pct_1d,
        "change_pct_5d": t.change_pct_5d,
        "change_pct_1m": t.change_pct_1m,
        "volume": t.volume,
        "reason": t.reason,
        "breakdown": {
            "trend": {"value": t.sub_trend, "weight": 25, "label": "Trend"},
            "rs": {"value": t.sub_rs, "weight": 20, "label": "Relative strength"},
            "fundamentals": {"value": t.sub_fundamentals, "weight": 15, "label": "Fundamentals"},
            "smart_money": {"value": t.sub_smart_money, "weight": 15, "label": "Smart money"},
            "macro": {"value": t.sub_macro, "weight": 15, "label": "Macro"},
            "momentum": {"value": t.sub_momentum, "weight": 10, "label": "Momentum"},
        },
        "squeeze": None if sq is None else {
            "spike_score": sq.spike_score,
            "squeeze_days": sq.squeeze_days,
            "volume_multiple": sq.volume_multiple,
            "obv_trend": sq.obv_trend,
            "breakout_type": sq.breakout_type,
            "suggested_window": sq.suggested_window,
            "reason": sq.reason,
        },
        "news": [
            {
                "id": n.id,
                "title": n.title,
                "publisher": n.publisher,
                "published_at": n.published_at.isoformat() if hasattr(n.published_at, "isoformat") else str(n.published_at),
                "url": n.url,
                "sentiment": getattr(n, "sentiment", None),
            }
            for n in news_rows
        ],
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


class _DictNews:
    """Tiny adapter so live-fetched news items render through the same serializer."""
    def __init__(self, **kw): self.__dict__.update(kw)
