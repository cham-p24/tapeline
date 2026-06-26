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
from datetime import UTC, date, timedelta
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


# ---- Recent insider transactions — DB-backed, cross-process ---------------
# Powers /app/holdings ("Recent Insider Buys") and the per-ticker InsiderTab.
# Before 2026-05-16 this was an in-process `_INSIDER_FEED` list — the worker
# wrote to its own list, the API read from its own list, and on Fly (where
# api + worker run on separate machines) the API ALWAYS saw an empty list.
# Now writes go to the `insider_transactions` table; reads query it directly.
#
# The setter/getter API is preserved bit-for-bit so callers (worker, router,
# tests) don't need to change. Synchronous wrappers around the async DB calls
# would have required threadlocal sessions; instead both functions are now
# async, with a single sync wrapper kept for legacy compute paths that don't
# have an event loop handy.


async def set_recent_insider_transactions_db(
    symbol: str, txns: list[dict[str, Any]],
) -> None:
    """Bulk-replace this symbol's insider transactions in the DB.

    Pattern:
      DELETE FROM insider_transactions WHERE symbol = :sym
      INSERT INTO insider_transactions (...) VALUES (...) -- N rows

    Idempotent — running the daily refresh twice in a row produces the same
    end state because we delete-then-insert. The UniqueConstraint is a
    belt-and-braces guard in case a future bug duplicates inserts.
    """
    from sqlalchemy import delete
    from sqlalchemy.exc import IntegrityError

    from app.db import session_scope
    from app.models import InsiderTransaction

    sym = symbol.upper()
    async with session_scope() as session:
        await session.execute(delete(InsiderTransaction).where(InsiderTransaction.symbol == sym))
        for t in txns or []:
            share_change = int(t.get("share_change") or 0)
            price = float(t.get("transaction_price") or 0)
            row = InsiderTransaction(
                symbol=sym,
                insider_name=(t.get("filer_name") or "")[:120],
                transaction_date=(t.get("transaction_date") or "")[:10],
                share_change=share_change,
                transaction_price=round(price, 4),
                transaction_value=round(abs(share_change * price), 2),
                code=(t.get("code") or "")[:4],
            )
            session.add(row)
        try:
            await session.commit()
        except IntegrityError:
            # Race against another concurrent refresh — the unique constraint
            # caught a duplicate. Roll back and let the next refresh re-run
            # cleanly. Doesn't bring the worker tick down.
            await session.rollback()
            logger.warning("insider.write_race symbol=%s", sym)


# Legacy alias for the worker, which still calls the sync-named helper.
def set_recent_insider_transactions(symbol: str, txns: list[dict[str, Any]]) -> None:
    """Sync facade — schedules the async DB write without blocking the worker.

    The worker loop is inside asyncio.run, so we can grab the running loop
    and create_task. If somehow there's no loop (sync test), we fall back to
    asyncio.run on a one-shot loop.
    """
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(set_recent_insider_transactions_db(symbol, txns))
    except RuntimeError:
        # No running loop — sync caller, e.g. a test. Run inline.
        asyncio.run(set_recent_insider_transactions_db(symbol, txns))


async def get_recent_insider_transactions_db(
    days: int = 30,
    limit: int = 100,
    symbol: str | None = None,
    buys_only: bool = False,
) -> list[dict[str, Any]]:
    """Query the DB-backed feed.

    days        — only entries whose transaction_date is within this many days
    limit       — max rows to return (post-filter)
    symbol      — optional ticker filter (case-insensitive)
    buys_only   — if True, return only net positive share_change rows

    Same shape and ordering as the prior in-memory implementation so the
    router/UI don't see any contract change.
    """
    from sqlalchemy import desc, select

    from app.db import session_scope
    from app.models import InsiderTransaction

    cutoff = (date.today() - timedelta(days=max(1, days))).isoformat()
    sym = symbol.upper() if symbol else None

    stmt = (
        select(InsiderTransaction)
        .where(InsiderTransaction.transaction_date >= cutoff)
        .order_by(desc(InsiderTransaction.transaction_date))
        .limit(limit)
    )
    if sym:
        stmt = stmt.where(InsiderTransaction.symbol == sym)
    if buys_only:
        stmt = stmt.where(InsiderTransaction.share_change > 0)

    async with session_scope() as session:
        result = await session.execute(stmt)
        rows = result.scalars().all()

    return [
        {
            "symbol":            r.symbol,
            "insider_name":      r.insider_name,
            "transaction_date":  r.transaction_date,
            "share_change":      r.share_change,
            "transaction_price": r.transaction_price,
            "transaction_value": r.transaction_value,
            "code":              r.code,
        }
        for r in rows
    ]


def get_recent_insider_transactions(
    days: int = 30,
    limit: int = 100,
    symbol: str | None = None,
    buys_only: bool = False,
) -> list[dict[str, Any]]:
    """Sync facade for legacy callers (none expected — router is async).

    Kept so existing tests that imported the old sync API continue to work.
    Returns [] if called from inside an async context (use the _db variant
    directly there).
    """
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            get_recent_insider_transactions_db(days, limit, symbol, buys_only)
        )
    # Inside an event loop — can't run another. Caller should use the async
    # variant. Return empty as a defensive default.
    logger.warning("insider.sync_facade_called_in_async_context")
    return []


async def insider_feed_size_db() -> int:
    """Total rows in the DB-backed feed. Cheap COUNT(*) — runs against an
    index'd column so it's sub-millisecond even with the full universe."""
    from sqlalchemy import func as sa_func
    from sqlalchemy import select as sa_select

    from app.db import session_scope
    from app.models import InsiderTransaction

    async with session_scope() as session:
        result = await session.execute(sa_select(sa_func.count(InsiderTransaction.id)))
        return int(result.scalar_one() or 0)


def insider_feed_size() -> int:
    """Sync facade — kept for callers that show the count without an async
    context. Returns 0 if inside an event loop (use *_db variant)."""
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(insider_feed_size_db())
    return 0


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
        # Defensive: prior versions of this function (pre-2026-05-16) cached an
        # all-null dict for ETFs because the explicit all-None check below
        # wasn't here. Treat any cached value where every field is None as
        # "no coverage" so the bug doesn't haunt us until the 7-day TTL clears.
        if isinstance(cached, dict) and cached and all(v is None for v in cached.values()):
            return None
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
    # ETFs and funds: Finnhub returns a non-empty `metric` object (price/return
    # stats) but NONE of the stock-fundamentals fields we look for. Without
    # this check we cache an all-None dict and the router reports
    # available=true, which makes the frontend render 6 cards full of "—"
    # dashes — exactly what the user reported on /app/ticker/BBP. Treat
    # all-null as no coverage.
    if all(v is None for v in out.values()):
        _save_cache(cache_key, None)
        return None
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
            # SEC Form 4 transaction code (P/S/A/M/G/F/etc) — exposed so the
            # /app/holdings UI can filter open-market buys ("P") from grants ("A").
            "code": it.get("transactionCode", "") or "",
        })
    _save_cache(cache_key, rows)
    return rows


# ---------------------------------------------------------------------------
# News + analyst coverage
# ---------------------------------------------------------------------------
# Finnhub has broad coverage including international / UK-listed names (BUR,
# RIO ADR, etc.) because they aggregate from a wide wire net. Used as the
# secondary news source in news_feed (alongside Massive) and as the source
# for the per-ticker analyst-ratings widget.

CACHE_TTL_NEWS_HOURS = 0.25  # 15 min — news is the most time-sensitive
CACHE_TTL_RECS_HOURS = 12    # Analyst recs aggregate is monthly; 12h is plenty


async def fetch_news_for_ticker(
    symbol: str, days_back: int = 14, limit: int = 10,
) -> list[dict[str, Any]]:
    """Per-ticker news from Finnhub /company-news.

    One of the parallel sources in news_feed (alongside Massive), with
    broad coverage of UK-listed names, smaller US ADRs, etc. Returns the
    canonical news-row shape so consumers don't care which source served it.
    """
    from datetime import datetime

    if not configured():
        return []

    sym = symbol.upper()
    cache_key = f"news_{sym}_{days_back}d_{limit}"
    cached = _load_cache(cache_key, CACHE_TTL_NEWS_HOURS)
    if cached is not None:
        # The on-disk cache stores published_at as an ISO string (a datetime
        # isn't JSON-serializable). Re-hydrate to a tz-aware datetime so this
        # function returns the SAME type on a cache hit as on a cache miss —
        # and the same type as edgar/massive. news_feed.merge sorts
        # the combined list by published_at and raises TypeError if some rows
        # are str and others datetime.
        for r in cached:
            pa = r.get("published_at")
            if isinstance(pa, str):
                try:
                    r["published_at"] = datetime.fromisoformat(pa)
                except ValueError:
                    r["published_at"] = datetime.now(UTC)
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
            r = await c.get(f"{BASE_URL}/company-news", params=params)
            if r.status_code != 200:
                return []
            data = r.json() if isinstance(r.json(), list) else []
    except Exception:
        logger.exception("finnhub.news_fetch_failed symbol=%s", sym)
        return []

    rows: list[dict[str, Any]] = []
    for a in data[:limit]:
        # Finnhub's `datetime` is a unix timestamp (seconds).
        try:
            ts = int(a.get("datetime") or 0)
            published = datetime.fromtimestamp(ts, tz=UTC)
        except Exception:
            published = datetime.now(UTC)
        article_id = f"fh-{a.get('id') or ts}"
        # clip_news_row caps every column to its DB length so a Finnhub
        # tracking-URL >500 chars can't poison the session.
        from app.services.news_feed import clip_news_row
        rows.append(clip_news_row({
            "id": article_id,
            "title": str(a.get("headline") or "").strip()[:300],
            "publisher": (a.get("source") or "Finnhub").strip(),
            "author": None,
            "published_at": published,
            "url": a.get("url") or "",
            "description": (a.get("summary") or "").strip()[:300] or None,
            "tickers": sym,
            "sentiment": None,
        }))
    # published_at is a datetime, which json.dumps can't serialize — so
    # _save_cache was silently TypeError-ing (logged as cache_write_failed)
    # and news was NEVER cached. Every /api/ticker render then re-hit Finnhub
    # (httpx 15s, 60/min rate-limited) while holding a DB connection, the core
    # driver of the QueuePool-exhaustion latency. Serialize published_at to ISO
    # for the on-disk copy only; the returned `rows` keep their datetimes and
    # the cache-hit path above re-hydrates.
    _save_cache(cache_key, [
        {
            **r,
            "published_at": r["published_at"].isoformat()
            if hasattr(r.get("published_at"), "isoformat")
            else r.get("published_at"),
        }
        for r in rows
    ])
    return rows


async def fetch_market_news(limit: int = 40) -> list[dict[str, Any]]:
    """Market-wide latest headlines from Finnhub /news?category=general.

    Added as a parallel source to news_feed.fetch_latest_news so universe-level
    freshness no longer depends solely on Massive's reference/news feed (which
    lags); the old real-time wire (Benzinga) was removed 2026-06-24. Returns the
    canonical news-row shape so callers don't care which source served it.

    Deliberately NOT cached: freshness is the whole point here, and it's a single
    cheap request per ~5-min worker refresh (well inside Finnhub's 60/min free
    tier). Mirrors the row-building of fetch_news_for_ticker.
    """
    from datetime import datetime

    if not configured():
        return []

    params = {"category": "general", "token": _api_key()}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{BASE_URL}/news", params=params)
            if r.status_code != 200:
                return []
            payload = r.json()
            data = payload if isinstance(payload, list) else []
    except Exception:
        logger.exception("finnhub.market_news_fetch_failed")
        return []

    # Local import avoids a circular import at module load (news_feed imports
    # this module lazily too).
    from app.services.news_feed import clip_news_row

    rows: list[dict[str, Any]] = []
    for a in data[:limit]:
        # Finnhub's `datetime` is a unix timestamp (seconds).
        try:
            ts = int(a.get("datetime") or 0)
            published = datetime.fromtimestamp(ts, tz=UTC)
        except Exception:
            published = datetime.now(UTC)
        rows.append(clip_news_row({
            "id": f"fh-{a.get('id') or ts}",
            "title": str(a.get("headline") or "").strip()[:300],
            "publisher": (a.get("source") or "Finnhub").strip(),
            "author": None,
            "published_at": published,
            "url": a.get("url") or "",
            "description": (a.get("summary") or "").strip()[:300] or None,
            # General news often carries a comma-separated `related` ticker list
            # (frequently empty for macro headlines).
            "tickers": (a.get("related") or "").strip(),
            "sentiment": None,
        }))
    return rows


async def fetch_analyst_recommendations(symbol: str) -> dict[str, Any] | None:
    """Aggregate analyst tally from Finnhub /stock/recommendation.

    Returns the latest-period buy/hold/sell consensus in the canonical
    ratings shape the frontend's Analyst Ratings widget renders. Covers
    US, UK-listed, and international names.

    Note: Finnhub's free tier only exposes the AGGREGATE — individual
    rating events (firm-by-firm with prior/current + price targets) are
    a paid endpoint. So `events: []` and `avg_pt: null` here. The
    frontend handles the empty events list gracefully.
    """
    if not configured():
        return None

    sym = symbol.upper()
    cache_key = f"recs_{sym}"
    cached = _load_cache(cache_key, CACHE_TTL_RECS_HOURS)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                f"{BASE_URL}/stock/recommendation",
                params={"symbol": sym, "token": _api_key()},
            )
            if r.status_code != 200:
                return None
            data = r.json() if isinstance(r.json(), list) else []
    except Exception:
        logger.exception("finnhub.recs_fetch_failed symbol=%s", sym)
        return None

    if not data:
        return None

    # Pick the latest period. Finnhub returns desc by period.
    latest = data[0]
    bull = int(latest.get("strongBuy") or 0) + int(latest.get("buy") or 0)
    bear = int(latest.get("strongSell") or 0) + int(latest.get("sell") or 0)
    neutral = int(latest.get("hold") or 0)
    total = bull + bear + neutral
    if total == 0:
        return None

    result = {
        "symbol": sym,
        "consensus": {"bull": bull, "bear": bear, "neutral": neutral, "total": total},
        "avg_pt": None,
        "events": [],  # Finnhub free tier doesn't expose per-firm events.
        "source": "finnhub",
        "as_of_period": str(latest.get("period") or ""),
    }
    _save_cache(cache_key, result)
    return result


def _empty_ratings(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "consensus": {"bull": 0, "bear": 0, "neutral": 0, "total": 0},
        "avg_pt": None,
        "events": [],
        "source": "empty",
    }


async def fetch_analyst_ratings(symbol: str) -> dict[str, Any]:
    """Recent analyst ratings + consensus for a ticker — backs the per-ticker
    Analyst Ratings widget (GET /api/ticker/{symbol}/ratings).

    Returns the canonical ratings shape:

        {
          "symbol": "AAPL",
          "consensus": {"bull": int, "bear": int, "neutral": int, "total": int},
          "avg_pt": float | None,
          "events": [...],          # per-firm events (empty on Finnhub free tier)
          "source": "finnhub" | "empty",
        }

    When there's no analyst coverage for the ticker (common for thinly-covered
    long-tail names), returns the empty shape so the frontend renders a clean
    "no consensus tracked" state.
    """
    symbol = (symbol or "").upper()
    if not symbol:
        return _empty_ratings(symbol)
    try:
        data = await fetch_analyst_recommendations(symbol)
    except Exception:
        logger.exception("finnhub.ratings_fetch_failed symbol=%s", symbol)
        return _empty_ratings(symbol)
    if data and data.get("consensus", {}).get("total", 0) > 0:
        return data
    return _empty_ratings(symbol)
