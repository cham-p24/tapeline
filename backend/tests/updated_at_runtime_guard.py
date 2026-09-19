"""The RUNTIME half of the `Ticker.updated_at` contract, enforced on every test.

WHY THIS EXISTS
---------------
tests/test_ticker_updated_at_means_live_data.py guards the source with an AST
walk: every `update(Ticker)` in backend/app must hold updated_at still unless
it is an allowlisted live-data writer. A walk can only judge the spellings it
understands. Review of #813 wrote four it did not —
`from sqlalchemy import update as _update`, `update(models.Ticker)`,
`from app.models import Ticker as T`, `TICKERS = Ticker.__table__` — and each
passed the walker AND the token-scan cross-check that was meant to back it up,
because the token scan looked for the same literal spellings. A cross-check
that shares the walker's assumptions cannot catch the walker's blind spots.

So this file checks the other end: the SQL that reaches the database. A
`before_cursor_execute` listener on every Engine sees each `UPDATE tickers`
the suite runs however the Python was spelled — including an ORM flush of a
dirtied Ticker, which no `update(Ticker)` walk can see at all. When the SET
moves updated_at and the innermost backend frame that issued it is app code
outside RUNTIME_LIVE_DATA_WRITERS, the test that ran it errors at teardown
(conftest.py's `ticker_update_log` fixture).

Measured on the full suite before this was switched on (2026-09-13): 46
`UPDATE tickers` statements from 11 app callers, and the only app callers that
moved updated_at were the three ORM live-data writers listed below. The tick
itself issued none, because no test ran it — which is the first review
finding, fixed by the real-tick test in the contract file.

BOTH HALVES KEY ON THE FUNCTION
-------------------------------
The AST walk keys an `update(Ticker)` on the function that BUILDS it; this
listener keys the UPDATE on the function that EXECUTES it. They agree only
when one function does both, which every writer here does. A statement built
in a helper and executed elsewhere fails both the real-tick test and the
walker cross-check, with a message that says so — keep build and execute
together, or move the whole write and re-key the entry.

LIMITS, STATED RATHER THAN DISCOVERED
-------------------------------------
* It sees only what the suite executes. The AST walk still covers code no
  test runs; this covers spellings the walk does not understand.
* "Moves updated_at" is read off SQLite's rendering: the onupdate renders as
  `updated_at=CURRENT_TIMESTAMP`, a Python datetime as `updated_at=?`, and a
  hold as `updated_at=tickers.updated_at`. Anything but the last counts.
* An ORM flush is attributed to the frame that triggered it — the function
  whose `session_scope` committed, or whose query autoflushed — not to the
  line that dirtied the object. app/db.py is skipped so session_scope's own
  commit is charged to its caller.
"""
from __future__ import annotations

import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType
from typing import Any

import greenlet
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.sql.dml import Update

BACKEND = Path(__file__).resolve().parents[1]

#: `update(Ticker)` statements that WRITE LIVE DATA and therefore must let the
#: onupdate advance updated_at. Keyed by (path under backend/, enclosing
#: function qualname). Every other `update(Ticker)` is metadata and must hold
#: it still. The AST walk in the contract file enforces both directions.
LIVE_DATA_WRITERS: dict[tuple[str, str], str] = {
    ("app/workers/signal_publisher.py", "tick"):
        "the per-minute score upsert: price, factors and composite from this "
        "tick's snapshot",
}

#: Live-data writers that go through the ORM unit of work (load a Ticker, set
#: attributes, commit) rather than an `update(Ticker)` statement, so the AST
#: walk has no statement to key them on. Observed on the full suite
#: 2026-09-13 as the only app callers whose UPDATE moved updated_at.
ORM_LIVE_DATA_WRITERS: dict[tuple[str, str], str] = {
    ("app/services/sheet_feed.py", "upsert_tickers"):
        "the ALL SIGNALS sheet: price and change_pct_1m (the six factors, score "
        "and signal go through _write_factor_sets, which holds updated_at)",
    ("app/services/sheet_feed.py", "upsert_smart_money"):
        "the SMART MONEY sheet tab: the sub_smart_money factor (not called "
        "since 2026-09-17)",
    ("app/services/sheet_feed.py", "upsert_etfs"):
        "the ETF BENCHMARKS sheet: change_pct_1m beside name, sector and asset "
        "class; first exercised on an existing row 2026-09-17",
    ("app/workers/signal_publisher.py", "_refresh_crypto_universe"):
        "the daily crypto refresh: price, score and factors for each pair",
}

RUNTIME_LIVE_DATA_WRITERS: frozenset[tuple[str, str]] = frozenset(
    LIVE_DATA_WRITERS.keys() | ORM_LIVE_DATA_WRITERS.keys()
)

_UPDATE_TICKERS = re.compile(
    r"\s*UPDATE\s+tickers\s+SET\s+(?P<set>.*?)(?:\s+WHERE\s|\s+RETURNING\s|\s*$)",
    re.IGNORECASE | re.DOTALL,
)
_UPDATED_AT_ASSIGNMENT = re.compile(
    r"\bupdated_at\s*=\s*(?P<value>[^,\s]+)", re.IGNORECASE,
)
_HOLD = "tickers.updated_at"


def moves_updated_at(sql: str) -> bool | None:
    """None when `sql` is not an UPDATE of tickers; otherwise whether its SET
    assigns updated_at anything other than itself."""
    m = _UPDATE_TICKERS.match(sql)
    if m is None:
        return None
    assignment = _UPDATED_AT_ASSIGNMENT.search(m.group("set"))
    return assignment is not None and assignment.group("value").lower() != _HOLD


@dataclass(frozen=True)
class TickerUpdate:
    #: (path under backend/, qualname) of the innermost app/ or tests/ frame,
    #: or None when no backend frame is on the stack.
    caller: tuple[str, str] | None
    moves_updated_at: bool
    #: Emitted by the ORM unit of work (a dirtied object), not a statement.
    flush: bool
    #: The statement was an `Update` construct, as opposed to `text()`.
    construct: bool
    sql: str


@dataclass
class Recorder:
    events: list[TickerUpdate] = field(default_factory=list)

    def problems(self) -> list[str]:
        return [
            f"{e.caller[0]}::{e.caller[1]} moved Ticker.updated_at at runtime "
            f"outside the live-data writers — {e.sql}. A metadata write must "
            "hold it still (updated_at=Ticker.updated_at); if this writes live "
            "data, add it to LIVE_DATA_WRITERS or ORM_LIVE_DATA_WRITERS in "
            "tests/updated_at_runtime_guard.py."
            for e in self.events
            if e.moves_updated_at and e.caller is not None
            and e.caller[0].startswith("app/")
            and e.caller not in RUNTIME_LIVE_DATA_WRITERS
        ]


# A stack, not one slot: the contract file drives conftest's real fixture
# function inside a test that is itself being recorded.
_recorders: list[Recorder] = []

_NORM_BACKEND = os.path.normcase(str(BACKEND)) + os.sep
_SELF = os.path.normcase(__file__)
_PERSISTENCE = os.path.normcase(os.path.join("sqlalchemy", "orm", "persistence.py"))


def _stack(start: FrameType | None) -> Iterator[FrameType]:
    """Frames from `start` outward, CONTINUING through parent greenlets.

    Async SQLAlchemy runs the synchronous core inside a child greenlet
    (greenlet_spawn), so `f_back` stops at the greenlet boundary and the app
    coroutine that awaited `session.execute` is not on that chain. It is on
    the parent greenlet's suspended frame chain — measured, not assumed:
    `greenlet_spawn -> session.execute -> <the app function> -> asyncio`.
    """
    frame, g = start, greenlet.getcurrent()
    while True:
        while frame is not None:
            yield frame
            frame = frame.f_back
        g = g.parent
        if g is None:
            return
        frame = g.gr_frame


def attribute(frames: Iterator[FrameType]) -> tuple[tuple[str, str] | None, bool]:
    """(caller, emitted-by-a-flush) for the statement being executed."""
    flush = False
    for frame in frames:
        path = os.path.normcase(frame.f_code.co_filename)
        if frame.f_code.co_name == "save_obj" and path.endswith(_PERSISTENCE):
            flush = True
        if not path.startswith(_NORM_BACKEND) or path == _SELF:
            continue
        rel = path[len(_NORM_BACKEND):].replace(os.sep, "/")
        if not rel.startswith(("app/", "tests/")) or rel == "app/db.py":
            continue
        return (rel, frame.f_code.co_qualname.replace(".<locals>", "")), flush
    return None, flush


def _on_cursor_execute(
    conn: Any, cursor: Any, statement: str, parameters: Any, context: Any,
    executemany: bool,
) -> None:
    if not _recorders:
        return
    moves = moves_updated_at(statement)
    if moves is None:
        return
    caller, flush = attribute(_stack(sys._getframe(1)))
    compiled = getattr(context, "compiled", None)
    _recorders[-1].events.append(TickerUpdate(
        caller=caller, moves_updated_at=moves, flush=flush,
        construct=isinstance(getattr(compiled, "statement", None), Update),
        sql=" ".join(statement.split()),
    ))


def install() -> None:
    """Idempotent. On the Engine CLASS, so the per-test engines conftest
    builds after this runs are covered too."""
    if not event.contains(Engine, "before_cursor_execute", _on_cursor_execute):
        event.listen(Engine, "before_cursor_execute", _on_cursor_execute)


def listening() -> bool:
    return event.contains(Engine, "before_cursor_execute", _on_cursor_execute)


@contextmanager
def recording() -> Iterator[Recorder]:
    install()
    rec = Recorder()
    _recorders.append(rec)
    try:
        yield rec
    finally:
        _recorders.remove(rec)


def current() -> Recorder | None:
    return _recorders[-1] if _recorders else None
