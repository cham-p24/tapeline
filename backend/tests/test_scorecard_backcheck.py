"""Tests for `backcheck_all_pending` — the back-check backlog drainer.

Context (real prod incident, 2026-06-01): the worker scheduled the back-check
with `if _last_backcheck is None`, so it ran ONLY on the first tick after a
reboot, and the job itself (`backcheck_yesterday`) only ever scored today-1.
On a stable deploy the worker doesn't reboot daily, so the back-check silently
stopped — 91 of 140 scorecard rows (every day after ~May 20) sat with
`price_next_day IS NULL` forever and the public scorecard froze on a stale
49-pick sample.

`backcheck_all_pending` is the fix: it finds EVERY distinct `as_of` that still
has unscored rows and replays the single-date job for each, so a missed day
self-heals on the next run instead of being stranded.

These tests pin the drain ORCHESTRATION (the distinct-date discovery query +
the loop), not the scoring math — `backcheck_yesterday` is stubbed so the test
doesn't depend on a vendor price feed. The scoring math lives in
`backcheck_yesterday` and is exercised against the live feed in prod.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import delete

import app.services.scorecard_backcheck as bc
from app.db import session_scope
from app.models import DailyScorecardEntry

#: Next free rank per date, so seeded rows match the shape the freeze writes.
#:
#: This used to hardcode rank=1 for every row, which several tests then used to
#: seed two symbols on the SAME date — a shape production cannot produce, since
#: _ensure_daily_scorecard does `rank += 1` before each add. Harmless until
#: (as_of, rank) became a unique constraint, at which point the fixture, not the
#: code, was what broke. Ranks are irrelevant to what these tests assert (which
#: DATES the back-check drains, and in what order), so they just need to be
#: distinct.
_next_rank: dict[date, int] = {}


async def _clear_table() -> None:
    async with session_scope() as s:
        await s.execute(delete(DailyScorecardEntry))
        await s.commit()
    _next_rank.clear()


async def _seed(as_of: date, symbol: str, *, scored: bool) -> None:
    """Insert one scorecard row. `scored=False` leaves price_next_day NULL
    (i.e. still pending a back-check); `scored=True` fills it in."""
    rank = _next_rank.get(as_of, 0) + 1
    _next_rank[as_of] = rank
    async with session_scope() as s:
        s.add(
            DailyScorecardEntry(
                as_of=as_of,
                symbol=symbol,
                rank=rank,
                score_at_flag=0.9,
                price_at_flag=100.0,
                price_next_day=101.0 if scored else None,
            )
        )
        await s.commit()


def _patch_single_date(monkeypatch) -> list[date]:
    """Replace the single-date job with a stub that records which dates it was
    asked to score and returns 1 (pretend it scored one row). Returns the list
    the stub appends to, so callers can assert call order + membership."""
    calls: list[date] = []

    async def _stub(session, as_of_override=None):
        calls.append(as_of_override)
        return 1

    monkeypatch.setattr(bc, "backcheck_yesterday", _stub)
    return calls


@pytest.mark.asyncio
async def test_drains_only_pending_dates_newest_first(monkeypatch):
    """Discovers every distinct date with an unscored row, NEWEST-first, and
    skips dates whose rows are all already scored.

    The invariants here are "every pending date, and only pending dates" —
    05-28 is fully scored and must not be revisited. The ORDER flipped
    2026-09-11: unscorable dates sort oldest and can never complete, so
    oldest-first spent the entire wall-clock budget on them and the most
    recent day's picks were never back-checked at all. Measured on prod, three
    consecutive runs, 20s budget, zero scored. See
    test_the_backcheck_reaches_the_newest_day.py."""
    await _clear_table()
    # Two fully-pending dates...
    await _seed(date(2026, 5, 26), "AAA", scored=False)
    await _seed(date(2026, 5, 27), "BBB", scored=False)
    # ...one fully-scored date (must NOT be revisited)...
    await _seed(date(2026, 5, 28), "CCC", scored=True)
    # ...and a date with a MIX: one scored + one still pending → must appear,
    # because it still has back-check work left to do.
    await _seed(date(2026, 5, 29), "DDD", scored=True)
    await _seed(date(2026, 5, 29), "EEE", scored=False)

    calls = _patch_single_date(monkeypatch)

    async with session_scope() as s:
        total = await bc.backcheck_all_pending(s)

    # 05-28 excluded (no pending rows); the rest in DESCENDING date order.
    assert calls == [date(2026, 5, 29), date(2026, 5, 27), date(2026, 5, 26)]
    # Stub returns 1 per call → 3 dates → total 3.
    assert total == 3


@pytest.mark.asyncio
async def test_distinct_dates_not_per_row(monkeypatch):
    """A date with many pending rows is back-checked ONCE, not once per row —
    the single-date job already scores all rows for its date in one pass."""
    await _clear_table()
    for sym in ("AAA", "BBB", "CCC", "DDD", "EEE"):
        await _seed(date(2026, 5, 26), sym, scored=False)

    calls = _patch_single_date(monkeypatch)

    async with session_scope() as s:
        await bc.backcheck_all_pending(s)

    assert calls == [date(2026, 5, 26)]


@pytest.mark.asyncio
async def test_max_dates_caps_work_per_run(monkeypatch):
    """`max_dates` bounds the dates touched per run (each is its own SPY +
    per-symbol fetch) so a huge backlog can't stall the worker loop. Remaining
    dates are picked up on the next run; the cap takes the NEWEST first.

    What this test protects is the CAP, not the order — but the order it takes
    them in decides which dates get the budget, and newest-first is the one
    that reaches the day a reader is actually looking at."""
    await _clear_table()
    for d in (date(2026, 5, 25), date(2026, 5, 26), date(2026, 5, 27)):
        await _seed(d, "AAA", scored=False)

    calls = _patch_single_date(monkeypatch)

    async with session_scope() as s:
        total = await bc.backcheck_all_pending(s, max_dates=2)

    assert calls == [date(2026, 5, 27), date(2026, 5, 26)]
    assert total == 2


@pytest.mark.asyncio
async def test_empty_backlog_returns_zero_without_calling(monkeypatch):
    """No pending rows → returns 0 and never invokes the single-date job."""
    await _clear_table()
    await _seed(date(2026, 5, 26), "AAA", scored=True)  # already scored

    calls = _patch_single_date(monkeypatch)

    async with session_scope() as s:
        total = await bc.backcheck_all_pending(s)

    assert total == 0
    assert calls == []
