"""Cross-process locks for jobs that must have exactly one writer.

WHY THIS EXISTS
---------------
Every "run this once per day" guard in `signal_publisher` is a process-global
variable (`_last_*`, signal_publisher.py:203-231). Those dedupe within one
process and not at all across machines. Fly runs a STANDBY worker machine beside
the primary, and on 2026-09-08 `fly status -a tapeline-backend` showed BOTH
`started` and both emitting `tick.timeout` logs — i.e. both actively running
`tick()`, not one idling:

    worker  2879770f913628  started  2026-09-08T14:03:39Z
    worker† 080e971dad0298  started  2026-09-08T14:03:45Z
    † Standby machine (it will take over only in case of host hardware failure)

So every one of those latches has been giving a guarantee it never had. That was
harmless only because the `score_upsert` timeout has been killing each tick long
before the downstream stages ran at all.

ONLY THE TRANSACTION-SCOPED VARIANT IS SAFE HERE
------------------------------------------------
Production `DATABASE_URL` points at Neon's `-pooler` host — PgBouncer in
transaction mode, see `db.is_transaction_pooled` — which hands one client
connection to a DIFFERENT server backend between transactions. A session-scoped
`pg_advisory_lock` taken in one transaction is therefore held on a backend that
is then handed to somebody else: it protects nothing, and it fails silently.
The same multiplexing already broke prepared statements on this infrastructure
(see `db.build_engine_kwargs`). A transaction-scoped lock lives inside a single
transaction, which PgBouncer keeps pinned to one backend, so it is safe.

This is why the fix is in the database and not in `fly scale count worker=1`:
destroying the standby machine would trade a correctness bug for the loss of
host-failure failover.

NOT A CORRECTNESS GUARANTEE ON ITS OWN
--------------------------------------
No-op on SQLite (dev, and the entire test suite), which is single-process by
construction. Callers must therefore never depend on this for the correctness of
WHAT they write. It decides *who writes*; a unique constraint decides *what the
table is allowed to contain*. Both, or neither is worth much.
"""
from __future__ import annotations

import functools
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: Namespace for every Tapeline advisory lock, so an id here can never collide
#: with one taken by an extension or by a future caller.
LOCK_NAMESPACE = 8266

#: Registry of lock ids. Add here; never reuse a number.
LOCK_SCORECARD_FREEZE = 1
LOCK_DAILY_NEWSLETTER = 2
LOCK_DAILY_DRIPS = 3
LOCK_EOD_DIGEST = 4
LOCK_WEEKLY_NEWSLETTER = 5
LOCK_CHECKOUT_RECOVERY = 6
LOCK_ACTIVATION_NUDGE = 7
LOCK_SEO_DIGEST = 8
LOCK_SURVEY_REMINDER = 9


async def try_xact_lock(session: AsyncSession, objid: int) -> bool:
    """Try to take transaction-scoped advisory lock `objid`. Never waits.

    Returns True when this transaction now holds it, or when the dialect has no
    advisory locks (SQLite). Returns False when another transaction — on this
    machine or any other — holds it right now; the caller should SKIP its work
    rather than block on it. Skipping is the right move for a periodic job:
    whoever holds the lock is already doing the work, and the caller comes back
    next tick.

    The lock releases on COMMIT or ROLLBACK, so a worker that is killed
    mid-transaction (which is exactly what the tick watchdog does) cannot strand
    it and leave the job permanently unrunnable.
    """
    if session.get_bind().dialect.name != "postgresql":
        return True
    return bool(
        await session.scalar(
            text("SELECT pg_try_advisory_xact_lock(:ns, :obj)"),
            {"ns": LOCK_NAMESPACE, "obj": objid},
        )
    )


@asynccontextmanager
async def hold_xact_lock(objid: int) -> AsyncIterator[bool]:
    """Hold advisory lock `objid` in a session of its own, and say who won.

    `try_xact_lock` above is enough for a job that writes once and commits
    once — the scorecard freeze. It is NOT enough for the email jobs, and the
    reason is worth stating plainly, because it looks like it should be.

    A transaction-scoped lock releases on COMMIT. Both email jobs commit ONCE
    PER RECIPIENT, deliberately: a failure on one row must not roll back the
    delivery record of everyone the provider has already sent to (see the
    comments at newsletter.run_daily_digest and email.run_daily_drip). So a
    lock taken on the working session would be released by the first
    subscriber's commit, and the other machine would take it and start sending
    from row two. The lock would be doing nothing, and — as with the
    session-scoped variant above — nothing would raise.

    Holding it on a SEPARATE session solves that. The lock session opens a
    transaction, takes the lock, and then sits idle for the duration while the
    caller works on its own session and commits as often as it likes. Being a
    real open transaction, PgBouncer keeps it pinned to one backend, which is
    the property the module docstring says is required.

    WHAT THIS PROTECTS, CONCRETELY
    Both email jobs are read-then-send-then-record: SELECT everyone who has
    not been sent to today, then loop. Two machines that both SELECT before
    either commits get the same list and both send it. The per-row commit
    makes a RESTART replay-safe — the next process re-reads and sees the
    record — and does nothing at all about a machine running right now. The
    newsletter goes to the whole confirmed list; the drips go to people in a
    trial. Sending either twice is the kind of thing a subscriber remembers.

    Yields True when this process holds the lock and should do the work, False
    when another machine holds it and this one should skip. Never blocks —
    whoever holds it is already doing the job.
    """
    from app.db import session_scope

    async with session_scope() as lock_session:
        yield await try_xact_lock(lock_session, objid)
        # session_scope commits on the way out, which releases the lock. That
        # is the intended release point: the caller is done.


def one_machine_at_a_time(
    objid: int,
    name: str,
    *,
    default_factory: Callable[[], Any] = lambda: None,
) -> Callable[[Any], Any]:
    """Let only one machine run the decorated job at a time.

    A DECORATOR rather than a wrapper at the call site, for two reasons.

    The first is that the guard then travels with the job. #799 put the lock
    at the two dispatch sites in tick() and said in its own description that
    "a guard repeated twelve times is a guard that will be missed on the
    thirteenth" — and it was: five more email jobs in the same tick were left
    with nothing but their process-global `_last_*` latch, which on a
    two-machine deploy has never guaranteed anything (see the module
    docstring). Decorating the entry point means a future caller cannot
    reintroduce the bug by calling it from somewhere new.

    The second is that it does not touch the body. Each of these jobs is a
    gated try/except block inside tick(); wrapping them in place would mean
    re-indenting five live email paths, which is a lot of risk for a change
    whose entire purpose is to stop mail going out twice.

    `default_factory` supplies the return value when this machine loses the
    lock, and it matters: the callers do `if count:` and
    `if any(counts.values())`, so a job returning counts must lose with an
    empty dict and one returning a number with 0. Returning None to a caller
    expecting a dict would trade a duplicate email for a crash.
    """
    def _decorate(fn):  # type: ignore[no-untyped-def]
        @functools.wraps(fn)
        async def _wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
            async with hold_xact_lock(objid) as won:
                if not won:
                    logger.info("%s.skipped_other_machine_is_running", name)
                    return default_factory()
                return await fn(*args, **kwargs)

        # Read by test_no_email_job_is_left_unlocked, which derives the list of
        # jobs that need this from tick()'s own source rather than a list
        # somebody has to remember to update.
        _wrapped._one_machine_lock_id = objid  # type: ignore[attr-defined]
        _wrapped._one_machine_name = name      # type: ignore[attr-defined]
        # Exposed so the guard can check the loss value against how tick()
        # actually consumes each result, not just that one was supplied.
        _wrapped._one_machine_default_factory = default_factory  # type: ignore[attr-defined]
        return _wrapped

    return _decorate
