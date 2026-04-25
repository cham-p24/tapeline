"""
Polygon.io production data adapter.

Single file is the ONLY place the codebase talks to Polygon. Swapping
`app.services.mock_feed` → `app.services.polygon_feed` in the worker is
the complete "go live with real data" change.

Starter tier ($29/mo):
    - 5 requests/min rate limit — handled by the built-in retry/sleep
    - 15-minute delayed quotes
    - Commercial redistribution rights
    - Aggregates API: end-of-day bars

Developer tier ($79/mo):
    - Unlimited req/min, real-time quotes

Tapeline MVP uses Starter. Upgrade to Developer once MRR > $500/mo.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

BASE_URL = "https://api.polygon.io"
_RATE_LIMIT_PER_MIN = {"starter": 5, "developer": 1000, "advanced": 10_000}

# Seed universe — list of symbols we score. In production this gets
# populated from Polygon's ticker reference API, filtered to liquid names.
DEFAULT_UNIVERSE = [
    # Mega caps + S&P 100 names (edit to taste)
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AVGO", "ORCL", "AMD",
    "CRM", "ADBE", "NFLX", "DIS", "JPM", "BAC", "WFC", "GS", "MS", "V", "MA", "BRK.B",
    "JNJ", "UNH", "PFE", "LLY", "ABBV", "MRK", "TMO", "DHR", "XOM", "CVX", "COP",
    "HD", "LOW", "NKE", "SBUX", "MCD", "BKNG", "WMT", "COST", "PG", "KO", "PEP",
    "BA", "CAT", "DE", "HON", "UPS", "LMT", "RTX", "GE", "UNP", "T", "VZ", "TMUS",
    "NEE", "DUK", "SO", "LIN", "FCX", "NEM", "AEM", "SLB", "OXY", "MPC",
    "SPY", "QQQ", "IWM", "DIA", "VTI", "SMH", "XLK", "XLF", "XLE", "XLV", "GLD", "TLT",
]


async def _request(client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """One GET with retries on 429/5xx."""
    params = {**(params or {}), "apiKey": settings.polygon_api_key}
    for attempt in range(5):
        try:
            resp = await client.get(f"{BASE_URL}{path}", params=params, timeout=20.0)
            if resp.status_code == 429:
                # Rate-limited — back off progressively
                wait = 2 ** attempt
                logger.warning("polygon.rate_limit retrying in %ds", wait)
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            if 500 <= exc.response.status_code < 600 and attempt < 4:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"polygon request failed after retries: {path}")


async def fetch_snapshots(symbols: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Latest snapshots for a list of symbols. Returns rows compatible with
    the worker's upsert, matching the mock_feed schema.
    """
    if not settings.polygon_api_key:
        raise RuntimeError("POLYGON_API_KEY not set — set it in .env and restart the worker")

    syms = symbols or DEFAULT_UNIVERSE
    rows = []

    async with httpx.AsyncClient() as client:
        # Polygon's batched snapshot: /v2/snapshot/locale/us/markets/stocks/tickers?tickers=...
        # Limit of tickers per call depends on tier; keep chunks <= 250 to be safe.
        for i in range(0, len(syms), 250):
            batch = syms[i : i + 250]
            body = await _request(
                client,
                "/v2/snapshot/locale/us/markets/stocks/tickers",
                params={"tickers": ",".join(batch)},
            )
            for t in body.get("tickers", []):
                row = _to_scanner_row(t)
                if row is not None:
                    rows.append(row)

    return rows


def _to_scanner_row(snap: dict[str, Any]) -> dict[str, Any] | None:
    """Reshape Polygon snapshot to our DB schema."""
    ticker = snap.get("ticker")
    day = snap.get("day", {}) or {}
    prev_day = snap.get("prevDay", {}) or {}
    last_trade = snap.get("lastTrade", {}) or {}

    last_price = last_trade.get("p") or day.get("c")
    if not ticker or last_price is None:
        return None

    prev_close = prev_day.get("c") or day.get("o")
    change_1d = ((last_price / prev_close) - 1) * 100 if prev_close else 0.0

    # Composite score requires historical aggregates — worker runs a secondary
    # pass to fill this in. For now, derive a naive score from today's move.
    score = _naive_score_from_move(change_1d)
    signal = _signal_from_score(score)

    return {
        "symbol": ticker,
        "score": round(score, 1),
        "signal": signal,
        "price": round(last_price, 2),
        "change_pct_1d": round(change_1d, 2),
        "change_pct_5d": 0.0,   # filled by historical pass
        "change_pct_1m": 0.0,   # filled by historical pass
        "volume": int(day.get("v", 0) or 0),
        "last_timestamp": datetime.now(UTC).isoformat(),
    }


def _naive_score_from_move(move_pct: float) -> float:
    """
    Placeholder scoring until historical aggregates are wired in.
    Real score incorporates trend, RS, fundamentals, momentum, macro.
    """
    # Map -5%..+5% move to 10..90 score
    s = 50 + (move_pct * 8)
    return max(0.0, min(100.0, s))


def _signal_from_score(score: float) -> str:
    """Descriptive labels. See LEGAL_CHECKLIST.md — no prescriptive action words."""
    if score >= 85: return "HIGH CONVICTION"
    if score >= 70: return "STRONG SETUP"
    if score >= 55: return "CONSTRUCTIVE"
    if score >= 40: return "NEUTRAL"
    if score >= 25: return "CAUTION"
    return "WEAK"


async def fetch_aggregates(
    symbol: str,
    from_date: date | None = None,
    to_date: date | None = None,
    timespan: str = "day",
) -> list[dict[str, Any]]:
    """Historical OHLCV bars for scoring indicators. Uses v2 aggregates endpoint."""
    to_date = to_date or date.today()
    from_date = from_date or (to_date - timedelta(days=400))

    async with httpx.AsyncClient() as client:
        body = await _request(
            client,
            f"/v2/aggs/ticker/{symbol}/range/1/{timespan}/{from_date.isoformat()}/{to_date.isoformat()}",
            params={"adjusted": "true", "sort": "asc", "limit": 500},
        )
    return body.get("results", []) or []


async def fetch_squeezes() -> list[dict[str, Any]]:
    """
    Detect BB squeeze + volume expansion setups across the universe.

    This is a background job — for each ticker we pull 60 days of aggregates,
    compute BB width percentile, ATR contraction, volume ratio, OBV trend,
    and emit a spike score.

    On Starter tier (5 req/min) this takes ~15 minutes to sweep the full
    universe, so squeeze detection runs on a slower cadence than snapshots.
    """
    from app.services.squeeze_detection import detect_squeezes_batch
    return await detect_squeezes_batch(DEFAULT_UNIVERSE)


async def fetch_regime() -> dict[str, Any]:
    """
    Classify market regime from VIX, breadth (% of S&P above 200DMA),
    rate direction (10Y yield slope), and sector leader rotation.
    """
    # Fetch VIX + 10Y via index tickers
    async with httpx.AsyncClient() as client:
        vix_snap = await _request(
            client, "/v2/snapshot/locale/us/markets/indices/tickers/I:VIX",
        )
    vix = vix_snap.get("ticker", {}).get("value", 20.0)

    # Placeholder — real implementation computes breadth from constituent snapshots
    regime = (
        "BULL" if vix < 15
        else "NEUTRAL" if vix < 20
        else "CAUTIOUS" if vix < 25
        else "BEAR"
    )
    return {
        "regime": regime,
        "vix": round(vix, 2),
        "dxy": 103.5,  # TODO: fetch DXY
        "yield_10y": 4.25,  # TODO: fetch from FRED or Polygon
        "rate_direction": "SIDEWAYS",
        "breadth_pct": 55.0,  # TODO: compute
        "sector_leaders": "Technology, Industrials, Financials",
    }


async def fetch_congress_trades() -> list[dict[str, Any]]:
    """
    Congress trades are NOT in Polygon. Source them from QuiverQuant
    (Premium tier), or scrape official House/Senate STOCK Act disclosures.

    Returns empty list by default — populate via `congress_ingestor.py`.
    """
    return []


def universe() -> list[dict[str, str]]:
    """Seed list of tickers. In production, refresh weekly from Polygon reference."""
    return [
        {"symbol": sym, "name": sym, "sector": "Unknown", "asset_class": "equity"}
        for sym in DEFAULT_UNIVERSE
    ]
