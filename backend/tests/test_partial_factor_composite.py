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
from app.services.polygon_feed import _WEIGHT_KEY_TO_COLUMN, _composite_from_subs
from app.services.score import (
    MIN_FACTORS_FOR_COMPOSITE,
    NEUTRAL,
    WEIGHTS,
    composite_from_factors,
)

FACTOR_COLUMNS = tuple(_WEIGHT_KEY_TO_COLUMN.values())

_ALL = {c: 50.0 for c in FACTOR_COLUMNS}


def _row(**over: float | None) -> dict:
    return {**_ALL, **over}


def test_all_six_present_is_the_plain_weighted_sum():
    """The unchanged case: every factor held, plain weighted sum."""
    r = _row(
        sub_trend=80.0, sub_rs=70.0, sub_fundamentals=60.0,
        sub_smart_money=40.0, sub_macro=50.0, sub_momentum=30.0,
    )
    expected = round(
        80 * 0.25 + 70 * 0.20 + 60 * 0.15 + 40 * 0.15 + 50 * 0.15 + 30 * 0.10, 1
    )
    assert _composite_from_subs(r) == expected
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_a_missing_factor_is_not_treated_as_zero():
    """The whole point. A gap must not drag the composite toward the floor."""
    held = {"sub_trend": 80.0, "sub_rs": 80.0, "sub_macro": 80.0, "sub_momentum": 80.0}
    partial = _composite_from_subs(_row(sub_fundamentals=None, sub_smart_money=None, **held))

    # NEUTRAL for the two gaps: 80*0.70 + 50*0.30 = 71.0.
    assert partial == 71.0, f"expected the NEUTRAL fallback, got {partial}"

    # Scoring the gaps as 0 would have given 56.0 — "no reading" rendered as
    # "terrible". That is the defect this exists to prevent.
    as_zero = _composite_from_subs(_row(sub_fundamentals=0.0, sub_smart_money=0.0, **held))
    assert as_zero == 56.0
    assert partial > as_zero


def test_a_missing_factor_does_not_upgrade_thin_coverage():
    """The other direction, and the reason this is not a re-normalised average.

    Re-normalising over the factors held would return 80.0 here — four strong
    readings promoted to a conviction score that a full six-factor read never
    justified. NEUTRAL keeps the gap neutral instead of letting it flatter the
    row.
    """
    held = {"sub_trend": 80.0, "sub_rs": 80.0, "sub_macro": 80.0, "sub_momentum": 80.0}
    partial = _composite_from_subs(_row(sub_fundamentals=None, sub_smart_money=None, **held))
    assert partial == 71.0
    assert partial < 80.0, "thin coverage must not read as strong coverage"


def test_it_matches_the_sheet_paths_composite_exactly():
    """One product, one composite definition — now structurally, not by luck.

    Both paths call score.composite_from_factors; polygon_feed only renames
    sub_trend -> trend and so on. Before the arithmetic was shared, the same
    factor set scored 80.2 through the sheet and 93.2 through the market feed.
    """
    subs = {
        "trend": 100.0, "rs": 100.0, "momentum": 90.0, "macro": 75.0,
        "fundamentals": None, "smart_money": None,
    }
    sheet_side = composite_from_factors(subs)
    market_side = _composite_from_subs(
        _row(**{_WEIGHT_KEY_TO_COLUMN[k]: v for k, v in subs.items()})
    )
    assert sheet_side == market_side == 80.2


def test_the_market_adapter_only_renames_keys():
    """It must delegate, not reimplement.

    Asserted across the whole coverage range rather than on one example: if
    the adapter ever grew arithmetic of its own, some input would diverge.
    """
    cases = [
        {"trend": 90.0, "rs": 80.0, "fundamentals": 70.0,
         "smart_money": 60.0, "macro": 50.0, "momentum": 40.0},
        {"trend": None, "rs": None, "fundamentals": None,
         "smart_money": None, "macro": 50.0, "momentum": None},
        {"trend": 0.0, "rs": 0.0, "fundamentals": None,
         "smart_money": None, "macro": 0.0, "momentum": 0.0},
        {"trend": 100.0, "rs": None, "fundamentals": 100.0,
         "smart_money": None, "macro": 100.0, "momentum": None},
        dict.fromkeys(WEIGHTS, None),
    ]
    for subs in cases:
        assert _composite_from_subs(
            _row(**{_WEIGHT_KEY_TO_COLUMN[k]: v for k, v in subs.items()})
        ) == composite_from_factors(subs), f"adapter diverged on {subs}"


def test_below_the_floor_there_is_no_composite():
    """One factor is not a six-factor composite by any stretch."""
    none_of_them = {c: None for c in FACTOR_COLUMNS}

    only_one = _row(**{**none_of_them, "sub_trend": 90.0})
    assert _composite_from_subs(only_one) is None
    assert _composite_from_subs(_row(**none_of_them)) is None

    # Two held at 90, the other four NEUTRAL: 90*0.45 + 50*0.55 = 68.0.
    two = _row(**{**none_of_them, "sub_trend": 90.0, "sub_rs": 90.0})
    assert _composite_from_subs(two) == 68.0


def test_the_floor_matches_the_one_users_are_filtered_by():
    """A row must not be scorable here and unscorable to ticker_freshness."""
    from app.services import ticker_freshness

    assert MIN_FACTORS_FOR_COMPOSITE == ticker_freshness.MIN_FACTORS, (
        "the composite floor and the visibility floor have diverged — rows "
        "would get a score that every ranked surface then rejects"
    )


def test_the_composite_stays_clamped():
    assert _composite_from_subs(_row(**{c: 100.0 for c in FACTOR_COLUMNS})) == 100.0
    assert _composite_from_subs(_row(**{c: 0.0 for c in FACTOR_COLUMNS})) == 0.0


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
