"""The calendar seed must finish inside a tick, not merely fail politely.

MEASURED ON PRODUCTION 2026-09-07
---------------------------------
    tick.timeout elapsed=60.0s limit=60s consecutive=4 stage=calendar_seed

`_seed_calendar` replaces the earnings table with Finnhub's window - 3,362 rows
on the day this was measured - and did it with one ORM `session.add()` per row.
The ORM emits one INSERT per added instance, so that is ~3,400 sequential
round-trips to a remote database inside a 60s tick. It never finished:
`calendar.refreshed` appears nowhere in the production logs.

WHAT #777 FIXED, AND WHAT IT LEFT
---------------------------------
#777 fixed the CONSEQUENCE. Every cadence-gated job in `tick()` stamped its
latch AFTER the work, so a watchdog kill meant the stamp never happened and the
same expensive job restarted on the next tick, starving everything behind it
forever. Stamping first turns that into one missed cycle.

That is the right fix and it is not this one. It made the calendar seed stop
being *other jobs'* problem; it did not make the calendar seed finish. Left
alone, the job would still be killed at 60s on each daily attempt and the
earnings window would never refresh again - a silent, permanent staleness
instead of a loud, permanent wedge. Both halves are needed.

WHICH TEST CATCHES WHAT
-----------------------
Only `test_the_seed_does_not_insert_row_by_row` is a regression guard for the
bug: it is the one watched red against the pre-fix worker. The other two pass
on the old code as well, and are not claimed as guards for it — the row-by-row
loop wrote the same rows, it just took too long to survive the watchdog, and no
test in a fast local database can reproduce "too slow against a remote pooler"
honestly.

They earn their place by covering what the FIX could newly break: a bulk insert
that silently writes nothing would satisfy any source-level check, and
`insert()` with an empty sequence raises, which makes "the vendor returned
nothing" newly capable of wiping the calendar and crashing.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
from datetime import date

import pytest
from sqlalchemy import func, select

from app.db import session_scope
from app.models import EarningsEvent, IPOEvent
from app.workers import signal_publisher

# NO `pytestmark = pytest.mark.anyio` - pytest.ini sets `asyncio_mode = auto`.


def _earnings_rows(n: int) -> list[dict]:
    return [
        {
            "symbol": f"CAL{i:04d}",
            "report_date": date(2026, 10, 1),
            "report_time": "AMC",
            "fiscal_quarter": "Q3 2026",
            "eps_estimate": 1.0,
        }
        for i in range(n)
    ]


def _ipo_rows(n: int) -> list[dict]:
    return [
        {
            "symbol": f"IPO{i:04d}",
            "company_name": f"Newco {i}",
            "exchange": "NASDAQ",
            "expected_date": date(2026, 10, 1),
        }
        for i in range(n)
    ]


async def test_the_seed_writes_every_row_it_was_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bulk insert that quietly wrote nothing would pass a source check.

    So drive the real function and count what landed. 250 rows rather than
    3,400 - the point is that the whole batch arrives, not the timing.
    """
    earnings, ipos = _earnings_rows(250), _ipo_rows(5)

    async def _earnings() -> list[dict]:
        return earnings

    async def _ipos() -> list[dict]:
        return ipos

    monkeypatch.setattr("app.services.calendar_feed.upcoming_earnings", _earnings)
    monkeypatch.setattr("app.services.calendar_feed.upcoming_ipos", _ipos)

    await signal_publisher._seed_calendar()

    async with session_scope() as s:
        n_earnings = await s.scalar(
            select(func.count()).select_from(EarningsEvent)
            .where(EarningsEvent.symbol.like("CAL%"))
        )
        n_ipos = await s.scalar(
            select(func.count()).select_from(IPOEvent)
            .where(IPOEvent.symbol.like("IPO%"))
        )
    assert n_earnings == 250, f"only {n_earnings} of 250 earnings rows landed"
    assert n_ipos == 5, f"only {n_ipos} of 5 IPO rows landed"


async def test_an_empty_feed_leaves_the_previous_window_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The delete is gated on a non-empty fetch, and must stay that way.

    An `insert()` with an empty sequence raises, so moving to executemany makes
    it newly possible to turn "Finnhub returned nothing" into a wiped calendar
    plus a crash. It is the same guard the original loop had, and it now
    carries a second reason.
    """
    keep = _earnings_rows(3)

    async def _some() -> list[dict]:
        return keep

    async def _none() -> list[dict]:
        return []

    monkeypatch.setattr("app.services.calendar_feed.upcoming_earnings", _some)
    monkeypatch.setattr("app.services.calendar_feed.upcoming_ipos", _none)
    await signal_publisher._seed_calendar()

    monkeypatch.setattr("app.services.calendar_feed.upcoming_earnings", _none)
    await signal_publisher._seed_calendar()  # must not raise

    async with session_scope() as s:
        still_there = await s.scalar(
            select(func.count()).select_from(EarningsEvent)
            .where(EarningsEvent.symbol.like("CAL%"))
        )
    assert still_there == 3, (
        "an empty vendor response wiped the calendar; 'unavailable' is not a "
        "statement that no company reports this quarter"
    )


def test_the_seed_does_not_insert_row_by_row() -> None:
    """Read off the AST of `_seed_calendar`, so the comment explaining the old
    loop cannot satisfy the assertion that the loop is gone."""
    tree = ast.parse(
        pathlib.Path(inspect.getfile(signal_publisher)).read_text(encoding="utf-8")
    )
    seed = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_seed_calendar"
    )
    adds_in_loops = [
        sub.lineno
        for loop in ast.walk(seed) if isinstance(loop, (ast.For, ast.AsyncFor))
        for sub in ast.walk(loop)
        if isinstance(sub, ast.Call) and getattr(sub.func, "attr", None) == "add"
    ]
    assert not adds_in_loops, (
        f"session.add() inside a loop at line(s) {adds_in_loops} — one INSERT "
        f"per row for ~3,400 rows is what stopped this job completing inside "
        f"the 60s tick watchdog"
    )
