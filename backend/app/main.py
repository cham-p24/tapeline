"""FastAPI entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

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


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env, "version": "0.1.0"}


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
