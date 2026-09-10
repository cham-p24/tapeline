"""The permanent public record must be writable by exactly one worker.

THE BUG THIS PREVENTS
---------------------
`_ensure_daily_scorecard` is a check-then-insert: SELECT one row for today, and
if there is none, INSERT ten. That dedupes within one process and not at all
across machines.

Fly runs a STANDBY worker beside the primary. On 2026-09-08
`fly status -a tapeline-backend` showed both machines `started`, and both were
emitting `tick.timeout` — i.e. both actively running tick(), not one idling:

    worker  2879770f913628  started
    worker† 080e971dad0298  started

Two machines that both read "no row for today" both write ten. `/scorecard`
then publishes 20 rows for that day, the hit-rate denominator doubles, and
NOTHING raises — an append-only public trust record silently gains a day it
counts twice.

WHY IT HAS NOT HAPPENED YET, WHICH IS NOT REASSURING
----------------------------------------------------
The freeze stage sits behind `score_upsert` in tick(), and score_upsert has been
blowing the 60s watchdog every cycle since 2026-09-06, so nothing downstream of
it has run. The outage is the only thing that has been preventing the double
write. Repairing the timeout re-arms this race, which is why the guard ships
first.

Measured on prod 2026-09-11, before the constraints were added: 800 rows over 80
days, zero duplicate (as_of, symbol), zero duplicate (as_of, rank), zero days
over ten rows. Clean, so no repair migration was needed.

WHY A CONSTRAINT AND NOT JUST THE LOCK
--------------------------------------
`dblock.try_xact_lock` is a no-op on SQLite (dev and this whole suite), and it
cannot cover a caller that reaches the insert without taking it. The lock
decides WHO writes; the constraint decides what the table is ALLOWED TO CONTAIN.
The tests below cover both halves separately, because either one alone is a
guarantee with a hole in it.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import date

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.db import session_scope
from app.models.scorecard import DailyScorecardEntry

#: Dates used only by this file, so a leftover row cannot collide with fixtures
#: seeded elsewhere in the suite.
DAY = date(2091, 9, 11)
PRIOR = date(2091, 9, 10)


def _row(as_of: date, symbol: str, rank: int) -> DailyScorecardEntry:
    return DailyScorecardEntry(
        as_of=as_of, symbol=symbol, rank=rank,
        score_at_flag=90.0, price_at_flag=10.0,
    )


@pytest.fixture(autouse=True)
async def _clean() -> None:
    async with session_scope() as s:
        await s.execute(
            delete(DailyScorecardEntry).where(DailyScorecardEntry.as_of.in_([DAY, PRIOR]))
        )
    yield
    async with session_scope() as s:
        await s.execute(
            delete(DailyScorecardEntry).where(DailyScorecardEntry.as_of.in_([DAY, PRIOR]))
        )


class TestTheDatabaseRefusesADoubleFreeze:
    """The half that holds even when the advisory lock is a no-op."""

    async def test_two_machines_cannot_both_claim_the_same_rank(self) -> None:
        """(as_of, rank) is what BOUNDS a day to ten rows.

        This is the constraint that still holds when the two machines pick
        DIFFERENT symbol sets — which is the realistic race, since each reads
        its own snapshot of a table the other is also writing.
        """
        async with session_scope() as s:
            s.add(_row(DAY, "AAA", 1))
            await s.flush()

            s.add(_row(DAY, "ZZZ", 1))  # different symbol, SAME rank
            with pytest.raises(IntegrityError):
                await s.flush()
            await s.rollback()

    async def test_the_same_symbol_cannot_be_frozen_twice_in_one_day(self) -> None:
        """(as_of, symbol) is the invariant the model's docstring already claimed."""
        async with session_scope() as s:
            s.add(_row(DAY, "AAA", 1))
            await s.flush()

            s.add(_row(DAY, "AAA", 7))  # same symbol, different rank
            with pytest.raises(IntegrityError):
                await s.flush()
            await s.rollback()

    async def test_a_normal_ten_row_day_is_still_allowed(self) -> None:
        """The constraints must not break the thing they protect.

        Ten distinct symbols at ten distinct ranks is exactly what the freeze
        writes every trading day, and it must stay legal.
        """
        async with session_scope() as s:
            for i in range(1, 11):
                s.add(_row(DAY, f"SYM{i}", i))
            await s.flush()  # must not raise

    async def test_the_same_symbol_on_a_different_day_is_fine(self) -> None:
        """A ticker recurring across days is the normal case, not a violation."""
        async with session_scope() as s:
            s.add(_row(PRIOR, "AAA", 1))
            s.add(_row(DAY, "AAA", 1))
            await s.flush()  # must not raise


class TestTheWorkerTakesTheLock:
    """The half that stops the second machine before it does the work.

    Structural, on executable source with docstrings stripped. An earlier guard
    in this repo asserted a constant appeared in a module and was satisfied by
    the constant's own definition; another was satisfied by the prose in the
    docstring explaining the fix. Both are avoided here by walking the AST of
    the function itself.
    """

    def _freeze_fn(self) -> ast.AsyncFunctionDef:
        from app.workers import signal_publisher

        tree = ast.parse(textwrap.dedent(inspect.getsource(signal_publisher)))
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "_ensure_daily_scorecard"
            ):
                # Strip the docstring so its prose cannot satisfy anything.
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    node.body = node.body[1:]
                return node
        raise AssertionError("_ensure_daily_scorecard not found; re-point this test")

    def test_the_freeze_takes_the_advisory_lock(self):
        fn = self._freeze_fn()
        calls = [
            n for n in ast.walk(fn)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "try_xact_lock"
        ]
        assert calls, (
            "_ensure_daily_scorecard never calls try_xact_lock — two worker "
            "machines will both freeze the permanent public record"
        )

    def test_the_lock_is_taken_before_the_insert(self):
        """A lock taken after the write guards nothing."""
        fn = self._freeze_fn()
        lock_lines = [
            n.lineno for n in ast.walk(fn)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "try_xact_lock"
        ]
        add_lines = [
            n.lineno for n in ast.walk(fn)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "add"
        ]
        assert lock_lines and add_lines, "expected both a lock call and a session.add"
        assert min(lock_lines) < min(add_lines), (
            "the lock is taken after rows are already staged for insert"
        )

    def test_not_getting_the_lock_returns_instead_of_continuing(self):
        """`if not await try_xact_lock(...)` must guard an early return.

        Falling through on a failed acquire would make the lock decorative.
        """
        fn = self._freeze_fn()
        for node in ast.walk(fn):
            if not isinstance(node, ast.If):
                continue
            test_src = ast.unparse(node.test)
            if "try_xact_lock" in test_src and test_src.strip().startswith("not"):
                assert any(isinstance(b, ast.Return) for b in node.body), (
                    "the failed-acquire branch does not return; the second "
                    "machine would carry on and write anyway"
                )
                return
        raise AssertionError(
            "no `if not await try_xact_lock(...)` guard found in the freeze"
        )


def test_the_lock_helper_is_transaction_scoped_not_session_scoped():
    """Session-scoped locks are silently useless on this infrastructure.

    Prod DATABASE_URL is Neon's `-pooler` host — PgBouncer in transaction mode —
    which hands one client connection to a DIFFERENT server backend between
    transactions. A session-scoped `pg_advisory_lock` is therefore held on a
    backend that is then given to someone else: it protects nothing and raises
    nothing. The same multiplexing already broke prepared statements here.

    Checked on executable source: this module's own docstring explains the
    distinction and names both functions, so a plain substring search over the
    file would pass against the explanation rather than the code.
    """
    from app.services import dblock

    tree = ast.parse(textwrap.dedent(inspect.getsource(dblock)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef))
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    code = ast.unparse(tree)

    assert "pg_try_advisory_xact_lock" in code, (
        "the helper no longer uses the transaction-scoped lock"
    )
    # The session-scoped forms, banned. `_xact_` variants must not trip this.
    for banned in ("pg_advisory_lock(", "pg_try_advisory_lock("):
        assert banned not in code, (
            f"{banned} is session-scoped and is silently a no-op behind "
            f"PgBouncer transaction pooling, which is what prod runs on"
        )
