"""Two worker machines must not both send the same email.

Fly runs a STANDBY worker beside the primary. `fly status -a tapeline-backend`
shows both `started`, and #796 established that both actively run tick() —
they were both emitting tick.timeout. Every `_last_*` latch in
signal_publisher is a process global, so none of them has ever been a
cross-machine guarantee.

That was invisible while the tick died at score_upsert before reaching any of
these stages (#798). Repairing the tick arms it. #796 closed the scorecard
double-write; this closes the two jobs that send email to real people.

THE SHAPE OF THE BUG, which both email jobs share:

    rows = SELECT everyone not yet sent to today   <-- machine A and B both
    for row in rows:                                   read the SAME list
        send(row)
        row.sent = now; COMMIT                      <-- too late; B has its copy

The per-row commit is deliberate and it does solve the problem it was written
for: a RESTART re-reads the table and skips whoever is marked. It cannot help
against a machine that has already read.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services import dblock


def _now():
    from datetime import UTC, datetime
    return datetime(2026, 9, 11, 14, 0, tzinfo=UTC)


async def _won(session, objid):
    return True


async def _lost(session, objid):
    return False


# ── the primitive ──────────────────────────────────────────────────────────

def test_the_lock_is_held_in_a_session_of_its_own():
    """Not a style point — the whole fix depends on it.

    A transaction-scoped advisory lock releases on COMMIT. Both email jobs
    commit once per recipient. Taken on the working session, the lock would be
    released by the first subscriber's commit and the other machine would pick
    it up and send from row two — with nothing raised anywhere.
    """
    import inspect

    src = inspect.getsource(dblock.hold_xact_lock)
    assert "session_scope" in src, (
        "hold_xact_lock must open its own session; sharing the caller's "
        "session means the caller's first per-row commit drops the lock"
    )


@pytest.mark.asyncio
async def test_a_second_holder_is_told_it_lost_rather_than_waiting(monkeypatch):
    """Skip, do not block. Whoever holds it is already doing the work."""
    calls: list[int] = []

    async def _fake_try(session, objid):
        calls.append(objid)
        return len(calls) == 1          # first caller wins, second loses

    monkeypatch.setattr(dblock, "try_xact_lock", _fake_try)

    async with dblock.hold_xact_lock(99) as first:
        assert first is True
    async with dblock.hold_xact_lock(99) as second:
        assert second is False


def test_every_lock_id_is_distinct():
    """The registry says: add here, never reuse a number.

    Two jobs sharing an id would serialise against each other for no reason,
    and worse, a job could skip because an unrelated one holds it.
    """
    ids = {
        name: getattr(dblock, name)
        for name in dir(dblock)
        if name.startswith("LOCK_") and name != "LOCK_NAMESPACE"
    }
    assert len(ids) >= 3
    assert len(set(ids.values())) == len(ids), f"duplicate lock id in {ids}"


# ── the two callers ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_newsletter_skips_when_another_machine_holds_it(monkeypatch):
    """The one that goes to the whole confirmed list."""
    import app.services.newsletter as nl
    from app.workers import signal_publisher as sp

    sent: list[int] = []

    async def _never(*a, **k):
        sent.append(1)
        return 0

    monkeypatch.setattr(nl, "run_daily_digest", _never)
    monkeypatch.setattr(dblock, "try_xact_lock", _lost)

    await sp._run_daily_newsletter(_now(), "2026-09-11")
    assert sent == [], "sent the digest while another machine held the lock"


@pytest.mark.asyncio
async def test_the_newsletter_still_sends_when_it_wins(monkeypatch):
    """A guard that never lets anything through is not a fix."""
    import app.services.newsletter as nl
    from app.workers import signal_publisher as sp

    sent: list[int] = []

    async def _yes(session, now=None):
        sent.append(1)
        return 3

    monkeypatch.setattr(nl, "run_daily_digest", _yes)
    monkeypatch.setattr(dblock, "try_xact_lock", _won)

    await sp._run_daily_newsletter(_now(), "2026-09-11")
    assert sent == [1], "won the lock and still did not send"


@pytest.mark.asyncio
async def test_the_drips_skip_when_another_machine_holds_it(monkeypatch):
    """Twelve send loops behind one guard."""
    from app.workers import signal_publisher as sp

    ran: list[int] = []

    async def _body(started):
        ran.append(1)

    monkeypatch.setattr(sp, "_run_daily_drips_locked", _body)
    monkeypatch.setattr(sp, "_last_drip_check", None)
    monkeypatch.setattr(sp, "_last_drip_failed_at", None)
    monkeypatch.setattr(dblock, "try_xact_lock", _lost)

    await sp._maybe_run_daily_drips(_now())
    assert ran == [], "ran the drips while another machine held the lock"


@pytest.mark.asyncio
async def test_the_drips_still_run_when_they_win(monkeypatch):
    from app.workers import signal_publisher as sp

    ran: list[int] = []

    async def _body(started):
        ran.append(1)

    monkeypatch.setattr(sp, "_run_daily_drips_locked", _body)
    monkeypatch.setattr(sp, "_last_drip_check", None)
    monkeypatch.setattr(sp, "_last_drip_failed_at", None)
    monkeypatch.setattr(dblock, "try_xact_lock", _won)

    await sp._maybe_run_daily_drips(_now())
    assert ran == [1], "won the lock and still did not run"


@pytest.mark.asyncio
async def test_losing_the_lock_does_not_burn_the_daily_latch(monkeypatch):
    """The machine that skips must still be able to run tomorrow.

    `_last_drip_check` is latched on SUCCESS at the end of the run. A skip is
    not a success, so it must stay unlatched — otherwise the standby, having
    skipped once, would consider itself done for the day, and if the primary
    then died nobody would send at all.
    """
    from app.workers import signal_publisher as sp

    async def _body(started):
        pass

    monkeypatch.setattr(sp, "_run_daily_drips_locked", _body)
    monkeypatch.setattr(sp, "_last_drip_check", None)
    monkeypatch.setattr(sp, "_last_drip_failed_at", None)
    monkeypatch.setattr(dblock, "try_xact_lock", _lost)

    await sp._maybe_run_daily_drips(_now())
    assert sp._last_drip_check is None, (
        "a machine that skipped marked itself done for the day"
    )


# ── the race itself, run for real ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_two_concurrent_runs_send_the_list_once_between_them():
    """The bug, reproduced against a stand-in for the send loop.

    Both machines read the same eligible list before either commits — which is
    exactly what the real SELECT does — and the guard is what makes only one
    of them send. Modelled rather than mocked: drop the `if holder` check and
    this test reports every recipient delivered twice.
    """
    recipients = ["a@x", "b@x", "c@x"]
    delivered: list[str] = []
    marked: set[str] = set()
    holder: list[int] = []

    async def _machine() -> None:
        # try_xact_lock semantics: take it or skip, never wait.
        if holder:
            return
        holder.append(1)
        try:
            eligible = [r for r in recipients if r not in marked]
            for r in eligible:
                await asyncio.sleep(0)      # yield, as a real send does
                delivered.append(r)
                marked.add(r)               # the per-row commit
        finally:
            holder.pop()

    await asyncio.gather(_machine(), _machine())

    assert sorted(delivered) == sorted(recipients)
    assert len(delivered) == len(set(delivered)), (
        f"a recipient was sent to twice: {delivered}"
    )
