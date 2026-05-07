"""
Benzinga news adapter.

Benzinga's news API delivers wire copy faster than Polygon and tends to
mention more tickers per article (Polygon often only tags primary tickers,
Benzinga tags every cashtag mentioned in body). We prefer Benzinga as the
primary news source when BENZINGA_API_KEY is set, falling back to Polygon
(via news_feed.py) on error.

Auth: query-param `token=...`. Endpoint:
    https://api.benzinga.com/api/v2/news

Response items expose:
    {
        "id": 12345,
        "title": "...",
        "author": "...",
        "created": "Tue, 06 May 2026 14:23:11 -0400",
        "updated": "...",
        "url": "https://www.benzinga.com/...",
        "stocks": [{"name": "AAPL"}, {"name": "MSFT"}],
        "channels": [{"name": "Earnings"}],
        "teaser": "...",
        "body": "<p>...</p>",
    }

Important: Benzinga's free tier doesn't carry sentiment scores. Articles
return with sentiment=None and the news-alert evaluator falls through to
"fire on any new article" semantics, same as Polygon's cheap tier.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_BASE_URL = "https://api.benzinga.com/api/v2/news"
# Conservative timeout — Benzinga is generally <500ms but flaky during NYSE open.
_TIMEOUT_SECONDS = 12.0


def _api_key() -> str:
    """Read Benzinga key — supports both BENZINGA_API_KEY and the bz.* prefix."""
    return getattr(settings, "benzinga_api_key", "") or ""


def is_configured() -> bool:
    return bool(_api_key())


async def fetch_news_for_ticker(symbol: str, limit: int = 10) -> list[dict[str, Any]]:
    """Headlines for a single symbol, ordered most-recent first."""
    if not is_configured():
        return []
    return await _fetch(tickers=[symbol], limit=limit)


async def fetch_latest_news(limit: int = 30) -> list[dict[str, Any]]:
    """General market news — no ticker filter."""
    if not is_configured():
        return []
    return await _fetch(tickers=None, limit=limit)


async def _fetch(tickers: list[str] | None, limit: int) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "token": _api_key(),
        "pageSize": min(max(limit, 1), 100),
        "displayOutput": "headline",  # body content not needed for the strip
    }
    if tickers:
        params["tickers"] = ",".join(t.upper() for t in tickers)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as c:
            r = await c.get(_BASE_URL, params=params, headers={"Accept": "application/json"})
            r.raise_for_status()
            body = r.json()
    except Exception:
        logger.exception("benzinga.fetch_failed tickers=%s", tickers)
        return []

    # Benzinga responds with a top-level array; some accounts get an envelope.
    items = body if isinstance(body, list) else body.get("articles", []) or body.get("data", [])
    out: list[dict[str, Any]] = []
    for a in items:
        try:
            out.append(_normalise(a))
        except Exception:
            logger.exception("benzinga.parse_failed article_id=%s", a.get("id"))
    return out


def _normalise(a: dict[str, Any]) -> dict[str, Any]:
    """Map Benzinga's shape onto the canonical news-row shape used elsewhere.

    Canonical shape (matches news_feed._fetch_from_polygon output so the
    consumers don't need to know which feed served the article):

        id, title, publisher, author, published_at (datetime),
        url, description, tickers (comma-string), sentiment (float | None)
    """
    # `id` is numeric on Benzinga — keep it as a string so the SQL primary
    # key (`id String(80)`) doesn't collide with mock/Polygon ids.
    article_id = f"bz-{a.get('id')}"

    # Created is RFC-2822 ("Tue, 06 May 2026 14:23:11 -0400"). parsedate_to_datetime
    # returns an aware datetime when the string carries a tz; otherwise we
    # default to UTC.
    created_raw = a.get("created") or a.get("published") or ""
    try:
        published = parsedate_to_datetime(created_raw) if created_raw else datetime.now(timezone.utc)
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        published = datetime.now(timezone.utc)

    # `stocks` and `tickers` are both used across Benzinga product variants.
    raw_syms = a.get("stocks") or a.get("tickers") or []
    sym_list = []
    for s in raw_syms:
        if isinstance(s, dict):
            n = s.get("name") or s.get("symbol")
            if n:
                sym_list.append(str(n).upper())
        elif isinstance(s, str):
            sym_list.append(s.upper())
    tickers_str = ",".join(sym_list)

    return {
        "id": article_id,
        "title": str(a.get("title") or "").strip()[:300],
        "publisher": "Benzinga",
        "author": (a.get("author") or None),
        "published_at": published,
        "url": a.get("url") or a.get("permalink") or "https://www.benzinga.com/",
        "description": a.get("teaser"),
        "tickers": tickers_str,
        "sentiment": None,  # not in the base news endpoint
    }
