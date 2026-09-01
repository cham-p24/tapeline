"""The liquidity floor must be measured on a STABLE basis, on both surfaces.

Two floors exist and they have to agree:

  routers/scanner.SCANNER_MIN_DOLLAR_VOLUME        — the ranked product view
  signal_publisher._MIN_DOLLAR_VOLUME_FOR_SCORECARD — the permanent public record

Both were raised to $1M on 2026-08-30 and both moved off `Ticker.volume`.

**Why the basis mattered more than the number.** `volume` is the SESSION's
running total, not a full day. Measuring liquidity against it means the same
ticker fails the floor at 10am and passes it at 4pm. Worse, the two surfaces
ran at different times — the scorecard freezes after the US close, the scanner
serves all day — so they were applying the same threshold to a full-day figure
and a partial one respectively, and silently disagreed about which names were
tradeable. `avg_volume_30d` comes from daily bars via `compute_bar_stats` and
does not move during the session.

The observed symptom that prompted this: a direct read of `tickers` mid-session
showed CHCI at 737 shares (≈$14.6k), while the live API minutes later showed
45,299 shares (≈$0.90M) — the same column, the same day, a running total.

A null read is still KEPT on both surfaces. That carve-out is load-bearing
while feed coverage fills in: on 2026-08-30, 3,662 of 6,753 scored tickers had
no volume read at all (see docs/FEED_COVERAGE_AUDIT_2026-08-30.md), and failing
them closed would have emptied most of the scanner.
"""
from __future__ import annotations

import inspect

from app.routers.scanner import SCANNER_MIN_DOLLAR_VOLUME
from app.workers.signal_publisher import _MIN_DOLLAR_VOLUME_FOR_SCORECARD


def test_both_floors_agree() -> None:
    """If a name is too thin for the top of the ranked view, it is too thin to
    enter a permanent public track record."""
    assert SCANNER_MIN_DOLLAR_VOLUME == _MIN_DOLLAR_VOLUME_FOR_SCORECARD, (
        "the scanner and scorecard floors have drifted apart; the scorecard "
        "must never be laxer than the surface it is a record of"
    )


def test_the_floor_is_meaningful_for_a_retail_swing_trader() -> None:
    """$50k (the old scanner value) is below anything a person can trade out of.

    Pinned as a range, not an equality, so tuning the number is a one-line
    change but dropping it back to a cosmetic value fails loudly.
    """
    assert SCANNER_MIN_DOLLAR_VOLUME >= 500_000, (
        f"floor is ${SCANNER_MIN_DOLLAR_VOLUME:,.0f} — below the point where a "
        "retail swing trader can reliably get in and out"
    )


def test_scanner_floor_uses_the_thirty_day_average_not_intraday() -> None:
    src = inspect.getsource(__import__("app.routers.scanner", fromlist=["x"]).list_scanner)
    assert "avg_volume_30d" in src, (
        "the scanner floor must measure against avg_volume_30d; Ticker.volume is "
        "the session's running total and makes the floor time-of-day dependent"
    )


def test_scorecard_floor_uses_the_thirty_day_average_not_intraday() -> None:
    from app.workers import signal_publisher

    src = inspect.getsource(signal_publisher._ensure_daily_scorecard)
    assert "avg_volume_30d" in src, (
        "the scorecard freeze must measure against avg_volume_30d — it runs "
        "after the close while the scanner runs all day, so an intraday basis "
        "made the two surfaces disagree about the same ticker"
    )


def test_a_null_read_is_still_kept_on_both_surfaces() -> None:
    """The carve-out that stops the floor emptying the scanner.

    While feed coverage is incomplete, a missing liquidity read means "unknown",
    not "illiquid". Failing unknowns closed would remove more than half the
    scored universe.
    """
    scanner_src = inspect.getsource(
        __import__("app.routers.scanner", fromlist=["x"]).list_scanner
    )
    # The scanner keeps nulls via an OR against is_(None).
    assert "is_(None)" in scanner_src

    from app.workers import signal_publisher

    card_src = inspect.getsource(signal_publisher._ensure_daily_scorecard)
    # The scorecard keeps nulls by only skipping when the read is not None.
    assert "_liquidity is not None" in card_src


def test_floor_arithmetic() -> None:
    """The comparison itself: price * liquidity, against the floor.

    Worked examples from the live data on the day the floor was raised.
    """
    floor = SCANNER_MIN_DOLLAR_VOLUME
    # CIX: $33.00 x 13,815 = $455,895 -> excluded
    assert 33.00 * 13_815 < floor
    # BBP: $107.36 x 5,129 = $550,649 -> excluded
    assert 107.36 * 5_129 < floor
    # BBH: $239.00 x 28,687 = $6,856,193 -> kept
    assert 239.00 * 28_687 >= floor
    # OKTA-scale: comfortably kept
    assert 100.0 * 7_000_000 >= floor
