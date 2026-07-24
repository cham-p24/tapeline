"""GET /api/ticker/{symbol} — detailed single-ticker view with breakdown + news.

Also: GET /api/ticker/{symbol}/ratings — analyst ratings consensus from
Finnhub's aggregate recommendations. Premium-only — mirrors holdings.elite
gating. Lazy-loaded by the frontend so the main ticker page doesn't block on
the upstream rating call.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, get_session, is_sqlite
from app.models import NewsItem, SqueezeSetup, Ticker
from app.models.news import exclude_mock_clause, tickers_match_clause
from app.services.auth import current_user_optional, current_user_required
from app.services.finnhub_feed import (
    fetch_analyst_ratings,
    fetch_basic_financials,
    fetch_insider_transactions,
)
from app.services.news_feed import fetch_news_for_ticker
from app.services.symbols import clean_symbol
from app.services.tier import Tier, has_feature

router = APIRouter()
logger = logging.getLogger(__name__)

# --- News freshness strategy (incident fix 2026-05-31, rev 2) --------------
# /api/ticker MUST be fast: it backs both the SSR'd public /t/{symbol} page
# and the daily SEO audit, which HEADs ~1.1k of those pages. The previous
# design live-fetched news (Massive ∥ Finnhub — parallel upstream calls)
# synchronously inside the request. Even after the earlier
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

# Per-ticker headline read window + hard cap (incident fix 2026-06-01) ---------
# The headline lookup is `WHERE tickers LIKE '%SYM%' ORDER BY published_at DESC
# LIMIT 8`. The leading-wildcard LIKE can't use the tickers B-tree index, so
# Postgres serves the LIMIT by walking the published_at index newest→oldest and
# filtering each row until it collects 8. For a symbol that's RARE in recent
# news (TSLA, GME, NIO, …) that walk ran to the end of the table — a 30s+ hang
# that held a pooled connection the whole time; under fan-out (the SEO audit /
# a crawl) those holds exhausted the 30-slot pool and 500'd EVERY /t page. The
# window caps how far the walk can scan; the per-statement timeout is the
# backstop that kills any still-slow scan so the page degrades to no-news
# instead of hanging. (A symbol abundant in recent news — AMD, "F" — always
# found 8 immediately, which is why only a subset of tickers ever 500'd.)
NEWS_LOOKBACK_DAYS = 90                 # only scan the last N days of headlines
NEWS_QUERY_TIMEOUT_MS = 2500           # Postgres per-statement cap on the scan

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


async def _fetch_ticker_news(symbol: str) -> list[dict]:
    """Newest ≤8 headlines mentioning `symbol` — bounded so it can never wedge.

    Two guards added after the 2026-06-01 incident (see NEWS_LOOKBACK_DAYS):
      • a recency window caps how far the published_at-DESC index walk can scan
        when `symbol` is rare in recent news (the root cause of the 30s hangs),
      • a short per-statement timeout (Postgres only — SQLite ignores it) is the
        backstop: a still-slow scan is cancelled server-side and we serve the
        page with no news instead of 500ing it.
    Runs in its OWN short session so a slow or cancelled headline scan can never
    hold the core read's connection or corrupt the core ticker payload. Every
    failure mode degrades to [] — news is never load-bearing for the page.
    """
    try:
        async with SessionLocal() as session:
            # Bound the scan server-side first (Postgres); harmless no-op skip on
            # SQLite, which has no statement_timeout.
            if not is_sqlite():
                await session.execute(
                    text(f"SET LOCAL statement_timeout = '{NEWS_QUERY_TIMEOUT_MS}ms'")
                )
            cutoff = datetime.now(UTC) - timedelta(days=NEWS_LOOKBACK_DAYS)
            rows = (
                await session.execute(
                    select(NewsItem)
                    .where(
                        # Never surface fabricated mock headlines (LEGAL
                        # read-path invariant). See models.news.exclude_mock_clause.
                        exclude_mock_clause(),
                        # Exact comma-delimited token match: 'GM' must NOT match
                        # a 'GME'-only row. See models.news.tickers_match_clause.
                        tickers_match_clause(symbol),
                        NewsItem.published_at >= cutoff,
                    )
                    .order_by(desc(NewsItem.published_at))
                    .limit(8)
                )
            ).scalars().all()
        return [
            {
                "id": n.id,
                "title": n.title,
                "publisher": n.publisher,
                "published_at": n.published_at.isoformat() if hasattr(n.published_at, "isoformat") else str(n.published_at),
                "url": n.url,
                "sentiment": getattr(n, "sentiment", None),
            }
            for n in rows
        ]
    except Exception:
        # Slow scan (timed out), aborted txn, or any read error → no news.
        logger.warning("ticker.news_query_degraded symbol=%s", symbol)
        return []


def _next_utc_midnight() -> datetime:
    """Start of the next UTC day — when the daily look-up counter rolls over.

    services.usage keys the durable counter on the UTC date
    (lookups_reset_on), so "resets at the next UTC midnight" is exact, not an
    estimate. Derived rather than stored: there is no reset-timestamp column.
    """
    now = datetime.now(UTC)
    return (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _lookup_meter_payload(meter: dict) -> dict:
    """Shape the freemium look-up meter for the /api/ticker 200 response.

    These numbers are ALREADY computed by consume_ticker_lookup on every
    metered look-up; until now they were used only to decide 402-vs-200 and
    then discarded. That meant a free user's first contact with metering was
    the hard wall at the cap, with no warning at 9, 10 or 11 — a normal limit
    presented as a punishment. Returning the meter lets the page state the
    user's own usage calmly and factually well before the wall.

    `limit is None` is the UNLIMITED sentinel (paid tiers, active no-card
    trial, and the first-session grace window). There is no cap to report, so
    remaining and resets_at are None too — the counter that would reset isn't
    running for that caller.
    """
    cap = meter.get("limit")
    return {
        "used": meter.get("used", 0),
        "limit": cap,
        "remaining": meter.get("remaining"),
        "resets_at": None if cap is None else _next_utc_midnight().isoformat(),
    }


def _client_ip(request: Request) -> str | None:
    """Real client IP behind Fly's edge proxy. Mirrors routers/auth +
    services/rate_limit: request.client.host is the proxy's internal peer (the
    SAME for every external visitor), so prefer the leftmost X-Forwarded-For
    entry (the original client). Used to key the anonymous lookup meter."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("/{symbol}")
async def ticker_detail(symbol: str, request: Request) -> dict:
    """Complete view of a single ticker — score breakdown, squeeze status, news.

    Freemium metering (added 2026-06-20): a "lookup" is one of these detailed
    views. Pro / Premium / active-trial callers are never metered. A logged-in
    FREE user gets tier.FREE_DAILY_LOOKUPS per UTC day; an anonymous (no-account)
    caller gets tier.ANON_DAILY_LOOKUPS per IP per day. Over-cap callers get a
    402 per the shared API contract (error "free_lookup_limit" for free users,
    "signup_required" for anon). The lookup is only counted AFTER the symbol is
    confirmed to resolve to a real ticker, so a 404/invalid symbol never burns
    the caller's daily budget.

    The 200 response also carries the meter as `lookups`
    (used / limit / remaining / resets_at) so the client can show the count
    approaching the cap rather than only discovering it at the 402. See
    _lookup_meter_payload.

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
    connection across the multi-second Massive→Finnhub chain →
    QueuePool exhaustion. Then, after the connection was released but the fetch
    stayed inline, the multi-second call (× audit concurrency × the frontend's
    2x SSR retry) drove a latency death-spiral that 500'd the SSR pages. Both
    failure modes are gone now that the request path touches only the DB.
    """
    # Validate the symbol SHAPE before touching the DB — junk like "🏆 IVV" (a
    # legacy ghost row may match it exactly) 404s instead of rendering a
    # fabricated page + a duplicate-content /t/🏆 IVV URL for Google.
    # clean_symbol also strips + uppercases. Mirrors the ingestion chokepoint in
    # sheet_feed. (Re-applied after a concurrent ticker.py revert dropped it.)
    cleaned = clean_symbol(symbol)
    if cleaned is None:
        raise HTTPException(404, f"Ticker {symbol!r} is not a valid symbol")
    symbol = cleaned

    # Single short read txn: core ticker + squeeze (both indexed point lookups).
    # The pooled connection is checked out only for these, then returned on
    # context exit. News is read separately afterward (its own bounded session)
    # so a slow headline scan can never hold THIS connection — no upstream call
    # ever holds it either.
    async with SessionLocal() as session:
        t = (
            await session.execute(select(Ticker).where(Ticker.symbol == symbol))
        ).scalar_one_or_none()
        if t is None:
            raise HTTPException(404, f"Ticker {symbol} not in scanner universe")
        # Corruption guard: the composite is clamped 0-100 at every write path
        # (score.py:compute_tapeline_composite), so a score > 100 can only be a
        # legacy pre-clamp ghost that dropped out of the universe and was never
        # re-scored (e.g. MCW=104). Don't serve it as a real conviction page —
        # it would show an impossible score and overstate a stale ghost. 404
        # keeps this consistent with public_top_tickers (which excludes
        # score > 100 from the sitemap), so Google is never pointed at a URL
        # that then 404s. A genuinely-current ticker can never trip this.
        if t.score is not None and t.score > 100:
            raise HTTPException(404, f"Ticker {symbol} not in scanner universe")

        # ── Freemium daily-lookup metering ──────────────────────────────────
        # Only NOW that the symbol is confirmed to be a real, servable ticker do
        # we charge a lookup against the caller's daily budget — a 404 above
        # never reaches here, so an invalid/missing symbol never burns budget.
        # Pro/Premium/active-trial callers are uncapped (consume_* returns
        # allowed=True with no increment). Over-cap free/anon callers get a 402
        # per the shared contract (the frontend renders an upgrade / sign-up
        # wall). We resolve the caller in THIS short read txn (sub-ms auth read)
        # — the connection is still released on context exit before the news
        # fetch, preserving the rev2 connection discipline above.
        from app.services.usage import consume_ticker_lookup

        user = await current_user_optional(request, session)
        # Anonymous callers are NOT metered on this endpoint. The public
        # /t/{symbol} SEO pages are server-rendered from the single frontend
        # machine, so a per-IP anon cap here counted our OWN renders and 402'd
        # every ticker page after the first couple — the whole /t/ surface 500'd.
        # That data is meant to be public for SEO anyway. Anonymous "sign up to
        # keep looking" gating, if we want it, belongs as a client-side prompt on
        # the page itself, not on this shared SSR/public endpoint. Logged-in FREE
        # users are still capped (durable per-user counter); Pro/Premium/active-
        # trial remain uncapped. (consume_anon_lookup stays in services.usage as
        # a dormant utility for that future client-side gate.)
        #
        # The meter is also RETURNED (see `lookups` in the payload) so the
        # ticker page can show the user where they stand before the wall,
        # instead of the cap arriving as a surprise 402. Anonymous callers
        # aren't metered here, so `lookups` stays None for them.
        lookups_payload: dict | None = None
        if user is not None:
            meter = await consume_ticker_lookup(session, user)
            if not meter["allowed"]:
                # Free user out of daily look-ups — the conversion wall. Log the
                # cap hit (fire-and-forget; only free tiers reach allowed=False,
                # and record_cap_hit refuses paid tiers anyway) before the 402.
                from app.services.cap_events import record_cap_hit

                await record_cap_hit(session, user.id, "daily_lookups", user.tier)
                raise HTTPException(
                    402,
                    detail={
                        "error": "free_lookup_limit",
                        "used": meter["used"],
                        "limit": meter["limit"],
                        "tier": "free",
                    },
                )
            lookups_payload = _lookup_meter_payload(meter)

        sq = (
            await session.execute(
                select(SqueezeSetup).where(SqueezeSetup.symbol == symbol)
            )
        ).scalar_one_or_none()
        # News is fetched separately, AFTER this core read txn closes (see
        # _fetch_ticker_news) — its own bounded session so a slow/timed-out
        # headline scan can never hold THIS pooled connection or affect the
        # core payload. This is what stops the 2026-06-01 pool-exhaustion
        # death-spiral at the root.

    # Per-ticker headlines — newest ≤8 mentioning this symbol. Bounded (recency
    # window + Postgres statement timeout) and isolated, so a slow scan degrades
    # to [] instead of 500ing the page or wedging the pool (incident 2026-06-01).
    news_payload = await _fetch_ticker_news(symbol)

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
        # Freemium daily look-up meter for THIS caller (null for anonymous
        # callers, who aren't metered on this endpoint). limit=null means
        # unmetered — paid tier, active trial, or first-session grace.
        "lookups": lookups_payload,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("/{symbol}/ratings")
async def ticker_ratings(symbol: str, request: Request) -> dict:
    """Analyst ratings consensus + recent events for a ticker — Premium-only.

    Trial users (auto-Premium for 14 days) and paid Premium subscribers see
    the widget. Free + Pro users hit the Paywall on the frontend; this
    endpoint also enforces the gate so the data can't be sniffed via direct
    API call.

    Lazy-loaded — the main ticker payload doesn't include this so the page
    paints before the upstream ratings call completes. When Finnhub has no
    coverage, the response shape stays the same with an empty events list so
    the frontend renders a clean empty state.
    """
    # Resolve + tier-gate the user in a SHORT-LIVED session that is released
    # BEFORE the upstream ratings call. Holding a pooled DB connection across
    # the multi-second upstream is what exhausted the pool and downed the API on
    # 2026-06-01 — the same anti-pattern the ticker_detail rev2 fix removed for
    # the news fetch. The auth read is sub-ms; the connection must not stay
    # pinned for the duration of the upstream request. See app/db.py.
    async with SessionLocal() as session:
        user = await current_user_required(request, session)
        allowed = has_feature(Tier(user.tier), "ratings.analyst")
    if not allowed:
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
    request: Request,
    days_back: int = 90,
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
    # Short-lived session, released BEFORE the upstream Finnhub call (see the
    # ticker_ratings note + app/db.py — avoids pinning a pooled connection
    # across the multi-second upstream, which exhausted the pool on 2026-06-01).
    async with SessionLocal() as session:
        user = await current_user_required(request, session)
        allowed = has_feature(Tier(user.tier), "insider.form4")
    if not allowed:
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
