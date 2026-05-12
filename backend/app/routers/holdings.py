"""GET /api/holdings — Recent Insider Buys feed (Premium-only).

Replaces the legacy 13F holdings endpoint. The 13F path required a paid Quiver
key that was never wired in production, so the page sat empty.

Data source: Finnhub `/stock/insider-transactions` (SEC Form 4), already
fetched daily by `_refresh_insider_cache` in the worker for the active scoring
universe. The same data powers the Smart Money sub-score, so this endpoint
is the visible "receipt" for the 15% Smart Money pillar of every Tapeline Score.

Response shape (kept stable for the frontend that paginates/filters):
    {
      "count": int,
      "items": [
        {
          "symbol": str,
          "insider_name": str,
          "transaction_date": str (YYYY-MM-DD),
          "share_change": int (negative = sale, positive = buy),
          "transaction_price": float,
          "transaction_value": float (abs of shares * price),
          "code": str (SEC Form 4 transaction code, e.g. "P"=buy, "S"=sale)
        }
      ]
    }
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import User
from app.services.auth import current_user_required
from app.services.finnhub_feed import (
    get_recent_insider_transactions,
    insider_feed_size,
)
from app.services.tier import Tier, has_feature

router = APIRouter()


@router.get("")
async def list_insider_buys(
    user: User = Depends(current_user_required),
    symbol: str | None = Query(None, description="Filter to one ticker"),
    days: int = Query(30, ge=1, le=180, description="Lookback window in days"),
    buys_only: bool = Query(False, description="Only return net positive (buy) transactions"),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """
    Recent insider Form 4 transactions across the active universe.
    Refreshed daily by the signal-publisher worker. Premium-only.
    """
    if not has_feature(Tier(user.tier), "holdings.elite"):
        raise HTTPException(403, "Recent insider activity is a Premium feature")

    items = get_recent_insider_transactions(
        days=days,
        limit=limit,
        symbol=symbol,
        buys_only=buys_only,
    )
    return {
        "count": len(items),
        "items": items,
        "feed_size": insider_feed_size(),
    }


@router.get("/funds")
async def list_funds_legacy(
    user: User = Depends(current_user_required),
) -> dict:
    """
    Legacy endpoint kept for frontend compatibility. The "elite funds" concept
    moved off-roadmap in 2026-05 when we replaced Quiver 13F with Finnhub
    Form 4 insider data. Returns an empty list — the frontend's fund filter
    is hidden when this is empty.
    """
    if not has_feature(Tier(user.tier), "holdings.elite"):
        raise HTTPException(403, "Recent insider activity is a Premium feature")
    return {"items": []}
