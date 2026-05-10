"""
News feed adapter.

Source preference (first non-empty wins):

    1. Benzinga (BENZINGA_API_KEY)  — faster wire, better ticker tagging.
    2. Massive / Polygon (MASSIVE_API_KEY or POLYGON_API_KEY) — included
       with the data subscription we already pay for.
    3. Mock — synthesised headlines so the UI has something to render
       before either key exists. Cleared on first real fetch.
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


_MOCK_HEADLINES = [
    ("{sym} beats Q{q} estimates, revenue up {pct}% YoY", 0.7),
    ("Analyst upgrades {sym} citing improved margins", 0.5),
    ("{sym} announces $2B share buyback program", 0.6),
    ("{sym} guides full-year revenue above consensus", 0.65),
    ("{sym} shares slip on profit-taking after rally", -0.2),
    ("Institutional investors increase stake in {sym}", 0.4),
    ("{sym} secures major contract with government agency", 0.55),
    ("Citi raises {sym} price target to ${target}", 0.5),
    ("Goldman Sachs reiterates Buy rating on {sym}", 0.4),
    ("{sym} insider sales disclosed in latest Form 4", -0.15),
    ("JP Morgan initiates coverage of {sym} with Overweight", 0.5),
    ("Options activity spikes in {sym} ahead of earnings", 0.1),
    ("{sym} announces partnership with leading cloud provider", 0.45),
    ("Regulatory filing shows {sym} expanding into new market", 0.35),
]

_MOCK_PUBLISHERS = ["Reuters", "Bloomberg", "Seeking Alpha", "Barrons", "WSJ", "CNBC", "MarketWatch"]


def _vendor_key() -> str:
    """Massive (formerly Polygon) accepts either env var. Prefer the new one."""
    return settings.massive_api_key or settings.polygon_api_key or ""


async def fetch_news_for_ticker(symbol: str, limit: int = 10) -> list[dict[str, Any]]:
    """Get recent news items mentioning a specific symbol.

    Queries all three sources (Benzinga, Massive, Finnhub) in parallel,
    merges by `published_at desc`, dedupes by id, returns top N.

    Why parallel-merge instead of fallback chain:
    The previous "first non-empty wins" pattern broke for tickers like
    BUR (Burford Capital, UK ADR). Massive returns 5 stale 2024 articles
    for BUR — non-empty, so the chain stopped there and never queried
    Finnhub's fresh 2026 coverage. Visitors saw 2-year-old news forever.
    Parallel-merge sorts everything by date and naturally surfaces the
    freshest article regardless of which source produced it.

    Quota cost is only marginally higher (3 requests instead of 1-2)
    and worth it for accuracy. Falls back to mock when all three return
    nothing.
    """
    import asyncio

    # Resolve each source to a coroutine (or None if not configured).
    bz_task = None
    massive_task = None
    fh_task = None

    try:
        from app.services import benzinga_feed as bz
        if bz.is_configured():
            bz_task = bz.fetch_news_for_ticker(symbol, limit)
    except Exception:
        logger.exception("news.benzinga_setup_failed symbol=%s", symbol)

    if _vendor_key():
        massive_task = _fetch_from_polygon([symbol], limit)

    try:
        from app.services import finnhub_feed as fh
        if fh.configured():
            fh_task = fh.fetch_news_for_ticker(symbol, limit=limit)
    except Exception:
        logger.exception("news.finnhub_setup_failed symbol=%s", symbol)

    coros = [t for t in (bz_task, massive_task, fh_task) if t is not None]
    if not coros:
        return _mock_news(symbol, limit)

    results = await asyncio.gather(*coros, return_exceptions=True)

    merged: list[dict[str, Any]] = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("news.source_failed symbol=%s err=%s", symbol, str(r)[:120])
            continue
        if isinstance(r, list):
            merged.extend(r)

    if not merged:
        return _mock_news(symbol, limit)

    # Dedupe by id (different sources can occasionally surface the same
    # article via licensing partnerships).
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for a in merged:
        aid = a.get("id")
        if not aid or aid in seen:
            continue
        seen.add(aid)
        unique.append(a)

    # Sort by published_at desc — freshest first regardless of source.
    unique.sort(key=lambda a: a.get("published_at") or "", reverse=True)
    return unique[:limit]


async def fetch_latest_news(limit: int = 30) -> list[dict[str, Any]]:
    """Get recent news across the universe."""
    # Benzinga first.
    try:
        from app.services import benzinga_feed as bz
        if bz.is_configured():
            rows = await bz.fetch_latest_news(limit)
            if rows:
                return rows
    except Exception:
        logger.exception("news.benzinga_latest_failed")

    if _vendor_key():
        try:
            rows = await _fetch_from_polygon(None, limit)
            if rows:
                return rows
        except Exception:
            logger.exception("news.latest_fetch_failed")
    # Mix of tickers for the markets/news landing
    from app.services.mock_feed import TICKER_UNIVERSE
    tickers = random.sample([t[0] for t in TICKER_UNIVERSE], k=min(limit, len(TICKER_UNIVERSE)))
    items = []
    for t in tickers:
        items.extend(_mock_news(t, 1))
    items.sort(key=lambda x: x["published_at"], reverse=True)
    return items[:limit]


async def _fetch_from_polygon(tickers: list[str] | None, limit: int) -> list[dict[str, Any]]:
    """Massive.com reference/news endpoint.

    Hostname overridable via MASSIVE_BASE_URL env var; api.polygon.io still
    works during the rebrand grace period.
    """
    params: dict[str, Any] = {
        "apiKey": _vendor_key(),
        "limit": limit,
        "order": "desc",
        "sort": "published_utc",
    }
    if tickers and len(tickers) == 1:
        params["ticker"] = tickers[0]

    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://api.massive.com/v2/reference/news", params=params)
        r.raise_for_status()
        body = r.json()

    rows = []
    for a in body.get("results", []):
        # Match benzinga_feed: column widened to String(2000) in
        # migration 0014; we cap at 1900 with a comma-boundary truncate
        # to avoid partial symbols and leave headroom.
        tickers_str = ",".join(a.get("tickers", []) or [])
        if len(tickers_str) > 1900:
            cutoff = tickers_str.rfind(",", 0, 1900)
            tickers_str = tickers_str[:cutoff] if cutoff > 0 else tickers_str[:1900]
        rows.append({
            "id": a["id"],
            "title": a["title"],
            "publisher": (a.get("publisher") or {}).get("name", ""),
            "author": a.get("author"),
            "published_at": datetime.fromisoformat(a["published_utc"].replace("Z", "+00:00")),
            "url": a["article_url"],
            "description": a.get("description"),
            "tickers": tickers_str,
            "sentiment": (a.get("insights", [{}])[0] or {}).get("sentiment_score") if a.get("insights") else None,
        })
    return rows


def _mock_news(symbol: str, n: int) -> list[dict[str, Any]]:
    items = []
    for _ in range(n):
        template, sentiment = random.choice(_MOCK_HEADLINES)
        ts = datetime.now(UTC) - timedelta(hours=random.randint(1, 72), minutes=random.randint(0, 59))
        title = template.format(
            sym=symbol,
            q=random.choice([1, 2, 3, 4]),
            pct=random.randint(4, 28),
            target=random.randint(50, 600),
        )
        items.append({
            "id": f"mock-{symbol}-{uuid.uuid4().hex[:10]}",
            "title": title,
            "publisher": random.choice(_MOCK_PUBLISHERS),
            "author": None,
            "published_at": ts,
            "url": f"https://example.com/news/{symbol.lower()}",
            "description": None,
            "tickers": symbol,
            "sentiment": round(sentiment + random.uniform(-0.1, 0.1), 2),
        })
    return items
