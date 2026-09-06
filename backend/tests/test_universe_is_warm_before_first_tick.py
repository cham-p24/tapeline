"""The active universe must be loaded before the first tick, not during it.

`fetch_snapshots()` is the first thing tick() does, and it reads
`active_universe()` — a process-local cache. On a cold process that cache is
empty and falls back to `mock_feed.TICKER_UNIVERSE`: 112 hardcoded symbols. The
refresh that fills it properly sits ~560 lines further down the SAME tick.

That ordering is fine only if the tick reaches the bottom. On 2026-09-07,
minutes after a deploy, it did not. The first cold tick does the calendar
refresh, a 1.4MB sheet fetch and a 3,352-row earnings pull, and hit:

    ERROR tick.timeout elapsed=60.0s limit=60s consecutive=1 — killing this
    cycle and moving on

killed before the refresh. The next tick started cold and did the same. The
`tickers` write log told the story plainly:

    15:24   1,625 rows
    15:26   1,007 rows
    15:28     112 rows     <- the mock fallback, and stuck there

Production was publishing snapshots for 112 tickers out of 7,417, with no error
beyond the timeout line, and could not recover on its own. There is no
self-healing path: every tick starts from the same cold cache and dies at the
same place.

So the warm-up belongs on the boot path, next to `seed_universe()` and
`warm_factor_caches_from_db()`, which are there for the same reason and say so.
"""
from __future__ import annotations

import asyncio

import pytest

from app.workers import signal_publisher as sp


class _StopLoop(BaseException):
    """Escapes main()'s `except Exception` handlers to end the infinite loop.

    Deliberately BaseException: an ordinary exception is swallowed by the
    `except Exception: logger.exception("tick.failure")` arm and the loop
    continues forever.
    """


@pytest.fixture
def harness(monkeypatch):
    """Run main() for exactly one cycle, recording the order of boot steps."""
    calls: list[str] = []

    async def _noop_seed():
        calls.append("seed_universe")

    async def _noop_warm():
        calls.append("warm_factor_caches")

    async def _refresh():
        calls.append("refresh_universe")
        return 7_667

    async def _tick():
        calls.append("tick")

    async def _sleep(_seconds):
        raise _StopLoop

    monkeypatch.setattr(sp, "_init_sentry", lambda: None, raising=True)
    monkeypatch.setattr(sp, "seed_universe", _noop_seed, raising=True)
    monkeypatch.setattr(sp, "warm_factor_caches_from_db", _noop_warm, raising=True)
    monkeypatch.setattr(sp, "refresh_active_universe", _refresh, raising=True)
    monkeypatch.setattr(sp, "tick", _tick, raising=True)
    monkeypatch.setattr(asyncio, "sleep", _sleep, raising=True)
    return calls


@pytest.mark.asyncio
async def test_the_universe_is_loaded_before_the_first_tick(harness):
    """The whole point: warm, THEN tick."""
    with pytest.raises(_StopLoop):
        await sp.main()

    assert "refresh_universe" in harness, (
        "the worker never loaded the active universe on boot, so the first "
        "tick snapshots the 112-symbol mock fallback"
    )
    assert "tick" in harness, "fixture assumption: one tick ran"
    assert harness.index("refresh_universe") < harness.index("tick"), (
        f"the universe was refreshed AFTER the first tick (order: {harness}). "
        f"fetch_snapshots runs at the top of tick() and reads the cache, so "
        f"the first cycle publishes the mock fallback — and if that tick times "
        f"out before its own in-tick refresh, every later cycle does too"
    )


@pytest.mark.asyncio
async def test_a_failed_warm_up_does_not_stop_the_worker(harness, monkeypatch):
    """An empty cache is survivable. A worker that will not boot is not."""
    async def _boom():
        raise RuntimeError("database unreachable on boot")

    monkeypatch.setattr(sp, "refresh_active_universe", _boom, raising=True)

    with pytest.raises(_StopLoop):
        await sp.main()

    assert "tick" in harness, (
        "a failing universe warm-up prevented the worker from ticking at all; "
        "it must degrade to the fallback, not refuse to start"
    )


@pytest.mark.asyncio
async def test_the_warm_up_runs_after_the_seed(harness):
    """Ordering against the other boot steps.

    `seed_universe()` is what puts rows in `tickers` on a first boot. Refreshing
    the cache before that would read an empty table and cache nothing.
    """
    with pytest.raises(_StopLoop):
        await sp.main()

    # Checked before indexing so a missing warm-up fails with this sentence
    # rather than a bare `ValueError: x not in list`.
    assert "refresh_universe" in harness, (
        f"the universe was never refreshed on boot (order: {harness})"
    )
    assert harness.index("seed_universe") < harness.index("refresh_universe"), (
        f"the universe cache was loaded before the table was seeded "
        f"(order: {harness}), so on a first boot it caches an empty result"
    )
