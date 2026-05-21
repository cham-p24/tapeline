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
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticker, User
from app.services.auth import current_user_required
from app.services.sector import CANONICAL_ORDER, canonical_sector
from app.services.tier import Tier, has_feature

# Hard freshness floor: a ticker that hasn't been re-snapshotted in this
# many minutes is excluded from the heatmap, even if it passes every
# other filter. Founder feedback (2026-05-21): "people trade based on the
# information being live". 15 min is generous (real-time feeds tick by
# the second; we're on 60s worker cycles plus rate-limit batching) but
# guards against the worst case where Massive's rate-limit queue stretches
# a long tail of tickers out to >2hrs stale.
HEATMAP_MAX_STALE_MIN = 15

router = APIRouter()


@router.get("")
async def get_heatmap(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
    q: str | None = Query(None, max_length=20, description="Optional symbol substring filter"),
) -> dict:
    if not has_feature(Tier(user.tier), "heatmap"):
        raise HTTPException(403, "Heatmap is a Pro feature")
    # 2026-05-21 universe scoping — match competitor heatmap posture.
    #
    # Finviz Map ships ~500 (S&P 500), TradingView Heatmap ships per-market
    # (~500 each), CoinMarketCap ships top 100. None of them try to render
    # all 3,000+ instruments — because at that scale, the long-tail
    # micro-caps don't get refreshed often enough by any consumer-grade
    # price feed (we use Massive/Polygon Starter), so most tiles render
    # "+0.00%" and make the heatmap feel broken.
    #
    # The Tapeline universe is sourced from the signal-system Google Sheet
    # at ~3,000 rows — that's the right scoring universe but the wrong
    # display universe for a heatmap. Filter to three thresholds:
    #   1. score IS NOT NULL — the ticker has been scored at all
    #   2. change_pct_1d IS NOT NULL — the price feed has it
    #   3. volume IS NOT NULL AND > 100,000 — actually-liquid
    # 100K shares/day is the floor below which a tile would mislead a
    # retail user into thinking they can trade size at the displayed
    # change. (Real institutions use higher thresholds — 1M+ — but we're
    # serving retail.)
    LIQUIDITY_FLOOR = 100_000
    fresh_cutoff = datetime.now(timezone.utc) - timedelta(minutes=HEATMAP_MAX_STALE_MIN)
    result = await session.execute(
        select(Ticker).where(
            Ticker.score.isnot(None),
            Ticker.change_pct_1d.isnot(None),
            Ticker.volume.isnot(None),
            Ticker.volume > LIQUIDITY_FLOOR,
            Ticker.updated_at >= fresh_cutoff,
        )
    )
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

    # Freshness summary so the frontend can surface "Updated 12s ago"
    # next to the LiveBadge without needing to compute it client-side.
    newest_update = max((t.updated_at for t in tickers if t.updated_at), default=None)
    oldest_update = min((t.updated_at for t in tickers if t.updated_at), default=None)

    return {
        "sectors": [
            {"sector": name, "tickers": items}
            for name, items in ordered
            if items  # drop empty buckets so the UI doesn't render headers with no tiles
        ],
        "available_sectors": CANONICAL_ORDER,  # for the frontend filter dropdown
        "query": needle or None,
        "freshness": {
            "newest_updated_at": newest_update.isoformat() if newest_update else None,
            "oldest_updated_at": oldest_update.isoformat() if oldest_update else None,
            "max_stale_minutes": HEATMAP_MAX_STALE_MIN,
            "ticker_count": len(tickers),
        },
    }
