"""GET /api/scanner — paginated ticker list with filters + tier gating."""
from __future__ import annotations

import time
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

# Module-level cache for /popular — recomputed every hour. The query is cheap
# but we'd rather not run it on every empty-state render in /app/watchlist.
_POPULAR_CACHE: dict[str, object] = {"ts": 0.0, "items": []}
_POPULAR_TTL_SECONDS = 3600


@router.get("/popular")
async def popular_tickers(
    session: AsyncSession = Depends(get_session),
    n: int = Query(8, ge=1, le=20),
) -> dict:
    """Top N actively-scored tickers by daily dollar-volume.

    Powers the watchlist starter pack + any "what's hot right now" surface.
    Cached in process memory for an hour — replaces the prior hardcoded
    AAPL/MSFT/NVDA/... list. Returns just symbols + names; the watchlist
    seeder fills in scores when the user actually adds them.
    """
    now = time.time()
    cached_ts = _POPULAR_CACHE.get("ts", 0.0)
    cached_items = _POPULAR_CACHE.get("items") or []
    if isinstance(cached_ts, (int, float)) and isinstance(cached_items, list) \
       and (now - float(cached_ts)) < _POPULAR_TTL_SECONDS and len(cached_items) >= n:
        return {"items": cached_items[:n], "cached": True}

    # Compute "popularity" as price * volume so a thinly-traded $400 stock
    # doesn't outrank a $40 stock with 10x the share volume. Skip rows
    # missing either field. Cap to actively-scored tickers (score IS NOT NULL)
    # so we don't seed the watchlist with stale rows from auto-discovery.
    rows = (await session.execute(
        select(Ticker)
        .where(
            Ticker.score.isnot(None),
            Ticker.price.isnot(None),
            Ticker.volume.isnot(None),
            Ticker.volume > 0,
        )
        .order_by(desc(Ticker.price * Ticker.volume))
        .limit(max(n * 2, 16))  # over-fetch so we have a fallback if some have NULL fields
    )).scalars().all()

    items = [
        {"symbol": r.symbol, "name": r.name, "sector": r.sector, "score": r.score}
        for r in rows
    ][:n]

    # Repopulate cache only if the DB returned something — otherwise the
    # client falls back to a hardcoded seed and we keep the prior cache.
    if items:
        _POPULAR_CACHE["ts"] = now
        _POPULAR_CACHE["items"] = items

    return {"items": items, "cached": False}


@router.get("")
async def list_scanner(
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(current_user_optional),
    min_score: float = Query(0, ge=0, le=100),
    max_score: float = Query(100, ge=0, le=100),
    signal: str | None = None,
    sector: str | None = None,
    q: str | None = Query(None, max_length=20, description="Symbol substring search (case-insensitive)"),
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
    # Symbol substring search. SQL LIKE with leading wildcard prevents index use
    # but the active universe is <2,500 rows so a full scan is fine; the query
    # still returns in <50ms in production. Uppercase the query to match how
    # symbols are stored.
    if q:
        needle = q.strip().upper()
        if needle:
            stmt = stmt.where(Ticker.symbol.like(f"%{needle}%"))

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
