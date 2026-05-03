"""
Finnhub adapter — fundamentals, earnings calendar, IPO calendar, insider data.

Used to enrich Tapeline's `sub_fundamentals` factor with real financial metrics
and to replace mock earnings + IPO calendars with real upcoming events.

Auth:
    - Requires FINNHUB_API_KEY env var (free tier from https://finnhub.io/dashboard).
    - Without a key, every fetch returns None (caller falls back to mock).

Rate limits:
    - Free tier: 60 calls/minute. Plenty for Tapeline at expected volumes:
      870 tickers × weekly fundamentals refresh = ~125 calls/day = ~5/hour.
      Earnings + IPO calendars are 1 call each per refresh.

Cache:
    - 24h for fundamentals + insider (slow-moving data)
    - 12h for calendars (new earnings dates appear daily)
    - Written to backend/.cache/finnhub_*.json
"""
from __future__ import annotations

import contextlib
import json
import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache"
BASE_URL = "https://finnhub.io/api/v1"

CACHE_TTL_FUNDAMENTALS_HOURS = 24 * 7   # Fundamentals refresh weekly
CACHE_TTL_CALENDAR_HOURS = 12           # Calendars refresh twice a day
CACHE_TTL_INSIDER_HOURS = 24            # Insider Form 4 refresh daily


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"finnhub_{name}.json"


def _load_cache(name: str, ttl_hours: float) -> Any | None:
    p = _cache_path(name)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        if (time.time() - data.get("_ts", 0)) > ttl_hours * 3600:
            return None
        return data.get("payload")
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(name: str, payload: Any) -> None:
    try:
        _cache_path(name).write_text(json.dumps({"payload": payload, "_ts": time.time()}))
    except (OSError, TypeError):
        logger.warning("finnhub.cache_write_failed name=%s", name)


def _api_key() -> str:
    return getattr(settings, "finnhub_api_key", "") or ""


def configured() -> bool:
    return bool(_api_key())


# ---- In-memory fundamentals score cache --------------------------------
# Populated by the worker's daily _refresh_fundamentals task. Keyed by
# uppercase symbol; value is the 0-100 sub_fundamentals score (or None
# if Finnhub returned no data — typical for ETFs without P/E).
# polygon_feed.fetch_snapshots reads from this cache per tick — the
# expensive Finnhub fetches happen once per day, the cheap dict lookup
# happens 60×/min during market hours.
_FUND_SCORE_CACHE: dict[str, float] = {}


def get_cached_score(symbol: str) -> float | None:
    """Per-tick lookup. Returns None if the symbol hasn't been refreshed yet
    or had no Finnhub fundamentals (e.g. ETFs, foreign ADRs)."""
    return _FUND_SCORE_CACHE.get(symbol.upper())


def set_cached_score(symbol: str, score: float | None) -> None:
    """Worker-side setter — call after each fetch_basic_financials + compute."""
    if score is not None:
        _FUND_SCORE_CACHE[symbol.upper()] = score


def fund_cache_size() -> int:
    """For diagnostics."""
    return len(_FUND_SCORE_CACHE)


# ---- In-memory smart-money score cache (insider Form 4) ----------------
# Same pattern as _FUND_SCORE_CACHE — populated daily by the worker,
# read per-tick by polygon_feed.fetch_snapshots.
_SMART_MONEY_SCORE_CACHE: dict[str, float] = {}


def get_cached_smart_money_score(symbol: str) -> float | None:
    return _SMART_MONEY_SCORE_CACHE.get(symbol.upper())


def set_cached_smart_money_score(symbol: str, score: float | None) -> None:
    if score is not None:
        _SMART_MONEY_SCORE_CACHE[symbol.upper()] = score


def smart_money_cache_size() -> int:
    return len(_SMART_MONEY_SCORE_CACHE)


def compute_smart_money_score(transactions: list[dict[str, Any]] | None) -> float | None:
    """
    0-100 score from insider Form 4 transactions.

    Net buying (insiders adding to their position) → score above 50.
    Net selling (insiders dumping) → score below 50.
    Magnitude scales with the dollar value of the net position change relative
    to total transaction volume — so a $50M buy by one insider weighs more than
    50 separate $1M sells, but only if it's net of the activity.

    Returns None for tickers with no transactions in the window — caller falls
    back to mock or keeps existing value.
    """
    if not transactions:
        return None

    net_value = 0.0
    total_value = 0.0
    for t in transactions:
        change = t.get("share_change") or 0
        price = t.get("transaction_price") or 0
        signed = change * price
        net_value += signed
        total_value += abs(signed)

    if total_value == 0:
        return 50.0

    # Net buy ratio: -1 (all selling) to +1 (all buying)
    ratio = net_value / total_value
    # Map to 10–90 score band — leave headroom at the extremes for stronger signals
    score = 50 + (ratio * 40)
    return round(max(0, min(100, score)), 1)


# ---- Earnings calendar -----------------------------------------------------

async def fetch_earnings_calendar(days_ahead: int = 14) -> list[dict[str, Any]] | None:
    """
    Returns earnings events scheduled in the next `days_ahead` days.
    Shape matches mock_upcoming_earnings() so it's a drop-in replacement.

    Returns None if no API key OR fetch failed (caller falls back to mock).
    """
    if not configured():
        logger.info("finnhub.earnings_skipped reason=no_api_key")
        return None

    cache_key = f"earnings_{days_ahead}d"
    cached = _load_cache(cache_key, CACHE_TTL_CALENDAR_HOURS)
    if cached is not None:
        logger.info("finnhub.earnings_cache_hit count=%d", len(cached))
        return cached

    today = date.today()
    end = today + timedelta(days=days_ahead)
    params = {
        "from": today.isoformat(),
        "to": end.isoformat(),
        "token": _api_key(),
    }
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{BASE_URL}/calendar/earnings", params=params)
            if r.status_code != 200:
                logger.warning("finnhub.earnings_failed status=%s body=%s", r.status_code, r.text[:200])
                return None
            data = r.json()
    except Exception:
        logger.exception("finnhub.earnings_exception")
        return None

    raw_rows = data.get("earningsCalendar", []) or []
    rows: list[dict[str, Any]] = []
    for r in raw_rows:
        sym = r.get("symbol", "")
        report_date_str = r.get("date")
        if not sym or not report_date_str:
            continue
        try:
            report_d = date.fromisoformat(report_date_str)
        except ValueError:
            continue
        # Finnhub `hour` field: bmo / amc / dmh (before/after/during market hours)
        report_time = (r.get("hour") or "").upper() or "BMO"
        if report_time not in ("BMO", "AMC", "DMH"):
            report_time = "BMO"
        quarter = r.get("quarter")
        year = r.get("year")
        fiscal_quarter = f"Q{quarter} {year}" if quarter and year else f"Q{((report_d.month - 1) // 3) + 1} {report_d.year}"

        eps_est = r.get("epsEstimate")
        eps_act = r.get("epsActual")
        rev_est = r.get("revenueEstimate")
        rev_act = r.get("revenueActual")
        # Surprise pct vs estimate, only if both actual and estimate are populated
        surprise_pct = None
        if eps_act is not None and eps_est is not None and eps_est != 0:
            surprise_pct = round(((eps_act - eps_est) / abs(eps_est)) * 100, 2)

        rows.append({
            "symbol": sym.upper(),
            "report_date": report_d,
            "report_time": report_time,
            "fiscal_quarter": fiscal_quarter,
            "eps_estimate": float(eps_est) if eps_est is not None else None,
            "eps_actual": float(eps_act) if eps_act is not None else None,
            "revenue_estimate_m": round(float(rev_est) / 1_000_000, 0) if rev_est else None,
            "revenue_actual_m": round(float(rev_act) / 1_000_000, 0) if rev_act else None,
            "surprise_pct": surprise_pct,
        })

    rows.sort(key=lambda r: r["report_date"])
    # Date isn't JSON-serialisable directly — store as ISO string in cache
    _save_cache(cache_key, [{**r, "report_date": r["report_date"].isoformat()} for r in rows])
    logger.info("finnhub.earnings_fetched count=%d days=%d", len(rows), days_ahead)
    return rows


# ---- IPO calendar ----------------------------------------------------------

async def fetch_ipo_calendar(days_ahead: int = 90) -> list[dict[str, Any]] | None:
    """
    Returns upcoming IPOs scheduled in the next `days_ahead` days.
    Shape matches mock_upcoming_ipos().
    """
    if not configured():
        logger.info("finnhub.ipo_skipped reason=no_api_key")
        return None

    cache_key = f"ipo_{days_ahead}d"
    cached = _load_cache(cache_key, CACHE_TTL_CALENDAR_HOURS)
    if cached is not None:
        logger.info("finnhub.ipo_cache_hit count=%d", len(cached))
        return cached

    today = date.today()
    end = today + timedelta(days=days_ahead)
    params = {"from": today.isoformat(), "to": end.isoformat(), "token": _api_key()}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{BASE_URL}/calendar/ipo", params=params)
            if r.status_code != 200:
                logger.warning("finnhub.ipo_failed status=%s body=%s", r.status_code, r.text[:200])
                return None
            data = r.json()
    except Exception:
        logger.exception("finnhub.ipo_exception")
        return None

    raw_rows = data.get("ipoCalendar", []) or []
    rows: list[dict[str, Any]] = []
    for r in raw_rows:
        sym = (r.get("symbol") or "").upper()
        if not sym:
            continue
        ipo_date_str = r.get("date")
        try:
            ipo_d = date.fromisoformat(ipo_date_str) if ipo_date_str else None
        except ValueError:
            ipo_d = None
        if ipo_d is None:
            continue
        # Finnhub price field is a string like "30-35" or single price
        price_low, price_high = None, None
        price_str = r.get("price") or ""
        if "-" in price_str:
            try:
                lo, hi = price_str.split("-", 1)
                price_low, price_high = float(lo), float(hi)
            except ValueError:
                pass
        elif price_str:
            with contextlib.suppress(ValueError):
                price_low = price_high = float(price_str)

        status_raw = (r.get("status") or "").lower()
        status = {
            "expected": "upcoming",
            "filed": "upcoming",
            "priced": "priced",
            "withdrawn": "withdrawn",
            "postponed": "postponed",
        }.get(status_raw, "upcoming")

        rows.append({
            "symbol": sym,
            "company_name": r.get("name") or sym,
            "sector": "Unknown",  # Finnhub IPO endpoint doesn't provide sector
            "exchange": r.get("exchange") or "NASDAQ",
            "expected_date": ipo_d,
            "price_low": price_low,
            "price_high": price_high,
            "shares_offered": int(r.get("numberOfShares") or 0),
            "status": status,
            "lead_underwriter": "—",  # Finnhub free tier doesn't include underwriter
            "description": f"{r.get('name') or sym} listing on {r.get('exchange') or 'a US exchange'}.",
        })

    rows.sort(key=lambda r: r["expected_date"])
    _save_cache(cache_key, [{**r, "expected_date": r["expected_date"].isoformat()} for r in rows])
    logger.info("finnhub.ipo_fetched count=%d days=%d", len(rows), days_ahead)
    return rows


# ---- Fundamentals ----------------------------------------------------------

async def fetch_basic_financials(symbol: str) -> dict[str, float] | None:
    """
    Per-ticker financial metrics: P/E, margin, ROE, EPS growth, revenue growth.
    Cached 7 days per symbol — fundamentals don't change tick-to-tick.

    Returns None if no API key OR ticker has no data (e.g. ETFs without fundamentals).
    """
    if not configured():
        return None

    sym = symbol.upper()
    cache_key = f"fund_{sym}"
    cached = _load_cache(cache_key, CACHE_TTL_FUNDAMENTALS_HOURS)
    if cached is not None:
        return cached

    params = {"symbol": sym, "metric": "all", "token": _api_key()}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{BASE_URL}/stock/metric", params=params)
            if r.status_code != 200:
                return None
            data = r.json()
    except Exception:
        return None

    metric = data.get("metric") or {}
    if not metric:
        # ETFs / funds typically return empty here — that's fine, caller falls back
        _save_cache(cache_key, None)  # cache the negative so we don't re-poll
        return None

    out = {
        "pe":             _f(metric.get("peNormalizedAnnual") or metric.get("peTTM")),
        "margin":         _f(metric.get("netProfitMarginAnnual") or metric.get("netProfitMarginTTM")),
        "roe":            _f(metric.get("roeRfy") or metric.get("roeTTM")),
        "eps_growth":     _f(metric.get("epsGrowth5Y") or metric.get("epsGrowthTTMYoy")),
        "revenue_growth": _f(metric.get("revenueGrowth5Y") or metric.get("revenueGrowthTTMYoy")),
        "debt_to_equity": _f(metric.get("totalDebt/totalEquityAnnual")),
    }
    _save_cache(cache_key, out)
    return out


def _f(v: Any) -> float | None:
    """Coerce to float or None — Finnhub sometimes returns null/empty/strings."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compute_fundamentals_score(metrics: dict[str, float | None] | None) -> float | None:
    """
    Convert raw Finnhub fundamentals into a 0-100 sub-score.
    Returns None for tickers with no fundamentals (ETFs, funds) — caller
    should fall back to a neutral 50 or skip the factor entirely.

    Algorithm: weighted blend of (margin, ROE, EPS growth, revenue growth)
    bucketed against rough industry-typical ranges. Not academically rigorous
    but signals direction: high-margin / growing / profitable tickers score
    higher, money-losing / shrinking tickers score lower.
    """
    if not metrics:
        return None

    components: list[float] = []

    margin = metrics.get("margin")
    if margin is not None:
        # 0% margin = 30; 20% margin = 80; >40% margin = 100
        components.append(max(0, min(100, 30 + margin * 2.5)))

    roe = metrics.get("roe")
    if roe is not None:
        # 0% ROE = 30; 15% = 75; >30% = 100
        components.append(max(0, min(100, 30 + roe * 2.3)))

    eps_g = metrics.get("eps_growth")
    if eps_g is not None:
        # -10% = 20; 0% = 50; 15% = 80; >30% = 100
        components.append(max(0, min(100, 50 + eps_g * 2)))

    rev_g = metrics.get("revenue_growth")
    if rev_g is not None:
        # Same scale as EPS growth
        components.append(max(0, min(100, 50 + rev_g * 2)))

    pe = metrics.get("pe")
    if pe is not None and pe > 0:
        # Inverse: P/E 15 = 70 (cheap-ish), 25 = 55, 40 = 35 (expensive)
        components.append(max(0, min(100, 100 - pe * 1.5)))

    if not components:
        return None
    return round(sum(components) / len(components), 1)


async def fetch_company_profile(symbol: str) -> dict[str, Any] | None:
    """
    Sector + industry + name + market cap for a ticker. Used to backfill
    Ticker.sector="Unknown" rows after universe auto-discovery.

    Cached 7 days per symbol — sectors don't change.
    """
    if not configured():
        return None

    sym = symbol.upper()
    cache_key = f"profile_{sym}"
    cached = _load_cache(cache_key, CACHE_TTL_FUNDAMENTALS_HOURS)
    if cached is not None:
        return cached if cached else None  # may be {} for unknown tickers

    params = {"symbol": sym, "token": _api_key()}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{BASE_URL}/stock/profile2", params=params)
            if r.status_code != 200:
                return None
            data = r.json()
    except Exception:
        return None

    if not data:
        _save_cache(cache_key, {})  # cache the empty so we don't re-poll
        return None

    profile = {
        "sector":      data.get("finnhubIndustry") or "Unknown",
        "industry":    data.get("finnhubIndustry") or "",
        "name":        data.get("name") or sym,
        "market_cap":  _f(data.get("marketCapitalization")),
        "country":     data.get("country") or "",
        "exchange":    data.get("exchange") or "",
        "ipo":         data.get("ipo") or "",
    }
    _save_cache(cache_key, profile)
    return profile


async def fetch_insider_transactions(symbol: str, days_back: int = 90) -> list[dict[str, Any]] | None:
    """
    Recent insider Form 4 filings for a ticker. Used to enrich sub_smart_money.
    Returns list of {filer_name, transaction_date, share_change, transaction_value}.
    """
    if not configured():
        return None

    sym = symbol.upper()
    cache_key = f"insider_{sym}_{days_back}d"
    cached = _load_cache(cache_key, CACHE_TTL_INSIDER_HOURS)
    if cached is not None:
        return cached

    today = date.today()
    start = today - timedelta(days=days_back)
    params = {
        "symbol": sym,
        "from": start.isoformat(),
        "to": today.isoformat(),
        "token": _api_key(),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{BASE_URL}/stock/insider-transactions", params=params)
            if r.status_code != 200:
                return None
            data = r.json()
    except Exception:
        return None

    raw = data.get("data") or []
    rows: list[dict[str, Any]] = []
    for it in raw:
        rows.append({
            "filer_name": it.get("name", ""),
            "transaction_date": it.get("transactionDate", ""),
            "share_change": int(it.get("change") or 0),
            "transaction_price": float(it.get("transactionPrice") or 0),
        })
    _save_cache(cache_key, rows)
    return rows
