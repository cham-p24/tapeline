"""The pre-charge timing we PROMISE is the timing we SEND (T-09, 2026-09-14).

`run_trial_precharge_drip` sends the card-required trial's pre-charge notice
about 7 days out (Visa requires at least 7, Mastercard 3 to 7; see
test_precharge_notice_is_seven_days.py). The customer-facing copy on
/app/start, /signup, /legal/refund and in two emails kept saying "we email you
three days before", left over from when the notice rode on Stripe's
`trial_will_end`. Founder-approved fix: one constant,
services/precharge_notice.PRECHARGE_NOTICE_DAYS, drives the drip window AND
the copy; the frontend mirrors it in lib/trial.ts.

This file pins:
  * the drip window is built from the constant and brackets it;
  * a trial exactly PRECHARGE_NOTICE_DAYS out is picked up, and one at
    PRECHARGE_NOTICE_DAYS +/- 2 is not;
  * the frontend constant equals the backend one;
  * the emails that state the timing interpolate the constant's phrase and no
    longer say "three days before".
"""
from __future__ import annotations

import inspect
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import Subscription, User
from app.services import email as email_mod
from app.services.precharge_notice import (
    PRECHARGE_NOTICE_DAYS,
    PRECHARGE_WINDOW_LOWER_DAYS,
    PRECHARGE_WINDOW_UPPER_DAYS,
    precharge_notice_phrase,
)

_FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def test_the_constant_is_seven_and_the_window_brackets_it():
    assert PRECHARGE_NOTICE_DAYS == 7
    assert PRECHARGE_WINDOW_LOWER_DAYS < PRECHARGE_NOTICE_DAYS < PRECHARGE_WINDOW_UPPER_DAYS
    assert (PRECHARGE_WINDOW_LOWER_DAYS, PRECHARGE_WINDOW_UPPER_DAYS) == (6, 8)


def test_the_drip_window_reads_the_constant_not_literals():
    src = inspect.getsource(email_mod.run_trial_precharge_drip)
    assert "PRECHARGE_WINDOW_LOWER_DAYS" in src and "PRECHARGE_WINDOW_UPPER_DAYS" in src
    assert not re.search(r"timedelta\(days=\s*\d", src), (
        "the pre-charge drip window is hardcoded again; the copy's number and "
        "the send can drift apart"
    )


def test_the_frontend_copy_constant_matches_the_backend():
    src = (_FRONTEND / "lib" / "trial.ts").read_text(encoding="utf-8")
    m = re.search(r"export const PRECHARGE_NOTICE_DAYS\s*=\s*(\d+)\s*;", src)
    assert m, "lib/trial.ts no longer exports a literal PRECHARGE_NOTICE_DAYS"
    assert int(m.group(1)) == PRECHARGE_NOTICE_DAYS, (
        f"the site promises a notice {m.group(1)} days before the charge while "
        f"the drip sends at {PRECHARGE_NOTICE_DAYS}"
    )


@pytest.fixture
def sent(monkeypatch):
    out: list[dict] = []

    async def _capture(to, subject, html, **kw):
        out.append({"to": to, "subject": subject, "html": html})
        return {"ok": True}

    async def _amount(customer_id, sub_id):
        return "$19.99 USD/month"

    monkeypatch.setattr("app.services.email.send_email", _capture, raising=True)
    monkeypatch.setattr(
        "app.services.email.upcoming_renewal_amount_label", _amount, raising=True
    )
    return out


async def _trialist(days_out: float) -> str:
    uid = f"u_{uuid.uuid4().hex}"
    ends = datetime.now(UTC) + timedelta(days=days_out)
    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.com", name="Trialist",
            tier="premium", password_hash="x", drip_state="",
            stripe_customer_id=f"cus_{uuid.uuid4().hex[:18]}",
            trial_started_at=datetime.now(UTC) - timedelta(days=30 - days_out),
            trial_ends_at=ends,
        ))
        s.add(Subscription(
            id=f"sub_{uuid.uuid4().hex[:18]}", user_id=uid, tier="premium",
            status="trialing", billing_period="monthly",
            cancel_at_period_end=False, current_period_end=ends,
        ))
    return uid


async def _cleanup(uid: str) -> None:
    async with session_scope() as s:
        await s.execute(delete(Subscription).where(Subscription.user_id == uid))
        await s.execute(delete(User).where(User.id == uid))


@pytest.mark.parametrize(
    "days_out,expected",
    [
        (PRECHARGE_NOTICE_DAYS, 1),
        (PRECHARGE_NOTICE_DAYS + 0.5, 1),
        (PRECHARGE_NOTICE_DAYS - 2, 0),
        (PRECHARGE_NOTICE_DAYS + 2, 0),
    ],
)
async def test_the_drip_sends_at_the_promised_distance(sent, days_out, expected):
    uid = await _trialist(days_out)
    try:
        async with session_scope() as s:
            counts = await email_mod.run_trial_precharge_drip(s)
        assert counts["trial_precharge"] == expected
        if expected:
            html = sent[0]["html"]
            assert "Your trial ends in 3 days" not in html, (
                "the notice sent 7 days out still headlines '3 days'"
            )
    finally:
        await _cleanup(uid)
        async with session_scope() as s:
            assert (
                await s.execute(select(User).where(User.id == uid))
            ).scalar_one_or_none() is None


def test_the_copy_phrase_interpolates_the_constant():
    assert precharge_notice_phrase() == f"about {PRECHARGE_NOTICE_DAYS} days before"


def test_the_emails_that_state_the_timing_use_the_phrase():
    phrase = precharge_notice_phrase()
    invite = email_mod.render_free_trial_invite_email("Sam", open_access=False)
    started = email_mod.render_trial_started_email(
        "Sam",
        tier="premium",
        amount_label="$19.99 USD/month",
        charge_date_label="Friday, October 9",
    )
    for html in (invite, started):
        flat = " ".join(html.split())
        assert f"{phrase} that date" in flat
        assert "three days before" not in flat.lower()


def test_the_precharge_email_headline_states_the_date_not_a_day_count():
    html = email_mod.render_trial_precharge_reminder_email(
        "Sam", tier="premium", amount_label="$19.99 USD/month",
        charge_date_label="Friday, October 9",
    )
    assert "Your trial ends on Friday, October 9." in html
    assert "ends in 3 days" not in html


def test_the_precharge_email_guards_the_dateless_webhook_fallback():
    """webhooks.py passes charge_date_label="when your trial ends" when Stripe
    sends no trial_end. The email must not read "ends on when your trial ends"."""
    html = email_mod.render_trial_precharge_reminder_email(
        "Sam", tier="premium", amount_label="$19.99 USD/month",
        charge_date_label="when your trial ends",
    )
    flat = " ".join(html.split())
    assert "on when your trial ends" not in flat
    assert "ends when your trial ends" not in flat
    assert "Your trial is ending soon." in flat
    assert "When your trial ends the card you added is charged" in flat
