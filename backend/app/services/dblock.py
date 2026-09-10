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

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Namespace for every Tapeline advisory lock, so an id here can never collide
#: with one taken by an extension or by a future caller.
LOCK_NAMESPACE = 8266

#: Registry of lock ids. Add here; never reuse a number.
LOCK_SCORECARD_FREEZE = 1


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
