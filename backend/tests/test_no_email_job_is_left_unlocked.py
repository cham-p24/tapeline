"""No job that sends mail may run on both machines at once.

#799 fixed the daily newsletter and the daily drips by putting a
cross-machine lock at their two dispatch sites in tick(). Its own description
said "a guard repeated twelve times is a guard that will be missed on the
thirteenth" — and then missed five:

    run_eod_watchlist_digest            -> Premium users' watchlists
    run_weekly_newsletter               -> the whole confirmed list
    run_checkout_abandonment_recovery   -> people who left a card at checkout
    run_activation_nudge_drip           -> users mid-trial
    run_weekly_digest (seo_health)      -> the founder

Every one of them was gated by nothing but a process-global `_last_*` latch,
which on a two-machine deploy has never guaranteed anything (see
services/dblock's module docstring, and #796 for how that was established).

So this file does not carry a list of jobs to protect. It DERIVES the list
from tick()'s own source and from what those functions actually do, and fails
if any of them is unlocked. Adding a sixth email job to the tick without a
lock fails the build rather than sending someone two of the same email.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from app.services import dblock

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SERVICE_FILES = (
    _ROOT / "app" / "services" / "email.py",
    _ROOT / "app" / "services" / "newsletter.py",
    _ROOT / "app" / "services" / "seo_health.py",
)


def _tick_source() -> str:
    from app.workers import signal_publisher as sp

    return inspect.getsource(sp.tick)


def _mailing_entry_points() -> set[str]:
    """Public `run_*` coroutines in the mail services whose body sends mail."""
    found: set[str] = set()
    for path in _SERVICE_FILES:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            if not node.name.startswith("run_"):
                continue
            body = ast.get_source_segment(src, node) or ""
            # All three transports. `send_message` is the Telegram ops bot and
            # was the one this scan originally missed: run_weekly_digest sends
            # with it, so mutation-testing showed the job could be
            # un-decorated with every test still green. A guard that only
            # knows some of the ways a job can reach a human is not a guard.
            if any(t in body for t in ("send_email", "send_telegram", "send_message")):
                found.add(node.name)
    return found


def _called_directly_by_tick() -> set[str]:
    """Mailing entry points tick() calls itself, rather than via a wrapper."""
    src = _tick_source()
    return {name for name in _mailing_entry_points() if f"{name}(" in src}


# ── the derivation itself has to work ──────────────────────────────────────

def test_the_scan_finds_the_mail_senders():
    """A guard that silently matches nothing passes forever."""
    senders = _mailing_entry_points()
    assert len(senders) >= 10, (
        f"only found {len(senders)} mail-sending entry points, which means the "
        f"AST scan has stopped matching and this whole file is now vacuous"
    )
    assert "run_daily_drip" in senders
    assert "run_eod_watchlist_digest" in senders
    assert "run_weekly_digest" in senders   # Telegram, not email — see above


def test_tick_calls_at_least_one_of_them_directly():
    """Same reason: if this set empties, the main test below proves nothing."""
    assert _called_directly_by_tick(), (
        "tick() no longer appears to call any mail-sending job directly — "
        "either the call sites moved (fine, but re-point this file) or the "
        "scan broke (not fine)"
    )


# ── the invariant ──────────────────────────────────────────────────────────

def test_no_email_job_is_left_unlocked():
    """Every mail sender tick() calls directly must hold a cross-machine lock.

    Not a hand-written list. If someone adds `run_something_drip` to the tick
    tomorrow, it appears here automatically and fails until it is decorated.
    """
    import app.services.email as email_mod
    import app.services.newsletter as nl_mod
    import app.services.seo_health as seo_mod

    unlocked: list[str] = []
    for name in sorted(_called_directly_by_tick()):
        fn = (
            getattr(email_mod, name, None)
            or getattr(nl_mod, name, None)
            or getattr(seo_mod, name, None)
        )
        assert fn is not None, f"{name} is called by tick() but cannot be imported"
        if getattr(fn, "_one_machine_lock_id", None) is None:
            unlocked.append(name)

    assert not unlocked, (
        f"{unlocked} send mail and are called straight from tick(), with no "
        f"cross-machine lock. Both worker machines run tick(), so every "
        f"recipient gets two. Decorate with dblock.one_machine_at_a_time."
    )


def test_every_lock_id_is_unique():
    """Two jobs sharing an id would block each other for no reason — and worse,
    one would skip because an unrelated job holds it."""
    ids = {
        n: getattr(dblock, n)
        for n in dir(dblock)
        if n.startswith("LOCK_") and n != "LOCK_NAMESPACE"
    }
    assert len(ids) >= 8
    assert len(set(ids.values())) == len(ids), f"duplicate lock id: {ids}"


# ── losing the lock must not break the caller ──────────────────────────────

@pytest.mark.asyncio
async def test_a_job_that_loses_returns_what_its_caller_expects(monkeypatch):
    """The subtle way this fix could cause an outage instead of preventing one.

    tick() does `if count:` for the digests and `if any(counts.values())` for
    the drip-style jobs. A job that loses the lock and returns None would turn
    a duplicate email into an AttributeError inside the tick — trading a
    embarrassing bug for a breaking one. Each decoration therefore declares
    what losing looks like.
    """
    async def _never_runs(*a, **k):
        raise AssertionError("body ran despite losing the lock")

    async def _lost(session, objid):
        return False

    monkeypatch.setattr(dblock, "try_xact_lock", _lost)

    counts = dblock.one_machine_at_a_time(99, "t", default_factory=dict)(_never_runs)
    number = dblock.one_machine_at_a_time(98, "t", default_factory=int)(_never_runs)

    got_counts = await counts()
    got_number = await number()

    assert got_counts == {}
    assert any(got_counts.values()) is False     # the exact call tick() makes
    assert got_number == 0
    assert not got_number


@pytest.mark.asyncio
async def test_the_winner_still_does_the_work(monkeypatch):
    """A guard that never lets anything through is not a fix."""
    ran: list[int] = []

    async def _body(*a, **k):
        ran.append(1)
        return {"sent": 3}

    async def _won(session, objid):
        return True

    monkeypatch.setattr(dblock, "try_xact_lock", _won)

    wrapped = dblock.one_machine_at_a_time(97, "t", default_factory=dict)(_body)
    assert await wrapped() == {"sent": 3}
    assert ran == [1]


def test_the_decorator_keeps_the_functions_identity():
    """functools.wraps, so tracebacks and monkeypatching still make sense."""
    from app.services.email import run_eod_watchlist_digest

    assert run_eod_watchlist_digest.__name__ == "run_eod_watchlist_digest"
    assert run_eod_watchlist_digest.__doc__


def test_each_decorated_job_loses_with_the_shape_its_caller_expects():
    """Testing the decorator does not test the decorations.

    `test_a_job_that_loses_returns_what_its_caller_expects` above exercises
    the decorator in isolation. It says nothing about whether
    run_checkout_abandonment_recovery was actually given
    `default_factory=dict` — and mutation-testing showed that argument could
    be deleted with every test still green. tick() then evaluates
    `any(None.values())` and the whole tick dies, which is a worse outcome
    than the duplicate email this was added to prevent.

    So check the REAL decorations against how tick() consumes each result: a
    name tick() calls `.values()` on has to lose with a dict.
    """
    import re

    import app.services.email as email_mod
    import app.services.newsletter as nl_mod
    import app.services.seo_health as seo_mod

    tick_src = _tick_source()
    problems: list[str] = []

    for name in sorted(_called_directly_by_tick()):
        fn = (
            getattr(email_mod, name, None)
            or getattr(nl_mod, name, None)
            or getattr(seo_mod, name, None)
        )
        factory = getattr(fn, "_one_machine_default_factory", None)
        if factory is None:
            problems.append(f"{name}: decorated without a declared loss value")
            continue

        lost = factory()
        if lost is None:
            problems.append(
                f"{name}: loses the lock with None, which no caller in tick() "
                f"can use"
            )
            continue

        # How does tick() bind and then use this call's result?
        bound = re.search(r"(\w+)\s*=\s*await\s+" + name + r"\(", tick_src)
        if bound:
            var = bound.group(1)
            uses_values = re.search(r"\b" + var + r"\.values\(\)", tick_src)
            if uses_values and not isinstance(lost, dict):
                problems.append(
                    f"{name}: tick() calls {var}.values(), so losing the lock "
                    f"must yield a dict, not {type(lost).__name__}"
                )

    assert not problems, "; ".join(problems)

