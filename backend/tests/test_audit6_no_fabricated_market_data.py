"""Production must never publish fabricated market data.

fetch_snapshots builds EVERY row from _mock_snapshots() and then overwrites
selected fields with the vendor snapshot. Two fields were never in that
overwrite list, so they shipped mock_feed's random numbers as real market data:

    mock_feed.py:209  "change_pct_5d": round(random.gauss(0, 3.0), 2)
    mock_feed.py:210  "change_pct_1m": round(random.gauss(2, 6.0), 2)

Re-randomised on every 60s tick. And any symbol the vendor snapshot omitted kept
mock_feed's random-walk price/volume too — a fabricated quote presented as real.

For a financial product this is the most serious class of defect there is, so
these tests assert the honest contract: real values derived from real daily
bars, or NULL (an em-dash in the UI). Never a plausible-looking invention.
"""
from __future__ import annotations

from app.services.polygon_feed import compute_bar_stats


def _bars(closes, *, day_ms=86_400_000):
    """Daily bars in the /v2/aggs shape, oldest first."""
    return [
        {"c": c, "h": c * 1.01, "l": c * 0.99, "v": 1_000_000, "t": i * day_ms}
        for i, c in enumerate(closes)
    ]


def test_five_day_change_is_computed_from_real_closes():
    # 6 closes: last is 110, five sessions back is 100 -> +10.00%
    stats = compute_bar_stats(_bars([100, 101, 102, 103, 104, 110]))
    assert stats is not None
    assert stats["change_pct_5d"] == 10.0


def test_one_month_change_is_computed_from_real_closes():
    # 22 closes: closes[-22] == 100, last == 120 -> +20.00%
    closes = [100] + [105] * 20 + [120]
    assert len(closes) == 22
    stats = compute_bar_stats(_bars(closes))
    assert stats is not None
    assert stats["change_pct_1m"] == 20.0


def test_insufficient_history_yields_null_not_a_number():
    """THE REGRESSION. Too little history must produce None — never a
    fabricated stand-in."""
    stats = compute_bar_stats(_bars([100, 101, 102]))  # only 3 sessions
    if stats is not None:
        assert stats["change_pct_5d"] is None
        assert stats["change_pct_1m"] is None


def test_five_day_available_before_one_month():
    """A name with 10 sessions has a real 5d change but no real 1m change."""
    stats = compute_bar_stats(_bars([100] * 5 + [110] * 5))
    assert stats is not None
    assert stats["change_pct_5d"] is not None
    assert stats["change_pct_1m"] is None


def test_zero_baseline_close_does_not_divide_by_zero():
    stats = compute_bar_stats(_bars([0, 1, 2, 3, 4, 5]))
    if stats is not None:
        assert stats["change_pct_5d"] is None


def test_mock_feed_still_fabricates_so_the_overwrite_is_load_bearing():
    """Guards against a vacuous pass: if mock_feed ever stopped producing random
    multi-session changes, these tests would prove nothing about the real fix.
    mock_feed is the dev fallback and is ALLOWED to fabricate — the contract is
    that fetch_snapshots must never let those values reach the DB."""
    import inspect

    from app.services import mock_feed

    src = inspect.getsource(mock_feed)
    assert "change_pct_5d" in src and "random.gauss" in src, (
        "mock_feed no longer fabricates these — re-check that the "
        "fetch_snapshots overwrite is still needed"
    )


def test_fetch_snapshots_clears_mock_values_unconditionally():
    """The overwrite must happen even when the aggregates cache is cold, or a
    stale mock number survives into the DB after every worker restart."""
    import inspect

    from app.services import polygon_feed

    src = inspect.getsource(polygon_feed.fetch_snapshots)
    # Cleared BEFORE the cache lookup, so a None cache can't leave mock in place.
    assert 'r["change_pct_5d"] = None' in src
    assert 'r["change_pct_1m"] = None' in src
    # And a symbol absent from a successful vendor response must not keep a
    # mock price/volume.
    assert 'r["price"] = None' in src
    assert 'r["volume"] = None' in src
