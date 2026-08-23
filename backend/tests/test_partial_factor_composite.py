"""Score the factors we hold; say nothing about the ones we don't.

Follow-up to the cache-miss fix. That change made a missing factor NULL instead
of a `random.gauss` draw, and made the composite refuse to average an
incomplete set. Measuring production afterwards showed why refusing is the
wrong half of the answer:

    factors-per-scored-row: {0: 93, 1: 316, 2: 30, 3: 1, 4: 4780, 5: 7, 6: 1318}

**4,780 rows hold exactly four factors** — the Finnhub fundamentals and insider
backfills are rate-capped and will never cover the whole universe. Refusing to
score them freezes those rows at their last value forever, and because the tick
COALESCEs the score, the frozen value is the one computed back when the missing
factors were random draws. Refusing preserves the fabrication rather than
washing it out.

So the composite re-normalises over the factors present, above a floor of two —
the same floor `ticker_freshness` already applies to decide what a user may
see, so a row cannot be scored here and rejected as unscorable there.
`confidence_pct` publishes how many inputs were sourced, which is what makes a
four-factor composite honest rather than merely convenient.
"""
from __future__ import annotations

import pytest

from app.services.mock_feed import _render_reason
from app.services.polygon_feed import (
    FACTOR_WEIGHTS,
    MIN_FACTORS_FOR_COMPOSITE,
    _composite_from_subs,
)

_ALL = {k: 50.0 for k in FACTOR_WEIGHTS}


def _row(**over: float | None) -> dict:
    return {**_ALL, **over}


def test_all_six_present_is_the_plain_weighted_sum():
    """Re-normalising must not change the number when nothing is missing."""
    r = _row(
        sub_trend=80.0, sub_rs=70.0, sub_fundamentals=60.0,
        sub_smart_money=40.0, sub_macro=50.0, sub_momentum=30.0,
    )
    expected = round(
        80 * 0.25 + 70 * 0.20 + 60 * 0.15 + 40 * 0.15 + 50 * 0.15 + 30 * 0.10, 1
    )
    assert _composite_from_subs(r) == expected
    assert sum(FACTOR_WEIGHTS.values()) == pytest.approx(1.0)


def test_a_missing_factor_is_not_treated_as_zero():
    """The whole point. A gap must not drag the composite toward the floor."""
    held = {"sub_trend": 80.0, "sub_rs": 80.0, "sub_macro": 80.0, "sub_momentum": 80.0}
    partial = _composite_from_subs(_row(sub_fundamentals=None, sub_smart_money=None, **held))

    assert partial == 80.0, (
        f"four factors all reading 80 produced {partial}. Anything below 80 "
        f"means the two we hold nothing for were averaged in as low values."
    )

    # Explicitly: scoring the gaps as 0 would have given 56.0.
    as_zero = _composite_from_subs(_row(sub_fundamentals=0.0, sub_smart_money=0.0, **held))
    assert as_zero == 56.0
    assert partial != as_zero


def test_the_gap_does_not_shift_the_composite_at_all():
    """Re-normalisation, not partial-sum: the divisor must shrink with the set."""
    for missing in FACTOR_WEIGHTS:
        r = _row(**{k: (None if k == missing else 62.0) for k in FACTOR_WEIGHTS})
        assert _composite_from_subs(r) == 62.0, (
            f"with {missing} absent and every other factor at 62, the average "
            f"of what we hold is still 62"
        )


def test_below_the_floor_there_is_no_composite():
    """One factor is not a six-factor composite by any stretch."""
    none_of_them = {k: None for k in FACTOR_WEIGHTS}

    only_one = _row(**{**none_of_them, "sub_trend": 90.0})
    assert _composite_from_subs(only_one) is None
    assert _composite_from_subs(_row(**none_of_them)) is None

    two = _row(**{**none_of_them, "sub_trend": 90.0, "sub_rs": 90.0})
    assert _composite_from_subs(two) == 90.0


def test_the_floor_matches_the_one_users_are_filtered_by():
    """A row must not be scorable here and unscorable to ticker_freshness."""
    from app.services import ticker_freshness

    assert MIN_FACTORS_FOR_COMPOSITE == ticker_freshness.MIN_FACTORS, (
        "the composite floor and the visibility floor have diverged — rows "
        "would get a score that every ranked surface then rejects"
    )


def test_the_composite_stays_clamped():
    assert _composite_from_subs(_row(**{k: 100.0 for k in FACTOR_WEIGHTS})) == 100.0
    assert _composite_from_subs(_row(**{k: 0.0 for k in FACTOR_WEIGHTS})) == 0.0


# --------------------------------------------------------------------------
# The sentence printed beside the score
# --------------------------------------------------------------------------

def test_reason_says_nothing_about_a_factor_it_has_no_reading_for():
    """A missing factor must contribute no clause, at any extreme."""
    # Trend is the only factor we hold, and it is emphatic.
    sentence = _render_reason("TEST", "Technology", 95.0, None, None, None, None, None)
    assert sentence, "a held factor should still produce a sentence"

    # With everything absent there is nothing to say about the factors at all.
    empty = _render_reason("TEST", "Technology", None, None, None, None, None, None)
    from app.services.mock_feed import _NEUTRAL

    assert empty in _NEUTRAL, (
        f"no factors held, yet the sentence claimed something: {empty!r}"
    )


def test_a_missing_factor_reads_the_same_as_a_midpoint_one():
    """The substitution the implementation relies on, asserted directly.

    If a future re-banding makes 50 fall inside a band, absence would start
    generating a clause — a claim about a factor we do not hold. This is the
    test that catches it.
    """
    import random

    for i, name in enumerate(("trend", "rs", "fund", "mom", "macro", "smart")):
        args: list[float | None] = [50.0] * 6
        args[i] = None
        random.seed(1)
        with_none = _render_reason("TEST", "Technology", *args)
        args[i] = 50.0
        random.seed(1)
        with_mid = _render_reason("TEST", "Technology", *args)
        assert with_none == with_mid, (
            f"a missing {name} produced a different sentence than a midpoint "
            f"one, so 50 now falls inside a band and absence has become a claim"
        )
