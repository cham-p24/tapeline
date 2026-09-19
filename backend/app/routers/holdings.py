"""GET /api/holdings — Recent Insider Buys feed (Premium-only).

Replaces the legacy 13F holdings endpoint. The 13F path required a paid Quiver
key that was never wired in production, so the page sat empty.

Data source: SEC Form 4 filings read directly from SEC EDGAR by the worker's
insider pass (`_refresh_insider_cache` -> services/edgar_form4.py; Finnhub until
2026-09-14), each stock re-read about every two days. The same data powers the Smart Money sub-score, so this endpoint
is the visible "receipt" for the Smart Money pillar of every Tapeline Score.

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
          "code": str (SEC Form 4 transaction code, e.g. "P"=buy, "S"=sale),
          "symbols": [str] (every ticker the line is listed under: since
                     2026-09-19 one issuer's common-stock classes all carry
                     its lines, and this list shows such a line once;
                     `symbol` is the first of them)
        }
      ]
    }
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import User
from app.services.auth import current_user_required
from app.services.finnhub_feed import (
    get_recent_insider_transactions_db,
    insider_feed_size_db,
)
from app.services.tier import Tier, has_feature

router = APIRouter()

# How many Form 4 rows the FREE preview returns, and over what window. Small on
# purpose: enough to show the feed is real and populated (the paywalled page
# previously blurred an EMPTY table, so a Free user saw zero evidence the
# feature had any content), nowhere near enough to replace the Premium feed.
FREE_INSIDER_PREVIEW_LIMIT = 3
FREE_INSIDER_PREVIEW_DAYS = 30


@router.get("/preview")
async def insider_preview(
    user: User = Depends(current_user_required),
) -> dict:
    """Read-only 3 most-recent Form 4 filings — a FREE taste of the feed.

    Requires login, matching the free-taste pattern in routers/squeeze.py —
    this is a logged-in activation nudge, not a public/scrapeable surface.

    `feed_size` is the real total row count of the DB-backed feed so the
    frontend's locked section can state the true held-back number instead of
    inventing one. Zero when the worker hasn't backfilled yet; the UI omits
    the number in that case rather than printing "of 0".
    """
    items = await get_recent_insider_transactions_db(
        days=FREE_INSIDER_PREVIEW_DAYS,
        limit=FREE_INSIDER_PREVIEW_LIMIT,
    )
    return {
        "count": len(items),
        "preview": True,
        "limit": FREE_INSIDER_PREVIEW_LIMIT,
        "days": FREE_INSIDER_PREVIEW_DAYS,
        "feed_size": await insider_feed_size_db(),
        "items": items,
    }


@router.get("")
async def list_insider_buys(
    user: User = Depends(current_user_required),
    symbol: str | None = Query(None, description="Filter to one ticker"),
    # At most signal_publisher._INSIDER_WINDOW_DAYS (90), the window the worker
    # reads from SEC EDGAR. Stored rows older than that are deleted when a
    # symbol's next answer is empty (#824) and kept until then, so a longer
    # lookback would return a different window per symbol.
    days: int = Query(30, ge=1, le=90, description="Lookback window in days"),
    buys_only: bool = Query(
        False, description="Only return purchases: Form 4 code P with a positive share change",
    ),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """
    Recent insider Form 4 transactions across the active universe.
    Each stock is re-checked about every two days by the signal-publisher
    worker. Premium-only.
    """
    if not has_feature(Tier(user.tier), "holdings.elite"):
        raise HTTPException(403, "Recent insider activity is a Premium feature")

    items = await get_recent_insider_transactions_db(
        days=days,
        limit=limit,
        symbol=symbol,
        buys_only=buys_only,
    )
    return {
        "count": len(items),
        "items": items,
        "feed_size": await insider_feed_size_db(),
    }


@router.get("/funds")
async def list_funds_legacy(
    user: User = Depends(current_user_required),
) -> dict:
    """
    Legacy endpoint kept for frontend compatibility. The "elite funds" concept
    moved off-roadmap in 2026-05 when we replaced Quiver 13F with SEC Form 4
    insider data (read from Finnhub until 2026-09-14, from SEC EDGAR since). Returns an empty list — the frontend's fund filter
    is hidden when this is empty.
    """
    if not has_feature(Tier(user.tier), "holdings.elite"):
        raise HTTPException(403, "Recent insider activity is a Premium feature")
    return {"items": []}
