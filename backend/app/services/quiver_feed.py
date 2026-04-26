"""
Quiver QuantData adapter — elite-investor 13F holdings.

Used to enrich the `smart_money` sub-score with real institutional positioning
data from the eight elite funds we track. Pattern adapted from the personal
signal-system Quiver integration: 24h cache, multi-endpoint fallback,
graceful degradation when API is unavailable.

Auth:
    - Requires QUIVER_API_KEY env var.
    - Without a key, every fetch returns None (caller falls back to mock).

Cache:
    - 24h per query, written to backend/.cache/quiver_*.json.
    - SEC reporting window for 13Fs is 45 days, so 24h cadence is conservative.

Wiring (still TODO):
    - signal_publisher.py worker: call fetch_elite_13f_holdings() once per 24h
      and store results in a new `institutional_holdings` table (migration needed).
    - smart_money sub-score: when a tracked fund has a recent buy in a ticker,
      bump that ticker's sub_smart_money toward 100.
    - /api/holdings endpoint: expose to Premium users (gated via FEATURES dict).

Without that wiring this module is a ready-to-use library; the worker
integration is on the post-launch list because it requires a new migration.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache"
CACHE_TTL_HOURS = 24

# Elite investors we track for the smart-money signal.
# Ported from the personal signal-system tracked-funds list.
TRACKED_FUNDS: list[dict[str, str]] = [
    {"name": "Berkshire Hathaway",     "manager": "Buffett",       "cik": "0001067983", "slug": "berkshire-hathaway"},
    {"name": "Scion Asset Management", "manager": "Burry",         "cik": "0001649339", "slug": "scion-asset-management"},
    {"name": "Appaloosa LP",           "manager": "Tepper",        "cik": "0001656456", "slug": "appaloosa-lp"},
    {"name": "Pershing Square",        "manager": "Ackman",        "cik": "0001336528", "slug": "pershing-square-capital"},
    {"name": "Duquesne Family Office", "manager": "Druckenmiller", "cik": "0001536411", "slug": "duquesne-family-office"},
    {"name": "Coatue Management",      "manager": "Laffont",       "cik": "0001135730", "slug": "coatue-management"},
    {"name": "Tiger Global",           "manager": "Coleman",       "cik": "0001167483", "slug": "tiger-global-management"},
    {"name": "Elliott Management",     "manager": "Singer",        "cik": "0001791786", "slug": "elliott-management"},
]


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"quiver_{name}.json"


def _load_cache(name: str) -> dict | None:
    p = _cache_path(name)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        if (time.time() - data.get("_ts", 0)) > CACHE_TTL_HOURS * 3600:
            return None  # stale
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(name: str, payload: dict) -> None:
    payload["_ts"] = time.time()
    try:
        _cache_path(name).write_text(json.dumps(payload))
    except OSError:
        logger.warning("quiver.cache_write_failed name=%s", name)


def _api_key() -> str:
    return getattr(settings, "quiver_api_key", "") or ""


async def fetch_elite_13f_holdings(top_n_per_fund: int = 6) -> list[dict[str, Any]] | None:
    """
    Returns a flat list of top-N positions across all tracked elite funds.

    Each entry: {fund_name, manager, symbol, value_usd, shares, percent_portfolio}.

    Returns None if no API key OR every fund's endpoints all failed (caller
    should fall back to mock data so the sheet never goes empty).
    """
    api_key = _api_key()
    if not api_key:
        logger.info("quiver.13f_skipped reason=no_api_key")
        return None

    cached = _load_cache("13f_all")
    if cached:
        logger.info("quiver.13f_cache_hit count=%d", len(cached.get("rows", [])))
        return cached.get("rows", [])

    rows: list[dict[str, Any]] = []
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=20, headers=headers) as client:
        for fund in TRACKED_FUNDS:
            data = await _try_fund_endpoints(client, fund)
            if not data:
                logger.info("quiver.13f_fund_empty fund=%s", fund["name"])
                continue
            # Sort by position size descending; take top N
            data_sorted = sorted(
                data,
                key=lambda h: float(h.get("Value") or h.get("value") or 0),
                reverse=True,
            )
            for h in data_sorted[:top_n_per_fund]:
                rows.append({
                    "fund_name": fund["name"],
                    "manager": fund["manager"],
                    "symbol": (h.get("Ticker") or h.get("symbol") or "").upper(),
                    "value_usd": float(h.get("Value") or h.get("value") or 0),
                    "shares": int(h.get("Shares") or h.get("shares") or 0),
                    "percent_portfolio": float(h.get("Percent") or h.get("percent_portfolio") or 0),
                })

    if not rows:
        logger.warning("quiver.13f_empty no_funds_returned_data")
        return None

    _save_cache("13f_all", {"rows": rows})
    logger.info("quiver.13f_fetched count=%d funds=%d", len(rows), len(TRACKED_FUNDS))
    return rows


async def _try_fund_endpoints(client: httpx.AsyncClient, fund: dict) -> list | None:
    """Different Quiver tiers expose different endpoint shapes. Try each."""
    candidates = [
        f"https://api.quiverquant.com/beta/live/institutions/{fund['slug']}",
        f"https://api.quiverquant.com/beta/historical/13F/{fund['cik']}",
        f"https://api.quiverquant.com/beta/live/institutionalholdings/{fund['slug']}",
    ]
    for url in candidates:
        try:
            r = await client.get(url)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    return data
        except (httpx.HTTPError, json.JSONDecodeError):
            continue
    return None


def get_tracked_funds() -> list[dict[str, str]]:
    """Public accessor for the tracked-funds list (used by /api/holdings router)."""
    return list(TRACKED_FUNDS)


def mock_elite_13f_holdings() -> list[dict[str, Any]]:
    """
    Plausible mock 13F data for the eight tracked funds.

    Used in dev when QUIVER_API_KEY isn't set so the holdings sheet never
    goes empty. Deterministic seed (Random(20260427)) so the same mock data
    appears across worker restarts during a dev session.

    Returns the same shape as fetch_elite_13f_holdings(): a flat list of
    per-position dicts with fund_name, manager, cik, symbol, value_usd,
    shares, percent_portfolio.
    """
    import random as _r

    rng = _r.Random(20260427)
    candidate_pool = [
        "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "BRK.B", "JPM", "V", "MA",
        "UNH", "LLY", "JNJ", "XOM", "CVX", "WMT", "COST", "HD", "TSLA", "AMD",
        "AVGO", "ORCL", "BAC", "WFC", "GS", "MRK", "PFE", "ABBV", "CAT", "DE",
        "GLD", "SLV", "USO", "URA", "GDX",  # commodity ETFs occasionally show up
    ]
    rows: list[dict[str, Any]] = []
    for fund in TRACKED_FUNDS:
        portfolio_total = rng.uniform(5e9, 200e9)  # $5B–$200B AUM
        picks = rng.sample(candidate_pool, k=6)
        for i, sym in enumerate(picks):
            # Position sizes decay — top pick ~12%, last ~2%
            pct = max(1.5, rng.uniform(2, 15) * (1 - i * 0.12))
            value = portfolio_total * pct / 100
            shares = int(value / rng.uniform(50, 600))
            rows.append({
                "fund_name": fund["name"],
                "manager": fund["manager"],
                "cik": fund["cik"],
                "symbol": sym,
                "value_usd": round(value, 2),
                "shares": shares,
                "percent_portfolio": round(pct, 2),
            })
    return rows
