"""
Fear & Greed Index — 0-100 sentiment score.

Tapeline's version of the CNN F&G index, computed from data we already have:
VIX (via FRED), breadth_pct (% of S&P above 200DMA, computed live each tick),
regime label, and short-window SPY momentum. No new data sources needed —
all four inputs already feed the regime endpoint.

Score buckets (matches CNN's labels for instant familiarity):
   0-24  Extreme Fear      red
  25-44  Fear              orange
  45-54  Neutral           grey
  55-74  Greed             light green
  75-100 Extreme Greed     green

Inputs:
  vix          — lower = greed (low expected vol). 12 = floor, 40 = max stress.
  breadth_pct  — % of S&P above 200DMA. Higher = greed.
  regime       — BULL / NEUTRAL / CAUTIOUS / BEAR. Anchor + sanity check.
  spy_change_5d_pct — momentum tilt; positive = greed, negative = fear.

Weighting (sum to 1.0):
  VIX     0.35   — most-watched single fear input
  Breadth 0.30   — strongest internal-strength signal
  Regime  0.20   — composite of the above plus rate-direction
  SPY 5d  0.15   — short-window emotion proxy

When inputs are missing (worker boot, FRED down, etc.) we fall back to the
neutral midpoint of each component so the overall index degrades gracefully
rather than hard-failing.
"""
from __future__ import annotations

from typing import Any


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _vix_to_greed(vix: float | None) -> float:
    """Map VIX to a 0-100 greed score. Lower VIX = more greed."""
    if vix is None:
        return 50.0
    # 12 (very calm) -> 100 greed, 40 (panic) -> 0 greed. Linear in between.
    raw = 100.0 * (40.0 - vix) / (40.0 - 12.0)
    return _clamp(raw)


def _breadth_to_greed(breadth_pct: float | None) -> float:
    """% of S&P 500 above 200-day moving average. Already 0-100 — pass through."""
    if breadth_pct is None:
        return 50.0
    return _clamp(breadth_pct)


def _regime_to_greed(regime: str | None) -> float:
    """Anchor score per regime label."""
    return {
        "BULL": 80.0,
        "NEUTRAL": 50.0,
        "CAUTIOUS": 30.0,
        "BEAR": 15.0,
    }.get((regime or "").upper(), 50.0)


def _spy_momentum_to_greed(spy_change_5d_pct: float | None) -> float:
    """5-day SPY % change. -3% or worse = 0 (panic), +3% or better = 100 (euphoria),
    linear in between, anchored at 50 for flat."""
    if spy_change_5d_pct is None:
        return 50.0
    # Map [-3%, +3%] linearly to [0, 100]; clamp outside that.
    raw = 50.0 + (spy_change_5d_pct / 3.0) * 50.0
    return _clamp(raw)


def label_for(score: float) -> tuple[str, str]:
    """Return (label, color_token) for a 0-100 score. Color tokens match
    Tailwind classes already used elsewhere (down/yellow-400/muted/up)."""
    if score < 25:
        return ("Extreme Fear", "down")
    if score < 45:
        return ("Fear", "yellow-400")
    if score < 55:
        return ("Neutral", "muted")
    if score < 75:
        return ("Greed", "accent")
    return ("Extreme Greed", "up")


def compute_fear_greed(
    vix: float | None,
    breadth_pct: float | None,
    regime: str | None,
    spy_change_5d_pct: float | None = None,
) -> dict[str, Any]:
    """Compute the index + return a structured response.

    Returns:
        {
            "score": 0-100 integer,
            "label": "Extreme Fear" | "Fear" | "Neutral" | "Greed" | "Extreme Greed",
            "color": "down" | "yellow-400" | "muted" | "accent" | "up",
            "components": {
                "vix":     {"score": float, "input": float | None},
                "breadth": {"score": float, "input": float | None},
                "regime":  {"score": float, "input": str | None},
                "spy_5d":  {"score": float, "input": float | None},
            },
        }
    """
    vix_score = _vix_to_greed(vix)
    breadth_score = _breadth_to_greed(breadth_pct)
    regime_score = _regime_to_greed(regime)
    spy_score = _spy_momentum_to_greed(spy_change_5d_pct)

    composite = (
        0.35 * vix_score
        + 0.30 * breadth_score
        + 0.20 * regime_score
        + 0.15 * spy_score
    )
    score = int(round(_clamp(composite)))
    label, color = label_for(score)

    return {
        "score": score,
        "label": label,
        "color": color,
        "components": {
            "vix":     {"score": round(vix_score, 1),     "input": vix},
            "breadth": {"score": round(breadth_score, 1), "input": breadth_pct},
            "regime":  {"score": round(regime_score, 1),  "input": regime},
            "spy_5d":  {"score": round(spy_score, 1),     "input": spy_change_5d_pct},
        },
    }
