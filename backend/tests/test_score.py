"""Tests for the Tapeline 6-factor composite (services/score.py).

These tests pin the contract that /how-it-works advertises:
  - Composite is always 0-100
  - Weights sum to 1.0
  - Cache misses degrade to NEUTRAL (50) per factor, never None in the
    composite math
  - Sub-scores returned to the caller stay None when data is genuinely
    absent (so the UI can show "—" instead of fabricating 50)
"""

import pytest

from app.services.score import (
    WEIGHTS,
    NEUTRAL,
    compute_tapeline_composite,
    sub_trend,
    sub_rs,
    sub_macro,
    sub_momentum,
    sub_fundamentals,
    sub_smart_money,
)


def test_weights_sum_to_one():
    """The 6-factor formula on /how-it-works must sum to 100%."""
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_weights_match_advertised():
    """Touching these is a brand-promise change. Pin them."""
    assert WEIGHTS == {
        "trend":        0.25,
        "rs":           0.20,
        "fundamentals": 0.15,
        "smart_money":  0.15,
        "macro":        0.15,
        "momentum":     0.10,
    }


def test_composite_strong_ticker():
    """All-positive inputs → composite well above 70."""
    row = {
        "symbol": "NVDA",
        "change_pct_3m": 15.0,
        "rs_vs_spy_3m": 10.0,
        "rs_vs_spy_6m": 12.0,
        "rs_vs_spy_1y": 30.0,
        "market_regime": "RISING",
        "momentum_quality": "HIGH",
        "near_52w_high_pct": 95.0,
    }
    composite, subs = compute_tapeline_composite(
        row, get_fund=lambda s: 75.0, get_sm=lambda s: 70.0
    )
    assert composite >= 70
    assert composite <= 100
    assert all(0 <= v <= 100 for v in subs.values() if v is not None)


def test_composite_weak_ticker():
    """All-negative inputs → composite well below 50."""
    row = {
        "symbol": "BAD",
        "change_pct_3m": -15.0,
        "rs_vs_spy_3m": -10.0,
        "rs_vs_spy_6m": -8.0,
        "rs_vs_spy_1y": -5.0,
        "market_regime": "FALLING",
        "momentum_quality": "LOW",
        "near_52w_high_pct": 25.0,
    }
    composite, subs = compute_tapeline_composite(
        row, get_fund=lambda s: 30.0, get_sm=lambda s: 35.0
    )
    assert composite < 50


def test_composite_etf_cache_miss_lands_at_neutral():
    """ETFs lack fundamentals + insider data. Cache misses should default
    each missing factor to NEUTRAL (50) in the composite math, so a flat
    ETF doesn't fall below 50."""
    row = {
        "symbol": "SPY",
        "change_pct_3m": 0.0,
        "rs_vs_spy_3m": 0.0,
        "rs_vs_spy_6m": 0.0,
        "rs_vs_spy_1y": 0.0,
        "market_regime": "SIDEWAYS",
        "momentum_quality": "MEDIUM",
        "near_52w_high_pct": 50.0,
    }
    composite, subs = compute_tapeline_composite(
        row, get_fund=lambda s: None, get_sm=lambda s: None
    )
    # All inputs are exactly neutral, so composite must land at exactly 50
    assert composite == 50.0
    # And the missing factor sub-scores must stay None (UI shows "—")
    assert subs["fundamentals"] is None
    assert subs["smart_money"] is None


def test_composite_is_clamped_0_100():
    """Even with extreme inputs, composite never escapes [0, 100].

    Note: the maximum *realistic* composite is NOT 100 even with all-max
    inputs, because the macro factor caps at 75 (RISING regime is the
    strongest label the sheet writes) and momentum quality VERY HIGH
    maps to 90. So a fully-saturated ticker lands around 95-97 — the
    composite headroom is preserved for genuinely extraordinary states.
    """
    row = {
        "symbol": "EXTREME",
        "change_pct_3m": 500.0,           # absurdly high (gets clamped per-factor)
        "rs_vs_spy_3m": 500.0,
        "rs_vs_spy_6m": 500.0,
        "rs_vs_spy_1y": 500.0,
        "market_regime": "RISING",
        "momentum_quality": "VERY HIGH",
        "near_52w_high_pct": 100.0,
    }
    composite, _ = compute_tapeline_composite(
        row, get_fund=lambda s: 100.0, get_sm=lambda s: 100.0
    )
    assert composite <= 100.0
    assert composite >= 90.0   # all-saturated should land in HIGH CONVICTION band

    row_neg = {**row, "change_pct_3m": -500.0,
               "rs_vs_spy_3m": -500.0, "rs_vs_spy_6m": -500.0,
               "rs_vs_spy_1y": -500.0, "market_regime": "FALLING",
               "momentum_quality": "VERY LOW", "near_52w_high_pct": 0.0}
    composite_neg, _ = compute_tapeline_composite(
        row_neg, get_fund=lambda s: 0.0, get_sm=lambda s: 0.0
    )
    assert composite_neg >= 0.0
    assert composite_neg <= 10.0   # all-floored should land in WEAK band


def test_sub_macro_handles_regime_variants():
    """Sheet writes free-text. We tolerate the common variants."""
    assert sub_macro({"market_regime": "RISING"}) == 75
    assert sub_macro({"market_regime": "rising"}) == 75   # case-insensitive
    assert sub_macro({"market_regime": "STRONG BULL"}) == 75  # substring match (BULL)
    assert sub_macro({"market_regime": "SIDEWAYS"}) == 50
    assert sub_macro({"market_regime": "FALLING"}) == 25
    assert sub_macro({"market_regime": ""}) is None
    assert sub_macro({"market_regime": None}) is None


def test_sub_momentum_handles_label_and_numeric():
    """Momentum Quality column can be a number or a label."""
    # Numeric
    assert sub_momentum({"momentum_quality": 75.0}) == 75.0
    # Label
    high = sub_momentum({"momentum_quality": "HIGH"})
    assert high == 75.0
    # Mixed with 3M return contribution
    blended = sub_momentum({"momentum_quality": "HIGH", "change_pct_3m": 30.0})
    assert blended is not None
    assert 50 < blended < 100


def test_sub_trend_blends_3m_and_52w():
    """Trend factor blends 3M return with proximity-to-52W-high."""
    # Both inputs
    score = sub_trend({"change_pct_3m": 30.0, "near_52w_high_pct": 100.0})
    assert score == 100.0   # both maxed
    # Only 3M
    only_3m = sub_trend({"change_pct_3m": 0.0})
    assert only_3m == 50.0  # neutral midpoint
    # Neither
    assert sub_trend({}) is None


def test_sub_rs_weighted_toward_longer_windows():
    """1Y outperformance should weigh ~2x more than 3M."""
    row_short = {"rs_vs_spy_3m": 50.0}
    row_long = {"rs_vs_spy_1y": 50.0}
    # Both are above 50 (positive RS), but with only one window provided
    # the math is just `50 + rs` clamped.
    assert sub_rs(row_short) == 100.0
    assert sub_rs(row_long) == 100.0
    # With both, they combine and the long-window weighting matters
    mixed = sub_rs({"rs_vs_spy_3m": 0.0, "rs_vs_spy_1y": 30.0})
    # 1Y is weighted 2x of 3M. 3M contributes 50 (weight 1), 1Y contributes
    # 80 (weight 2). Weighted average = (1*50 + 2*80) / 3 = 70
    assert mixed == pytest.approx(70.0, abs=0.1)


def test_sub_fundamentals_uses_cache():
    """Fundamentals score comes from the Finnhub cache via injectable getter."""
    assert sub_fundamentals("AAPL", get_fund=lambda s: 75.0) == 75.0
    assert sub_fundamentals("ETFXYZ", get_fund=lambda s: None) is None


def test_sub_smart_money_uses_cache():
    """Smart money score comes from the Form 4 cache."""
    assert sub_smart_money("AAPL", get_sm=lambda s: 60.0) == 60.0
    assert sub_smart_money("XYZ", get_sm=lambda s: None) is None
