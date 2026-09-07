"""A tick stage that overruns the watchdog must not starve the stages behind it.

MEASURED ON PRODUCTION 2026-09-07
---------------------------------
    tick.timeout elapsed=60.0s limit=60s consecutive=4 stage=calendar_seed

Not a transient slow tick - a permanent wedge, and the reason the two composite
factor passes had made no progress at all:

    last_fundamentals_at stamped: 1,320 of 11,781  (frozen)
    last_smart_money_at  stamped:     0 of 11,781  (never ran)

`_seed_calendar` replaces the earnings table with Finnhub's window - ~3,400
rows - using one ORM `session.add()` per row, which emits one INSERT per row.
Over the Neon pooler that never finished inside the 60s tick watchdog, so the
coroutine was cancelled every time it ran ("calendar.refreshed" appears nowhere
in the production logs).

The cancellation is what made it permanent. `asyncio.wait_for` raises
CancelledError, which is a **BaseException**, so the stage's `except Exception`
never saw it - and the latch was written on the line AFTER the await. It was
therefore never written at all: the stage re-ran on the very next tick, timed
out again, and every job scheduled after it in `tick()` was skipped forever.
The Finnhub factor chain is one of those jobs.

"Latch on success" and "latch first, clear on caught failure" behave
identically for a transient error - both retry on the next tick. They differ in
exactly one case, the one above. So the latch goes first.

Two independent guards, because either alone can be satisfied without fixing
the bug: the insert could be made fast while the wedge pattern stays (and
returns the next time a stage runs long), or the latch could be fixed while the
calendar never refreshes at all.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from app.workers import signal_publisher

# NO `pytestmark = pytest.mark.anyio` - pytest.ini sets `asyncio_mode = auto`.


def _tick_node() -> ast.AsyncFunctionDef:
    tree = ast.parse(
        pathlib.Path(inspect.getfile(signal_publisher)).read_text(encoding="utf-8")
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "tick":
            return node
    raise AssertionError("tick() not found")


def _latch_writes_and_awaits(latch: str, callee: str) -> tuple[int, int]:
    """(line of the first write to `latch`, line of the first await of `callee`).

    AST, not text: the comment blocks around these stages discuss the latch
    ordering at length, including the arrangement that caused the bug, and a
    source grep cannot tell an explanation of the fix from the fix.
    """
    writes, awaits = [], []
    for node in ast.walk(_tick_node()):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == latch:
                    writes.append(node.lineno)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == callee:
            awaits.append(node.lineno)
    assert writes, f"nothing in tick() assigns {latch}"
    assert awaits, f"tick() never calls {callee}"
    return min(writes), min(awaits)


@pytest.mark.parametrize(
    ("latch", "callee"),
    [
        ("_last_calendar_seed", "_seed_calendar"),
        ("_last_backcheck", "_run_backcheck"),
    ],
)
def test_long_stages_latch_before_they_await(latch: str, callee: str) -> None:
    """The latch write must precede the await that can be cancelled.

    Both of these stages are unbounded: the calendar seed rewrites a ~3,400-row
    table, the back-check drains an arbitrarily long date backlog. Either can
    exceed the watchdog, and an after-the-await latch turns that into permanent
    starvation of everything behind it rather than a skipped run.
    """
    first_write, first_await = _latch_writes_and_awaits(latch, callee)
    assert first_write < first_await, (
        f"{latch} is written at line {first_write}, AFTER the await of "
        f"{callee}() at line {first_await}. A watchdog cancellation raises "
        f"CancelledError (a BaseException), so that write never happens and "
        f"the stage re-runs on every tick, skipping every job behind it."
    )


def test_the_calendar_seed_does_not_insert_row_by_row() -> None:
    """~3,400 individual INSERTs is what made the stage exceed the watchdog.

    Asserted on the AST of `_seed_calendar` so a comment describing the old
    loop cannot satisfy it.
    """
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
        if isinstance(sub, ast.Call)
        and getattr(sub.func, "attr", None) == "add"
    ]
    assert not adds_in_loops, (
        f"session.add() inside a loop at line(s) {adds_in_loops} — one INSERT "
        f"per row for ~3,400 rows is what made this stage un-completable "
        f"inside the 60s tick watchdog"
    )


def test_the_calendar_seed_clears_its_latch_on_a_caught_failure() -> None:
    """The other half: latching first must not cost the transient-failure retry.

    "Latch on success" and "latch first, clear on caught failure" are identical
    for an ordinary exception - both retry on the next tick - and differ only
    for a watchdog cancellation, which is a BaseException and so reaches
    neither handler. Latching first fixes the wedge; clearing in the `except`
    is what keeps a transient Finnhub failure from burning the whole 24h
    window, which is what the original "latch only on success" comment was for.

    Structural, like the guards above: read off the AST of the handler so no
    prose about the pattern can satisfy it.
    """
    cleared = False
    for node in ast.walk(_tick_node()):
        if not isinstance(node, ast.Try):
            continue
        calls = {
            getattr(sub.func, "id", None)
            for sub in ast.walk(node) if isinstance(sub, ast.Call)
        }
        if "_seed_calendar" not in calls:
            continue
        for handler in node.handlers:
            for sub in ast.walk(handler):
                if (
                    isinstance(sub, ast.Assign)
                    and any(
                        isinstance(t, ast.Name) and t.id == "_last_calendar_seed"
                        for t in sub.targets
                    )
                    and isinstance(sub.value, ast.Constant)
                    and sub.value.value is None
                ):
                    cleared = True
    assert cleared, (
        "the calendar seed's exception handler does not reset "
        "_last_calendar_seed to None. Latching before the await without "
        "clearing on failure turns a transient feed error into a 24h skip."
    )


# NOTE ON WHAT IS NOT TESTED HERE
# ------------------------------
# An end-to-end version of this - drive tick() twice under a short watchdog and
# assert the stubbed stage ran once, not twice - was written and DID reproduce
# the bug exactly ("ran 2 times across two ticks"). It is not kept: tick()
# runs the scoring pass, which upserts the mock universe into the SHARED test
# database, and that broke
# test_universe_bootstrap::test_never_scored_tickers_are_admitted whenever the
# two files ran in the same session. A guard that corrupts an unrelated test is
# a worse trade than the coverage it buys.
#
# The three structural assertions above pin the same defect - all three were
# watched red against the pre-fix worker - but they are structural: they will
# not notice a THIRD stage in tick() acquiring the same latch-after-await
# shape. If one does, the symptom is `tick.timeout ... stage=<name>` with a
# climbing consecutive count in the production logs, and the fix is to add that
# stage to the parametrised list above.
