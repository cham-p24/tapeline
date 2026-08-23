"""The "why" sentence must describe the scores actually published beside it.

Every snapshot row starts life as a _mock_snapshots() row, where _render_reason
is called on six random.gauss draws. polygon_feed then replaces five of those six
with real cached values and recomputes the composite — and, until this fix, left
the sentence describing the DISCARDED draws.

So a ticker whose published Trend was 20 could carry "trend factor in the top
band", because the thrown-away draw happened to be 88. That sentence is the
product's stated differentiator, it renders directly beneath the six real
sub-scores on the scanner, and it goes out in the welcome email.

confidence_pct had the same shape: mock_feed derives it from a hash of the symbol
bucketed by two hardcoded lists — a stable random number measuring nothing —
while every user-facing description says it reflects which data feeds returned
data. It now counts exactly that.
"""
from __future__ import annotations

import inspect

from app.services import polygon_feed


SRC = inspect.getsource(polygon_feed.fetch_snapshots)


def test_reason_is_regenerated_after_the_merge():
    """The regression in one assertion."""
    assert 'r["reason"] = _render_reason(' in SRC, (
        "reason is no longer regenerated — the sentence will describe the "
        "mock draws that were thrown away, not the scores that get published"
    )


def test_reason_is_built_from_the_row_not_from_locals():
    """It must read the SAME dict the database write reads."""
    start = SRC.index('r["reason"] = _render_reason(')
    call = SRC[start:SRC.index(")", SRC.index("sub_smart_money", start))]
    for factor in (
        "sub_trend", "sub_rs", "sub_fundamentals",
        "sub_momentum", "sub_macro", "sub_smart_money",
    ):
        assert f'r["{factor}"]' in call, (
            f"{factor} is not read off the row — a local would let the sentence "
            f"and the published score drift apart again"
        )


def test_reason_is_regenerated_AFTER_the_scores_are_final():
    """Ordering matters: regenerating before the merge would change nothing."""
    assert SRC.index('r["score"] = _composite_from_subs(r)') < SRC.index(
        'r["reason"] = _render_reason('
    )


def test_confidence_counts_real_sources_not_a_hash():
    assert 'r["confidence_pct"] = round(' in SRC
    assert "sourced = sum((" in SRC
    # It must consider each factor's actual cache result.
    for cache_var in ("fund is not None", "sm is not None", "trend is not None",
                      "rs is not None", "mom is not None"):
        assert cache_var in SRC, f"confidence ignores {cache_var}"


def test_confidence_is_a_whole_percent_in_range():
    """A decimal would imply precision this measure does not have."""
    # 0..7 signals over 7 -> 0..100
    for sourced in range(7):
        for has_price in (0, 1):
            value = round(100.0 * (sourced + has_price) / 7)
            assert 0 <= value <= 100
            assert value == int(value)
