"""change_pct_5d and change_pct_1m must be MEASURED, never generated.

Both were `random.gauss` draws that reached production. polygon_feed builds each
row on the mock base and overrides only some fields, so the draws survived into
the database and were republished every 60 seconds. Confirmed on the live
database: change_pct_5d had mean -0.023 and standard deviation 3.011 across 2,500
rows — the generator's signature, not a market's.

They are now derived from the daily OHLCV bars. These tests pin the arithmetic,
and — more importantly — pin that ABSENCE STAYS ABSENT: a symbol whose bars cannot
support a return must render an em-dash, not a plausible invented number. That
second property is what actually failed before.
"""
from __future__ import annotations

from app.services.polygon_feed import compute_bar_stats


def _bars(closes: list[float], *, day_ms: int = 86_400_000) -> list[dict]:
    """Minimal bar shape: close plus a timestamp, oldest first."""
    return [
        {"c": c, "h": c, "l": c, "v": 1_000_000, "t": (i + 1) * day_ms}
        for i, c in enumerate(closes)
    ]


def test_five_day_return_is_measured_over_five_SESSIONS():
    # 6 closes = 5 sessions of change. 100 -> 110 is +10%.
    stats = compute_bar_stats(_bars([100, 101, 102, 103, 104, 110]))
    assert stats is not None
    assert stats["change_pct_5d"] == 10.0


def test_one_month_return_uses_21_sessions():
    closes = [100.0] * 21 + [125.0]   # 22 closes = 21 sessions
    stats = compute_bar_stats(_bars(closes))
    assert stats["change_pct_1m"] == 25.0


def test_a_negative_move_keeps_its_sign():
    stats = compute_bar_stats(_bars([100, 99, 98, 97, 96, 90]))
    assert stats["change_pct_5d"] == -10.0


def test_too_few_bars_gives_NULL_not_zero_and_not_a_guess():
    """The load-bearing one. This is exactly where the fabricated value used to
    survive: no history, so the mock's draw stayed."""
    stats = compute_bar_stats(_bars([100, 101, 102]))  # only 2 sessions
    assert stats is None or stats["change_pct_5d"] is None
    assert stats is None or stats["change_pct_1m"] is None


def test_a_zero_or_negative_base_is_refused():
    """Percentage change off a non-positive base is meaningless, not infinite."""
    stats = compute_bar_stats(_bars([0, 1, 2, 3, 4, 5]))
    assert stats is None or stats["change_pct_5d"] is None


def test_the_result_is_deterministic():
    """A generator would produce a different answer each call."""
    bars = _bars([100, 101, 102, 103, 104, 110])
    first = compute_bar_stats(bars)
    for _ in range(25):
        assert compute_bar_stats(bars) == first


def test_the_snapshot_writer_nulls_unsupported_returns():
    """polygon_feed must not leave the mock's value in place when the bars
    cannot support a real one — the half that made this bug invisible."""
    import inspect

    from app.services import polygon_feed

    src = inspect.getsource(polygon_feed.fetch_snapshots)
    assert 'r["change_pct_5d"] = None' in src
    assert 'r["change_pct_1m"] = None' in src


def test_the_columns_survive_a_restart():
    """Bar-derived now, so they need the same COALESCE guard as the others."""
    import inspect

    from app.workers import signal_publisher

    src = inspect.getsource(signal_publisher)
    start = src.index("cache_derived = (")
    block = src[start:src.index(")", start)]
    assert '"change_pct_5d"' in block
    assert '"change_pct_1m"' in block
