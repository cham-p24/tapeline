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

# Polygon rebranded to Massive on 2025-10-30. Same API shape, same auth, same
# endpoints — only the hostname changed. Massive accepts the legacy POLYGON_API_KEY
# as well as the new MASSIVE_API_KEY for an extended grace period. Hostname is
# overridable via MASSIVE_BASE_URL for sandbox / failover targets.
import os

BASE_URL = os.environ.get("MASSIVE_BASE_URL", "https://api.massive.com")


def _api_key() -> str:
    """Returns whichever vendor key is configured. Prefer the new MASSIVE_API_KEY
    when both are set so accounts created post-rebrand work cleanly."""
    return settings.massive_api_key or settings.polygon_api_key or ""


# Module-level latch — set to True after the first VIX-endpoint failure so we
# stop hammering an endpoint that requires indices entitlement we don't have.
# Resets on worker restart, which is fine — the cost of one failed probe per
# boot is negligible.
_vix_endpoint_disabled: bool = False

# Seed universe — list of symbols we score. In production this gets populated
# from Massive's ticker reference API, filtered to liquid names.
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
    params = {**(params or {}), "apiKey": _api_key()}
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
    Latest snapshots — returns rows in the same schema as mock_feed.fetch_snapshots
    so the worker's upsert path stays unchanged.

    Strategy (hybrid until the full per-factor pipeline lands):
    - **Real**: price, change_pct_1d, volume — from Massive snapshot endpoint
    - **Real**: sub_fundamentals — from Finnhub cache (if pre-fetched), else mock
    - **Mock**: sub_trend, sub_rs, sub_momentum, sub_macro, sub_smart_money,
      reason, confidence_pct — until each factor's real source is wired

    The composite `score` gets recomputed after merging so real fundamentals
    actually move the needle (they're 15% of the total weight).
    """
    from app.services.finnhub_feed import get_cached_score, get_cached_smart_money_score
    from app.services.mock_feed import _signal_from_score
    from app.services.mock_feed import fetch_snapshots as _mock_snapshots
    from app.services.universe import active_universe
    # Trend / RS / Momentum caches live in this same module (populated by worker)

    # Active universe = top-N by daily $-volume (cached by worker via
    # universe.refresh_active_universe). Falls back to the hardcoded
    # TICKER_UNIVERSE if the cache hasn't been populated yet.
    universe_list = active_universe()
    # Generate the full mock-shape base rows for THIS universe (including
    # synthesised sub_* scores + reason + confidence). polygon_feed will
    # then override price/volume/sub_fundamentals/sub_smart_money/etc.
    # with real Massive + Finnhub data per row.
    base_rows = _mock_snapshots(universe_override=universe_list)

    if not _api_key():
        # No Massive key — pure mock fallback
        return base_rows

    # Pull real prices + volumes from Massive in one batched call
    syms = [r["symbol"] for r in base_rows] if symbols is None else symbols
    real_by_sym: dict[str, dict[str, Any]] = {}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for i in range(0, len(syms), 250):
                batch = syms[i : i + 250]
                # Massive's v3 snapshot endpoint (the v2 path returned the
                # legacy {day,prevDay,lastTrade} shape that parsed to zeros
                # after the 2026-Q1 schema migration to {session,last_minute}).
                body = await _request(
                    client,
                    "/v3/snapshot",
                    params={"ticker.any_of": ",".join(batch), "limit": len(batch)},
                )
                for t in body.get("results", []):
                    naive = _to_scanner_row(t)
                    if naive is not None:
                        real_by_sym[naive["symbol"]] = naive
    except Exception:
        logger.exception("polygon.fetch_snapshots_failed — returning mock-only rows")
        return base_rows

    # Merge: real price/volume + real fundamentals + recomputed composite
    for r in base_rows:
        sym = r["symbol"]
        real = real_by_sym.get(sym)
        if real:
            r["price"] = real["price"]
            r["change_pct_1d"] = real["change_pct_1d"]
            r["volume"] = real["volume"]

        # Real fundamentals from Finnhub cache (pre-fetched daily by worker)
        fund = get_cached_score(sym)
        if fund is not None:
            r["sub_fundamentals"] = fund

        # Real smart-money from Finnhub insider Form 4 cache
        sm = get_cached_smart_money_score(sym)
        if sm is not None:
            r["sub_smart_money"] = sm

        # Real trend / RS / momentum from Massive aggregates cache
        # (populated daily by worker via _refresh_aggregates_cache)
        trend = get_cached_trend(sym)
        if trend is not None:
            r["sub_trend"] = trend
        rs = get_cached_rs(sym)
        if rs is not None:
            r["sub_rs"] = rs
        mom = get_cached_momentum(sym)
        if mom is not None:
            r["sub_momentum"] = mom

        # Recompute composite from updated sub_* — keeps all 6 factors blended.
        # Weights mirror mock_feed/signal_publisher: trend .25 rs .20 fund .15 smart .15 macro .15 mom .10
        composite = (
            r["sub_trend"] * 0.25
            + r["sub_rs"] * 0.20
            + r["sub_fundamentals"] * 0.15
            + r["sub_smart_money"] * 0.15
            + r["sub_macro"] * 0.15
            + r["sub_momentum"] * 0.10
        )
        r["score"] = round(max(0, min(100, composite)), 1)
        r["signal"] = _signal_from_score(r["score"])

    return base_rows


def _to_scanner_row(snap: dict[str, Any]) -> dict[str, Any] | None:
    """Reshape Massive v3 snapshot result to our DB schema.

    v3 shape (post-2026-Q1 migration):
        {"ticker": "AAPL", "session": {"price": 293.41, "previous_close": 293.32,
         "change_percent": 0.0307, "volume": 5.27e7, "close": 293.32, "open": ...},
         "last_minute": {...}}

    `change_percent` is already in percent units (0.0307 means 0.0307%),
    so use it as-is — no /100 or *100 conversion.
    """
    ticker = snap.get("ticker")
    session = snap.get("session", {}) or {}
    last_minute = snap.get("last_minute", {}) or {}

    # `price` is the live mid; fall back to last-minute close or session close.
    last_price = session.get("price") or last_minute.get("close") or session.get("close")
    if not ticker or last_price is None:
        return None

    # Massive provides change_percent directly — use it. Fall back to manual
    # math if missing (e.g. just-listed tickers without a previous_close).
    cp = session.get("change_percent")
    if cp is None:
        prev_close = session.get("previous_close") or session.get("open")
        change_1d = ((last_price / prev_close) - 1) * 100 if prev_close else 0.0
    else:
        change_1d = float(cp)

    # Composite score requires historical aggregates — worker runs a secondary
    # pass to fill this in. For now, derive a naive score from today's move.
    score = _naive_score_from_move(change_1d)
    signal = _signal_from_score(score)

    return {
        "symbol": ticker,
        "score": round(score, 1),
        "signal": signal,
        "price": round(float(last_price), 2),
        "change_pct_1d": round(change_1d, 2),
        "change_pct_5d": 0.0,   # filled by historical pass
        "change_pct_1m": 0.0,   # filled by historical pass
        "volume": int(session.get("volume", 0) or 0),
        "last_timestamp": datetime.now(UTC).isoformat(),
    }


# =====================================================================
# Per-factor score caches — populated daily by worker, read per-tick by
# fetch_snapshots. Same pattern as finnhub_feed._FUND_SCORE_CACHE.
# =====================================================================
_TREND_SCORE_CACHE: dict[str, float] = {}
_RS_SCORE_CACHE: dict[str, float] = {}
_MOMENTUM_SCORE_CACHE: dict[str, float] = {}


def get_cached_trend(symbol: str) -> float | None:
    return _TREND_SCORE_CACHE.get(symbol.upper())


def get_cached_rs(symbol: str) -> float | None:
    return _RS_SCORE_CACHE.get(symbol.upper())


def get_cached_momentum(symbol: str) -> float | None:
    return _MOMENTUM_SCORE_CACHE.get(symbol.upper())


def set_cached_trend(symbol: str, score: float | None) -> None:
    if score is not None:
        _TREND_SCORE_CACHE[symbol.upper()] = score


def set_cached_rs(symbol: str, score: float | None) -> None:
    if score is not None:
        _RS_SCORE_CACHE[symbol.upper()] = score


def set_cached_momentum(symbol: str, score: float | None) -> None:
    if score is not None:
        _MOMENTUM_SCORE_CACHE[symbol.upper()] = score


def aggregate_cache_sizes() -> dict[str, int]:
    return {
        "trend": len(_TREND_SCORE_CACHE),
        "rs": len(_RS_SCORE_CACHE),
        "momentum": len(_MOMENTUM_SCORE_CACHE),
    }


def compute_trend_score(bars: list[dict[str, Any]]) -> float | None:
    """
    0-100 trend score from a list of OHLC bars (Polygon /v2/aggs response shape).
    Each bar dict has: o, h, l, c, v, t (open, high, low, close, volume, timestamp).

    Algorithm — distance from 200DMA + slope of 50DMA + above/below structure:
    - Above 200DMA + 50DMA above 200DMA + 50DMA rising → 80–95
    - Above 200DMA but flattening → 65–80
    - Below 200DMA but trying to recover → 35–55
    - Below 200DMA with negative 50DMA slope → 10–30

    Returns None if fewer than 200 bars available.
    """
    if not bars or len(bars) < 200:
        return None
    closes = [b.get("c") for b in bars if b.get("c") is not None]
    if len(closes) < 200:
        return None

    last = closes[-1]
    sma_50 = sum(closes[-50:]) / 50
    sma_200 = sum(closes[-200:]) / 200
    sma_50_prev = sum(closes[-60:-10]) / 50  # 50DMA from 10 bars ago, for slope

    # Distance from 200DMA as % — positive = above
    dist_200 = (last / sma_200 - 1) * 100 if sma_200 > 0 else 0
    # 50DMA slope (% change over 10 bars)
    slope_50 = (sma_50 / sma_50_prev - 1) * 100 if sma_50_prev > 0 else 0
    # Above/below 200DMA bias
    above_200 = sma_50 > sma_200

    # Build score: start at 50 (neutral), shift by structure
    score = 50.0
    score += min(20, max(-20, dist_200 * 1.5))   # +/- 20 based on distance from 200DMA
    score += min(15, max(-15, slope_50 * 8))     # +/- 15 based on 50DMA slope
    score += 10 if above_200 else -10            # +10/-10 for golden/death-cross structure

    return round(max(0, min(100, score)), 1)


def compute_rs_score(bars: list[dict[str, Any]], spy_bars: list[dict[str, Any]]) -> float | None:
    """
    Relative-strength score vs SPY over the last ~3 months (63 trading days).

    Score 50 = matched SPY return. >50 = outperformed. <50 = underperformed.
    Magnitude scales with size of out/under-performance.
    """
    if not bars or not spy_bars or len(bars) < 63 or len(spy_bars) < 63:
        return None

    closes = [b.get("c") for b in bars if b.get("c") is not None]
    spy_closes = [b.get("c") for b in spy_bars if b.get("c") is not None]
    if len(closes) < 63 or len(spy_closes) < 63:
        return None

    ticker_3m = (closes[-1] / closes[-63] - 1) * 100 if closes[-63] > 0 else 0
    spy_3m = (spy_closes[-1] / spy_closes[-63] - 1) * 100 if spy_closes[-63] > 0 else 0
    diff = ticker_3m - spy_3m  # +5 means ticker beat SPY by 5 percentage points

    # Map -20pp to +20pp difference → 10–90 score
    score = 50 + (diff * 2)
    return round(max(0, min(100, score)), 1)


def compute_momentum_score(bars: list[dict[str, Any]]) -> float | None:
    """
    Momentum score from 14-period RSI + recent volume thrust.

    RSI 30 = oversold (low momentum), RSI 70 = overbought (high momentum).
    Layer on volume: +10 if recent 5-bar avg volume > 1.5× the prior 20-bar avg.
    """
    if not bars or len(bars) < 30:
        return None
    closes = [b.get("c") for b in bars if b.get("c") is not None]
    volumes = [b.get("v", 0) or 0 for b in bars if b.get("c") is not None]
    if len(closes) < 30:
        return None

    # Wilder RSI(14)
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[-14:]) / 14
    avg_loss = sum(losses[-14:]) / 14
    if avg_loss == 0:
        rsi = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    score = rsi  # RSI is already 0-100

    # Volume thrust bonus: recent 5-bar avg vs prior 20-bar avg
    if len(volumes) >= 25:
        recent_vol = sum(volumes[-5:]) / 5
        prior_vol = sum(volumes[-25:-5]) / 20
        if prior_vol > 0 and recent_vol / prior_vol > 1.5:
            score += 10

    return round(max(0, min(100, score)), 1)


def _naive_score_from_move(move_pct: float) -> float:
    """
    Placeholder scoring until historical aggregates are wired in.
    Real score incorporates trend, RS, fundamentals, momentum, macro.
    """
    # Map -5%..+5% move to 10..90 score
    s = 50 + (move_pct * 8)
    return max(0.0, min(100.0, s))


def _signal_from_score(score: float) -> str:
    """
    Descriptive (not prescriptive) labels describing the STATE of the factor data.
    Legal posture: never tells the user what to do. See LEGAL_CHECKLIST.md.
    Mirrors the same buckets used in mock_feed._signal_from_score so labels
    stay consistent regardless of which feed produced the score.
    """
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

    Macro indicators come from FRED when FRED_API_KEY is set; falls back
    to hardcoded values otherwise. Polygon is used for the live VIX index.
    """
    # Try FRED first (free + reliable for daily series)
    from app.services.fred_feed import fetch_macro_indicators
    fred_data = await fetch_macro_indicators()

    # Live VIX from Massive — preferred over FRED's daily close for intraday.
    # Massive Stocks Starter does NOT include indices entitlement, so this
    # endpoint 403s every call. Probe once per worker boot and skip thereafter
    # so we don't spam the warning log (FRED's daily VIX close is the fallback).
    vix = fred_data.get("vix") or 20.0
    global _vix_endpoint_disabled
    if not _vix_endpoint_disabled:
        try:
            async with httpx.AsyncClient() as client:
                vix_snap = await _request(
                    client, "/v2/snapshot/locale/us/markets/indices/tickers/I:VIX",
                )
            vix_live = vix_snap.get("ticker", {}).get("value")
            if vix_live:
                vix = float(vix_live)
        except Exception:
            _vix_endpoint_disabled = True
            logger.info(
                "polygon.vix_endpoint_disabled — using FRED daily close (%.2f). "
                "Indices entitlement requires Massive Indices Starter, separate from Stocks.",
                vix,
            )

    dxy = fred_data.get("dxy") or 103.5
    y10 = fred_data.get("yield_10y") or 4.25
    # FRED returns RISING / FALLING / SIDEWAYS based on the 10Y's last 30 obs.
    # Defaults to SIDEWAYS when no FRED key is configured (graceful no-op).
    rate_direction = fred_data.get("rate_direction") or "SIDEWAYS"

    # Placeholder — breadth requires sector-constituent walk; on Starter tier
    # this is expensive. Schedule it as a hourly job rather than per-tick.
    breadth_pct = 55.0

    regime = (
        "BULL" if vix < 15
        else "NEUTRAL" if vix < 20
        else "CAUTIOUS" if vix < 25
        else "BEAR"
    )
    return {
        "regime": regime,
        "vix": round(vix, 2),
        "dxy": round(dxy, 2),
        "yield_10y": round(y10, 3),
        "rate_direction": rate_direction,
        "breadth_pct": round(breadth_pct, 1),
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


async def discover_active_us_tickers(max_tickers: int = 5000) -> list[dict[str, str]]:
    """
    Walk Polygon's `/v3/reference/tickers` and return active US common stocks
    plus ETFs, capped at `max_tickers` for sanity. Used by the worker's weekly
    universe-refresh task to discover new IPOs and new ETF launches.

    Returns rows in the same shape as `universe()` — drop-in replacement for
    the static seed list.
    """
    if not _api_key():
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    async with httpx.AsyncClient(timeout=30.0) as client:
        next_url: str | None = f"{BASE_URL}/v3/reference/tickers"
        params: dict[str, Any] | None = {
            "market": "stocks",
            "active": "true",
            "limit": 1000,
            "apiKey": _api_key(),
        }
        while next_url and len(rows) < max_tickers:
            try:
                r = await client.get(next_url, params=params)
                r.raise_for_status()
                data = r.json()
            except (httpx.HTTPError, ValueError):
                logger.exception("polygon.reference_tickers_failed url=%s", next_url)
                break

            for t in data.get("results", []):
                ttype = t.get("type") or ""
                # CS = Common Stock, ETF = exchange-traded fund. Skip warrants,
                # rights, units, OTC, etc. — we don't score those.
                if ttype not in ("CS", "ETF"):
                    continue
                sym = (t.get("ticker") or "").upper()
                if not sym or sym in seen:
                    continue
                seen.add(sym)
                rows.append({
                    "symbol": sym,
                    "name": t.get("name") or sym,
                    # Sector requires a per-ticker /v3/reference/tickers/{sym}
                    # call — too rate-limited on Starter to do for every name.
                    # Worker can backfill sectors lazily for tickers users actually look at.
                    "sector": "Unknown",
                    "asset_class": "etf" if ttype == "ETF" else "equity",
                })

            cursor = data.get("next_url")
            # Polygon's next_url omits the apiKey — re-add it
            if cursor:
                if "apiKey=" not in cursor:
                    sep = "&" if "?" in cursor else "?"
                    cursor = f"{cursor}{sep}apiKey={_api_key()}"
                next_url = cursor
                params = None  # next_url already encodes everything
            else:
                next_url = None

    logger.info("polygon.universe_discovered count=%d", len(rows))
    return rows
