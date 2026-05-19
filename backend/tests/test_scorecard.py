"""Scorecard aggregation tests — outlier filter + median + mean co-existence.

The /scorecard summary feeds the most visible page on the marketing site.
Vendor data occasionally ingests unadjusted-for-split closes (we've seen
+21,013% 1-day moves enter the back-check). Those skew the headline mean
and produce stats that read as either fraudulent or obviously broken.

These tests pin the contract that aggregation:
  1. Excludes |1d| > 50% rows from the mean / median / hit-rate
  2. Still counts them in `entries_scored` (they're real records)
  3. Surfaces the exclusion count via `entries_excluded_outliers`
  4. Returns BOTH mean and median so the page can show median primary +
     mean as a transparency footnote.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.routers.scorecard import _is_outlier, _summary_stats


def _entry(pct: float, alpha: float | None = None) -> SimpleNamespace:
    """Build a minimal DailyScorecardEntry stand-in for aggregation tests.

    _summary_stats only reads change_pct_1d_after + alpha_vs_spy off the
    rows, so a SimpleNamespace with those two attributes is sufficient —
    we don't need to spin up an in-memory DB just to test the math.
    """
    return SimpleNamespace(
        change_pct_1d_after=pct,
        alpha_vs_spy=alpha if alpha is not None else pct,  # fallback for tests
    )


def test_is_outlier_threshold():
    """Per the constant, |1d| > 50% trips the filter; <= 50% is kept."""
    assert _is_outlier(_entry(50.01)) is True
    assert _is_outlier(_entry(-50.01)) is True
    assert _is_outlier(_entry(50.0)) is False  # boundary keeps
    assert _is_outlier(_entry(-49.99)) is False
    assert _is_outlier(_entry(0.0)) is False
    # None-pct rows aren't outliers — they're "not yet back-checked" and
    # never enter the summary stats anyway.
    assert _is_outlier(SimpleNamespace(change_pct_1d_after=None, alpha_vs_spy=None)) is False


def test_summary_stats_filters_extreme_outliers():
    """ALZN-style data error (21,013%) must be excluded from the mean
    AND the median, but still counted in entries_scored + disclosed via
    entries_excluded_outliers."""
    scored = [
        _entry(1.0),
        _entry(2.0),
        _entry(3.0),
        _entry(-1.0),
        _entry(21013.46),   # the ALZN data error
    ]
    stats = _summary_stats(scored)
    assert stats["entries_scored"] == 5
    assert stats["entries_excluded_outliers"] == 1
    # Mean of [1, 2, 3, -1] = 1.25 — NOT (1+2+3-1+21013)/5 = 4203.69
    assert stats["avg_1d_return"] == 1.25
    # Median of [1, 2, 3, -1] sorted = [-1, 1, 2, 3] → (1+2)/2 = 1.5
    assert stats["median_1d_return"] == 1.5


def test_summary_stats_returns_none_when_all_outliers():
    """Edge case: if every row is suspect (5 entries all >50%), the
    summary returns None for averages — better to show 'pending' on the
    UI than to compute aggregates from zero clean rows."""
    scored = [
        _entry(100.0),
        _entry(200.0),
        _entry(300.0),
    ]
    stats = _summary_stats(scored)
    assert stats["entries_scored"] == 3
    assert stats["entries_excluded_outliers"] == 3
    assert stats["avg_1d_return"] is None
    assert stats["median_1d_return"] is None
    assert stats["avg_alpha_vs_spy"] is None
    assert stats["median_alpha_vs_spy"] is None
    assert stats["hit_rate_beat_spy"] is None


def test_summary_stats_hit_rate_uses_clean_subset():
    """Hit-rate-beat-SPY is computed from the clean subset only, otherwise
    a single huge outlier would push the rate to 100% (since it counts
    as 'beat SPY' regardless of whether it's real data)."""
    scored = [
        _entry(1.0, alpha=-2.0),   # missed
        _entry(2.0, alpha=-1.0),   # missed
        _entry(3.0, alpha=4.0),    # beat
        _entry(99999.0, alpha=99999.0),  # outlier — excluded
    ]
    stats = _summary_stats(scored)
    assert stats["entries_excluded_outliers"] == 1
    # Hit rate is 1 of 3 = 33.33% (NOT 2 of 4 = 50%)
    assert abs(stats["hit_rate_beat_spy"] - (1 / 3) * 100) < 1e-9


def test_summary_stats_empty_input():
    """No scored entries → all stats None. Same shape as 'all-outliers'."""
    stats = _summary_stats([])
    assert stats["entries_scored"] == 0
    assert stats["entries_excluded_outliers"] == 0
    assert stats["avg_1d_return"] is None
    assert stats["median_1d_return"] is None
    assert stats["hit_rate_beat_spy"] is None
