"""
FRED (Federal Reserve Economic Data) adapter — free macro indicators.

Used by polygon_feed.fetch_regime to replace the hardcoded DXY / 10Y / VIX
values. FRED requires a free API key (https://fred.stlouisfed.org/docs/api/api_key.html);
without one, this module returns None for every series and the caller falls back
to the existing hardcoded values.

Cache: 1h per series (FRED data updates daily, so 1h is plenty courteous).
"""
from __future__ import annotations

import contextlib
import json
import logging
import time
from pathlib import Path
from typing import TypedDict

import httpx

from app.config import get_settings


class MacroIndicators(TypedDict):
    """Typed return shape for `fetch_macro_indicators`.

    Numeric series return None when FRED isn't configured or the call failed
    (caller substitutes a sensible default). `rate_direction` is always one
    of RISING / FALLING / SIDEWAYS — never None — because we treat absence of
    history as SIDEWAYS rather than nullable.
    """

    dxy: float | None
    yield_10y: float | None
    vix: float | None
    rate_direction: str

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
                    with contextlib.suppress(OSError):
                        cache_file.write_text(json.dumps({"_ts": time.time(), "value": value}))
                    return value
    except (httpx.HTTPError, ValueError, KeyError):
        logger.exception("fred.fetch_failed series=%s", series_id)
    return None


async def _fetch_series_history(series_id: str, limit: int = 35) -> list[float]:
    """Most recent N observations for a FRED series (newest first).

    Used to compute slopes — e.g. is the 10Y yield rising or falling over
    the last ~30 trading days. Returns [] on any failure or missing key.
    """
    api_key = getattr(settings, "fred_api_key", "") or ""
    if not api_key:
        return []

    cache_file = _cache_path(f"{series_id}_hist{limit}")
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            if (time.time() - cached.get("_ts", 0)) < CACHE_TTL_SECONDS:
                return cached.get("values", []) or []
        except (json.JSONDecodeError, OSError):
            pass

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(FRED_API, params=params)
            r.raise_for_status()
            obs = r.json().get("observations", [])
            values: list[float] = []
            for o in obs:
                raw = o.get("value", "")
                if raw and raw != ".":
                    try:
                        values.append(float(raw))
                    except ValueError:
                        continue
            if values:
                with contextlib.suppress(OSError):
                    cache_file.write_text(json.dumps({"_ts": time.time(), "values": values}))
                return values
    except (httpx.HTTPError, ValueError, KeyError):
        logger.exception("fred.history_failed series=%s", series_id)
    return []


def _direction(history: list[float], threshold_pct: float = 0.5) -> str:
    """Newest-first values -> RISING / FALLING / SIDEWAYS.

    Compares the latest value to the value ~30 observations back. Any
    move under `threshold_pct` (relative) is treated as SIDEWAYS so we
    don't flicker on noise. Falls back to SIDEWAYS without enough data.
    """
    if len(history) < 10:
        return "SIDEWAYS"
    latest = history[0]
    base = history[min(len(history) - 1, 29)]
    if base == 0:
        return "SIDEWAYS"
    pct = (latest - base) / base * 100
    if pct > threshold_pct:
        return "RISING"
    if pct < -threshold_pct:
        return "FALLING"
    return "SIDEWAYS"


async def fetch_macro_indicators() -> MacroIndicators:
    """Returns {dxy, yield_10y, vix, rate_direction}.

    `rate_direction` is RISING / FALLING / SIDEWAYS based on the 10Y
    yield's move over the last ~30 trading days. SIDEWAYS when no key
    is configured.
    """
    history_10y = await _fetch_series_history(TREASURY_10Y, limit=35)
    yield_10y_latest: float | None = history_10y[0] if history_10y else await _fetch_series_latest(TREASURY_10Y)
    return MacroIndicators(
        dxy=await _fetch_series_latest(DXY_SERIES),
        yield_10y=yield_10y_latest,
        vix=await _fetch_series_latest(VIX_SERIES),
        rate_direction=_direction(history_10y),
    )
