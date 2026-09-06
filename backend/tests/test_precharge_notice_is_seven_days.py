"""The pre-charge notice goes at SEVEN days, because both card networks say so.

No law requires this email. ROSCA's duty is to disclose the terms at the point
of order, which the trial screen does in full, and the FTC rule that would have
mandated reminders was vacated by the Eighth Circuit in July 2025.

The requirement is the card networks', and it is mandatory for any merchant
running a free trial:

  Visa        a reminder "at least 7 days before initiating a recurring
              transaction if a trial period ... is about to expire".
  Mastercard  "no less than three days and no more than seven days before the
              end of the trial period", with the steps to cancel.

Visa wants >= 7. Mastercard wants <= 7. SEVEN IS THE ONLY NUMBER THAT SATISFIES
BOTH, and Tapeline takes both cards.

Until now the notice rode on Stripe's `customer.subscription.trial_will_end`,
which fires at a fixed ~3 days: inside Mastercard's window and outside Visa's.
A card-network breach is not a fine, it is the merchant account.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import Subscription, User
from app.services.email import run_trial_precharge_drip

# The window the drip selects on, and the two network limits it sits between.
VISA_MIN_DAYS = 7
MASTERCARD_MAX_DAYS = 7


@pytest.fixture
def sent(monkeypatch):
    out: list[dict] = []

    async def _capture(to, subject, html, **kw):
        out.append({"to": to, "subject": subject, "html": html, **kw})
        return {"ok": True}

    monkeypatch.setattr("app.services.email.send_email", _capture, raising=True)

    async def _no_amount(customer_id, sub_id):
        return "$19.99 USD/month"

    monkeypatch.setattr(
        "app.services.email.upcoming_renewal_amount_label", _no_amount, raising=True
    )
    return out


async def _trialist(*, days_out: float, cancelled: bool = False, drip: str = "") -> User:
    uid = f"u_{uuid.uuid4().hex}"
    ends = datetime.now(UTC) + timedelta(days=days_out)
    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.com", name="Trialist",
            tier="premium", password_hash="x", drip_state=drip,
            stripe_customer_id=f"cus_{uuid.uuid4().hex[:18]}",
            trial_started_at=datetime.now(UTC) - timedelta(days=30 - days_out),
            trial_ends_at=ends,
        ))
        s.add(Subscription(
            id=f"sub_{uuid.uuid4().hex[:18]}", user_id=uid, tier="premium",
            status="trialing", billing_period="monthly",
            cancel_at_period_end=cancelled,
            current_period_end=ends,
        ))
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


async def _cleanup(user: User) -> None:
    async with session_scope() as s:
        await s.execute(delete(Subscription).where(Subscription.user_id == user.id))
        await s.execute(delete(User).where(User.id == user.id))


async def _run() -> dict:
    async with session_scope() as s:
        return await run_trial_precharge_drip(s)


@pytest.mark.asyncio
async def test_a_trial_seven_days_out_is_warned(sent):
    """The whole point. Visa's floor is 7; this is the send that meets it."""
    user = await _trialist(days_out=7)
    try:
        counts = await _run()
        assert counts["trial_precharge"] == 1, (
            "a trial converting in 7 days got no pre-charge notice — Visa "
            "requires one at least 7 days before the charge"
        )
        assert len(sent) == 1
        body = sent[0]["html"]
        assert "19.99" in body, "the notice must state the amount being charged"
        # Mastercard requires the steps to cancel; Visa requires a cancel link.
        assert "cancel" in body.lower(), (
            "no cancellation route in the notice; both networks require one"
        )
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_a_trial_three_days_out_is_not_picked_up_here(sent):
    """T-3 is Stripe's backstop, not this drip's job.

    If this window widened to catch 3-day-out trials it would double-send
    alongside the webhook.
    """
    user = await _trialist(days_out=3)
    try:
        counts = await _run()
        assert counts["trial_precharge"] == 0
        assert sent == []
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_a_cancelled_trial_is_never_told_a_charge_is_coming(sent):
    """No charge is coming. Saying otherwise is the complaint this prevents."""
    user = await _trialist(days_out=7, cancelled=True)
    try:
        counts = await _run()
        assert counts["trial_precharge"] == 0, (
            "someone who cancelled during their trial was told their card is "
            "about to be charged"
        )
        assert sent == []
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_it_does_not_send_twice_for_the_same_trial(sent):
    """Two emails about one charge is the failure the dedup token prevents."""
    user = await _trialist(days_out=7)
    try:
        first = await _run()
        second = await _run()
        assert first["trial_precharge"] == 1
        assert second["trial_precharge"] == 0, (
            "the drip re-sent on its next run; drip_state dedup is not holding"
        )
        assert len(sent) == 1
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_a_later_trial_gets_its_own_notice(sent):
    """Dedup is per TRIAL, not per user — a win-back trial must be warned too."""
    old_token = "pc7" + (datetime.now(UTC) - timedelta(days=300)).strftime("%y%m%d")
    user = await _trialist(days_out=7, drip=old_token)
    try:
        counts = await _run()
        assert counts["trial_precharge"] == 1, (
            "a stale token from an earlier trial suppressed the notice for a "
            "new one — that trialist would be charged with no warning at all"
        )
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_the_token_is_stamped_with_THIS_trial_end(sent):
    """Pre-seed the exact token this trial should produce; it must suppress.

    Distinguishes a date-stamped token from a bare one. A bare "pc7" still
    dedups within one trial and still lets a later trial through, so the two
    tests above pass either way — but it would suppress every future trial for
    anyone who had one before, silently, and that trialist gets charged with no
    warning at all.
    """
    ends = datetime.now(UTC) + timedelta(days=7)
    user = await _trialist(days_out=7, drip="pc7" + ends.strftime("%y%m%d"))
    try:
        counts = await _run()
        assert counts["trial_precharge"] == 0, (
            "the token this trial generates did not match the one already "
            "stored for it, so the notice would send a second time"
        )
        assert sent == []
    finally:
        await _cleanup(user)


def test_seven_is_the_only_timing_both_networks_accept():
    """Documents the arithmetic, so nobody 'optimises' this back to 3.

    Visa: at least 7 days before. Mastercard: no more than 7 days before.
    The intersection is a single value.
    """
    assert VISA_MIN_DAYS == MASTERCARD_MAX_DAYS == 7
    allowed = [d for d in range(1, 31) if d >= VISA_MIN_DAYS and d <= MASTERCARD_MAX_DAYS]
    assert allowed == [7], (
        f"only {allowed} satisfies Visa's floor and Mastercard's ceiling at "
        f"once; a notice at 3 days meets Mastercard and breaches Visa"
    )
