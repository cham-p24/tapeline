"""A card-required trial must hear from us about the product, not only the bill.

WHY THIS EXISTS
---------------
`run_daily_drip` filters on `stripe_customer_id IS NULL`. That is deliberate:
its day-7/11/13 copy says "add a card" and "your account drops to Free", which
is right for the auto-granted card-free trials it was written for and false for
anyone who already has a card on file.

Since #536 every trial IS card-required, so that series reaches nobody, and a
modern trialist's only contact became `run_trial_precharge_drip`'s seven-day
payment notice. Measured 2026-09-06: of five accounts that ever added a card,
three cancelled, and the two still running had not opened the product since the
day they signed up. Sending someone a bill for something they have not used is
not a retention strategy.

`run_carded_trial_drip` fills that gap. These tests pin the three things that
make it safe rather than merely present:

  1. It reaches carded trials and ONLY carded trials -- the exact inverse of
     `run_daily_drip`, with no overlap and no double-send.
  2. Its copy is true for a reader who already has a card: never "add a card",
     never "you will drop to Free" (they will be CHARGED), and the first-charge
     date is the user's own, never a duration derived from TRIAL_DAYS. Trials
     created before #737 really are 14 days, so a constant would misstate the
     charge date to the people nearest one.
  3. It sits clear of the seven-day pre-charge notice's window. That notice is
     a legally-shaped message about money; an email beside it buries the one
     thing that has to be read.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import session_scope
from app.models import User
from app.services import email as email_module
from app.services.email import (
    render_carded_trial_setup_email,
    render_carded_trial_value_email,
    run_carded_trial_drip,
    run_daily_drip,
)

async def _seed(
    *,
    days_left: float,
    carded: bool = True,
    tier: str = "premium",
    drip_state: str = "",
    canceled: bool = False,
) -> tuple[str, str]:
    """Insert a trial user whose trial ends `days_left` days from now."""
    uid = f"ct_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=uid,
            email=email,
            name="NurtureTest",
            tier=tier,
            password_hash="not-used",
            drip_state=drip_state,
            trial_ends_at=datetime.now(UTC) + timedelta(days=days_left),
            stripe_customer_id=f"cus_{uid}" if carded else None,
            canceled_at=datetime.now(UTC) if canceled else None,
        ))
        await s.commit()
    return uid, email


async def _row(uid: str) -> User:
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


def _tracker(monkeypatch) -> list[tuple[str, str, str]]:
    sends: list[tuple[str, str, str]] = []

    async def _track(to, subject, html, *_a, **_k):
        sends.append((to, subject, html))
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _track)
    return sends


# ── Who it reaches ───────────────────────────────────────────────────────────

async def test_carded_trial_in_the_value_window_gets_exactly_one_email(monkeypatch):
    sends = _tracker(monkeypatch)
    uid, email = await _seed(days_left=4)

    async with session_scope() as s:
        await run_carded_trial_drip(s)

    mine = [h for (to, _s, h) in sends if to == email]
    assert len(mine) == 1
    assert "ct_value" in (await _row(uid)).drip_state.split(",")


async def test_carded_trial_in_the_setup_window_gets_the_setup_email(monkeypatch):
    sends = _tracker(monkeypatch)
    uid, email = await _seed(days_left=14)

    async with session_scope() as s:
        await run_carded_trial_drip(s)

    assert len([h for (to, _s, h) in sends if to == email]) == 1
    assert "ct_setup" in (await _row(uid)).drip_state.split(",")


async def test_a_card_free_trial_is_never_touched(monkeypatch):
    """That population belongs to run_daily_drip, whose copy suits it."""
    sends = _tracker(monkeypatch)
    _uid, email = await _seed(days_left=4, carded=False)

    async with session_scope() as s:
        await run_carded_trial_drip(s)

    assert [h for (to, _s, h) in sends if to == email] == []


async def test_a_cancelled_trial_is_never_touched(monkeypatch):
    """They already decided. Selling after that is the win-back path's job."""
    sends = _tracker(monkeypatch)
    _uid, email = await _seed(days_left=4, canceled=True)

    async with session_scope() as s:
        await run_carded_trial_drip(s)

    assert [h for (to, _s, h) in sends if to == email] == []


async def test_a_free_tier_row_with_a_customer_id_is_not_treated_as_a_trial(monkeypatch):
    sends = _tracker(monkeypatch)
    _uid, email = await _seed(days_left=4, tier="free")

    async with session_scope() as s:
        await run_carded_trial_drip(s)

    assert [h for (to, _s, h) in sends if to == email] == []


async def test_each_stage_sends_at_most_once(monkeypatch):
    sends = _tracker(monkeypatch)
    _uid, email = await _seed(days_left=4)

    async with session_scope() as s:
        await run_carded_trial_drip(s)
    async with session_scope() as s:  # a same-day worker restart
        await run_carded_trial_drip(s)

    assert len([h for (to, _s, h) in sends if to == email]) == 1


# ── Where it sits relative to the payment notice ─────────────────────────────

@pytest.mark.parametrize("days_left", [6.5, 7.0, 7.5])
async def test_nothing_fires_inside_the_precharge_notice_window(
    monkeypatch, days_left: float,
):
    """run_trial_precharge_drip owns (now+6d, now+8d).

    Its notice is the disclosure a card-required trial owes, shaped by Visa's
    "at least 7 days" and Mastercard's 3-7 day rules. An email beside it is an
    email on top of the one message that must land.
    """
    sends = _tracker(monkeypatch)
    _uid, email = await _seed(days_left=days_left)

    async with session_scope() as s:
        await run_carded_trial_drip(s)

    assert [h for (to, _s, h) in sends if to == email] == [], (
        f"a stage fired {days_left} days out, inside the pre-charge window"
    )


async def test_the_two_drips_partition_trial_users(monkeypatch):
    """Each trial user is owned by exactly one drip, and gets its copy.

    Seeded at different points on purpose: the two drips key on different
    windows, so "same day" is not the interesting case. What matters is that a
    carded user never receives run_daily_drip's "add a card" copy, and a
    card-free one is still served by the series written for it.
    """
    sends = _tracker(monkeypatch)
    _carded_uid, carded_email = await _seed(days_left=4, carded=True)
    _free_uid, free_email = await _seed(days_left=2, carded=False)

    async with session_scope() as s:
        await run_carded_trial_drip(s)
        await run_daily_drip(s)

    carded_got = [h for (to, _s, h) in sends if to == carded_email]
    free_got = [h for (to, _s, h) in sends if to == free_email]

    assert len(carded_got) == 1, "the carded trial should hear from exactly one drip"
    assert all("add a card" not in h.lower() for h in carded_got), (
        "run_daily_drip's card-free copy reached a user who has a card"
    )
    assert len(free_got) >= 1, "the card-free trial still belongs to run_daily_drip"


# ── What it says ─────────────────────────────────────────────────────────────

_RENDERERS = {
    "setup": render_carded_trial_setup_email,
    "value": render_carded_trial_value_email,
}


@pytest.mark.parametrize("name", sorted(_RENDERERS))
def test_copy_never_tells_a_carded_reader_to_add_a_card(name: str):
    html = _RENDERERS[name](
        "Sam", trial_ends_at=datetime(2026, 9, 14, tzinfo=UTC),
    ).lower()
    for banned in ("add a card", "add your card", "no card", "no credit card"):
        assert banned not in html, f"{name} says {banned!r} to someone who has one"


@pytest.mark.parametrize("name", sorted(_RENDERERS))
def test_copy_never_says_the_account_drops_to_free(name: str):
    """It will be CHARGED. Saying otherwise removes the warning that matters."""
    html = _RENDERERS[name](
        "Sam", trial_ends_at=datetime(2026, 9, 14, tzinfo=UTC),
    ).lower()
    for banned in ("drops to free", "drop to free", "reverts to free"):
        assert banned not in html, f"{name} promises a downgrade, not a charge"


@pytest.mark.parametrize("name", sorted(_RENDERERS))
def test_copy_states_the_readers_own_charge_date(name: str):
    """A 14-day legacy trial must see ITS date, never a TRIAL_DAYS duration."""
    ends = datetime(2026, 9, 14, tzinfo=UTC)
    html = _RENDERERS[name]("Sam", trial_ends_at=ends)
    assert ends.strftime("%d %b %Y") in html
    assert "30 days" not in html, f"{name} states a constant duration"
    assert "14 days" not in html


@pytest.mark.parametrize("name", sorted(_RENDERERS))
def test_copy_carries_no_urgency_or_performance_claim(name: str):
    html = _RENDERERS[name](
        "Sam", trial_ends_at=datetime(2026, 9, 14, tzinfo=UTC),
    ).lower()
    for banned in (
        "hurry", "act now", "last chance", "don't miss", "limited time",
        "expires soon", "final notice", "only a few", "beat the market",
        "guaranteed", "you should", "we recommend", "hit rate",
    ):
        assert banned not in html, f"{name} leaked {banned!r}"


@pytest.mark.parametrize("name", sorted(_RENDERERS))
def test_copy_renders_without_a_trial_date(name: str):
    """The admin preview harness renders these with no user attached."""
    html = _RENDERERS[name]("Sam")
    assert "Sam" in html
