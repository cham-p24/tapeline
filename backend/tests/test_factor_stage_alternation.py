"""The second factor pass must not be starved by the first one's budget.

MEASURED ON PRODUCTION 2026-09-07 (read-only SQL), one day after the fix that
moved both factor passes to the FRONT of the daily Finnhub chain:

    last_fundamentals_at stamped: 1,320 rows
    last_smart_money_at  stamped:     0 rows   <-- of 11,781

Zero. Not "behind" - the insider pass had never completed a single symbol since
the stamp column shipped, so `sub_smart_money` (15% of the composite) was
NEUTRAL 50 across the entire universe.

WHY ORDERING COULD NOT FIX IT
-----------------------------
The chain ran the passes one after the other, each with a per-run budget of
ACTIVE_UNIVERSE_SIZE = 12,000. At the mandatory 1.1s Finnhub pacing that is
~3.7 HOURS for the first pass alone, so the second only began on a process that
had already survived 3.7 uninterrupted hours. Production restarts on every
deploy and never did. Whichever pass ran second was guaranteed to starve, so
swapping them would only have moved the hole from smart-money to fundamentals.

The passes now ALTERNATE in `_FACTOR_SLICE`-sized slices, so one round advances
both and a restart leaves them within a slice of each other.

The comment blocks in the chain had also under-counted it: they described a
"~2h chain" off a "per-run budget of 2,500" when the budget was 12,000. That
5x error is what let a total starvation read as a queue.

These tests pair a behavioural check (the `limit` argument genuinely bounds a
pass) with a structural one (the chain actually passes it, in a loop). Either
alone is vouchable: a source assertion cannot tell whether the parameter does
anything, and a behavioural test on the pass alone cannot see that the chain
still calls it unbounded.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
from datetime import UTC, datetime
from typing import Any

import pytest

from app.db import session_scope
from app.models import Ticker
from app.workers import signal_publisher

# NO `pytestmark = pytest.mark.anyio` - pytest.ini sets `asyncio_mode = auto`.


async def _seed(symbols: list[str]) -> None:
    async with session_scope() as s:
        for i, sym in enumerate(symbols):
            s.add(Ticker(
                symbol=sym, name=f"{sym} Inc", asset_class="equity",
                price=100.0, volume=1_000_000 - i,
            ))


@pytest.fixture(autouse=True)
def _no_pacing_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """The passes sleep 1.1s per symbol to stay under Finnhub's 60/min."""
    async def _noop(_seconds: float) -> None:
        return None
    monkeypatch.setattr(signal_publisher.asyncio, "sleep", _noop)


def _chain_node() -> ast.AsyncFunctionDef:
    tree = ast.parse(
        pathlib.Path(inspect.getfile(signal_publisher)).read_text(encoding="utf-8")
    )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AsyncFunctionDef)
            and node.name == "_serial_finnhub_refreshes"
        ):
            return node
    raise AssertionError("_serial_finnhub_refreshes not found")


_FACTOR_PASSES = ("_refresh_fundamentals_cache", "_refresh_insider_cache")


def _factor_calls() -> dict[str, ast.Call]:
    found: dict[str, ast.Call] = {}
    for sub in ast.walk(_chain_node()):
        if isinstance(sub, ast.Call) and getattr(sub.func, "id", None) in _FACTOR_PASSES:
            found[sub.func.id] = sub
    return found


# -- structural: the chain must not hand either pass an unbounded budget -------

def test_the_chain_bounds_both_factor_passes_with_the_slice_constant() -> None:
    calls = _factor_calls()
    assert set(calls) == set(_FACTOR_PASSES), (
        f"a factor pass vanished from the chain: found {sorted(calls)}"
    )
    for name, call in calls.items():
        limits = [kw for kw in call.keywords if kw.arg == "limit"]
        assert limits, (
            f"{name} is called with no `limit`, i.e. the full-universe budget "
            f"of ACTIVE_UNIVERSE_SIZE. At 1.1s/request that is ~3.7 hours, "
            f"and it is why the pass behind it never ran at all"
        )
        assert getattr(limits[0].value, "id", None) == "_FACTOR_SLICE", (
            f"{name} must be sliced with _FACTOR_SLICE, not an ad-hoc number"
        )


def test_the_factor_passes_run_inside_a_loop_so_they_alternate() -> None:
    """One slice each is not enough - the phase has to keep alternating.

    Without the loop the chain would close _FACTOR_SLICE rows per pass per
    process and the ~11,800-row universe would never converge.
    """
    loops = [
        node for node in ast.walk(_chain_node())
        if isinstance(node, (ast.While, ast.For, ast.AsyncFor))
    ]
    assert loops, "the factor phase is not a loop, so coverage cannot converge"
    looped = {
        sub.func.id
        for loop in loops for sub in ast.walk(loop)
        if isinstance(sub, ast.Call)
        and getattr(sub.func, "id", None) in _FACTOR_PASSES
    }
    assert looped == set(_FACTOR_PASSES), (
        f"only {sorted(looped)} runs inside the alternating loop; both passes "
        f"must, or the one left outside gets a single slice per process"
    )


def test_a_slice_is_far_smaller_than_the_full_universe_budget() -> None:
    """The constant has to be small enough to survive a deploy cadence.

    12,000 rows at 1.1s is 3.7h. The bound is deliberately loose - it fails the
    class of change that reintroduces the bug (raising the slice back toward
    the universe size), not a considered retune of the number itself.
    """
    from app.services.universe import ACTIVE_UNIVERSE_SIZE
    assert signal_publisher._FACTOR_SLICE < ACTIVE_UNIVERSE_SIZE / 4, (
        f"_FACTOR_SLICE={signal_publisher._FACTOR_SLICE} is a large fraction "
        f"of ACTIVE_UNIVERSE_SIZE={ACTIVE_UNIVERSE_SIZE}; at 1.1s/request one "
        f"slice must finish well inside a process lifetime"
    )


# -- behavioural: `limit` genuinely bounds each pass ---------------------------

async def test_limit_bounds_the_fundamentals_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed([f"F{i:02d}" for i in range(10)])
    monkeypatch.setattr(
        "app.services.universe.ACTIVE_UNIVERSE_SIZE", 10, raising=False,
    )
    seen: list[str] = []

    async def _fake(sym: str) -> dict[str, float]:
        seen.append(sym)
        return {"roe": 15.0}

    monkeypatch.setattr(
        "app.services.finnhub_feed.fetch_basic_financials", _fake,
    )

    await signal_publisher._refresh_fundamentals_cache(limit=3)
    assert len(seen) == 3, (
        f"limit=3 fetched {len(seen)} symbols - an ignored limit is an "
        f"unbounded pass, which is the starvation this guards"
    )


async def test_limit_bounds_the_insider_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed([f"I{i:02d}" for i in range(10)])
    monkeypatch.setattr(
        "app.services.universe.ACTIVE_UNIVERSE_SIZE", 10, raising=False,
    )
    seen: list[str] = []

    async def _fake(sym: str, days_back: int = 90) -> list[dict[str, Any]]:
        seen.append(sym)
        return []

    monkeypatch.setattr(
        "app.services.finnhub_feed.fetch_insider_transactions", _fake,
    )

    await signal_publisher._refresh_insider_cache(limit=3)
    assert len(seen) == 3


async def test_gap_counts_report_each_column_independently() -> None:
    """The loop's exit condition.

    A shared or swapped count would let a closed fundamentals frontier declare
    smart-money done - the exact confusion that produced 1,320 stamps against 0.
    """
    await _seed(["GAPA", "GAPB"])
    assert await signal_publisher._factor_gap_counts() == (2, 2)

    await signal_publisher._stamp_factor_attempts(
        "last_fundamentals_at", ["GAPA", "GAPB"], datetime.now(UTC),
    )
    assert await signal_publisher._factor_gap_counts() == (0, 2), (
        "stamping fundamentals must not clear the smart-money gap"
    )
