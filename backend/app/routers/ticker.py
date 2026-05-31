"""GET /api/ticker/{symbol} — detailed single-ticker view with breakdown + news.

Also: GET /api/ticker/{symbol}/ratings — analyst ratings consensus + recent
events from Benzinga (with Finnhub aggregate fallback). Premium-only —
mirrors holdings.elite gating. Lazy-loaded by the frontend so the main
ticker page doesn't block on the upstream rating call.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, get_session
from app.models import NewsItem, SqueezeSetup, Ticker, User
from app.services.auth import current_user_required
from app.services.benzinga_feed import fetch_analyst_ratings
from app.services.finnhub_feed import fetch_basic_financials, fetch_insider_transactions
from app.services.news_feed import fetch_news_for_ticker
from app.services.tier import Tier, has_feature

router = APIRouter()
logger = logging.getLogger(__name__)

# --- News freshness strategy (incident fix 2026-05-31, rev 2) --------------
# /api/ticker MUST be fast: it backs both the SSR'd public /t/{symbol} page
# and the daily SEO audit, which HEADs ~1.1k of those pages. The previous
# design live-fetched news (Benzinga ∥ Massive ∥ Finnhub — ~3 parallel
# upstream calls) synchronously inside the request. Even after the earlier
# fix today stopped holding a pooled DB connection across that fetch, the
# multi-second call — multiplied by the audit's concurrency AND the
# frontend's 2x SSR retry on slow responses — let in-flight requests pile up
# on the single small API machine and drove a latency death-spiral
# (2.8s → 20s → timeout). That tripped the frontend's 7s SSR timeout, so the
# /t/{symbol} pages 500'd (by design, as a "retry later" signal to Googlebot)
# during every audit window.
#
# Fix: serve news straight from the DB — the same warm cache /api/news reads,
# kept fresh by the worker (~every 5 min) plus EDGAR 8-Ks. The request path
# now makes ZERO upstream calls; it's pure indexed DB reads, sub-second under
# any load. Freshness for cold / long-tail tickers (e.g. BUR, which Massive
# serves stale) is preserved by an OPPORTUNISTIC background refresh that is:
#   • deduped per symbol     — never two concurrent refreshes for one symbol,
#   • throttled per symbol   — re-fetch at most once / NEWS_REFRESH_MIN_INTERVAL,
#   • globally capped         — ≤ MAX_CONCURRENT_NEWS_REFRESH in flight machine-wide,
#   • hard-timeout-bounded    — a wedged upstream can't hold an in-flight slot.
# So the audit's ~1.1k cold symbols can never spawn ~1.1k concurrent fetches:
# at most a small trickle drains in the background while every request that
# touched them has already returned.
NEWS_REFRESH_TIMEOUT_S = 12.0          # hard cap on a single background refresh
NEWS_REFRESH_MIN_INTERVAL_S = 600.0    # don't re-fetch the same symbol < 10 min apart
MAX_CONCURRENT_NEWS_REFRESH = 3        # machine-wide ceiling on background fetches

# Per-process state for the background refresh (one set of these per API worker).
_news_refresh_inflight: set[str] = set()          # symbols currently mid-refresh
_news_last_refresh_at: dict[str, datetime] = {}   # symbol -> last refresh start (UTC)
_news_bg_tasks: set[asyncio.Task] = set()         # strong refs so tasks aren't GC'd


async def _refresh_news_bg(symbol: str) -> None:
    """Background, fire-and-forget news refresh for one symbol.

    Runs OFF the request path: live-fetches the feed (hard-capped via
    wait_for so a wedged upstream releases its in-flight slot), then
    id-deduped-inserts any unseen rows in its own short-lived session and
    COMMITS (the request path only reads — this is what actually persists new
    articles). Every failure mode is swallowed: this is opportunistic
    freshness, never load-bearing.
    """
    try:
        live = await asyncio.wait_for(
            fetch_news_for_ticker(symbol, limit=8), timeout=NEWS_REFRESH_TIMEOUT_S
        )
        if not live:
            return
        async with SessionLocal() as session:
            inserted = 0
            for it in live:
                try:
                    existing = await session.execute(
                        select(NewsItem).where(NewsItem.id == it["id"])
                    )
                    if existing.scalar_one_or_none() is None:
                        session.add(NewsItem(**it))
                        inserted += 1
                except Exception:
                    pass
            if inserted:
                try:
                    await session.commit()
                except Exception:
                    try:
                        await session.rollback()
                    except Exception:
                        pass
    except Exception:
        logger.warning("ticker.news_bg_refresh_failed symbol=%s", symbol)
    finally:
        _news_refresh_inflight.discard(symbol)


def _maybe_refresh_news(symbol: str) -> None:
    """Opportunistically schedule a background news refresh for `symbol`.

    Cheap, synchronous, non-blocking guard: applies per-symbol dedup + a
    per-symbol throttle + a global concurrency ceiling, then spawns a detached
    task and returns immediately. The request never waits on the refresh, and
    under heavy fan-out (the SEO audit) the global ceiling caps machine-wide
    background work regardless of request volume.
    """
    if symbol in _news_refresh_inflight:
        return
    now = datetime.now(UTC)
    last = _news_last_refresh_at.get(symbol)
    if last is not None and (now - last).total_seconds() < NEWS_REFRESH_MIN_INTERVAL_S:
        return
    if len(_news_refresh_inflight) >= MAX_CONCURRENT_NEWS_REFRESH:
        return  # at capacity — skip; the DB news we already served stands
    _news_refresh_inflight.add(symbol)
    _news_last_refresh_at[symbol] = now
    task = asyncio.create_task(_refresh_news_bg(symbol))
    _news_bg_tasks.add(task)
    task.add_done_callback(_news_bg_tasks.discard)


@router.get("/{symbol}")
async def ticker_detail(symbol: str) -> dict:
    """Complete view of a single ticker — score breakdown, squeeze status, news.

    Connection + latency discipline (incident fix 2026-05-31, rev 2): this
    endpoint backs the SSR'd public /t/{symbol} page and the daily SEO audit
    that HEADs ~1.1k of them, so it MUST be fast and cheap. It does only
    indexed DB reads in a SINGLE short txn (connection released on exit) and
    makes NO upstream calls in the request path — news is served from the same
    warm DB cache /api/news reads (worker-refreshed ~every 5 min + EDGAR 8-Ks).
    A bounded, deduped, throttled background task (see _maybe_refresh_news)
    keeps long-tail tickers fresh without ever blocking the response or letting
    load pile up. `expire_on_commit=False` (see app.db) keeps the ORM objects
    readable after the `async with` closes, so building the payload outside the
    txn is safe.

    History: the news fetch used to run inline. First it held a pooled
    connection across the multi-second Benzinga→Massive→Finnhub chain →
    QueuePool exhaustion. Then, after the connection was released but the fetch
    stayed inline, the multi-second call (× audit concurrency × the frontend's
    2x SSR retry) drove a latency death-spiral that 500'd the SSR pages. Both
    failure modes are gone now that the request path touches only the DB.
    """
    symbol = symbol.upper()

    # Single short read txn: core ticker + squeeze + latest news. The pooled
    # connection is checked out only for these indexed lookups, then returned
    # to the pool on context exit — no upstream call ever holds it.
    async with SessionLocal() as session:
        t = (
            await session.execute(select(Ticker).where(Ticker.symbol == symbol))
        ).scalar_one_or_none()
        if t is None:
            raise HTTPException(404, f"Ticker {symbol} not in scanner universe")
        sq = (
            await session.execute(
                select(SqueezeSetup).where(SqueezeSetup.symbol == symbol)
            )
        ).scalar_one_or_none()
        news_rows = (
            await session.execute(
                select(NewsItem)
                .where(NewsItem.tickers.like(f"%{symbol}%"))
                .order_by(desc(NewsItem.published_at))
                .limit(8)
            )
        ).scalars().all()
        news_payload = [
            {
                "id": n.id,
                "title": n.title,
                "publisher": n.publisher,
                "published_at": n.published_at.isoformat() if hasattr(n.published_at, "isoformat") else str(n.published_at),
                "url": n.url,
                "sentiment": getattr(n, "sentiment", None),
            }
            for n in news_rows
        ]

    # Opportunistic, non-blocking freshness top-up for cold / long-tail tickers.
    # Bounded + deduped + throttled inside the helper; returns instantly so the
    # response (built from the DB read above) is never delayed by an upstream.
    _maybe_refresh_news(symbol)

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
        "news": news_payload,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


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
