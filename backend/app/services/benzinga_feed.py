"""
Benzinga adapter — news + analyst ratings.

Two products in one file:
    - News (`/api/v2/news`) preferred over Polygon for the live news bar
      and per-ticker headlines: faster wire, richer cashtag tagging.
    - Analyst ratings (`/api/v2.1/calendar/ratings`) powers the per-ticker
      consensus widget. Tapeline does not factor ratings into the
      6-factor score — they're displayed alongside it as a complement.

Auth: query-param `token=...` for both endpoints.

News response items:
    {
        "id": 12345,
        "title": "...",
        "author": "...",
        "created": "Tue, 06 May 2026 14:23:11 -0400",
        "url": "https://www.benzinga.com/...",
        "stocks": [{"name": "AAPL"}, {"name": "MSFT"}],
        "teaser": "...",
        "body": "<p>...</p>",
    }

Ratings response items (calendar.ratings):
    {
        "id": "...",
        "date": "2026-05-07",
        "ticker": "AAPL",
        "action_company": "Goldman Sachs",   # firm
        "analyst": "...",                    # analyst name (sometimes blank)
        "rating_current": "Buy",
        "rating_prior": "Hold",
        "pt_current": "220.00",              # price target (string in API!)
        "pt_prior": "195.00",
        "action_pt": "Raises",               # Maintains | Raises | Lowers | Announces
        "action_company": "Goldman Sachs",
        "url": "https://...",
    }

Important: Benzinga's free tier doesn't carry news sentiment. Articles
return with sentiment=None and the news-alert evaluator falls through to
"fire on any new article" semantics.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_BASE_URL = "https://api.benzinga.com/api/v2/news"
_RATINGS_URL = "https://api.benzinga.com/api/v2.1/calendar/ratings"
# Conservative timeout — Benzinga is generally <500ms but flaky during NYSE open.
_TIMEOUT_SECONDS = 12.0

# In-memory ratings cache. Ratings refresh in trickle (a few per ticker per
# week max), so a 6-hour TTL is plenty and keeps us well under any rate cap.
_RATINGS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_RATINGS_TTL_SECONDS = 6 * 60 * 60
_RATINGS_LOCK = asyncio.Lock()


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
        published = parsedate_to_datetime(created_raw) if created_raw else datetime.now(UTC)
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        published = datetime.now(UTC)

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


# ---------------------------------------------------------------------------
# Analyst ratings
# ---------------------------------------------------------------------------

# Map Benzinga's free-text ratings (which vary per firm — Buy / Outperform /
# Overweight / Strong Buy / Long-term Buy / Top Pick / ...) onto a small set
# of buckets used for the consensus tally on the widget.
_BULL_TOKENS = {
    "buy", "strong buy", "outperform", "overweight", "long-term buy",
    "positive", "top pick", "accumulate", "add", "conviction buy", "market outperform",
}
_BEAR_TOKENS = {
    "sell", "strong sell", "underperform", "underweight", "negative",
    "reduce", "market underperform",
}
_NEUTRAL_TOKENS = {
    "hold", "neutral", "market perform", "in-line", "equal-weight",
    "sector perform", "peer perform", "perform",
}


def _bucket(label: str | None) -> str:
    """Bucket a free-text rating string into bull / bear / neutral."""
    if not label:
        return "neutral"
    s = label.strip().lower()
    if s in _BULL_TOKENS:
        return "bull"
    if s in _BEAR_TOKENS:
        return "bear"
    if s in _NEUTRAL_TOKENS:
        return "neutral"
    # Fall back to a contains-check so brokerage-specific phrasing
    # ("Buy with caution", "Long-Term Buy") still bucket sensibly.
    if any(tok in s for tok in ("buy", "outperform", "overweight", "positive", "accumulate")):
        return "bull"
    if any(tok in s for tok in ("sell", "underperform", "underweight", "negative", "reduce")):
        return "bear"
    return "neutral"


def _parse_pt(raw: Any) -> float | None:
    """Benzinga returns price targets as strings ("220.00") or empty strings."""
    if raw is None:
        return None
    try:
        s = str(raw).strip()
        if not s:
            return None
        return float(s)
    except (TypeError, ValueError):
        return None


async def fetch_analyst_ratings(symbol: str, days_back: int = 180) -> dict[str, Any]:
    """Recent analyst ratings + consensus summary for a ticker.

    Returns:
        {
          "symbol": "AAPL",
          "consensus": {"bull": 8, "bear": 1, "neutral": 3, "total": 12},
          "avg_pt": 220.50,           # average of recent price targets, or None
          "avg_pt_upside_pct": 12.3,  # % above current price, computed by caller
          "events": [                 # most recent N rating actions
            {
              "date": "2026-05-07",
              "firm": "Goldman Sachs",
              "analyst": "...",
              "action_pt": "Raises",
              "rating_current": "Buy",
              "rating_prior": "Hold",
              "pt_current": 220.0,
              "pt_prior": 195.0,
              "url": "...",
            },
            ...
          ],
          "source": "benzinga" | "empty",
        }

    Empty/no-coverage tickers return an empty consensus + empty events list,
    not an error — many small-caps have zero analyst coverage and that's fine.
    """
    symbol = (symbol or "").upper()
    if not symbol:
        return _empty_ratings(symbol)
    if not is_configured():
        return _empty_ratings(symbol)

    # Cache hit?
    cached = _RATINGS_CACHE.get(symbol)
    if cached and (time.monotonic() - cached[0]) < _RATINGS_TTL_SECONDS:
        return cached[1]

    # Single-flight lock so a stampede of concurrent requests for a hot
    # ticker (NVDA, TSLA on a movement day) only fires one upstream call.
    async with _RATINGS_LOCK:
        cached = _RATINGS_CACHE.get(symbol)
        if cached and (time.monotonic() - cached[0]) < _RATINGS_TTL_SECONDS:
            return cached[1]

        date_to = datetime.now(UTC).date()
        date_from = date_to - timedelta(days=days_back)
        params: dict[str, Any] = {
            "token": _api_key(),
            "parameters[tickers]": symbol,
            "parameters[date_from]": date_from.isoformat(),
            "parameters[date_to]": date_to.isoformat(),
            "pagesize": 100,
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as c:
                r = await c.get(_RATINGS_URL, params=params, headers={"Accept": "application/json"})
                r.raise_for_status()
                body = r.json()
        except Exception:
            logger.exception("benzinga.ratings_fetch_failed symbol=%s", symbol)
            return _empty_ratings(symbol)

        # Response is either {"ratings": [...]} or a top-level list.
        raw_items = body.get("ratings") if isinstance(body, dict) else body
        if not isinstance(raw_items, list):
            raw_items = []

        events: list[dict[str, Any]] = []
        consensus = {"bull": 0, "bear": 0, "neutral": 0, "total": 0}
        pt_values: list[float] = []

        # Benzinga returns most-recent first; we keep that order.
        # Track per-firm latest opinion so the consensus tally counts each
        # firm once (the most recent action), not every rating change ever.
        latest_per_firm: dict[str, str] = {}
        latest_pt_per_firm: dict[str, float] = {}

        for raw in raw_items:
            try:
                event = _normalise_rating(raw)
            except Exception:
                logger.exception("benzinga.rating_parse_failed id=%s", (raw or {}).get("id"))
                continue

            firm = event["firm"] or "(unknown)"
            # First-seen-wins because the list is sorted desc → it's the latest.
            if firm not in latest_per_firm:
                latest_per_firm[firm] = _bucket(event["rating_current"])
                pt = event["pt_current"]
                if pt is not None:
                    latest_pt_per_firm[firm] = pt
            events.append(event)

        for bucket in latest_per_firm.values():
            consensus[bucket] += 1
        consensus["total"] = sum(consensus[k] for k in ("bull", "bear", "neutral"))
        pt_values = list(latest_pt_per_firm.values())
        avg_pt = round(sum(pt_values) / len(pt_values), 2) if pt_values else None

        result = {
            "symbol": symbol,
            "consensus": consensus,
            "avg_pt": avg_pt,
            "events": events[:20],  # cap at 20 most-recent for the widget
            "source": "benzinga" if events else "empty",
        }
        _RATINGS_CACHE[symbol] = (time.monotonic(), result)
        return result


def _normalise_rating(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": str(raw.get("date") or ""),
        "firm": (raw.get("action_company") or raw.get("company") or "").strip() or None,
        "analyst": (raw.get("analyst") or "").strip() or None,
        "action_pt": (raw.get("action_pt") or "").strip() or None,
        "rating_current": (raw.get("rating_current") or "").strip() or None,
        "rating_prior": (raw.get("rating_prior") or "").strip() or None,
        "pt_current": _parse_pt(raw.get("pt_current")),
        "pt_prior": _parse_pt(raw.get("pt_prior")),
        "url": raw.get("url") or raw.get("url_news") or None,
    }


def _empty_ratings(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "consensus": {"bull": 0, "bear": 0, "neutral": 0, "total": 0},
        "avg_pt": None,
        "events": [],
        "source": "empty",
    }
