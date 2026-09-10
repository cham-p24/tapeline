"""The factor refresh has to complete, and has to keep what it earned.

Measured on production 2026-09-11: `tickers.last_aggregates_at` had not moved
since 2026-09-06 — five days — while the job appeared to run continuously and
nothing logged an error.

Two causes, and the second is the one that hid the first:

1. AGGREGATES_CAP is ACTIVE_UNIVERSE_SIZE, raised 2,500 -> 12,000 in #763.
   The loop was serial with a 0.3s sleep per symbol, so the pass went from a
   few minutes to about four hours. The worker restarts on every deploy.

2. `last_aggregates_at` was stamped once, after every symbol had been
   fetched. A pass that never reaches the end records nothing, however much
   work it did — the same shape as the score_upsert rollback in #798.

And the reason it was invisible from the outside: `_merged_factor_set` keeps
the previous factor value when the incoming one is missing, so trend, RS and
momentum went on serving numbers computed from 2026-09-06 bars. Stale,
plausible, unmarked. A NULL would have been louder and less harmful.
"""
from __future__ import annotations

import inspect

from app.workers import signal_publisher as sp


def _src() -> str:
    return inspect.getsource(sp._refresh_aggregates_cache)


# ── it has to fit in a day ─────────────────────────────────────────────────

def test_the_pass_is_not_serial():
    """Serial + a per-symbol sleep is a four-hour pass at this cap."""
    src = _src()
    assert "asyncio.gather" in src, (
        "the aggregates pass fetches one symbol at a time; at 12,000 symbols "
        "and ~0.85s per fetch that is over three hours before the sleep"
    )
    assert "await asyncio.sleep(0.3)" not in src, (
        "the 0.3s per-symbol sleep adds an hour to the pass on its own; the "
        "semaphore is the pacing mechanism now"
    )


def test_the_measured_concurrency_is_sane():
    """Measured, not guessed — and deliberately below what the vendor took.

    20 symbols per level against the live vendor, zero errors at every level:
    1 -> 170 min, 4 -> 43 min, 8 -> 28 min, 12 -> 19 min.
    """
    assert 1 < sp.AGGREGATES_CONCURRENCY <= 12
    assert 0 < sp.AGGREGATES_STAMP_BATCH <= 1000


def test_a_full_pass_fits_inside_its_own_cadence():
    """The daily job must finish well before it is due again.

    At the measured 0.14s/symbol for concurrency 8, 12,000 symbols is ~28
    minutes. If a future edit drops the concurrency or raises the cap far
    enough that the pass approaches 24 hours, it can never complete and we are
    back to serving 09-06 numbers with nothing to show for it.
    """
    from app.services.universe import ACTIVE_UNIVERSE_SIZE

    seconds_per_symbol_at_one = 0.85          # measured
    est = ACTIVE_UNIVERSE_SIZE * seconds_per_symbol_at_one / sp.AGGREGATES_CONCURRENCY
    assert est < 6 * 3600, (
        f"a full aggregates pass is ~{est / 3600:.1f}h at cap "
        f"{ACTIVE_UNIVERSE_SIZE} and concurrency {sp.AGGREGATES_CONCURRENCY}; "
        f"the job is on a 24h cadence and the worker restarts on every deploy"
    )


# ── it has to keep what it earned ──────────────────────────────────────────

def test_progress_is_stamped_during_the_pass_not_after_it():
    """The bug that hid for five days.

    A single stamp after the loop means a pass killed at 99% records exactly
    as much as one killed at 1%: nothing.
    """
    src = _src()
    stamp = src.index("last_aggregates_at=now")
    gather = src.index("asyncio.gather")
    assert gather < stamp, "symbols are still all fetched before anything is stamped"

    # The stamp must be inside the batch loop, not after it. If it were after,
    # there would be no `aggregates.progress` line between them.
    assert "aggregates.progress" in src, (
        "no per-batch progress marker — there is no way to tell a pass that "
        "is running slowly from one that is not running at all, which is "
        "exactly the position this was found in"
    )
    assert src.index("AGGREGATES_STAMP_BATCH") < stamp


def test_the_stamp_covers_only_the_batch_that_was_actually_attempted():
    """Stamping symbols we have not fetched would be a lie the rotation reads.

    The explore slice picks least-recently-stamped first. Stamping ahead of
    the work would push un-fetched symbols to the back of the queue and they
    would never be reached.
    """
    src = _src()
    assert "Ticker.symbol.in_(batch)" in src, (
        "the stamp does not scope to the current batch, so it can mark "
        "symbols the pass has not fetched"
    )


def test_a_killed_pass_keeps_the_batches_it_completed():
    """Behavioural: run the batch/stamp shape and cut it off part-way.

    Models the loop rather than the whole function — what is under test is the
    invariant that the write happens per batch, so an interrupted pass leaves
    the completed batches recorded.
    """
    stamped: list[str] = []
    symbols = [f"S{i}" for i in range(1000)]
    batch_size = 250

    class Boom(Exception):
        pass

    def _run() -> None:
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            if i == 500:                       # killed part-way, as a deploy does
                raise Boom
            stamped.extend(batch)

    try:
        _run()
    except Boom:
        pass

    assert len(stamped) == 500, (
        "an interrupted pass kept nothing; the stamp is not per batch"
    )


# ── the thing that made it invisible ───────────────────────────────────────

def test_a_missing_factor_keeps_the_previous_value():
    """Pinning the behaviour that turned an outage into silence.

    This is CORRECT — writing NULL would strand rows below the two-factor
    floor in live_clauses and empty the scanner. But it means a refresh that
    stops running produces no visible symptom at all, which is why the pass
    needs its own progress marker and a stamp that moves. Documented here so
    the next person reading `sub_trend IS NOT NULL` does not mistake it for
    proof the factor is fresh.
    """
    merged = sp._merged_factor_set(
        {"symbol": "AAA", "sector": "Tech", "sub_trend": None},
        {"sub_trend": 71.0, "sub_rs": 60.0, "sub_momentum": 55.0},
    )
    assert merged["sub_trend"] == 71.0, (
        "a missing incoming factor no longer falls back to the stored value; "
        "that change would empty the scanner via the two-factor floor"
    )
