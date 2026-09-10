"""The most recent day's picks must get back-checked before the archaeology.

Measured on production 2026-09-11, three consecutive runs, each a fresh
process:

    backcheck.drain pending_dates=19 attempted=11 scored=0
                    skipped_terminal=0 newly_terminal=11
                    elapsed=20.0s budget_hit=True          (x3, identical)

Nineteen pending dates. Eleven were delisted names from May and June — APLS,
TPH, EHAB, whose history the vendor no longer serves — and the entire
20-second budget went to re-discovering that, on every run.

The ten picks from 2026-09-08, the most recent frozen day and perfectly
scorable, were never reached. On a public track record whose whole claim is
that every pick is checked against the S&P the next session, the most recent
session was the one permanently missing.

WHY THE EXISTING GUARD DIDN'T CATCH IT
`_TERMINAL_DATES` already skips unscorable dates, and the docstring already
called out that they "sort oldest and can never complete ... permanently
starve the newer, scorable dates behind them". That fixed the DATE CAP. It
could not fix the WALL-CLOCK budget, because the budget is spent DISCOVERING
that a date is terminal — several vendor fetches each — and the registry is
in-process by design. The worker restarts on every deploy, so every restart
starts the discovery over.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services import scorecard_backcheck as bc


def test_the_candidate_query_is_newest_first():
    """One line decides whether today's picks are ever checked."""
    import inspect

    src = inspect.getsource(bc.backcheck_all_pending)
    assert "as_of.desc()" in src, (
        "pending dates are drained oldest-first; unscorable dates sort oldest, "
        "so they eat the wall-clock budget and the newest day never gets "
        "back-checked"
    )
    assert "as_of.asc()" not in src


@pytest.mark.asyncio
async def test_the_newest_day_is_reached_when_dead_dates_would_eat_the_budget(
    monkeypatch,
):
    """The production failure, reproduced.

    Eleven old dates that each burn budget and can never score, plus one recent
    scorable date. Oldest-first never reaches the recent one. Newest-first
    scores it first.
    """
    today = date(2026, 9, 10)
    dead = [today - timedelta(days=100 + i) for i in range(11)]
    live = date(2026, 9, 8)

    attempted: list[date] = []

    # Each attempt costs real budget, which is the whole point — the bound that
    # bites is wall clock, not the date cap.
    clock = {"t": 0.0}
    monkeypatch.setattr(bc.time, "monotonic", lambda: clock["t"])

    async def _fake_backcheck(session, *, as_of_override=None):
        attempted.append(as_of_override)
        clock["t"] += 2.0                       # ~ what a dead date cost on prod
        if as_of_override != live:
            bc._mark_terminal(as_of_override, "unresolvable_rows_after_90d")
            return 0
        return 10                               # the ten picks from 09-08

    monkeypatch.setattr(bc, "backcheck_yesterday", _fake_backcheck)
    bc._TERMINAL_DATES.clear()

    class _Rows:
        def __init__(self, ds): self._ds = ds
        def all(self): return [(d,) for d in self._ds]

    class _Session:
        async def execute(self, _stmt):
            # Newest first, as the real query now orders.
            return _Rows(sorted([*dead, live], reverse=True))

    scored = await bc.backcheck_all_pending(_Session(), budget_seconds=20.0)

    assert live in attempted, (
        "the most recent scorable day was never attempted — the budget went to "
        "dates that can never complete"
    )
    assert scored == 10
    assert attempted[0] == live, (
        "the newest date must be attempted first, not merely eventually"
    )
    bc._TERMINAL_DATES.clear()


@pytest.mark.asyncio
async def test_older_dates_are_still_attempted(monkeypatch):
    """Newest-first must not become newest-only.

    The self-healing property is the reason this function exists: a day the
    single-date job missed has to be picked up later. Reordering must not
    quietly turn the drain into "today and nothing else".
    """
    dates = [date(2026, 9, 8), date(2026, 9, 3), date(2026, 8, 28)]
    attempted: list[date] = []

    clock = {"t": 0.0}
    monkeypatch.setattr(bc.time, "monotonic", lambda: clock["t"])

    async def _fake_backcheck(session, *, as_of_override=None):
        attempted.append(as_of_override)
        clock["t"] += 0.1
        return 10

    monkeypatch.setattr(bc, "backcheck_yesterday", _fake_backcheck)
    bc._TERMINAL_DATES.clear()

    class _Rows:
        def __init__(self, ds): self._ds = ds
        def all(self): return [(d,) for d in self._ds]

    class _Session:
        async def execute(self, _stmt):
            return _Rows(sorted(dates, reverse=True))

    total = await bc.backcheck_all_pending(_Session(), budget_seconds=20.0)

    assert set(attempted) == set(dates), "an older pending date was dropped"
    assert total == 30
    bc._TERMINAL_DATES.clear()
