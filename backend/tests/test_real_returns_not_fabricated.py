"""change_pct_5d and change_pct_1m must be MEASURED, never generated.

Both were `random.gauss` draws that reached production. `polygon_feed` builds
each row on the mock base and overrides only some fields, so the draws survived
into the database and were republished every 60 seconds. It was confirmed on
the live database at the time: change_pct_5d had mean -0.023 and standard
deviation 3.011 across 2,500 rows — the generator's signature, not a market's.

For a financial product that is the most serious class of bug there is: a real
security, on a public page, with an invented number next to it.

They are now derived from the daily OHLCV bars, and `polygon_feed` says so in a
comment at the computation. **The forward fix shipped; this guard did not** —
it sat unmerged on `fix/real-returns-not-random` (2026-08-23) alongside a
migration whose revision id has since been taken by `0053_score_snapshots`, so
the branch can no longer merge as-is. Ported here without the migration.

These tests pin the arithmetic and — the part that actually failed before — pin
that ABSENCE STAYS ABSENT: a symbol whose bars cannot support a return must
yield None and render an em-dash, never a plausible invented number.

Deliberately NOT ported from that branch: two tests that asserted strings were
present in `inspect.getsource(...)`. This repo has already had a source-grep
test vouch for a bug it never exercised (the `COALESCE` assertion behind a
four-hour worker outage), and CLAUDE.md's house rule is that a test is only
real if you have watched it fail. A grep for `r["change_pct_5d"] = None` passes
against a line that is commented out.
"""
from __future__ import annotations

from app.services.polygon_feed import compute_bar_stats


def _bars(closes: list[float], *, day_ms: int = 86_400_000) -> list[dict]:
    """Minimal bar shape: close plus a timestamp, oldest first."""
    return [
        {"c": c, "h": c, "l": c, "v": 1_000_000, "t": (i + 1) * day_ms}
        for i, c in enumerate(closes)
    ]


def test_five_day_return_is_measured_over_five_sessions() -> None:
    # 6 closes = 5 sessions of change. 100 -> 110 is +10%.
    stats = compute_bar_stats(_bars([100, 101, 102, 103, 104, 110]))
    assert stats is not None
    assert stats["change_pct_5d"] == 10.0


def test_one_month_return_uses_21_sessions() -> None:
    closes = [100.0] * 21 + [125.0]   # 22 closes = 21 sessions
    stats = compute_bar_stats(_bars(closes))
    assert stats is not None
    assert stats["change_pct_1m"] == 25.0


def test_a_negative_move_keeps_its_sign() -> None:
    stats = compute_bar_stats(_bars([100, 99, 98, 97, 96, 90]))
    assert stats is not None
    assert stats["change_pct_5d"] == -10.0


def test_too_few_bars_gives_null_not_zero_and_not_a_guess() -> None:
    """The load-bearing one.

    This is exactly where the fabricated value used to survive: no history, so
    the mock's random draw stayed in the row and was published as fact. None is
    the honest answer and renders as an em-dash.
    """
    stats = compute_bar_stats(_bars([100, 101, 102]))  # only 2 sessions
    assert stats is None or stats["change_pct_5d"] is None
    assert stats is None or stats["change_pct_1m"] is None


def test_a_zero_or_negative_base_is_refused() -> None:
    """Percentage change off a non-positive base is meaningless, not infinite."""
    stats = compute_bar_stats(_bars([0, 1, 2, 3, 4, 5]))
    assert stats is None or stats["change_pct_5d"] is None


def test_the_result_is_deterministic() -> None:
    """A generator would produce a different answer each call.

    This is the single assertion that would have caught the original bug at any
    point in the 60s tick loop, without needing to know the right number.
    """
    bars = _bars([100, 101, 102, 103, 104, 110])
    first = compute_bar_stats(bars)
    for _ in range(25):
        assert compute_bar_stats(bars) == first
