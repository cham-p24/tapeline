"""FastAPI entry point."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
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
    heatmap,
    holdings,
    me,
    news,
    oauth,
    regime,
    roadmap,
    scanner,
    scorecard,
    squeeze,
    stream,
    ticker,
    watchlist,
    webhooks,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()

# ---- Sentry (env-gated) -----------------------------------------------------
# Initialised before app construction so the FastAPI integration can hook
# the request lifecycle. No-op when SENTRY_DSN is blank — zero overhead in
# dev or until the operator opts in.
if settings.sentry_dsn:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("app.startup env=%s", settings.app_env)
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
)


@app.middleware("http")
async def log_and_rate_limit(request: Request, call_next):
    # Rate-limit all /api/* requests except health + webhooks (which have their own signature check)
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/health") and not path.startswith("/api/webhooks/"):
        from app.services.rate_limit import limit_api
        try:
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
        result = await session.execute(
            select(Ticker.symbol)
            .where(Ticker.score.is_not(None))
            .order_by(desc(Ticker.score))
            .limit(capped)
        )
        symbols = [row[0] for row in result.all()]
    return {"count": len(symbols), "symbols": symbols}


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Bare-bones liveness probe — must stay cheap (no DB, no external calls).
    Used by Fly.io health checks + uptime monitors that just need a 200."""
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env, "version": "0.1.0"}


@app.get("/api/status")
async def status() -> dict[str, object]:
    """Richer status check — for the public /status page and external uptime
    monitors that want feature-level signals (DB reachable, ticker count,
    last worker tick). Wraps each probe in try/except so a single broken
    feature doesn't take the whole status response down.
    """
    from datetime import UTC, datetime

    from sqlalchemy import func, select

    from app.db import session_scope
    from app.models import NewsItem, RegimeState, Ticker

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
                age = (datetime.now(UTC) - regime_row.updated_at).total_seconds()
                checks["worker_last_tick"] = {
                    "status": "ok" if age < 300 else "stale",
                    "regime": regime_row.regime,
                    "updated_at": regime_row.updated_at.isoformat(),
                    "age_seconds": int(age),
                }
            else:
                checks["worker_last_tick"] = {"status": "unknown", "detail": "no regime row yet"}
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

    # If any required check is hard-failing, expose 503 so uptime monitors notice.
    if checks.get("database", {}).get("status") == "error":
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=out)
    return out


app.include_router(scanner.router, prefix="/api/scanner", tags=["scanner"])
app.include_router(squeeze.router, prefix="/api/squeeze", tags=["squeeze"])
app.include_router(regime.router, prefix="/api/regime", tags=["regime"])
app.include_router(congress.router, prefix="/api/congress", tags=["congress"])
app.include_router(holdings.router, prefix="/api/holdings", tags=["holdings"])
app.include_router(stream.router, prefix="/api/stream", tags=["stream"])
app.include_router(me.router, prefix="/api/me", tags=["me"])
app.include_router(billing.router, prefix="/api/billing", tags=["billing"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(ticker.router, prefix="/api/ticker", tags=["ticker"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(scorecard.router, prefix="/api/scorecard", tags=["scorecard"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(heatmap.router, prefix="/api/heatmap", tags=["heatmap"])
app.include_router(briefing.router, prefix="/api/briefing", tags=["briefing"])
app.include_router(account.router, prefix="/api/account", tags=["account"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(oauth.router, prefix="/api/auth/oauth", tags=["oauth"])
app.include_router(calendar_routes.ipo_router, prefix="/api/ipos", tags=["calendar"])
app.include_router(calendar_routes.earnings_router, prefix="/api/earnings", tags=["calendar"])
from app.routers import referrals  # noqa: E402

app.include_router(referrals.router, prefix="/api/referrals", tags=["referrals"])
from app.routers import usage  # noqa: E402

app.include_router(usage.router, prefix="/api/usage", tags=["usage"])
app.include_router(roadmap.router, prefix="/api/roadmap", tags=["roadmap"])
