"""
FRED (Federal Reserve Economic Data) adapter — free macro indicators.

Used by polygon_feed.fetch_regime to replace the hardcoded DXY / 10Y / VIX
values. FRED requires a free API key (https://fred.stlouisfed.org/docs/api/api_key.html);
without one, this module returns None for every series and the caller falls back
to the existing hardcoded values.

Cache: 1h per series (FRED data updates daily, so 1h is plenty courteous).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache"
CACHE_TTL_SECONDS = 3600

FRED_API = "https://api.stlouisfed.org/fred/series/observations"

# Series IDs
DXY_SERIES = "DTWEXBGS"   # USD broad index, daily
TREASURY_10Y = "DGS10"    # 10Y treasury constant maturity, daily
VIX_SERIES = "VIXCLS"     # VIX close, daily


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"fred_{name}.json"


async def _fetch_series_latest(series_id: str) -> float | None:
    """Most recent observation for a FRED series. Returns None on any failure."""
    api_key = getattr(settings, "fred_api_key", "") or ""
    if not api_key:
        return None  # graceful no-op

    cache_file = _cache_path(series_id)
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            if (time.time() - cached.get("_ts", 0)) < CACHE_TTL_SECONDS:
                return cached.get("value")
        except (json.JSONDecodeError, OSError):
            pass

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(FRED_API, params=params)
            r.raise_for_status()
            obs = r.json().get("observations", [])
            if obs:
                raw = obs[0].get("value", "")
                if raw and raw != ".":  # FRED uses "." for missing values
                    value = float(raw)
                    try:
                        cache_file.write_text(json.dumps({"_ts": time.time(), "value": value}))
                    except OSError:
                        pass
                    return value
    except (httpx.HTTPError, ValueError, KeyError):
        logger.exception("fred.fetch_failed series=%s", series_id)
    return None


async def fetch_macro_indicators() -> dict[str, float | None]:
    """Returns {dxy, yield_10y, vix} — None for any series that failed."""
    return {
        "dxy": await _fetch_series_latest(DXY_SERIES),
        "yield_10y": await _fetch_series_latest(TREASURY_10Y),
        "vix": await _fetch_series_latest(VIX_SERIES),
    }
