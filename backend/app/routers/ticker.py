"""GET /api/ticker/{symbol} — detailed single-ticker view with breakdown + news.

Also: GET /api/ticker/{symbol}/ratings — analyst ratings consensus + recent
events from Benzinga (with Finnhub aggregate fallback). Premium-only —
mirrors holdings.elite gating. Lazy-loaded by the frontend so the main
ticker page doesn't block on the upstream rating call.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import NewsItem, SqueezeSetup, Ticker, User
from app.services.auth import current_user_required
from app.services.benzinga_feed import fetch_analyst_ratings
from app.services.finnhub_feed import fetch_basic_financials, fetch_insider_transactions
from app.services.news_feed import fetch_news_for_ticker
from app.services.tier import Tier, has_feature

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

    # News — ALWAYS live-fetch on every visit (Benzinga → Massive → Finnhub
    # chain), persist any new articles, then return the latest 8 from DB.
    #
    # Previous version short-circuited on cache hit ("if not news_rows"),
    # which meant tickers like BUR (UK ADR with 5 stale 2024 Massive
    # articles cached) never re-fetched. Visitors saw 2-year-old news
    # forever. The new flow:
    #   1. Live fetch through the fallback chain (Benzinga first; falls
    #      through to Finnhub which has fresh BUR/UK/international coverage).
    #   2. Insert any unseen articles into NewsItem (id-deduped, per-row
    #      try/except so one bad insert can't poison the rest).
    #   3. SELECT the 8 most-recent — fresh articles rank above stale ones
    #      naturally via ORDER BY published_at DESC.
    try:
        live = await fetch_news_for_ticker(symbol, limit=8)
        for it in live:
            try:
                existing = await session.execute(
                    select(NewsItem).where(NewsItem.id == it["id"])
                )
                if existing.scalar_one_or_none() is None:
                    session.add(NewsItem(**it))
            except Exception:
                # Don't let one bad row kill the request — log + continue.
                pass
        await session.flush()
    except Exception:
        # Live fetch failure isn't fatal — fall through to cached news.
        pass

    news_result = await session.execute(
        select(NewsItem)
        .where(NewsItem.tickers.like(f"%{symbol}%"))
        .order_by(desc(NewsItem.published_at))
        .limit(8)
    )
    news_rows = news_result.scalars().all()

    return {
        "symbol": t.symbol,
        "name": t.name,
        "sector": t.sector,
        "asset_class": t.asset_class,
        "price": t.price,
        "score": t.score,
        "signal": t.signal,
        "confidence_pct": t.confidence_pct,
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


@router.get("/{symbol}/ratings")
async def ticker_ratings(
    symbol: str,
    user: User = Depends(current_user_required),
) -> dict:
    """Analyst ratings consensus + recent events for a ticker — Premium-only.

    Trial users (auto-Premium for 14 days) and paid Premium subscribers see
    the widget. Free + Pro users hit the Paywall on the frontend; this
    endpoint also enforces the gate so the data can't be sniffed via direct
    API call.

    Lazy-loaded — the main ticker payload doesn't include this so the page
    paints before the upstream Benzinga call completes. When both Benzinga
    and the Finnhub fallback have no coverage, the response shape stays the
    same with an empty events list so the frontend renders a clean empty
    state.
    """
    if not has_feature(Tier(user.tier), "ratings.analyst"):
        raise HTTPException(403, "Analyst consensus requires Premium tier")
    return await fetch_analyst_ratings(symbol.upper())


@router.get("/{symbol}/financials")
async def ticker_financials(symbol: str) -> dict:
    """Per-ticker financial metrics from Finnhub.

    Returns P/E, net margin, ROE, EPS growth, revenue growth, debt-to-equity.
    Public — same access surface as /{symbol} and /{symbol}/history. Cached
    7 days at the adapter layer; fundamentals don't change tick-to-tick.

    Most ETFs and funds have no Finnhub fundamentals coverage. The response
    keeps a stable shape (`available: false`, empty `metrics`) so the
    frontend can render a clean empty state instead of broken null fields.
    """
    sym = symbol.upper()
    metrics = await fetch_basic_financials(sym)
    return {
        "symbol": sym,
        "available": metrics is not None,
        "metrics": metrics or {},
    }


@router.get("/{symbol}/insider")
async def ticker_insider(
    symbol: str,
    days_back: int = 90,
    user: User = Depends(current_user_required),
) -> dict:
    """Recent Form 4 insider transactions for a ticker — Premium only.

    Returns insider buys/sells from Finnhub for the last `days_back` days
    (default 90, clamped to [1, 365] to bound upstream cost). Each row
    carries filer name, transaction date, share change, transaction price,
    and the SEC transaction code (P=purchase, S=sale, A=award, M=option
    exercise, G=gift, F=tax withholding).

    Mirrors the Premium gating on /api/holdings — Form 4 is explicit
    Premium territory per the tier model. The frontend Paywall handles the
    upsell card; this endpoint also enforces the gate so the data can't be
    sniffed via direct API call from a Free or Pro session.

    Cached 24h at the adapter layer (per-symbol).
    """
    if not has_feature(Tier(user.tier), "insider.form4"):
        raise HTTPException(403, "Insider transactions require Premium tier")

    sym = symbol.upper()
    days = max(1, min(days_back, 365))
    rows = await fetch_insider_transactions(sym, days_back=days)
    return {
        "symbol": sym,
        "days_back": days,
        "transactions": rows or [],
    }


@router.get("/{symbol}/history")
async def ticker_score_history(
    symbol: str,
    days: int = 60,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Sparse score history for a ticker — points pulled from the daily
    scorecard.

    Only days where this ticker landed in the top-10 are present (that's
    the only per-day score snapshot the DB stores). For mega-cap regulars
    that's near-daily; for one-time fliers it's sparse. Frontend renders
    an empty sparkline when no rows exist.

    Long-term: a per-tick or per-day score-history table would give every
    ticker a full trace. Tracked in TECH_DEBT.md as a post-launch lift.
    """
    from datetime import date, timedelta

    from app.models import DailyScorecardEntry

    sym = symbol.upper()
    cutoff = date.today() - timedelta(days=days)
    rows_r = await session.execute(
        select(
            DailyScorecardEntry.as_of,
            DailyScorecardEntry.score_at_flag,
            DailyScorecardEntry.rank,
            DailyScorecardEntry.change_pct_1d_after,
            DailyScorecardEntry.alpha_vs_spy,
        )
        .where(
            DailyScorecardEntry.symbol == sym,
            DailyScorecardEntry.as_of >= cutoff,
        )
        .order_by(DailyScorecardEntry.as_of)
    )
    points = [
        {
            "date": r[0].isoformat(),
            "score": float(r[1]),
            "rank": int(r[2]),
            "change_pct_1d_after": float(r[3]) if r[3] is not None else None,
            "alpha_vs_spy": float(r[4]) if r[4] is not None else None,
        }
        for r in rows_r.all()
    ]
    return {"symbol": sym, "days": days, "points": points}
