"""A cadence latch stamped after the work wedges the worker.

THE PATTERN, which has now bitten this codebase five separate times:

    if <due>:
        try:
            await <slow thing>
            _last_x = today          # <-- never runs if the cycle is killed
        except Exception:
            log()

The tick is wrapped in `asyncio.wait_for(tick(), TICK_TIMEOUT_SECONDS)`. A
watchdog kill raises CancelledError, which is a BaseException, so it does not
enter `except Exception` either. Neither the latch nor the rollback runs. The
next tick sees the same stale value, starts the same slow job, and dies in the
same place. Nothing below it ever runs again until something restarts the
process.

Every one of these carries a comment explaining that it latches on success so a
transient failure will retry. That reasoning is correct — for a caught error.
It says nothing about a hang, and a hang is the case that wedges.

FOUND THE HARD WAY, 2026-09-10
The worker went stale between roughly 21:05 and 21:20 UTC and the cloud
watchdog restarted both machines to recover it. Two jobs in that window were
stamped after their await: `_last_eod_digest_date` (hour >= 21) and
`_last_score_snapshot_date` (inside the 21:15 freeze block). The scorecard
freeze sits between them and did not run until the restart, landing at 21:29
instead of 21:15. `score_snapshots` had captured nothing at all for the day.

A hand-written sweep of the latches found four of the five. The fifth is
nested one level deeper, inside the freeze block, and the sweep's walk back to
the enclosing `if` never reached it. The AST check below found it on its first
run — which is the whole argument for deriving the list instead of writing
one.

So this file does not check a list. It walks tick()'s AST and fails on ANY
cadence latch with an await between its gate and its assignment.
"""
from __future__ import annotations

import ast
import inspect
import re

from app.workers import signal_publisher as sp


def _tick_ast() -> ast.AsyncFunctionDef:
    src = inspect.getsource(sp.tick)
    # getsource keeps the original indentation; dedent so it parses standalone.
    lines = src.split("\n")
    pad = len(lines[0]) - len(lines[0].lstrip())
    flat = "\n".join(line[pad:] if len(line) >= pad else line for line in lines)
    tree = ast.parse(flat)
    fn = tree.body[0]
    assert isinstance(fn, ast.AsyncFunctionDef)
    return fn


def _latch_targets(node: ast.AST) -> list[str]:
    """Names like `_last_something` assigned anywhere under `node`."""
    out: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign):
            for tgt in sub.targets:
                if isinstance(tgt, ast.Name) and tgt.id.startswith("_last_"):
                    out.append(tgt.id)
    return out


def _late_latches() -> list[str]:
    """Latches assigned AFTER an await inside the same gated block.

    A latch assigned before every await in its block is safe: the cadence is
    claimed whatever happens to the cycle. One assigned after an await is the
    wedge.
    """
    offenders: list[str] = []

    for node in ast.walk(_tick_ast()):
        if not isinstance(node, ast.If):
            continue
        # Walk the body in order, tracking whether an await has happened yet.
        seen_await = False
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Await):
                    # `_spawn(...)` is dispatch, not work — it cannot block.
                    seen_await = True
                    break
            if seen_await:
                # Anything assigned from here on is stamped after the work.
                for name in _latch_targets(stmt):
                    # Rollback inside `except` is legitimate and always follows
                    # an await; it restores, it does not claim.
                    if not _is_rollback(stmt, name):
                        offenders.append(name)
        # nested Ifs are visited by the outer ast.walk
    return sorted(set(offenders))


def _is_rollback(stmt: ast.AST, name: str) -> bool:
    """True when `name` is only assigned inside an exception handler.

    `_last_x = _x_prev` in an `except` is the correct counterpart to claiming
    the slot up front, not a late stamp.
    """
    for sub in ast.walk(stmt):
        if isinstance(sub, ast.Try):
            for handler in sub.handlers:
                if name in _latch_targets(handler):
                    return True
    return False


def test_no_cadence_latch_is_stamped_after_its_work():
    """The invariant, derived rather than listed."""
    offenders = _late_latches()
    assert not offenders, (
        f"{offenders} are stamped after an await inside their own gated block. "
        f"A cycle killed by the tick watchdog raises CancelledError, which is "
        f"a BaseException: neither the latch nor `except Exception` runs, so "
        f"the next tick restarts the same job and the worker wedges. Claim the "
        f"slot before the work and roll it back inside `except`."
    )


def test_the_five_fixed_ones_claim_before_and_roll_back():
    """Specifically pin the five found on 2026-09-10.

    Deriving the rule is the durable part; naming the instances keeps the
    reason for the change readable when someone opens this file in a year.
    """
    src = inspect.getsource(sp.tick)
    for var, prev in (
        ("_last_eod_digest_date", "_eod_prev"),
        ("_last_weekly_newsletter_token", "_weekly_prev"),
        ("_last_seo_digest_token", "_seo_prev"),
        ("_last_growth_tick_date", "_growth_prev"),
        # The fifth. A hand-written regex sweep found four; this one is nested
        # inside the 21:15 freeze block, so the sweep's backward walk to the
        # enclosing `if` never reached it. The AST guard above found it
        # immediately — which is the argument for deriving over listing.
        ("_last_score_snapshot_date", "_snap_prev"),
    ):
        claim = re.search(rf"{prev} = {var}\s*\n\s*{var} = ", src)
        assert claim, f"{var} no longer claims its slot before the work"
        rollback = re.search(rf"except Exception:\s*\n\s*{var} = {prev}", src)
        assert rollback, (
            f"{var} claims its slot but never rolls it back on a caught "
            f"failure, so one transient error now skips the whole period — "
            f"which is the thing its original comment was protecting"
        )


def test_the_detector_actually_detects():
    """A derived guard that matches nothing passes forever.

    Feed it the exact broken shape and confirm it is reported.
    """
    broken = (
        "async def tick():\n"
        "    global _last_thing\n"
        "    if _last_thing != today:\n"
        "        try:\n"
        "            await slow()\n"
        "            _last_thing = today\n"
        "        except Exception:\n"
        "            log()\n"
    )
    fn = ast.parse(broken).body[0]

    offenders: list[str] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        seen_await = False
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Await):
                    seen_await = True
                    break
            if seen_await and not _is_rollback(stmt, "_last_thing"):
                offenders.extend(_latch_targets(stmt))

    assert "_last_thing" in offenders, (
        "the detector no longer recognises the wedge shape, so "
        "test_no_cadence_latch_is_stamped_after_its_work proves nothing"
    )
