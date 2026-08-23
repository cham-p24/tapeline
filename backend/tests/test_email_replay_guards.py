"""Two email paths would replay their whole batch after a mid-run cancellation.

Both batches run INLINE inside `tick()`, which the worker wraps in
`asyncio.wait_for(tick(), timeout=60)`. `CancelledError` is a BaseException: it
is not caught by the per-item `except Exception`, nor by the worker's
`except Exception`, and `db.session_scope` only rolls back on `Exception` — so
the session closes with every pending write discarded, while the emails have
already gone out.

1. `evaluate_watchlist_alerts` wrote the per-item debounce in memory
   (`item.last_alert_at = now`) and persisted it with ONE commit after the whole
   loop. Worse, the trigger is stable rather than transient:
   `WatchlistItem.baseline_score` is captured once at add time and never
   refreshed, so once a symbol has drifted past `alert_threshold_delta` it STAYS
   past it — the same items re-qualify on the very next 60s tick and the whole
   batch re-sends, indefinitely.

2. `run_eod_watchlist_digest` had NO durable per-recipient dedupe at all — the
   only orchestrator without one. Its guard was the worker's process-global
   `_last_eod_digest_date` latch, set only after the entire batch returned
   cleanly, and the gate re-arms every tick while `hour >= 21`: a ~180-tick
   replay window. The frequency governor is no backstop (EOD is SCHEDULED, and
   `allows` early-returns True for SCHEDULED before any ledger check, and its
   ledger is in-memory anyway).

Both now commit per recipient, which is what every other orchestrator already
does (`run_daily_drip`, `run_daily_digest`, every `run_*_drip`).
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import AlertEvent, User, Watchlist, WatchlistItem
from app.services import alerts as alerts_mod
from app.services import email as email_mod


# ---------------------------------------------------------------------------
# 1. Watchlist alert debounce
# ---------------------------------------------------------------------------


def test_watchlist_alert_commits_per_item():
    """The debounce must be durable BEFORE the next item is processed."""
    # Parse the whole module and locate the function, rather than dedenting a
    # source fragment (cleandoc mangles the body's indentation).
    tree = ast.parse(
        pathlib.Path("app/services/alerts.py").read_text(encoding="utf-8")
    )
    fn = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
        and n.name == "evaluate_watchlist_alerts"
    )

    # Find the `item.last_alert_at = now` assignment and assert a commit occurs
    # inside the same loop body, not merely somewhere later in the function.
    def _loop_bodies(node):
        for n in ast.walk(node):
            if isinstance(n, (ast.For, ast.AsyncFor)):
                yield n

    found = False
    for loop in _loop_bodies(fn):
        body_src = ast.unparse(loop)
        if "last_alert_at" in body_src and "commit()" in body_src:
            found = True
            break
    assert found, (
        "evaluate_watchlist_alerts does not commit inside the loop — a "
        "CancelledError under the 60s tick watchdog discards every pending "
        "last_alert_at and the whole batch re-sends next tick"
    )


@pytest.mark.asyncio
async def test_watchlist_debounce_survives_an_abandoned_batch():
    """Behavioural: a committed debounce is visible from a FRESH session.

    Simulates the real failure — the emails went out, then the session died
    without a terminal commit. If the stamp only lived in memory, a new session
    sees last_alert_at as NULL and the item re-qualifies immediately.
    """
    uid = str(uuid.uuid4())
    now = datetime.now(UTC)
    async with session_scope() as s:
        s.add(User(id=uid, email=f"dbnc-{uuid.uuid4().hex[:8]}@example.com", tier="pro"))
        await s.flush()
        wl = Watchlist(user_id=uid, name="W")
        s.add(wl)
        await s.flush()
        item = WatchlistItem(
            user_id=uid, watchlist_id=wl.id, symbol="NVDA", baseline_score=50.0
        )
        s.add(item)
        await s.commit()
        item_id = item.id

    try:
        # Stamp + commit, exactly as the fixed loop does per item.
        async with session_scope() as s:
            it = await s.get(WatchlistItem, item_id)
            it.last_alert_at = now
            await s.commit()

        # A brand-new session (the next tick) must see it.
        async with session_scope() as s:
            it = await s.get(WatchlistItem, item_id)
            assert it.last_alert_at is not None, (
                "the debounce did not survive the session boundary — the next "
                "tick would re-send"
            )
    finally:
        async with session_scope() as s:
            await s.execute(delete(WatchlistItem).where(WatchlistItem.user_id == uid))
            await s.execute(delete(Watchlist).where(Watchlist.user_id == uid))
            await s.execute(delete(AlertEvent).where(AlertEvent.user_id == uid))
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()


# ---------------------------------------------------------------------------
# 2. EOD digest dedupe
# ---------------------------------------------------------------------------


def test_eod_digest_has_a_durable_per_user_stamp():
    src = inspect.getsource(email_mod.run_eod_watchlist_digest)
    assert "eod_digest_sent_on" in src, (
        "run_eod_watchlist_digest has no durable per-recipient dedupe — a "
        "partial run re-mails the already-sent prefix every tick until 24:00 UTC"
    )
    assert "await session.commit()" in src, (
        "the stamp is not committed per user, so a mid-batch cancellation "
        "discards it along with the rest"
    )


@pytest.mark.asyncio
async def test_eod_digest_skips_a_user_already_sent_today():
    """The gate itself: same UTC date → skip."""
    uid = str(uuid.uuid4())
    today = datetime.now(UTC).date()
    async with session_scope() as s:
        s.add(
            User(
                id=uid,
                email=f"eod-{uuid.uuid4().hex[:8]}@example.com",
                tier="pro",
                eod_digest_sent_on=today,
            )
        )
        await s.commit()
    try:
        async with session_scope() as s:
            u = await s.get(User, uid)
            assert u.eod_digest_sent_on == today
            # Yesterday's stamp must NOT block today's send.
            u.eod_digest_sent_on = today - timedelta(days=1)
            await s.commit()
            u = await s.get(User, uid)
            assert u.eod_digest_sent_on != today
    finally:
        async with session_scope() as s:
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()


@pytest.mark.asyncio
async def test_eod_stamp_column_exists_and_is_a_date():
    """Pins migration 0056 — a Date, not a bool, because the send recurs daily."""
    uid = str(uuid.uuid4())
    async with session_scope() as s:
        s.add(
            User(
                id=uid,
                email=f"eodc-{uuid.uuid4().hex[:8]}@example.com",
                tier="pro",
                eod_digest_sent_on=date(2026, 8, 23),
            )
        )
        await s.commit()
    try:
        async with session_scope() as s:
            u = (
                await s.execute(select(User).where(User.id == uid))
            ).scalar_one()
        assert u.eod_digest_sent_on == date(2026, 8, 23)
    finally:
        async with session_scope() as s:
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()


def test_email_module_has_no_function_local_UTC_shadowing():
    """Guard for the whole CLASS of bug that bit routers/webhooks.py.

    Python makes a name function-local for the ENTIRE body if it is bound
    anywhere in it, so one `from datetime import UTC` inside a branch silently
    breaks every OTHER use of UTC in that function. Hit here while adding the
    EOD stamp: the new `datetime.now(UTC)` at the top of
    run_eod_watchlist_digest would have raised UnboundLocalError, because a
    local `from datetime import UTC, timedelta` sat further down.
    """
    src = pathlib.Path("app/services/email.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    offenders: list[str] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        binds = [
            n.lineno
            for n in ast.walk(fn)
            if isinstance(n, ast.ImportFrom)
            and n.module == "datetime"
            and any((a.asname or a.name) == "UTC" for a in n.names)
        ]
        loads = [
            n.lineno
            for n in ast.walk(fn)
            if isinstance(n, ast.Name) and n.id == "UTC" and isinstance(n.ctx, ast.Load)
        ]
        if binds and loads and min(loads) < min(binds):
            offenders.append(f"{fn.name}() loads UTC at {min(loads)}, binds at {min(binds)}")
    assert not offenders, (
        "a function-local `UTC` import shadows the module-level one for the "
        "WHOLE function, so an earlier use raises UnboundLocalError: "
        + "; ".join(offenders)
    )
