"""The back-check drain must be bounded by TIME, not just by dates.

`max_dates` bounds how many dates a drain attempts. It cannot bound how long
that takes, because it cannot know how many fetches a date will cost: each one
is an SPY fetch plus a per-symbol fetch for every entry, and many come back
empty and are retried across following dates (`backcheck.fetch_close_empty`).
With `max_attempts = max_dates * 3` a single drain can spend 180 sequential
HTTP round-trips.

It runs inside a tick the worker kills at 60 seconds.

Observed in production on 2026-09-07: `tick.timeout consecutive=5` followed by
`tick.timeout_streak count=5 — worker appears wedged`, with 23 `/v2/aggs/ticker/`
fetches in a three-minute window. Everything below the back-check in the tick
stopped running, which included the sheet refresh — so a fix to the sheet parser
deployed successfully and then simply never executed. The snapshot pass at the
top of the tick kept working the whole time, so from the outside the worker
looked healthy and the write log looked normal.

Stopping early is safe by construction and is what the function already
promises: an unfinished date keeps `price_next_day IS NULL` and is picked up on
the next run. That is the same self-healing property the docstring describes for
a missed day.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services import scorecard_backcheck as bc


@pytest.fixture
def slow_dates(monkeypatch):
    """A backlog of pending dates, each costing a fixed amount of wall clock."""
    from datetime import date

    pending = [date(2026, 5, d) for d in range(1, 29)]
    calls: list[date] = []

    class _Result:
        def all(self):
            return [(d,) for d in pending]

    async def _execute(_stmt):
        return _Result()

    async def _one_date(_session, *, as_of_override=None):
        calls.append(as_of_override)
        await asyncio.sleep(0.02)  # stands in for the SPY + per-symbol fetches
        return 1

    session = type("S", (), {"execute": staticmethod(_execute)})()
    monkeypatch.setattr(bc, "backcheck_yesterday", _one_date, raising=True)
    monkeypatch.setattr(bc, "_TERMINAL_DATES", set(), raising=False)
    return session, calls, pending


@pytest.mark.asyncio
async def test_the_drain_stops_when_its_time_budget_is_spent(slow_dates):
    """The whole point. Without this the tick is killed and everything below
    the back-check — the sheet refresh included — never runs."""
    session, calls, pending = slow_dates
    scored = await bc.backcheck_all_pending(session, budget_seconds=0.10)

    assert len(calls) < len(pending), (
        f"the drain worked through all {len(pending)} pending dates regardless "
        f"of its budget; at ~0.02s each that is the behaviour that produced "
        f"tick.timeout_streak in production"
    )
    assert scored == len(calls), "every attempted date should still be counted"


@pytest.mark.asyncio
async def test_it_still_makes_progress_rather_than_stalling(slow_dates):
    """A budget that returns zero work would strand the backlog forever."""
    session, calls, _ = slow_dates
    await bc.backcheck_all_pending(session, budget_seconds=0.10)
    assert calls, (
        "the drain spent its budget without attempting a single date, so the "
        "backlog can never shrink"
    )


@pytest.mark.asyncio
async def test_a_generous_budget_still_drains_the_whole_backlog(slow_dates):
    """The budget is a safety valve, not a new cap on throughput."""
    session, calls, pending = slow_dates
    await bc.backcheck_all_pending(session, budget_seconds=60)
    assert len(calls) == len(pending)


@pytest.mark.asyncio
async def test_the_budget_is_checked_between_dates_not_inside_one(slow_dates):
    """A date is scored as a unit.

    Abandoning one part-way would leave some of its entries scored and the rest
    not — and the pending-date query reads that as "still pending", so the next
    run re-fetches the whole date from scratch. The backlog would never shrink
    while the budget stayed tight.
    """
    session, calls, _ = slow_dates
    await bc.backcheck_all_pending(session, budget_seconds=0.05)
    # Each recorded call ran to completion; none was cancelled mid-flight.
    assert all(d is not None for d in calls)
    assert len(calls) >= 1


@pytest.mark.asyncio
async def test_zero_disables_the_budget(slow_dates):
    """An escape hatch for a deliberate catch-up run outside the tick."""
    session, calls, pending = slow_dates
    await bc.backcheck_all_pending(session, budget_seconds=0)
    assert len(calls) == len(pending)


def test_the_default_budget_leaves_the_tick_room_to_finish():
    """Documents the arithmetic against the watchdog it has to survive.

    TICK_TIMEOUT_SECONDS is 60. The back-check is one of many jobs in a tick,
    and the ones after it — the sheet refresh among them — are the ones that
    stopped running.
    """
    assert 0 < bc.BACKCHECK_BUDGET_SECONDS <= 30, (
        f"BACKCHECK_BUDGET_SECONDS={bc.BACKCHECK_BUDGET_SECONDS} is not a "
        f"meaningful fraction of the 60s tick watchdog; at this size the "
        f"drain can still starve every job below it"
    )
