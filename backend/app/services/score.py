"""Tapeline composite scoring — the 6-factor composite described on /how-it-works.

Before this module existed, `sheet_feed` took the signal-system Google Sheet's
column F "Score" verbatim and called it Tapeline's score. That meant:

  1. The composite `score = 0.25*trend + 0.20*rs + 0.15*fundamentals
     + 0.15*smart_money + 0.15*macro + 0.10*momentum` was marketing copy,
     not running code. /how-it-works spelled the equation out at the time
     and it wasn't actually applied — the score came from a different
     (external, opaque) algorithm. PR #342 has since stripped the numbers
     from the public site: the weights are internal and stay that way, and
     the public methodology names the six factors and their weight ORDERING
     only.
  2. The per-factor breakdown shown on /t/{symbol} pages was mostly empty
     because the sheet only populates `sub_rs` derivation data.
  3. Scores could leak above 100 (we observed 131-133 live) until clamped
     in PR #223.

This module computes Tapeline's actual composite from the available inputs:

  - Trend factor       ← 3M return blended with proximity to 52-week high
  - Relative Strength  ← existing `_approx_sub_rs(row)` in sheet_feed (RS-vs-SPY
                          across 3M/6M/1Y, weighted toward longer windows)
  - Fundamentals       ← finnhub_feed._FUND_SCORE_CACHE (Piotroski F-score etc.)
  - Smart Money        ← finnhub_feed._SMART_MONEY_SCORE_CACHE (SEC Form 4)
  - Macro              ← Market Regime column (RISING/SIDEWAYS/FALLING)
  - Momentum           ← Momentum Quality column blended with 1M proxy

Cache misses (factor unavailable for a ticker) fall back to a NEUTRAL 50 so
a missing factor doesn't drag the composite toward zero. That's intentional:
ETFs without P/E shouldn't be penalised on `sub_fundamentals` — they just
get the average score on that axis.

These weights are INTERNAL. /how-it-works documents the factor set and the
weight ORDERING only — never the numbers (PR #342) — so changing them is not a
public-disclosure change, but it does change every score the product has ever
published and still needs a corresponding `/changelog` entry.
"""

from __future__ import annotations

from typing import Any

# Weights match /how-it-works exactly. Change requires changelog entry.
WEIGHTS: dict[str, float] = {
    "trend":        0.25,
    "rs":           0.20,
    "fundamentals": 0.15,
    "smart_money":  0.15,
    "macro":        0.15,
    "momentum":     0.10,
}

# Cache-miss fallback. NOT zero: missing factor data should be neutral
# (50) so we don't punish ETFs that lack P/E ratios or new-listing
# tickers without insider history. Documented on /how-it-works.
NEUTRAL = 50.0

# Fewest factors that can produce a composite. Below this the number would be
# a statement about the NEUTRAL fallback rather than about the security, so
# there is no composite at all. `ticker_freshness` imports this rather than
# declaring its own, so a row cannot be scored here and then rejected as
# unscorable by the surfaces that decide what a user may see.
MIN_FACTORS_FOR_COMPOSITE = 2


def composite_from_factors(subs: dict[str, float | None]) -> float | None:
    """THE six-factor composite. Every feed must reach this function.

    `subs` is keyed by WEIGHTS' names (trend, rs, fundamentals, smart_money,
    macro, momentum). Returns None below MIN_FACTORS_FOR_COMPOSITE; otherwise
    the weighted sum with NEUTRAL for each missing factor, clamped 0-100 and
    rounded to one decimal.

    This exists because the arithmetic used to be written out twice — here for
    the sheet path and again in polygon_feed for the market path — and on
    2026-08-24 the two drifted: one re-normalised over the factors held while
    the other used the NEUTRAL fallback, so CDNA scored 80.2 or 93.2 depending
    purely on which feed happened to write the row. A product whose pitch is an
    unedited record cannot have two numbers for the same name, so there is now
    one implementation and the callers are adapters onto it.

    NEUTRAL, not zero, and not a re-normalised average:

    * Zero drags every incompletely-covered row toward the floor, so "we hold
      no fundamentals read" renders as "the fundamentals are terrible".
    * Re-normalising lets four strong factors produce a score a full six-factor
      read would never have justified — it upgrades thin coverage into high
      conviction.
    * NEUTRAL lets a missing factor neither help nor hurt. The sub-score itself
      is still stored as None so the UI renders an em-dash: the gap is
      disclosed, it just does not move the number.
    """
    held = sum(1 for k in WEIGHTS if subs.get(k) is not None)
    if held < MIN_FACTORS_FOR_COMPOSITE:
        return None
    composite = sum(
        w * (v if (v := subs.get(k)) is not None else NEUTRAL)
        for k, w in WEIGHTS.items()
    )
    return round(_clamp(composite), 1)


# ---------------------------------------------------------------------------
# Per-factor scorers — each takes a sheet row (dict) plus optional cache
# getters and returns a 0-100 sub-score, or None if even the neutral
# fallback isn't appropriate (e.g. no row data at all).
# ---------------------------------------------------------------------------


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def sub_trend(row: dict[str, Any]) -> float | None:
    """Trend: blend of 3M return + near-52W-high distance.

    3M return mapping (linear): -30% → 0, 0% → 50, +30% → 100.
    Near-52W-high (already 0-100 from sheet): higher = stronger trend.

    If both are present, average. If only one, use it.
    """
    r3m = row.get("change_pct_3m")
    near52 = row.get("near_52w_high_pct")

    parts: list[float] = []
    if r3m is not None:
        # ±30% maps to ±50 score points around midpoint 50
        parts.append(_clamp(50.0 + (r3m * 50.0 / 30.0)))
    if near52 is not None:
        parts.append(_clamp(float(near52)))

    if not parts:
        return None
    return sum(parts) / len(parts)


def sub_rs(row: dict[str, Any]) -> float | None:
    """Relative Strength: weighted blend of RS vs SPY across 3M/6M/1Y.

    Re-uses the same math as `sheet_feed._approx_sub_rs`. We don't import
    that helper here to avoid a circular dependency — the math is short
    enough to duplicate, and the duplication keeps `score.py` standalone
    + testable.
    """
    weights = [("rs_vs_spy_3m", 1.0), ("rs_vs_spy_6m", 1.5), ("rs_vs_spy_1y", 2.0)]
    total = 0.0
    weight = 0.0
    for key, w in weights:
        v = row.get(key)
        if v is None:
            continue
        component = 50.0 + float(v)  # ±50% RS → ±50 score points
        total += w * component
        weight += w
    if weight == 0:
        return None
    return _clamp(total / weight)


def sub_fundamentals(symbol: str, get_fund: Any | None = None) -> float | None:
    """Look up the cached fundamentals score (Piotroski-derived).

    `get_fund` is a callable `(symbol) -> float | None`. We accept it as an
    injectable so tests can pass a stub without import-time side effects.
    """
    if get_fund is None:
        try:
            from app.services.finnhub_feed import get_cached_score as _gcs
            get_fund = _gcs
        except Exception:
            return None
    val = get_fund(symbol)
    return None if val is None else _clamp(float(val))


def sub_smart_money(symbol: str, get_sm: Any | None = None) -> float | None:
    """Look up the cached Smart Money score (SEC Form 4 net 90-day)."""
    if get_sm is None:
        try:
            from app.services.finnhub_feed import get_cached_smart_money_score as _gss
            get_sm = _gss
        except Exception:
            return None
    val = get_sm(symbol)
    return None if val is None else _clamp(float(val))


# Market regime → sub_macro mapping. The signal-system sheet writes free-text
# values; we normalise + map. Anything we don't recognise falls back to
# SIDEWAYS (neutral) rather than producing None so we never accidentally
# drop the macro factor entirely.
#
# Split into NEGATIVE / POSITIVE / NEUTRAL lists (rather than a single dict)
# because sub_macro does substring-matching for free-text phrases like
# "BULL TREND" or "BULLISH (with caveat)" and order matters. If we iterated
# a positive-first list, "UNFAVORABLE" would hit `"FAVORABLE" in "UNFAVORABLE"`
# → 70.0 (positive) before any negative token had a chance to match. We
# walk NEGATIVE first so polarity-reversing prefixes ("UN-", "NON-", "ANTI-")
# resolve to the correct hostile score. Codex caught this on PR #226.
_NEGATIVE_REGIME_TOKENS: list[tuple[str, float]] = [
    ("UNFAVORABLE", 25.0),
    ("FALLING",     25.0),
    ("BEARISH",     25.0),
    ("BEAR",        25.0),
    ("HOSTILE",     25.0),
    ("NEGATIVE",    30.0),
]
_POSITIVE_REGIME_TOKENS: list[tuple[str, float]] = [
    ("RISING",      75.0),
    ("BULLISH",     75.0),
    ("BULL",        75.0),
    ("FAVORABLE",   70.0),
    ("POSITIVE",    65.0),
]
_NEUTRAL_REGIME_TOKENS: list[tuple[str, float]] = [
    ("SIDEWAYS",    50.0),
    ("NEUTRAL",     50.0),
    ("MIXED",       50.0),
    ("RANGE",       50.0),
]

# Direct-match dict used for the fast O(1) lookup when the sheet writes one
# of the exact bare tokens. Built from the three lists above so adding a
# token in one place updates both the substring scan AND the direct-match
# table — keeps the two from drifting.
_REGIME_TO_SCORE: dict[str, float] = dict(
    [
        *_NEGATIVE_REGIME_TOKENS,
        *_POSITIVE_REGIME_TOKENS,
        *_NEUTRAL_REGIME_TOKENS,
    ]
)


def regime_to_macro_score(regime: str | None) -> float:
    """Map a market-regime label to the macro sub-score (0-100).

    Reuses the same NEGATIVE/POSITIVE/NEUTRAL token tables as ``sub_macro`` so
    the two never drift, but differs on the empty/unknown case: this returns a
    NEUTRAL 50.0 rather than None. Callers that must ALWAYS produce a macro score
    (e.g. polygon_feed.fetch_snapshots, which previously let a random value flow
    into the composite and onto the permanent public scorecard) use this so the
    macro factor is deterministic — a known regime maps to its fixed value, and
    an unknown/empty regime falls back to 50, NEVER to a random number.
    """
    key = str(regime or "").strip().upper()
    if not key:
        return 50.0
    if key in _REGIME_TO_SCORE:
        return _REGIME_TO_SCORE[key]
    for token, value in _NEGATIVE_REGIME_TOKENS:
        if token in key:
            return value
    for token, value in _POSITIVE_REGIME_TOKENS:
        if token in key:
            return value
    for token, value in _NEUTRAL_REGIME_TOKENS:
        if token in key:
            return value
    return 50.0


def sub_macro(row: dict[str, Any]) -> float | None:
    """Market regime → sub_macro. Free-text input; defensive normalisation."""
    raw = row.get("market_regime") or ""
    key = str(raw).strip().upper()
    if not key:
        return None
    # Direct match (fast path: bare "RISING" / "BULL" / etc.)
    if key in _REGIME_TO_SCORE:
        return _REGIME_TO_SCORE[key]
    # Substring match — sheet sometimes writes phrases like "BULL TREND" or
    # "BULLISH (with caveat)". Walk NEGATIVE first so an "UN-" / "NON-"
    # prefixed positive token doesn't outrank a hostile classification.
    for token, value in _NEGATIVE_REGIME_TOKENS:
        if token in key:
            return value
    for token, value in _POSITIVE_REGIME_TOKENS:
        if token in key:
            return value
    for token, value in _NEUTRAL_REGIME_TOKENS:
        if token in key:
            return value
    return None


# Momentum Quality cell can be a number (0-100) or a label (HIGH/MED/LOW).
# Defensive: try float first, then label map.
_MOM_QUALITY_LABEL_TO_SCORE: dict[str, float] = {
    "VERY HIGH": 90.0,
    "HIGH":      75.0,
    "STRONG":    75.0,
    "MEDIUM":    50.0,
    "MED":       50.0,
    "MODERATE":  50.0,
    "LOW":       30.0,
    "WEAK":      25.0,
    "VERY LOW":  15.0,
}


def sub_momentum(row: dict[str, Any]) -> float | None:
    """Momentum: blend of Momentum Quality column + 1M return proxy.

    The sheet doesn't publish 1M return directly. We approximate using the
    3M return rescaled (3M / 3 is the standard fallback used elsewhere in
    sheet_feed). For each component that's available, contribute 0-100.
    """
    parts: list[float] = []

    # Momentum Quality from the sheet — can be numeric or label
    mq = row.get("momentum_quality")
    if mq is not None:
        # Try numeric first
        try:
            parts.append(_clamp(float(mq)))
        except (TypeError, ValueError):
            label = str(mq).strip().upper()
            if label in _MOM_QUALITY_LABEL_TO_SCORE:
                parts.append(_MOM_QUALITY_LABEL_TO_SCORE[label])
            else:
                # Try substring against labels
                for token, value in _MOM_QUALITY_LABEL_TO_SCORE.items():
                    if token in label:
                        parts.append(value)
                        break

    # 1M return proxy (3M / 3) → ±30% maps to ±50 around midpoint 50
    r3m = row.get("change_pct_3m")
    if r3m is not None:
        r1m_proxy = r3m / 3.0
        parts.append(_clamp(50.0 + (r1m_proxy * 50.0 / 30.0)))

    if not parts:
        return None
    return sum(parts) / len(parts)


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


def compute_tapeline_composite(
    row: dict[str, Any],
    get_fund: Any | None = None,
    get_sm: Any | None = None,
) -> tuple[float | None, dict[str, float | None]]:
    """Compute Tapeline's six-factor composite for one ticker row.

    Returns (composite, sub_scores). `composite` is clamped 0-100, or None
    when fewer than MIN_FACTORS_FOR_COMPOSITE factors are held. `sub_scores`
    is a dict with keys: trend, rs, fundamentals, smart_money, macro,
    momentum. Missing factors are filled with NEUTRAL (50) in the composite
    math but recorded as None in the returned dict so the UI can display "—"
    instead of "50" when data is genuinely absent.

    `get_fund` and `get_sm` are injectable cache lookups for tests. In
    production, we lazy-import the live finnhub caches.
    """
    sym = row.get("symbol", "")

    subs = {
        "trend":        sub_trend(row),
        "rs":           sub_rs(row),
        "fundamentals": sub_fundamentals(sym, get_fund),
        "smart_money":  sub_smart_money(sym, get_sm),
        "macro":        sub_macro(row),
        "momentum":     sub_momentum(row),
    }

    # One implementation, shared with the market path — see
    # composite_from_factors. None when fewer than two factors are held.
    return composite_from_factors(subs), subs
