"""/api/heatmap — grouped by sector, sized by volume, coloured by 1D change."""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticker

router = APIRouter()


@router.get("")
async def get_heatmap(session: AsyncSession = Depends(get_session)) -> dict:
    result = await session.execute(select(Ticker).where(Ticker.score.isnot(None)))
    tickers = result.scalars().all()

    sectors: dict[str, list] = defaultdict(list)
    for t in tickers:
        sectors[t.sector or "Other"].append({
            "symbol": t.symbol,
            "score": t.score,
            "price": t.price,
            "change_pct_1d": t.change_pct_1d,
            "volume": t.volume,
            "signal": t.signal,
        })

    # Sort tickers within each sector by volume (biggest tiles first)
    for sector in sectors.values():
        sector.sort(key=lambda x: -(x["volume"] or 0))

    return {
        "sectors": [
            {"sector": name, "tickers": items}
            for name, items in sorted(sectors.items(), key=lambda kv: -sum(t["volume"] or 0 for t in kv[1]))
        ],
    }
