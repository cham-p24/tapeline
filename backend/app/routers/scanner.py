"""GET /api/scanner — paginated ticker list with filters + tier gating."""
from __future__ import annotations

import time
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, is_sqlite
from app.models import Ticker, User
from app.services.auth import current_user_optional
from app.services.ticker_freshness import live_clauses
from app.services.tier import Tier
from app.services.tier import limit as tier_limit

router = APIRouter()

# Per-statement ceiling for the scanner's filtered/sorted scan. The 2026-06-01
# pool-exhaustion incident was an unbounded query holding a pooled connection
# until the pool drained; an 8s server-side cap (Postgres only — SQLite has no
# statement_timeout) means a pathological filter combo is cancelled and 500s
# fast instead of wedging the pool. Mirrors routers/ticker.py's news-scan guard.
SCANNER_QUERY_TIMEOUT_MS = 8000

# Default liquidity floor for the ranked scanner view. A high Tapeline Score on
# a near-untradeable instrument (e.g. a bond/strategy ETF trading a few hundred
# dollars a day — BBBL at ~$800/day, AETH at ~$21k) was floating to the TOP of
# the list, a first-impression killer on the core product surface. We drop rows
# whose dollar-volume (price*volume) is KNOWN and below this floor; rows missing
# price or volume are KEPT, so the filter can only ever remove obvious junk,
# never hide a name we simply lack a volume read for. Conservative on purpose so
# the price-anchored listicle pages (penny stocks / under-$5) keep their long
# tail. Pass min_dollar_volume=0 to disable.
SCANNER_MIN_DOLLAR_VOLUME = 50_000.0

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
    # missing either field.
    # live_clauses() applies the full "a user may see this" floor: scored,
    # fresh (relative window), and data-quality clean (no raw >100 scores,
    # no space/emoji-in-symbol annotations, >=2 real factors) — so a
    # delisted/dropped ghost still carrying a high last-known price*volume
    # can't seed the watchlist. See app.services.ticker_freshness.
    pop_stmt = select(Ticker).where(
        Ticker.price.isnot(None),
        Ticker.volume.isnot(None),
        Ticker.volume > 0,
    )
    for clause in await live_clauses(session):
        pop_stmt = pop_stmt.where(clause)
    pop_stmt = (
        pop_stmt
        .order_by(desc(Ticker.price * Ticker.volume))
        .limit(max(n * 2, 16))  # over-fetch so we have a fallback if some have NULL fields
    )
    rows = (await session.execute(pop_stmt)).scalars().all()

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
    # Price filter — added 2026-05-20 to support the price-anchored strategy
    # listicle pages (/best-stocks-for/penny-stocks, /under-10, /under-5).
    # Optional; when both None the filter is a no-op.
    min_price: float | None = Query(None, ge=0, description="Lower price bound, inclusive"),
    max_price: float | None = Query(None, ge=0, description="Upper price bound, inclusive"),
    # Liquidity floor — see SCANNER_MIN_DOLLAR_VOLUME. Removes near-untradeable
    # names (known dollar-volume below the floor) from the ranked view. Pass 0
    # to disable, e.g. a deliberately liquidity-agnostic search.
    min_dollar_volume: float = Query(
        SCANNER_MIN_DOLLAR_VOLUME,
        ge=0,
        description="Minimum daily dollar-volume (price*volume); rows with a known value below this are excluded",
    ),
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
    # Ticker.score IS NOT NULL is enforced by live_clauses() below.
    stmt = select(Ticker).where(
        Ticker.score >= min_score,
        Ticker.score <= max_score,
    )
    if min_price is not None:
        stmt = stmt.where(Ticker.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Ticker.price <= max_price)
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

    # Freshness + data-quality floor — exclude stale "ghost" rows AND corrupt
    # rows so the score sort reflects the current, clean universe. Without it,
    # delisted tickers carrying raw pre-composite scores (>=98) or corrupt rows
    # (score>100, emoji-in-symbol annotations, <2 factors) outrank every fresh
    # 6-factor composite. See app.services.ticker_freshness.
    for clause in await live_clauses(session):
        stmt = stmt.where(clause)

    # Liquidity floor — keep rows with an unknown (null) price/volume, but drop
    # any whose KNOWN dollar-volume is below the floor so a high score on a
    # near-untradeable ETF can't top the ranked list. See SCANNER_MIN_DOLLAR_VOLUME.
    if min_dollar_volume > 0:
        stmt = stmt.where(
            or_(
                Ticker.price.is_(None),
                Ticker.volume.is_(None),
                Ticker.price * Ticker.volume >= min_dollar_volume,
            )
        )

    col = getattr(Ticker, sort)
    stmt = stmt.order_by(desc(col) if order == "desc" else col)
    stmt = stmt.limit(limit).offset(offset)

    # Cap the scan server-side (Postgres only; SQLite has no statement_timeout
    # and ignores this no-op skip) so a pathological filter combo can't hold a
    # pooled connection open and drain the pool (the 2026-06-01 incident). A
    # timed-out query raises and 500s fast instead of wedging — paired with the
    # new composite index (migration 0035) the healthy path stays well under 8s.
    if not is_sqlite():
        await session.execute(
            text(f"SET LOCAL statement_timeout = '{SCANNER_QUERY_TIMEOUT_MS}ms'")
        )

    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Read the delay from tier.py. Post-freemium-retune (2026-06-20) every tier
    # is LIVE (data_delay_minutes = 0) — the old 24h Free delay cliff is gone;
    # Free is now gated by row-cap + the daily ticker-lookup meter instead. Kept
    # config-driven so re-introducing a delay is a one-line tier.py change.
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
