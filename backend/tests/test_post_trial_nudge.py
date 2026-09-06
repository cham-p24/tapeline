"""A user whose trial ended is not the same as one who never had a trial.

Both sit on tier "free" and nothing else about the row distinguishes them at a
glance, so the in-app upgrade prompt treated them identically: a generic "here
is what you are missing" pitch. That is the one message that cannot land on
someone who spent 30 days using exactly those features. They do not need the
product explained; they need to know they are back on Free, what specifically
stopped, and what restarting costs.

The distinction has to be made server-side because `trial_ends_at` alone
cannot make it. It stays set after a trial finishes, and legacy no-card trials
have it set with no `trial_started_at` at all — which is precisely why that
second column exists. Both are required: started, and finished.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import User
from app.routers.me import _upgrade_nudge


async def _user(**over) -> User:
    uid = f"u_{uuid.uuid4().hex}"
    fields = {
        "id": uid,
        "email": f"{uid}@example.com",
        "name": "Nudge probe",
        "tier": "free",
        "password_hash": "x",
        "drip_state": "",
    }
    fields.update(over)
    async with session_scope() as s:
        s.add(User(**fields))
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


async def _cleanup(user: User) -> None:
    async with session_scope() as s:
        await s.execute(delete(User).where(User.id == user.id))


@pytest.mark.asyncio
async def test_a_finished_trial_is_reported_to_the_prompt():
    """The whole point: the frontend keys its message off this date."""
    ended = datetime.now(UTC) - timedelta(days=3)
    user = await _user(
        trial_started_at=ended - timedelta(days=30), trial_ends_at=ended
    )
    try:
        nudge = _upgrade_nudge(user)
        assert nudge is not None
        assert nudge["trial_ended_on"] == ended.date().isoformat(), (
            "a user whose trial has ended is indistinguishable from one who "
            "never had one, so they get sold the product they already used"
        )
        assert nudge["id"] == "post_trial_upgrade"
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_someone_who_never_trialled_gets_the_ordinary_prompt():
    """No false claim that a trial ended. They have not seen the product."""
    user = await _user()
    try:
        nudge = _upgrade_nudge(user)
        assert nudge is not None
        assert nudge["trial_ended_on"] is None, (
            "a user who never started a trial would be told their trial ended"
        )
        assert nudge["id"] == "free_upgrade"
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_a_legacy_no_card_trial_does_not_count_as_a_finished_trial():
    """`trial_ends_at` set with no `trial_started_at` is the legacy auto-grant.

    Those accounts were given Premium at signup without ever choosing a trial.
    Telling one of them "your Premium trial ended" describes something they
    never opted into, which is why the check requires BOTH columns.
    """
    user = await _user(
        trial_started_at=None, trial_ends_at=datetime.now(UTC) - timedelta(days=90)
    )
    try:
        nudge = _upgrade_nudge(user)
        assert nudge is not None
        assert nudge["trial_ended_on"] is None
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_a_trial_still_running_is_not_reported_as_ended():
    """Mid-trial, the user IS on Premium. Nudging them would be incoherent."""
    user = await _user(
        trial_started_at=datetime.now(UTC) - timedelta(days=5),
        trial_ends_at=datetime.now(UTC) + timedelta(days=25),
    )
    try:
        nudge = _upgrade_nudge(user)
        # tier is "free" in this fixture, so a nudge is returned — but it must
        # not claim the trial is over while it is still running.
        assert nudge is not None
        assert nudge["trial_ended_on"] is None, (
            "a live trial was reported as ended; the user would be told to "
            "re-subscribe to something they are currently using"
        )
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_paying_customers_get_no_prompt_at_all():
    """Unchanged behaviour, asserted because the branch above sits under it."""
    for tier in ("pro", "premium"):
        user = await _user(
            tier=tier,
            trial_started_at=datetime.now(UTC) - timedelta(days=60),
            trial_ends_at=datetime.now(UTC) - timedelta(days=30),
        )
        try:
            assert _upgrade_nudge(user) is None, (
                f"a paying {tier} customer was shown an upgrade prompt"
            )
        finally:
            await _cleanup(user)


@pytest.mark.asyncio
async def test_a_naive_trial_end_is_not_treated_as_the_future():
    """Postgres hands back tz-aware datetimes; SQLite and older rows may not.

    Comparing a naive datetime against an aware `now` raises TypeError, which
    inside this hot endpoint would surface as a 500 on /api/me — the call every
    authenticated page makes on load.
    """
    user = await _user(
        trial_started_at=datetime(2026, 1, 1),
        trial_ends_at=datetime(2026, 2, 1),  # naive, well in the past
    )
    try:
        nudge = _upgrade_nudge(user)
        assert nudge is not None
        assert nudge["trial_ended_on"] == "2026-02-01"
    finally:
        await _cleanup(user)
