"""Shadow logging: record what the removed card wall WOULD have blocked.

There is no A/B test here and there cannot be one. At two to three signups a
month, detecting even a 5% versus 10% difference needs roughly 430 people per
arm; splitting traffic would take decades to resolve and would halve the only
signal there is meanwhile.

Shadow logging answers the narrower question honestly and costs no traffic:
every user gets the current experience, and each recorded action carries
`would_have_been_walled` — computed from the same `services.tier.must_add_card`
predicate the wall itself used. The result is a direct count of product
interactions the wall was preventing.

It also closes a plain measurement gap. Before this, NOTHING recorded that a
user ran a scan: `users.lookups_today` counts ticker pages and `cap_events`
only fires on a refusal, so a free user who ran five scans and hit no limit
left no trace at all.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select

from app.db import session_scope
from app.models import FUNNEL_EVENTS, FunnelEvent, User
from app.services.funnel_events import record_funnel_event
from app.services.tier import CARD_GATE_START, must_add_card


async def _user(**over) -> User:
    uid = f"u_{uuid.uuid4().hex}"
    fields = dict(
        id=uid, email=f"{uid}@example.test", name="Funnel probe",
        tier="free", password_hash="x", drip_state="",
    )
    fields.update(over)
    async with session_scope() as s:
        s.add(User(**fields))
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


async def _cleanup(user: User) -> None:
    async with session_scope() as s:
        await s.execute(delete(FunnelEvent).where(FunnelEvent.user_id == user.id))
        await s.execute(delete(User).where(User.id == user.id))


async def _rows(user_id: str) -> list[FunnelEvent]:
    async with session_scope() as s:
        return list(
            (
                await s.execute(
                    select(FunnelEvent).where(FunnelEvent.user_id == user_id)
                )
            ).scalars().all()
        )


@pytest.mark.asyncio
async def test_a_scan_is_recorded_at_all():
    """The gap this closes. Running a scan used to leave no trace anywhere."""
    user = await _user()
    try:
        await record_funnel_event(user, "scan_run")

        rows = await _rows(user.id)
        assert len(rows) == 1, "a scan produced no funnel row"
        assert rows[0].event == "scan_run"
        assert rows[0].tier == "free"
        assert rows[0].day == datetime.now(UTC).date()
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_the_counterfactual_matches_the_wall_predicate():
    """`would_have_been_walled` must equal what the wall would have decided.

    This is the whole point of the table. If it drifts from `must_add_card`,
    the number being reported is not the wall's cost — it is an artefact.
    """
    # Created after the gate cutover, no card, never trialled: the wall would
    # have stopped this person.
    walled = await _user(created_at=datetime.combine(
        CARD_GATE_START + timedelta(days=1), datetime.min.time(), tzinfo=UTC
    ))
    # Grandfathered — signed up before the cutover, so the wall never applied.
    grandfathered = await _user(created_at=datetime.combine(
        CARD_GATE_START - timedelta(days=30), datetime.min.time(), tzinfo=UTC
    ))
    try:
        for u in (walled, grandfathered):
            await record_funnel_event(u, "scan_run")

        for u in (walled, grandfathered):
            rows = await _rows(u.id)
            assert len(rows) == 1
            assert rows[0].would_have_been_walled == bool(must_add_card(u)), (
                f"counterfactual disagrees with must_add_card for {u.id}; the "
                f"reported wall cost would be wrong"
            )

        # ...and the two accounts genuinely differ, so this is not vacuous.
        assert (await _rows(walled.id))[0].would_have_been_walled is True
        assert (await _rows(grandfathered.id))[0].would_have_been_walled is False
    finally:
        await _cleanup(walled)
        await _cleanup(grandfathered)


@pytest.mark.asyncio
async def test_one_row_per_user_per_event_per_day():
    """Coarse on purpose — 'did they, and when did they start', not 'how often'.

    Enforced by the unique index rather than SELECT-then-INSERT, so two
    concurrent requests race into the constraint instead of into two rows.
    """
    user = await _user()
    try:
        for _ in range(5):
            await record_funnel_event(user, "scan_run")

        assert len(await _rows(user.id)) == 1, "the daily dedup index is not holding"

        # A DIFFERENT event on the same day is its own row.
        await record_funnel_event(user, "ticker_view")
        assert len(await _rows(user.id)) == 2
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_paid_tiers_are_recorded_too():
    """Unlike cap_events, which deliberately refuses them.

    A cap hit is a free->paid signal and a paid ceiling would pollute it.
    Activation is not: whether subscribers actually run scans is exactly as
    worth knowing, and more so if one day nobody renews.
    """
    user = await _user(tier="premium")
    try:
        await record_funnel_event(user, "scan_run")
        rows = await _rows(user.id)
        assert len(rows) == 1 and rows[0].tier == "premium"
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_an_unknown_event_is_dropped_not_written():
    """Same closed-set discipline as CAP_NAMES — a typo must not enter the data.

    CAP_NAMES silently discarded three REAL events for months because they were
    never added to it. So the set is closed, and the test below checks the call
    sites against it rather than trusting the list.
    """
    user = await _user()
    try:
        await record_funnel_event(user, "definitely_not_an_event")
        assert await _rows(user.id) == []
    finally:
        await _cleanup(user)


def test_every_event_name_used_in_the_app_is_declared():
    """The check CAP_NAMES never had.

    `record_funnel_event` drops an undeclared name, so a call site using one
    writes nothing, forever, silently. Scanning the call sites means adding an
    event without declaring it fails here instead of in production six months
    later when someone asks why the number is zero.
    """
    import re
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1] / "app"
    used: set[str] = set()
    for path in app_dir.rglob("*.py"):
        for m in re.finditer(
            r'record_funnel_event\(\s*[^,]+,\s*"([a-z_]+)"', path.read_text(encoding="utf-8")
        ):
            used.add(m.group(1))

    assert used, "no record_funnel_event call sites found — the scan is wrong"
    undeclared = used - set(FUNNEL_EVENTS)
    assert not undeclared, (
        f"these event names are used but not in FUNNEL_EVENTS, so every one of "
        f"them is being silently dropped: {sorted(undeclared)}"
    )


def test_every_declared_event_is_actually_wired_up():
    """The direction the first version of this file MISSED.

    Its sibling above checks used ⊆ declared, which catches a typo at a call
    site. It does not catch the opposite and equally silent failure: an event
    declared in FUNNEL_EVENTS that nothing ever emits. That shipped — three of
    the four declared events had no call site at all, so the shadow log could
    only ever contain `scan_run` and the other three columns would have read
    zero forever while looking like real measurements.

    A zero that means "nobody did this" and a zero that means "nothing records
    this" are indistinguishable in a report, which is the whole reason this
    table exists. So both directions are pinned.
    """
    import re
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1] / "app"
    used: set[str] = set()
    for path in app_dir.rglob("*.py"):
        for m in re.finditer(
            r'record_funnel_event\(\s*[^,]+,\s*"([a-z_]+)"',
            path.read_text(encoding="utf-8"),
        ):
            used.add(m.group(1))

    unwired = set(FUNNEL_EVENTS) - used
    assert not unwired, (
        f"these events are declared but nothing emits them, so their counts "
        f"will read zero forever and look like a real measurement: "
        f"{sorted(unwired)}. Either wire them up or remove them."
    )


@pytest.mark.asyncio
async def test_a_logging_failure_never_breaks_the_caller():
    """It runs on the hot path of ordinary successful requests."""
    user = await _user()
    try:
        # A user object missing the fields must_add_card reads.
        await record_funnel_event(object(), "scan_run")  # must not raise
    finally:
        await _cleanup(user)
