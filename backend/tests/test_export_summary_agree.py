"""The downloadable artefact and the web summary must agree by construction.

The public scorecard's whole claim is that anyone can check it. That claim
fails silently if the page and the file disagree, and they did:

  routers/scorecard._compute_summary excluded any row whose |1-day move|
  exceeded 50% and reported only a COUNT of exclusions. The CSV/JSON export
  streamed every row with no flag. So a reader who downloaded the file and
  recomputed the hit rate got a different number from the one on the page,
  with nothing in the file to explain the gap.

The row that forced it: ADAC on 2026-05-13 shows +2,832.23%. The next largest
move in the entire 748-row back-checked record is +22.45% — 126x smaller. It is
an unadjusted reverse split, not a return.

Fix: an `excluded_from_summary` column, and ONE shared threshold constant.
The row stays in the file — it was published, and removing it would break the
append-only guarantee the artefact makes in its own header.
"""
from __future__ import annotations

from datetime import date

from app.routers.scorecard import _is_outlier
from app.services.scorecard_export import (
    COLUMN_DEFINITIONS,
    COLUMNS,
    OUTLIER_PCT_THRESHOLD,
    serialise_entry,
)


class _Entry:
    """Minimal stand-in with the fields both sides read."""

    def __init__(self, pct: float | None) -> None:
        self.as_of = date(2026, 5, 13)
        self.rank = 1
        self.symbol = "ADAC"
        self.score_at_flag = 88.0
        self.price_at_flag = 1.0
        self.price_next_day = 29.32
        self.change_pct_1d_after = pct
        self.spy_change_pct_1d = 0.315
        self.alpha_vs_spy = None if pct is None else pct - 0.315


def test_the_two_sides_use_one_threshold() -> None:
    """Not two constants that happen to match — the same object.

    They were separate, which is how they were free to drift.
    """
    import app.routers.scorecard as page

    assert page._OUTLIER_PCT_THRESHOLD is OUTLIER_PCT_THRESHOLD


def test_the_adac_row_is_flagged_in_the_export() -> None:
    """The actual production row that exposed this."""
    row = serialise_entry(_Entry(2832.23))
    assert row["excluded_from_summary"] is True
    assert _is_outlier(_Entry(2832.23)) is True, "page and file must agree"


def test_a_normal_row_is_not_flagged() -> None:
    """The next-largest real move in the record must survive untouched."""
    row = serialise_entry(_Entry(22.45))
    assert row["excluded_from_summary"] is False
    assert _is_outlier(_Entry(22.45)) is False


def test_agreement_holds_across_the_boundary() -> None:
    """Every value either side of the threshold, both directions."""
    for pct in (-2832.23, -50.01, -50.0, -22.45, 0.0, 22.45, 50.0, 50.01, 2832.23):
        entry = _Entry(pct)
        assert serialise_entry(entry)["excluded_from_summary"] == _is_outlier(entry), (
            f"page and file disagree at {pct}% — a reader recomputing from the "
            "download would not reproduce the published summary"
        )


def test_a_not_yet_backchecked_row_is_not_flagged() -> None:
    """None means 'not measured yet', not 'excluded'."""
    row = serialise_entry(_Entry(None))
    assert row["excluded_from_summary"] is False
    assert _is_outlier(_Entry(None)) is False


def test_the_column_is_published_and_documented() -> None:
    """A flag nobody can find explains nothing."""
    assert "excluded_from_summary" in COLUMNS
    assert "excluded_from_summary" in COLUMN_DEFINITIONS
    text = COLUMN_DEFINITIONS["excluded_from_summary"].lower()
    # It must say the row is still present — otherwise it reads as a deletion,
    # which would contradict the append-only guarantee.
    assert "still" in text


def test_the_new_column_was_appended_not_inserted() -> None:
    """Column order is a published contract; consumers index by position."""
    assert COLUMNS[-1] == "excluded_from_summary"
    assert COLUMNS[:9] == [
        "date", "rank", "symbol", "score_at_flag", "price_at_flag",
        "price_next_day", "change_pct_1d_after", "spy_change_pct_1d",
        "alpha_vs_spy",
    ]
