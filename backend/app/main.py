"""FastAPI entry point."""
from __future__ import annotations

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import (
    account,
    admin,
    alerts,
    auth,
    billing,
    briefing,
    calendar_routes,
    congress,
    contact,
    embed,
    export,
    extension,
    heatmap,
    holdings,
    inbox,
    internal,
    mcp,
    me,
    news,
    newsletter,
    oauth,
    regime,
    roadmap,
    scanner,
    scorecard,
    search,
    squeeze,
    stream,
    ticker,
    watchlist,
    webhooks,
)
from app.routers import (
    telegram as telegram_router,
)
from app.services.news_health import (
    NEWS_INGEST_DOWN_SECONDS,
    NEWS_INGEST_STALE_SECONDS,
    news_wire_canary_seconds,
)
from app.services.ticker_ordering import ORDER_PATTERN, SORT_PATTERN

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()

# Captured once at module import — exposed by /api/version so the operator
# can verify a deploy actually landed by checking that boot_time changed.
from datetime import UTC as _UTC
from datetime import datetime as _datetime

_boot_time_iso = _datetime.now(_UTC).isoformat()

# ---- Sentry (env-gated) -----------------------------------------------------
# Initialised before app construction so the FastAPI integration can hook
# the request lifecycle. No-op when SENTRY_DSN is blank — zero overhead in
# dev or until the operator opts in.
if settings.sentry_dsn:
    try:
        import sentry_sdk

        from app.sentry_filter import before_send

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            before_send=before_send,
            environment=settings.sentry_environment or settings.app_env,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            release="tapeline@0.1.0",
            # Don't accidentally upload PII (emails, watchlist contents, etc.)
            send_default_pii=False,
            # Filter the noisy /api/health pings — they don't need APM tracking.
            traces_sampler=lambda ctx: 0.0
            if (ctx.get("asgi_scope", {}) or {}).get("path", "").startswith("/api/health")
            else settings.sentry_traces_sample_rate,
        )
        logger.info("sentry.initialized env=%s sample_rate=%.2f",
                    settings.sentry_environment or settings.app_env,
                    settings.sentry_traces_sample_rate)
    except Exception:
        logger.exception("sentry.init_failed — continuing without error monitoring")


def _check_session_secret() -> None:
    """Refuse to boot in a non-dev environment when SESSION_SECRET is unset.

    `services/session._session_secret()` now fails CLOSED — with SESSION_SECRET
    unset in prod it raises rather than deriving a forgeable key (previously it
    fell back to STRIPE_WEBHOOK_SECRET, and failing that a constant hardcoded in
    a public repo, either of which let session cookies + the 2FA challenge token
    be forged). Surfacing that here converts a would-be per-request 500 into a
    clean, loud boot failure that the post-deploy smoke check catches — so a
    misconfiguration is caught at deploy, never on a user's first request.

    PREREQUISITE: SESSION_SECRET must be set in prod BEFORE this ships (run the
    'Set SESSION_SECRET' workflow). Setting it changes the signing key and signs
    every user out once — a one-time cost, not a fallback.
    """
    if settings.app_env == "development":
        return
    if getattr(settings, "session_secret", None):
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_message(
            "SESSION_SECRET is not set — refusing to boot", level="fatal",
        )
    except Exception:
        pass
    raise RuntimeError(
        "SESSION_SECRET is not set in a non-development environment. Run the "
        "'Set SESSION_SECRET (bootstrap / rotate)' GitHub Actions workflow, then "
        "redeploy. The app refuses to start rather than sign sessions with a "
        "guessable key."
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("app.startup env=%s", settings.app_env)
    _check_session_secret()
    yield
    logger.info("app.shutdown")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Tapeline — live quantitative market scanner API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["*"],
    # Content-Disposition carries the server-chosen CSV filename
    # (tapeline-scanner-<date>.csv). Without exposing it, the cross-origin
    # frontend (tapeline.io → api.tapeline.io) can't read the header and
    # falls back to a generic client-side filename.
    expose_headers=["Content-Disposition"],
)


INTERNAL_SSR_HEADER = "x-tapeline-internal"


def _is_trusted_ssr(request: Request) -> bool:
    """True when this request carries our own SSR shared secret.

    Server-side rendering funnels EVERY page render for the whole site through
    a single Fly egress IP, so it shares one limit_api bucket (120/min). A
    single ticker page fans out to ~3 upstream calls, so roughly 40 cold page
    renders a minute drains it — after which the backend 429s its OWN frontend
    and frontend/app/t/[symbol]/page.tsx turns that into a 500. Any bulk crawl
    trips it: the weekly SEO audit reported ~1,534 "broken" URLs it had broken
    itself, and Googlebot walking the ~8,400-page ticker sitemap would see the
    same 500s — a real deindexing risk on the site's biggest crawl surface.
    (main.py already exempts /api/embed/ for exactly this one-shared-IP reason;
    this closes the same gap for the SSR reads themselves.)

    Constant-time compare, and an unset token disables the exemption entirely,
    so a missing/mis-set secret degrades to today's behaviour rather than
    removing rate limiting. The token is server-only on the frontend (never
    NEXT_PUBLIC_*), so it is not reachable from a browser bundle.
    """
    token = settings.internal_ssr_token
    if not token:
        return False
    presented = request.headers.get(INTERNAL_SSR_HEADER)
    if not presented:
        return False
    return secrets.compare_digest(presented, token)


@app.middleware("http")
async def log_and_rate_limit(request: Request, call_next):
    # Rate-limit all /api/* requests except health + webhooks (which have their
    # own signature check) + embed-impression counting.
    #
    # Why /api/embed/ is exempt: limit_api keys on the CLIENT IP, and every
    # impression POST originates from the Fly frontend machine — one IP for the
    # whole site. Sharing that 120/min bucket would let badge traffic starve the
    # SSR calls that actually render pages (a hot README could 429 /api/ticker
    # for everyone). The embed router applies its own per-embedding-host and
    # global-write-volume buckets instead, which is the limit that's actually
    # meaningful here.
    path = request.url.path
    if (
        path.startswith("/api/")
        and not path.startswith("/api/health")
        and not path.startswith("/api/webhooks/")
        and not path.startswith("/api/embed/")
    ):
        from app.services.rate_limit import limit_api
        try:
            if not _is_trusted_ssr(request):
                await limit_api(request)
        except Exception as exc:
            status = getattr(exc, "status_code", 429)
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=status, content={"detail": str(exc)})

    response = await call_next(request)
    logger.info("%s %s -> %s", request.method, path, response.status_code)
    return response


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.exception("unhandled_error path=%s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.post("/api/log-client-error")
async def log_client_error(request: Request) -> dict[str, bool]:
    """Sink for client-side errors caught by the frontend's error.tsx.

    Browsers can't talk to Fly logs directly, so the React error boundary
    POSTs here when something explodes client-side. We log it with the URL,
    user agent, and (truncated) stack so it shows up in the same log stream
    as backend errors. Sentry, when configured, also captures it via the
    Sentry SDK call below — same event, two destinations.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    msg = str(body.get("message", ""))[:500]
    stack = str(body.get("stack", ""))[:2000]
    url = str(body.get("url", ""))[:300]
    ua = (request.headers.get("user-agent") or "")[:200]
    logger.warning(
        "client_error url=%s ua=%s msg=%s stack=%s",
        url, ua, msg, stack.replace("\n", " | "),
    )
    if settings.sentry_dsn:
        try:
            import sentry_sdk

            with sentry_sdk.push_scope() as scope:
                scope.set_tag("source", "client")
                scope.set_extra("url", url)
                scope.set_extra("user_agent", ua)
                scope.set_extra("client_stack", stack)
                sentry_sdk.capture_message(msg or "client error", level="error")
        except Exception:
            logger.exception("client_error.sentry_capture_failed")
    return {"ok": True}


@app.get("/api/public/top-tickers")
async def public_top_tickers(limit: int = 500) -> dict[str, object]:
    """Public, no-auth, no-tier-gating list of top tickers by score.

    Used by the frontend sitemap.ts at sitemap-render time to seed the
    /t/{symbol} URL list for Google. Intentionally separate from the
    /api/scanner endpoint, which tier-gates row count for the in-app
    scanner UI — sitemap surface needs to be wide regardless of auth.
    """
    from sqlalchemy import desc, select

    from app.db import session_scope
    from app.models import Ticker

    capped = max(1, min(limit, 1000))
    async with session_scope() as session:
        # Deliberately do NOT apply the FULL freshness/factor floor here: the
        # sitemap wants breadth (every real /t/{symbol} page Google should know
        # about), and a slightly-stale row still has a valid ticker page.
        # BUT exclude the two CORRUPTION signatures so the sitemap never points
        # Google at a URL that routers.ticker now 404s (which would be the exact
        # crawled-not-indexed problem):
        #   • space/emoji-in-symbol rows ("🏆 IVV") — sheet annotations ingested
        #     as symbols; broken /t/🏆 IVV URLs + dupes of real ETFs. notlike(
        #     "% %") keeps legit futures like CL=F.
        #   • score > 100 — impossible for the clamped composite, so it can only
        #     be a legacy pre-clamp ghost (e.g. MCW=104) that dropped out of the
        #     universe. A real ticker never exceeds 100, so breadth is unharmed.
        result = await session.execute(
            select(Ticker.symbol)
            .where(Ticker.score.is_not(None))
            .where(Ticker.score <= 100)
            .where(Ticker.symbol.notlike("% %"))
            .order_by(desc(Ticker.score))
            .limit(capped)
        )
        symbols = [row[0] for row in result.all()]
    return {"count": len(symbols), "symbols": symbols}


@app.get("/api/public/signals")
async def public_signals(
    limit: int = 1000,
    offset: int = 0,
    min_score: float = 0,
    signal: str | None = None,
    sector: str | None = None,
    max_price: float | None = None,
    # Liquidity floor, mirroring /api/scanner's SCANNER_MIN_DOLLAR_VOLUME.
    # Defaults to 0 (disabled) so every existing caller of this endpoint —
    # /signals, the sitemap, the ticker page — is completely unaffected; the
    # SEO pages that moved off the row-capped scanner pass the scanner's own
    # value so their ranked lists keep excluding near-untradeable names.
    # Rows with an UNKNOWN price or volume are kept either way, so the filter
    # can only remove obvious junk, never hide a name we lack a read for.
    min_dollar_volume: float = 0,
    sort: str = Query("score", pattern=SORT_PATTERN),
    order: str = Query("desc", pattern=ORDER_PATTERN),
) -> dict[str, object]:
    """Public, no-auth, no-tier-cap view of EVERY scored ticker.

    The companion to the /signals frontend page. Returns the full
    universe (or a sorted/filtered slice of it) so unauthenticated
    visitors can see exactly what Tapeline is scoring — same "public
    formula, public scorecard, public everything" stance as /scorecard
    and /how-it-works.

    Distinct from /api/scanner which tier-gates row count (Free → 10)
    AND applies the 24h delay for unauth/free visitors. /api/public/signals
    has neither cap nor delay — every visitor sees the same scores the
    paid scanner does. The paid scanner's value moves to its features
    (filter UX, watchlist, alerts, exports), not data access.

    Sorted desc by score. Capped at 2000 rows per request to keep the
    JSON payload reasonable; the full universe is currently ~500 names,
    so a single call returns everything.
    """
    from sqlalchemy import func, or_, select

    from app.db import session_scope
    from app.models import Ticker
    from app.services.ticker_freshness import live_clauses
    from app.services.ticker_ordering import deterministic_order_by

    capped = max(1, min(limit, 2000))
    # Ticker.score IS NOT NULL is enforced by live_clauses() below.
    stmt = select(Ticker).where(Ticker.score >= min_score)
    if signal:
        stmt = stmt.where(Ticker.signal == signal)
    if sector:
        # Case-insensitive so a URL slug ("technology") matches the stored
        # display casing ("Technology"). Lets an anonymous caller pull a
        # WHOLE sector cohort in one request — which is what the ticker
        # page's "ranks #X out of Y {sector} stocks" sentence needs to be
        # true. Doing it here rather than filtering client-side matters:
        # the alternative was fetching the top-N of the universe and
        # filtering, which silently yields a handful of rows per sector and
        # publishes a rank against a sample instead of the cohort.
        stmt = stmt.where(func.lower(Ticker.sector) == sector.strip().lower())
    if max_price is not None:
        # Mirrors /api/scanner's max_price so the price-anchored listicle pages
        # (/best-stocks-for/penny-stocks, /under-5, /under-10) can read the
        # un-gated endpoint and still get their price bound applied in SQL.
        stmt = stmt.where(Ticker.price <= max_price)
    if min_dollar_volume > 0:
        # Byte-for-byte the scanner's clause: keep rows whose price or volume
        # is UNKNOWN, drop only those with a KNOWN dollar-volume below the
        # floor. Any divergence here would show up as the SEO page and the
        # in-app scanner disagreeing about which names qualify.
        stmt = stmt.where(
            or_(
                Ticker.price.is_(None),
                Ticker.volume.is_(None),
                Ticker.price * Ticker.volume >= min_dollar_volume,
            )
        )

    async with session_scope() as session:
        # Freshness + data-quality floor — drop stale "ghost" rows (delisted
        # tickers still carrying a pre-refresh raw score that outranks fresh
        # composites) AND corrupt rows (score>100, emoji-in-symbol annotations,
        # <2 factors) so the public /signals front door ranks the live, clean
        # universe — not 12-day-old ghosts or ingestion artifacts. See
        # app.services.ticker_freshness.
        for clause in await live_clauses(session):
            stmt = stmt.where(clause)
        # Same ORDER BY the tier-gated scanner uses (services/ticker_ordering),
        # so a public SEO page and the in-app scanner can never rank the same
        # list differently — including the dollar-volume/symbol tiebreak that
        # makes the published order reproducible run to run.
        stmt = (
            stmt.order_by(*deterministic_order_by(sort, order))
            .limit(capped)
            .offset(max(0, offset))
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

    return {
        "count": len(rows),
        "limit": capped,
        "offset": offset,
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
                "confidence_pct": r.confidence_pct,
                "sub_trend": r.sub_trend,
                "sub_rs": r.sub_rs,
                "sub_fundamentals": r.sub_fundamentals,
                "sub_momentum": r.sub_momentum,
                "sub_macro": r.sub_macro,
                "sub_smart_money": r.sub_smart_money,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }


@app.get("/api/public/regime")
async def public_regime() -> dict[str, object]:
    """Public, no-auth regime snapshot — powers the /market-regime SEO page.

    Returns just the regime label, the four macro inputs (VIX, 10Y yield,
    DXY, breadth) + sector leaders + the Fear & Greed score. Intentionally
    a thinner payload than /api/regime (the Pro-gated authed endpoint),
    which includes the per-component F&G breakdown plus a more detailed
    `updated_at`. The public preview is enough to render a real macro card
    + dial on the SEO landing page; the deeper breakdown stays Pro.
    """
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import RegimeState, Ticker
    from app.services.fear_greed import compute_fear_greed

    async with session_scope() as session:
        row = (await session.execute(select(RegimeState).where(RegimeState.id == 1))).scalar_one_or_none()
        if row is None:
            return {"available": False}
        spy_5d = (await session.execute(
            select(Ticker.change_pct_5d).where(Ticker.symbol == "SPY")
        )).scalar_one_or_none()
    fg = compute_fear_greed(
        vix=row.vix,
        breadth_pct=row.breadth_pct,
        regime=row.regime,
        spy_change_5d_pct=spy_5d,
    )
    return {
        "available": True,
        "regime": row.regime,
        "vix": row.vix,
        "dxy": row.dxy,
        "yield_10y": row.yield_10y,
        "rate_direction": row.rate_direction,
        "breadth_pct": row.breadth_pct,
        "sector_leaders": row.sector_leaders,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "fear_greed": {"score": fg["score"], "label": fg["label"]},
    }


@app.get("/api/public/insider-buys")
async def public_insider_buys(limit: int = 10) -> dict[str, object]:
    """Public, no-auth feed of recent open-market insider buys (Form 4 code 'P').

    Powers /insider-buying. The underlying data is SEC EDGAR public
    filings (we fetch via Finnhub) so there's no licensing constraint
    on exposing a preview. Capped at 20 rows to keep the SEO surface
    a teaser, not a replacement for /app/holdings (Premium).
    """
    from sqlalchemy import desc, select

    from app.db import session_scope
    from app.models import InsiderTransaction

    capped = max(1, min(limit, 20))
    async with session_scope() as session:
        result = await session.execute(
            select(InsiderTransaction)
            # SEC Form 4 code 'P' = open-market buy. The high-signal cluster
            # we surface separately from option-grant / sale rows.
            .where(InsiderTransaction.code == "P")
            .where(InsiderTransaction.share_change > 0)
            .order_by(desc(InsiderTransaction.transaction_date))
            .limit(capped)
        )
        rows = result.scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "symbol": r.symbol,
                "insider_name": r.insider_name,
                "transaction_date": r.transaction_date,
                "share_change": r.share_change,
                "transaction_price": r.transaction_price,
                "transaction_value": r.transaction_value,
                "code": r.code,
            }
            for r in rows
        ],
    }


@app.get("/api/public/squeeze")
async def public_squeeze(limit: int = 5) -> dict[str, object]:
    """Public, no-auth preview of the squeeze-watch surface.

    Powers /short-squeeze-scanner. Capped tightly (5 rows by default,
    20 hard max) so the live /app/squeeze view (Pro+, no row cap) is
    still the upgrade reason. Pre-computed spike_score / squeeze_days /
    OBV trend are exposed — the structural setup is the SEO hook.
    """
    from sqlalchemy import desc, select

    from app.db import session_scope
    from app.models import SqueezeSetup

    capped = max(1, min(limit, 20))
    async with session_scope() as session:
        result = await session.execute(
            select(SqueezeSetup)
            .order_by(desc(SqueezeSetup.spike_score))
            .limit(capped)
        )
        rows = result.scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "symbol": r.symbol,
                "spike_score": r.spike_score,
                "squeeze_days": r.squeeze_days,
                "volume_multiple": r.volume_multiple,
                "obv_trend": r.obv_trend,
                "breakout_type": r.breakout_type,
                "reason": r.reason,
            }
            for r in rows
        ],
    }


@app.get("/api/public/heatmap")
async def public_heatmap() -> dict[str, object]:
    """Public, no-auth sector-level heatmap for /stock-market-heatmap.

    Returns the 11 GICS sectors + Tapeline buckets with their
    *aggregate* 1D change (volume-weighted average). Per-ticker
    drill-down stays on the Pro /app/heatmap surface. The aggregated
    sector tiles are enough to render a real heatmap on the SEO page
    without giving away the granular surface.
    """
    from collections import defaultdict

    from sqlalchemy import select

    from app.db import session_scope
    from app.models import Ticker
    from app.services.sector import canonical_sector
    from app.services.ticker_freshness import live_clauses

    async with session_scope() as session:
        # Freshness + data-quality floor — exclude stale ghost rows AND corrupt
        # rows from the aggregate so a dropped/ghost ticker's last-known 1D move
        # can't skew a sector tile. (Ticker.score IS NOT NULL is part of the
        # floor.) See app.services.ticker_freshness.
        stmt = (
            select(Ticker.sector, Ticker.change_pct_1d, Ticker.price, Ticker.volume)
            .where(Ticker.change_pct_1d.is_not(None))
            .where(Ticker.price.is_not(None))
            .where(Ticker.volume.is_not(None))
        )
        for clause in await live_clauses(session):
            stmt = stmt.where(clause)
        result = await session.execute(stmt)
        rows = result.all()

    buckets: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for sector_raw, change_pct, price, volume in rows:
        sector = canonical_sector(sector_raw or "Unknown")
        dollar_vol = (price or 0) * (volume or 0)
        if dollar_vol <= 0:
            continue
        buckets[sector].append((change_pct or 0.0, dollar_vol))

    out = []
    for sector, items in buckets.items():
        total_vol = sum(v for _, v in items)
        if total_vol <= 0:
            continue
        weighted = sum(c * v for c, v in items) / total_vol
        out.append({
            "sector": sector,
            "change_pct_1d": round(weighted, 3),
            "ticker_count": len(items),
        })
    # Sort by 1D move desc so the rendering side gets it in a usable order.
    out.sort(key=lambda s: s["change_pct_1d"], reverse=True)
    return {"count": len(out), "sectors": out}


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Bare-bones liveness probe — must stay cheap (no DB, no external calls).
    Used by Fly.io health checks + uptime monitors that just need a 200."""
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env, "version": "0.1.0"}


@app.get("/api/version")
async def version() -> dict[str, str]:
    """Reports the running build's git SHA + boot time. Use this when verifying
    a deploy actually landed: hit /api/version, compare commit to your latest
    git SHA, confirm boot_time updated since the deploy started.

    SHA is read once at process start from the FLY_IMAGE_REF env var (Fly.io
    sets it automatically), the GIT_SHA env var (manual override), or the
    fly machine ID. boot_time is captured at module import.
    """
    import os
    sha = (
        os.environ.get("GIT_SHA")
        or os.environ.get("FLY_IMAGE_REF", "").split(":")[-1]
        or os.environ.get("FLY_MACHINE_ID", "")
        or "unknown"
    )
    return {
        "version": "0.1.0",
        "commit": sha[:12] if sha else "unknown",
        "boot_time": _boot_time_iso,
        "env": settings.app_env,
    }


# Short-TTL cache for /api/status. Every homepage visitor's LiveCounters strip
# polls this every 60s, and each call runs 5 DB queries — so a traffic spike
# (a launch on HN/Reddit) would multiply straight onto Neon. The payload is a
# "~5min refresh" status band, so a 30s server cache is invisible to users and
# collapses N concurrent polls into one DB hit per window. Only healthy
# responses are cached; a hard DB error bypasses the cache so uptime monitors
# still see the 503 immediately.
_STATUS_CACHE: dict[str, object] = {"ts": 0.0, "payload": None}
_STATUS_TTL_SECONDS = 30.0


@app.get("/api/status")
async def status() -> dict[str, object]:
    """Richer status check — for the public /status page and external uptime
    monitors that want feature-level signals (DB reachable, ticker count,
    last worker tick). Wraps each probe in try/except so a single broken
    feature doesn't take the whole status response down.
    """
    import time as _time
    from datetime import UTC, datetime

    from sqlalchemy import func, select

    from app.db import session_scope
    from app.models import NewsItem, RegimeState, Ticker

    _now_ts = _time.time()
    _cached = _STATUS_CACHE.get("payload")
    _cts = _STATUS_CACHE.get("ts", 0.0)
    if (
        _cached is not None
        and isinstance(_cts, (int, float))
        and (_now_ts - _cts) < _STATUS_TTL_SECONDS
    ):
        return _cached  # type: ignore[return-value]

    out: dict[str, object] = {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "version": "0.1.0",
        "now": datetime.now(UTC).isoformat(),
        "checks": {},
    }
    checks: dict[str, dict[str, object]] = out["checks"]  # type: ignore[assignment]

    try:
        async with session_scope() as session:
            n_tickers = (await session.execute(select(func.count(Ticker.symbol)))).scalar_one()
            n_news = (await session.execute(select(func.count(NewsItem.id)))).scalar_one()
            regime_row = (await session.execute(select(RegimeState).where(RegimeState.id == 1))).scalar_one_or_none()
            checks["database"] = {"status": "ok", "tickers": int(n_tickers or 0), "news_items": int(n_news or 0)}
            if regime_row is not None and regime_row.updated_at is not None:
                # SQLite drops tzinfo on roundtrip (same guard as alerts.py /
                # auth.py / tier.py), so normalise naive->UTC before subtracting
                # from an aware now(). Without it the whole probe raised
                # "can't subtract offset-naive and offset-aware datetimes" and
                # the endpoint 503'd, blanking the homepage stat band.
                regime_updated = regime_row.updated_at
                if regime_updated.tzinfo is None:
                    regime_updated = regime_updated.replace(tzinfo=UTC)
                age = (datetime.now(UTC) - regime_updated).total_seconds()
                checks["worker_last_tick"] = {
                    "status": "ok" if age < 300 else "stale",
                    "regime": regime_row.regime,
                    "updated_at": regime_updated.isoformat(),
                    "age_seconds": int(age),
                }
            else:
                checks["worker_last_tick"] = {"status": "unknown", "detail": "no regime row yet"}

            # News-health probe — added 2026-05-09 after the 14h-stale incident
            # where _refresh_news was failing silently on a column-width
            # overflow.
            #
            # TWO DIFFERENT SIGNALS, and conflating them was a bug (retuned
            # 2026-08 after the freshness cron alerted on ~25% of runs with
            # nothing actually wrong):
            #
            #   ingest heartbeat = max(created_at) — when did WE last write a
            #     row? This is the real pipeline-health signal. It is driven by
            #     our own 5-min refresh loop, so it is phase-INDEPENDENT:
            #     measured over 21 days of production, p90 was 1.9–3.1 min in
            #     EVERY session phase and the longest silence was 54 min. A
            #     stall here means the worker, the vendor credentials, or the
            #     DB write is genuinely broken — which is exactly what the
            #     2026-05-09 incident was.
            #
            #   wire freshness = max(published_at) — how old is the newest
            #     article the VENDOR has published to us. Dominated by
            #     vendor-side delivery lag (measured p50 44 min, p90 96 min
            #     even for the freshest articles we receive), NOT by our
            #     health. Driving the pill off it flagged "degraded" on ~6% of
            #     all ticks while ingestion was perfectly healthy, so it is now
            #     only a loose "the wire looks dead" canary.
            from datetime import timedelta as _td

            latest_news = (
                await session.execute(
                    select(NewsItem.published_at)
                    .order_by(NewsItem.published_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            latest_ingest = (
                await session.execute(select(func.max(NewsItem.created_at)))
            ).scalar_one_or_none()
            since_24h = datetime.now(UTC) - _td(hours=24)
            n_24h = (
                await session.execute(
                    select(func.count(NewsItem.id)).where(
                        NewsItem.created_at >= since_24h
                    )
                )
            ).scalar_one()

            if latest_news is not None:
                now_utc = datetime.now(UTC)
                # Same SQLite naive->UTC normalisation as the regime probe above.
                if latest_news.tzinfo is None:
                    latest_news = latest_news.replace(tzinfo=UTC)
                news_age = (now_utc - latest_news).total_seconds()

                # --- PRIMARY: ingestion heartbeat -------------------------
                # Flat thresholds: unlike wire freshness this does not vary by
                # session phase, so phase tiers would add noise, not accuracy.
                # 120 min is ~2.2x the worst silence observed in 21 days (54
                # min) — 0 false positives across 1,992 simulated ticks — while
                # still catching a genuine stall inside two hours.
                ingest_age = None
                if latest_ingest is not None:
                    if latest_ingest.tzinfo is None:
                        latest_ingest = latest_ingest.replace(tzinfo=UTC)
                    ingest_age = (now_utc - latest_ingest).total_seconds()

                if ingest_age is None:
                    n_status = "unknown"
                elif ingest_age >= NEWS_INGEST_DOWN_SECONDS:
                    n_status = "down"
                elif ingest_age >= NEWS_INGEST_STALE_SECONDS:
                    n_status = "stale"
                else:
                    n_status = "ok"

                # --- SECONDARY: wire-dead canary --------------------------
                # Can only escalate ok -> stale; never "down". Thresholds are
                # set from the measured frontier-advance distribution so a
                # normally-lagging vendor never trips them (0/1,992 ticks).
                wire_threshold = news_wire_canary_seconds(now_utc)
                wire_stale = news_age >= wire_threshold
                if wire_stale and n_status == "ok":
                    n_status = "stale"

                checks["news"] = {
                    "status": n_status,
                    # Primary health signal — consumed by the freshness cron.
                    "ingest_age_seconds": (
                        int(ingest_age) if ingest_age is not None else None
                    ),
                    "latest_ingested_at": (
                        latest_ingest.isoformat() if latest_ingest else None
                    ),
                    "ingest_stale_after_seconds": NEWS_INGEST_STALE_SECONDS,
                    # Secondary canary — vendor publish lag, not our health.
                    "latest_article_age_seconds": int(news_age),
                    "latest_published_at": latest_news.isoformat(),
                    "wire_stale": wire_stale,
                    "wire_stale_after_seconds": wire_threshold,
                    "articles_last_24h": int(n_24h or 0),
                }
                # Bubble up to top-level status so the public /status pill
                # turns yellow when the PIPELINE is unhealthy. A merely-quiet
                # wire no longer degrades the pill on its own.
                if n_status in ("stale", "down"):
                    out["status"] = "degraded"
            else:
                checks["news"] = {"status": "unknown", "detail": "no news rows yet"}
    except Exception as exc:
        checks["database"] = {"status": "error", "detail": str(exc)[:200]}
        out["status"] = "degraded"

    # Per-vendor configured-ness (truthy presence, not connectivity — keeps this cheap)
    checks["integrations"] = {
        "massive": bool(settings.massive_api_key or settings.polygon_api_key),
        "finnhub": bool(settings.finnhub_api_key),
        "fred": bool(settings.fred_api_key),
        "stripe": bool(settings.stripe_secret_key),
        "resend": bool(settings.resend_api_key),
    }

    # If any required check is hard-failing, expose 503 so uptime monitors
    # notice. NOT cached — a hard error must stay visible on the very next poll.
    if checks.get("database", {}).get("status") == "error":
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=out)
    # Healthy response — cache it so the next 30s of polls skip the 5 DB queries.
    _STATUS_CACHE["payload"] = out
    _STATUS_CACHE["ts"] = _now_ts
    return out


app.include_router(scanner.router, prefix="/api/scanner", tags=["scanner"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(squeeze.router, prefix="/api/squeeze", tags=["squeeze"])
app.include_router(regime.router, prefix="/api/regime", tags=["regime"])
app.include_router(congress.router, prefix="/api/congress", tags=["congress"])
app.include_router(holdings.router, prefix="/api/holdings", tags=["holdings"])
app.include_router(stream.router, prefix="/api/stream", tags=["stream"])
app.include_router(me.router, prefix="/api/me", tags=["me"])
app.include_router(billing.router, prefix="/api/billing", tags=["billing"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(telegram_router.router, prefix="/api/telegram", tags=["telegram"])
app.include_router(ticker.router, prefix="/api/ticker", tags=["ticker"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(scorecard.router, prefix="/api/scorecard", tags=["scorecard"])
# Public dataset exports: /api/scorecard.csv and /api/scorecard.json.
#
# Registered DIRECTLY on the app rather than via a router. These paths are
# siblings of the "/api/scorecard" prefix, not children of it, so they cannot
# be expressed as router sub-paths: a suffix like ".csv" fails Starlette's
# "routed paths must start with '/'" rule and never mounts, and routing them
# through an extra prefix-less router proved to register unreliably. Binding
# the handlers here is explicit and cannot silently no-op — which matters,
# because the failure mode is a 404 on a public dataset we tell people to audit.
# Covered by tests/test_scorecard_dataset.py::test_both_export_routes_are_registered.
app.add_api_route(
    "/api/scorecard.csv",
    scorecard.export_scorecard_csv,
    methods=["GET"],
    tags=["scorecard"],
)
app.add_api_route(
    "/api/scorecard.json",
    scorecard.export_scorecard_json,
    methods=["GET"],
    tags=["scorecard"],
)
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(newsletter.router, prefix="/api/newsletter", tags=["newsletter"])
app.include_router(heatmap.router, prefix="/api/heatmap", tags=["heatmap"])
# Pro CSV export (scanner result set + watchlist) — the feature every pricing
# surface sells; tier-gated inside the router via FEATURES["export.csv"].
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(inbox.router, prefix="/api/inbox", tags=["inbox"])
app.include_router(briefing.router, prefix="/api/briefing", tags=["briefing"])
app.include_router(contact.router, prefix="/api/contact", tags=["contact"])
app.include_router(account.router, prefix="/api/account", tags=["account"])
app.include_router(internal.router, prefix="/api/internal", tags=["internal"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
# Embed-impression counting for /badge/{sym} + /embed/score/{sym}. Public and
# unauthenticated — it is called by the Next server on behalf of an anonymous
# browser. It runs its own (host-keyed + global) rate limits, and is exempt from
# the shared per-IP limiter below; see the note there.
app.include_router(embed.router, prefix="/api/embed", tags=["embed"])
app.include_router(extension.router, prefix="/api/extension", tags=["extension"])
# MCP lives at the bare /mcp (not under /api) because that is the URL shape MCP
# clients expect to paste: https://api.tapeline.io/mcp
app.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(oauth.router, prefix="/api/auth/oauth", tags=["oauth"])
app.include_router(calendar_routes.ipo_router, prefix="/api/ipos", tags=["calendar"])
app.include_router(calendar_routes.earnings_router, prefix="/api/earnings", tags=["calendar"])
from app.routers import referrals

app.include_router(referrals.router, prefix="/api/referrals", tags=["referrals"])
from app.routers import usage

app.include_router(usage.router, prefix="/api/usage", tags=["usage"])
app.include_router(roadmap.router, prefix="/api/roadmap", tags=["roadmap"])

# RFC 8058 one-click unsubscribe — public, HMAC-token-gated. Mounted at
# /api/unsubscribe (no auth) so List-Unsubscribe headers in marketing
# emails resolve quickly when Gmail / Outlook POSTs the one-click form.
from app.routers import unsubscribe as unsubscribe_router

app.include_router(unsubscribe_router.router, prefix="/api/unsubscribe", tags=["unsubscribe"])

# Phase A — multi-watchlists + scanner presets (PR Phase A1, 2026-05-18).
# Mounted alongside the legacy `/api/watchlist` (singular, item-level)
# router. `/api/watchlists` (plural) manages the list objects themselves;
# `/api/presets` manages saved scanner filter blobs.
from app.routers import presets, watchlists

app.include_router(watchlists.router, prefix="/api/watchlists", tags=["watchlists"])
app.include_router(presets.router, prefix="/api/presets", tags=["presets"])

# Premium public API — key management (session-authed) + the versioned,
# key-authenticated read surface (PR8, 2026-06-01). The /api/v1 router
# enforces the Premium tier gate + per-key daily quota in its dependency.
from app.routers import api_keys as api_keys_router
from app.routers import api_v1

app.include_router(api_keys_router.router, prefix="/api/api-keys", tags=["api-keys"])
app.include_router(api_v1.router, prefix="/api/v1", tags=["api-v1"])
