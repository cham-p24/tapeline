"""The tick must not throw away everything it writes when the watchdog fires.

THE BUG
-------
`score_upsert` opened ONE `session_scope()` spanning the whole active universe
and did not commit until the end of the stage. `main()` wraps the tick in
`asyncio.wait_for(tick(), timeout=TICK_TIMEOUT_SECONDS)`.

A watchdog kill is a ROLLBACK, not a pause:

  * `wait_for` cancels the coroutine, raising `CancelledError`
  * `CancelledError` is a **BaseException**, not an `Exception` (since 3.8)
  * `db.session_scope` catches `except Exception`, so that arm never runs AND
    its `await session.commit()` on the success path is never reached
  * `AsyncSession.__aexit__` then closes the session and the open transaction
    is discarded

So while the stage sat over budget, every row it wrote was thrown away — every
cycle, on both worker machines. Load had grown 2,500 → 12,000 symbols (#763)
inside an unchanged 60s all-or-nothing budget.

MEASURED IN PRODUCTION 2026-09-11, five days in:
    newest tickers.updated_at          24.1 HOURS stale
    newest tickers.last_aggregates_at  108 hours (4.5 days) stale
    rows scored in the last 2 hours    0
    rows with aggregates under 24h     0 of 7,535
    logs, both machines, every cycle   tick.timeout ... consecutive=10
                                       stage=score_upsert

`updated_at` is written BY the statement that was being rolled back, which is
exactly why it stood still while the worker burned 60s of write work a minute.

THE FIX IS TWO THINGS AND BOTH ARE LOAD-BEARING
-----------------------------------------------
1. Commit per chunk, so a kill costs one chunk instead of the universe.
2. Raise the ceiling, because the MANDATORY write no longer fits in 60s. The
   watchdog is a HANG detector, not a pacing knob — ticks are strictly
   sequential, so a slow tick delays the next one and can never overlap it.

Neither alone is enough: chunking without headroom still starves the ~20 stages
queued behind this one, and headroom without chunking still discards a whole
cycle whenever the ceiling is eventually hit.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import textwrap
from contextlib import asynccontextmanager

import pytest


class TestTheMechanismItself:
    """Pin WHY this happened, not just that it was patched.

    If a future refactor makes `session_scope` catch BaseException, or swaps
    `wait_for` for something that does not cancel, the reasoning behind the
    chunked commit changes and someone should have to read this.
    """

    def test_cancellederror_is_not_caught_by_except_exception(self):
        assert issubclass(asyncio.CancelledError, BaseException)
        assert not issubclass(asyncio.CancelledError, Exception), (
            "CancelledError became an Exception subclass — session_scope's "
            "`except Exception` would now catch a watchdog kill, which changes "
            "the whole analysis in this file's docstring"
        )

    async def test_a_cancelled_scope_never_commits(self):
        """The end-to-end proof, run rather than reasoned about.

        Mirrors db.session_scope's exact control flow. If COMMIT ever appears
        in the log below, the premise of this whole PR is wrong.
        """
        log: list[str] = []

        class FakeSession:
            async def commit(self) -> None:
                log.append("COMMIT")

            async def rollback(self) -> None:
                log.append("ROLLBACK")

            async def __aenter__(self) -> FakeSession:
                return self

            async def __aexit__(self, *a: object) -> None:
                log.append("CLOSE")

        @asynccontextmanager
        async def session_scope():
            async with FakeSession() as s:
                try:
                    yield s
                    await s.commit()
                except Exception:
                    await s.rollback()
                    raise

        async def stage() -> None:
            async with session_scope():
                log.append("wrote rows")
                await asyncio.sleep(5)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(stage(), timeout=0.05)

        assert "wrote rows" in log
        assert "COMMIT" not in log, (
            "the work committed after a cancel — if this is now true, the "
            "chunked commit is no longer load-bearing"
        )


def _executable_source(mod) -> str:
    """Module source with every docstring stripped.

    This file's own prose, and the module's, quote the constants and phrases
    asserted on below. This repo has shipped guards satisfied by exactly that.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(mod)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


class TestTheWriteIsChunkedAndCommitted:
    def test_the_snapshot_write_commits_inside_its_loop(self):
        """Structural: a commit must happen INSIDE the chunk loop.

        A commit after the loop is the original bug with extra steps. Walks the
        AST rather than grepping, because the explanatory comment beside the
        loop contains both `commit` and `UPSERT_CHUNK_ROWS`.
        """
        from app.workers import signal_publisher

        tree = ast.parse(textwrap.dedent(inspect.getsource(signal_publisher)))

        chunk_loops = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.For)
            and "UPSERT_CHUNK_ROWS" in ast.unparse(n.iter)
        ]
        assert chunk_loops, (
            "no `for ... range(..., UPSERT_CHUNK_ROWS)` loop — the snapshot "
            "write is back to one all-or-nothing transaction for the whole "
            "universe, which a watchdog kill discards in full"
        )

        for loop in chunk_loops:
            commits = [
                n for n in ast.walk(loop)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "commit"
            ]
            assert commits, (
                "the chunk loop executes but never commits inside itself; the "
                "work is still discarded wholesale on a watchdog kill"
            )

    def test_the_chunk_size_is_sane(self):
        from app.workers.signal_publisher import UPSERT_CHUNK_ROWS

        assert isinstance(UPSERT_CHUNK_ROWS, int)
        assert 50 <= UPSERT_CHUNK_ROWS <= 5000, (
            "below ~50 the round trips dominate; above ~5000 a kill again "
            "costs most of the universe, which is the bug"
        )

    def test_chunking_splits_rows_and_never_a_rows_columns(self):
        """The constraint that keeps the 158-row desync fixed.

        A row's six factors, the composite computed from them, its label and
        its reason are written by ONE statement. If a future edit chunked by
        COLUMN instead, a commit boundary could land between a score and the
        factors it came from — which is the incident this repo already had.
        """
        from app.workers import signal_publisher
        from app.workers.signal_publisher import CACHE_DERIVED_COLUMNS, FACTOR_COLUMNS

        tree = ast.parse(textwrap.dedent(inspect.getsource(signal_publisher)))
        for loop in [
            n for n in ast.walk(tree)
            if isinstance(n, ast.For) and "UPSERT_CHUNK_ROWS" in ast.unparse(n.iter)
        ]:
            sliced = ast.unparse(loop.iter)
            assert "len(rows)" in sliced or "len(batch)" in sliced, (
                f"the chunk loop iterates over {sliced!r}, which is not a row "
                f"count — chunking by anything but rows can split a score from "
                f"its own factors"
            )

        # And the standing invariant that guards the same incident from the
        # other direction: a factor column must never be COALESCE-protected.
        overlap = [c for c in FACTOR_COLUMNS if c in CACHE_DERIVED_COLUMNS]
        assert not overlap, overlap


class TestTheBudgetFitsTheWork:
    def test_the_tick_ceiling_is_module_level_and_env_overridable(self):
        """It was a hardcoded local inside main(), so an incident could only
        change it with a deploy — during an outage, on the box that is down."""
        from app.workers import signal_publisher

        assert hasattr(signal_publisher, "TICK_TIMEOUT_SECONDS")
        # ast.unparse normalises string quotes to single, so match on both
        # rather than on whatever the source file happens to use today.
        code = _executable_source(signal_publisher)
        assert (
            "environ.get('TICK_TIMEOUT_SECONDS'" in code
            or 'environ.get("TICK_TIMEOUT_SECONDS"' in code
        ), "the tick ceiling is no longer env-overridable"

    def test_the_ceiling_leaves_room_for_the_mandatory_write(self):
        """60s was the value that turned a latency problem into an outage.

        At 12,000 symbols the snapshot write alone approaches a minute, so a
        60s ceiling kills the tick's REQUIRED work plus every stage behind it.
        """
        from app.workers.signal_publisher import TICK_TIMEOUT_SECONDS

        assert TICK_TIMEOUT_SECONDS >= 120, (
            f"{TICK_TIMEOUT_SECONDS}s does not fit the mandatory snapshot "
            f"write at the current universe size; the aggregates refresh and "
            f"~20 other stages sit behind it and would starve again"
        )

    def test_the_watchdog_actually_uses_the_module_constant(self):
        """A constant nothing reads is decorative. An earlier guard in this
        repo asserted a constant existed and was satisfied by its own
        definition; this checks the watchdog LOADS it."""
        from app.workers import signal_publisher

        tree = ast.parse(textwrap.dedent(inspect.getsource(signal_publisher)))
        waits = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and "wait_for" in ast.unparse(n.func)
            and "tick()" in ast.unparse(n)
        ]
        assert waits, "the tick watchdog is gone entirely"
        for w in waits:
            assert "TICK_TIMEOUT_SECONDS" in ast.unparse(w), (
                "the watchdog no longer reads TICK_TIMEOUT_SECONDS"
            )

        # And it must not be shadowed by a local rebinding it back to 60.
        # AnnAssign as well as Assign — the module-level definition is
        # annotated (`TICK_TIMEOUT_SECONDS: int = ...`), and matching only
        # Assign would count zero and miss a plain local rebinding entirely.
        def _targets(n: ast.AST) -> list[ast.expr]:
            if isinstance(n, ast.AnnAssign):
                return [n.target]
            if isinstance(n, ast.Assign):
                return list(n.targets)
            return []

        assigns = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.Assign, ast.AnnAssign))
            and any(
                isinstance(t, ast.Name) and t.id == "TICK_TIMEOUT_SECONDS"
                for t in _targets(n)
            )
        ]
        assert len(assigns) == 1, (
            f"TICK_TIMEOUT_SECONDS is assigned {len(assigns)} times — a local "
            f"rebinding would silently restore the old ceiling"
        )
