"""/api/heatmap — grouped by sector, sized by volume, coloured by 1D change.

Pro+ feature per services/tier.FEATURES["heatmap"]. Locked down 2026-05-16
so Free / signed-out visitors can't bypass via direct API call.

Sector cleanup (2026-05-16): the raw heatmap had 51 distinct sector labels
because the upstream feeds (Finnhub `/stock/profile2` and the signal-
system Google Sheet) return granular sub-industries and inconsistent casing
("Health Care" vs "Healthcare", "Biotechnology" as its own bucket, etc.).
We now normalize through services/sector.canonical_sector() into the 11
GICS top-level sectors plus three Tapeline buckets (Commodities, Funds &
ETFs, Uncategorized). This collapses the 51 raw labels into 13 — much
better tile density and an actually-usable heatmap.

Search (2026-05-16): optional `q` query param filters tiles to symbols
matching the (case-insensitive, substring) query. Empty sectors are
dropped from the response so the UI doesn't render headers with zero
tiles underneath. The frontend uses this for the heatmap search box.
"""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticker, User
from app.services.auth import current_user_required
from app.services.sector import CANONICAL_ORDER, canonical_sector
from app.services.tier import Tier, has_feature

router = APIRouter()


@router.get("")
async def get_heatmap(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
    q: str | None = Query(None, max_length=20, description="Optional symbol substring filter"),
) -> dict:
    if not has_feature(Tier(user.tier), "heatmap"):
        raise HTTPException(403, "Heatmap is a Pro feature")
    result = await session.execute(select(Ticker).where(Ticker.score.isnot(None)))
    tickers = result.scalars().all()

    # Server-side symbol filter — cheaper than shipping all 1,700 tiles to the
    # client and filtering in JS. Substring match so "AAP" matches AAPL, AAP,
    # AAPB; case-insensitive so users don't have to think about uppercase.
    needle = (q or "").strip().upper()
    if needle:
        tickers = [t for t in tickers if needle in t.symbol]

    sectors: dict[str, list] = defaultdict(list)
    for t in tickers:
        bucket = canonical_sector(t.sector, t.asset_class)
        sectors[bucket].append({
            "symbol": t.symbol,
            "score": t.score,
            "price": t.price,
            "change_pct_1d": t.change_pct_1d,
            "volume": t.volume,
            "signal": t.signal,
        })

    # Sort tickers within each sector by volume (biggest tiles first).
    for sector in sectors.values():
        sector.sort(key=lambda x: -(x["volume"] or 0))

    # Order sectors using CANONICAL_ORDER so the heatmap layout is stable
    # across refreshes (Tech first, Uncategorized last). Any new bucket not
    # in CANONICAL_ORDER would sort last — shouldn't happen because every
    # canonical_sector return value IS in the order list, but defensive.
    order_index = {name: i for i, name in enumerate(CANONICAL_ORDER)}
    ordered = sorted(
        sectors.items(),
        key=lambda kv: order_index.get(kv[0], len(CANONICAL_ORDER)),
    )

    return {
        "sectors": [
            {"sector": name, "tickers": items}
            for name, items in ordered
            if items  # drop empty buckets so the UI doesn't render headers with no tiles
        ],
        "available_sectors": CANONICAL_ORDER,  # for the frontend filter dropdown
        "query": needle or None,
    }
