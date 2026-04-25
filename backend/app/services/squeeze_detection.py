"""
Bollinger Band squeeze and volume-expansion detection.

Pure numerical algorithm — same logic as the personal signal-system engine,
rewritten here to be self-contained (no imports from C:\\signal-system).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_squeeze_features(bars: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Given >= 40 daily bars, compute BB width + volume + OBV features.
    Returns None if insufficient history.
    """
    if len(bars) < 40:
        return None

    df = pd.DataFrame(bars)
    # Polygon agg fields: o, h, l, c, v, t
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    close = df["close"].astype(float)
    volume = df["volume"].astype(float)

    # Bollinger Bands (20, 2)
    bb_ma = close.rolling(20).mean()
    bb_sd = close.rolling(20).std()
    bb_upper = bb_ma + 2 * bb_sd
    bb_lower = bb_ma - 2 * bb_sd
    bb_width = (bb_upper - bb_lower) / bb_ma

    # Width percentile over trailing 120 days (lower = tighter squeeze)
    width_pct = bb_width.rolling(120).apply(
        lambda x: (x.iloc[-1] <= x).mean() * 100 if len(x.dropna()) > 10 else np.nan
    )
    current_width_pct = float(width_pct.iloc[-1]) if not pd.isna(width_pct.iloc[-1]) else 50.0

    # Squeeze days: consecutive days at or below 30th percentile
    below_thresh = width_pct <= 30
    squeeze_days = 0
    for v in reversed(below_thresh.fillna(False).tolist()):
        if v:
            squeeze_days += 1
        else:
            break

    # Volume ratio: today vs 20d avg
    vol_avg = volume.rolling(20).mean()
    vol_mult = float(volume.iloc[-1] / vol_avg.iloc[-1]) if vol_avg.iloc[-1] > 0 else 1.0

    # OBV trend: sign of 10-period slope
    direction = np.sign(close.diff()).fillna(0)
    obv = (direction * volume).cumsum()
    obv_slope = obv.iloc[-1] - obv.iloc[-10] if len(obv) >= 10 else 0
    obv_trend = "RISING" if obv_slope > 0 else "FALLING" if obv_slope < 0 else "FLAT"

    # Spike score = weighted blend of (tightness + volume + OBV direction)
    tightness_points = max(0, (30 - current_width_pct) * 2)  # up to 60
    vol_points = min(30, (vol_mult - 1) * 15)  # up to 30
    obv_points = 10 if obv_trend == "RISING" else -5 if obv_trend == "FALLING" else 0
    spike_score = max(0, min(100, 40 + tightness_points + vol_points + obv_points))

    breakout = (
        "SQUEEZE" if squeeze_days >= 10 and current_width_pct <= 20
        else "COIL" if squeeze_days >= 5
        else "VOLATILITY CONTRACTION" if current_width_pct <= 30
        else "EXPANSION PENDING"
    )

    suggested = (
        "days" if spike_score >= 80
        else "1-2 weeks" if spike_score >= 70
        else "2-6 weeks" if spike_score >= 55
        else "watch"
    )

    return {
        "spike_score": round(spike_score, 1),
        "squeeze_days": squeeze_days,
        "volume_multiple": round(vol_mult, 2),
        "obv_trend": obv_trend,
        "breakout_type": breakout,
        "suggested_window": suggested,
        "reason": f"BB width {current_width_pct:.0f}%ile, squeeze {squeeze_days}d, vol {vol_mult:.1f}x",
    }


async def detect_squeezes_batch(symbols: list[str]) -> list[dict[str, Any]]:
    """Sweep universe, return only setups with spike_score >= 50."""
    from app.services.polygon_feed import fetch_aggregates

    setups = []
    # Sequential fetches — Starter tier is rate-limited
    for sym in symbols:
        try:
            bars = await fetch_aggregates(sym)
            feat = compute_squeeze_features(bars)
            if feat and feat["spike_score"] >= 50:
                setups.append({"symbol": sym, **feat})
        except Exception:
            logger.exception("squeeze_detection.failed symbol=%s", sym)
        # Rate-limit safety: ~12s between calls ~= 5/min
        await asyncio.sleep(12)

    # Sort highest spike first
    setups.sort(key=lambda x: -x["spike_score"])
    return setups[:25]
