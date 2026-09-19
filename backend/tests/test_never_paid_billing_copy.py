"""Billing emails a subscriber who has NEVER paid can receive must be true for them.

THE STATE THIS GUARDS. On 2026-09-17 two card-required Premium trials sat
past_due: each trial ended, Stripe declined the first charge three times, and
each account had already been sent a "You're in" by the old status trigger
(so each subscription holds a `paid_start:` latch). Neither has ever paid
Tapeline anything. Stripe's next retries are on 2026-09-18.

What those people are sent, traced through the real handler:

* a declined retry -> `invoice.payment_failed` -> render_payment_failed_email.
  From the 2nd attempt it said "if it fails again, your account drops to
  Free". Both accounts were told that at attempt 2, attempt 3 then failed,
  and neither account dropped: Stripe still had retries scheduled. A
  non-final attempt has another retry after it by definition
  (`next_payment_attempt` is set), so the next failure is not known to be the
  last.
* a retry that clears on a latched subscription -> the dunning all-clear
  (render_payment_recovered_email). It said the subscription was "fully
  current again", "current again" in the preheader, "Nothing lapsed … ran
  uninterrupted the whole time", "Back to it" and "Jump back into the
  scanner" — all of which describe a paying subscriber returning to good
  standing, not someone whose first payment just cleared.
* a retry that clears on an unlatched subscription (every trial started
  under #834's trigger) -> the welcome instead, which told a 30-day trialist
  "Two things worth doing in the first session".

And the welcome's own lead, "Your first payment went through", is false the
other way round: a returning customer on a win-back subscription paid on an
earlier subscription. The latch is per subscription, so the welcome fires for
them too.

Every event goes through the real `/api/webhooks/stripe` route with a locally
computed signature, so Stripe's own `construct_event` builds a real
`stripe.Event` before any handler code runs (asserted). The harness and payload
builders are the ones #834's tests use, in the dahlia invoice shape.
"""
from __future__ import annotations

import html as htmllib
import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import stripe

from app.db import session_scope
from app.models import StripeWebhookEvent, Subscription
from tests.test_paid_welcome_waits_for_money import (
    DAY,
    Harness,
    _invoice,
    _now,
    _subscription,
    _user,
)

_PREHEADER = re.compile(r'<div style="display:none;[^"]*">(.*?)</div>', re.S)


def _preheader(html: str) -> str:
    m = _PREHEADER.search(html)
    assert m, "email has no preheader"
    return htmllib.unescape(m.group(1)).lower()


def _body(html: str) -> str:
    """Visible text only: no <style>, no preheader, no tags."""
    text = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    text = _PREHEADER.sub(" ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", htmllib.unescape(text)).lower()


async def _first_charge_declined_twice(h: Harness, u: dict) -> tuple[str, dict, dict]:
    """A card-required trial whose first charge Stripe has declined twice.

    The clock is past trial_end, as it is whenever the first charge is
    attempted, so the handler takes the trial-first-charge branch. Both
    declines have a further retry scheduled (`next_payment_attempt` set)."""
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    trial_end = _now() - 2 * 3600
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}

    await h.deliver("customer.subscription.created", _subscription(**kw, status="trialing", trial_end=trial_end))
    await h.deliver("invoice.payment_succeeded", _invoice(**kw, amount_paid=0, billing_reason="subscription_create"))
    await h.deliver("customer.subscription.updated", _subscription(**kw, status="active", trial_end=trial_end))
    charge = _invoice(
        **kw, amount_paid=0, amount_due=1999, status="open", period_start=trial_end,
        billing_reason="subscription_cycle", next_payment_attempt=_now() + 2 * DAY,
    )
    await h.deliver("invoice.payment_failed", charge)
    await h.deliver("customer.subscription.updated", _subscription(**kw, status="past_due", trial_end=trial_end))
    charge = dict(charge, attempt_count=2, next_payment_attempt=_now() + 3 * DAY)
    await h.deliver("invoice.payment_failed", charge)
    return sub_id, kw, charge


async def _declines(monkeypatch) -> list[dict]:
    h = Harness(monkeypatch)
    u = await _user()
    await _first_charge_declined_twice(h, u)
    declines = [m for m in h.sent if m["subject"] == "Your Tapeline payment didn't go through"]
    assert len(declines) == 2, [m["subject"] for m in h.sent]
    assert h.verified_event_types and all(t is stripe.Event for t in h.verified_event_types)
    # The fixture really is on the trial-first-charge branch.
    assert all("the first charge didn't go through" in _body(m["html"]) for m in declines)
    return declines


async def _all_clear_for_a_trial_already_welcomed(monkeypatch) -> dict:
    """The live state: latched by the old trigger, declined, then a retry clears."""
    h = Harness(monkeypatch)
    u = await _user()
    sub_id, _kw, charge = await _first_charge_declined_twice(h, u)
    async with session_scope() as s:
        s.add(StripeWebhookEvent(id=f"paid_start:{sub_id}", event_type="paid_start"))

    before = len(h.sent)
    await h.deliver(
        "invoice.payment_succeeded",
        dict(charge, status="paid", amount_paid=1999, attempt_count=3, next_payment_attempt=None),
    )
    at_the_charge = h.sent[before:]
    assert [m["subject"] for m in at_the_charge] == ["Payment received — you're all set"]
    assert all(t is stripe.Event for t in h.verified_event_types)
    return at_the_charge[0]


async def _trial_whose_retry_cleared(monkeypatch) -> tuple[Harness, dict]:
    """No latch (a trial started under #834): the welcome replaces the all-clear."""
    h = Harness(monkeypatch)
    u = await _user()
    _sub_id, _kw, charge = await _first_charge_declined_twice(h, u)

    before = len(h.sent)
    await h.deliver(
        "invoice.payment_succeeded",
        dict(charge, status="paid", amount_paid=1999, attempt_count=3, next_payment_attempt=None),
    )
    at_the_charge = h.sent[before:]
    assert [m["subject"] for m in at_the_charge] == ["You're in — welcome to Tapeline Premium"]
    assert all(t is stripe.Event for t in h.verified_event_types)
    return h, at_the_charge[0]


async def _welcome_for_a_trial_whose_retry_cleared(monkeypatch) -> dict:
    return (await _trial_whose_retry_cleared(monkeypatch))[1]


async def _returning_payer(monkeypatch) -> Harness:
    """A customer who paid on an earlier subscription, cancelled, and came back
    on a win-back discount. The new subscription's first paid invoice is a
    `subscription_create`, so the once-per-subscription welcome fires."""
    h = Harness(monkeypatch)
    u = await _user()
    old_sub = f"sub_{uuid.uuid4().hex[:24]}"
    async with session_scope() as s:
        s.add(Subscription(
            id=old_sub, user_id=u["id"], status="canceled", tier="premium",
            current_period_end=datetime.now(UTC) - timedelta(days=40),
            cancel_at_period_end=False, billing_period="monthly",
        ))
    h.paid[old_sub] = [(f"in_{uuid.uuid4().hex[:24]}", 1999)]

    new_sub = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": new_sub, "customer": u["customer"], "user_id": u["id"]}
    await h.deliver("customer.subscription.created", _subscription(**kw, status="active"))
    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, amount_paid=1199, unit_amount=1999, discount=800,
        billing_reason="subscription_create",
    ))
    assert len(h.welcomes) == 1
    assert all(t is stripe.Event for t in h.verified_event_types)
    return h


async def _welcome_for_a_returning_payer(monkeypatch) -> dict:
    return (await _returning_payer(monkeypatch)).welcomes[0]


def _revenue_alert(h: Harness) -> dict:
    """The one founder revenue alert, as the real formatter worded it."""
    alerts = [m for m in h.founder_messages if "New Tapeline subscription" in m["subject"]]
    assert len(alerts) == 1, h.founder_messages
    return alerts[0]


# ── invoice.payment_failed on a trial's first charge ────────────────────────

@pytest.mark.asyncio
async def test_a_non_final_decline_does_not_say_the_next_failure_drops_the_account(monkeypatch):
    second = (await _declines(monkeypatch))[1]
    text = _body(second["html"])
    assert "2nd attempt" in text
    assert "if it fails again" not in text, (
        "attempt 2 has a further retry scheduled; the failure after it is not "
        "known to be the last, and in production it was not"
    )
    assert "if its last retry fails, your account drops to free" in text


# ── a retry clears on a subscription the old trigger already welcomed ───────

@pytest.mark.asyncio
async def test_the_all_clear_does_not_call_a_first_payment_current_again(monkeypatch):
    text = _body((await _all_clear_for_a_trial_already_welcomed(monkeypatch))["html"])
    assert "payment just went through" in text and "charged successfully" in text
    assert "again" not in text, "nothing was current before this payment to be current again"


@pytest.mark.asyncio
async def test_the_all_clear_preheader_does_not_say_current_again(monkeypatch):
    pre = _preheader((await _all_clear_for_a_trial_already_welcomed(monkeypatch))["html"])
    assert pre.startswith("payment received")
    assert "again" not in pre


@pytest.mark.asyncio
async def test_the_all_clear_does_not_say_nothing_lapsed(monkeypatch):
    text = _body((await _all_clear_for_a_trial_already_welcomed(monkeypatch))["html"])
    assert "nothing lapsed" not in text
    assert "uninterrupted the whole time" not in text
    assert "premium plan is active" in text


@pytest.mark.asyncio
async def test_the_all_clear_does_not_send_a_never_paid_subscriber_back(monkeypatch):
    text = _body((await _all_clear_for_a_trial_already_welcomed(monkeypatch))["html"])
    assert "back to it" not in text
    assert "jump back" not in text


# ── a retry clears on a subscription with no latch: the welcome ─────────────

@pytest.mark.asyncio
async def test_the_welcome_after_a_trial_does_not_assume_a_first_session(monkeypatch):
    text = _body((await _welcome_for_a_trial_whose_retry_cleared(monkeypatch))["html"])
    assert "first session" not in text, "a 30-day trialist has had sessions"
    assert "two things worth setting up, if you haven't already" in text


# ── the welcome to a returning payer ────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_returning_payer_is_not_told_the_welcome_is_their_first_payment(monkeypatch):
    text = _body((await _welcome_for_a_returning_payer(monkeypatch))["html"])
    assert "charged today: $11.99 usd" in text
    assert "first payment" not in text, "they paid on an earlier subscription"
    assert "your payment went through" in text


@pytest.mark.asyncio
async def test_a_returning_payer_welcome_preheader_does_not_say_first_payment(monkeypatch):
    pre = _preheader((await _welcome_for_a_returning_payer(monkeypatch))["html"])
    assert "first payment" not in pre
    assert pre == "welcome to tapeline premium — your payment went through."


# ── the founder's revenue alert ──────────────────────────────────────────────
# Internal, but it is the only place the founder learns a sale happened, and
# it used to open "first payment received". The latch that sends it is per
# SUBSCRIPTION, so a win-back subscription's first invoice triggers it for a
# customer who paid on an earlier one — the same error #855 took out of the
# customer's welcome. What the handler does know is that this is the first
# payment on THIS subscription.

@pytest.mark.asyncio
async def test_a_returning_payer_revenue_alert_does_not_say_first_payment(monkeypatch):
    alert = _revenue_alert(await _returning_payer(monkeypatch))
    first_line = alert["text"].splitlines()[0]
    assert "first payment received" not in first_line.lower(), (
        "they paid on an earlier subscription"
    )
    assert first_line == "💰 New Tapeline subscription — first payment on this subscription"
    assert "charged today: 11.99 USD" in alert["text"]


@pytest.mark.asyncio
async def test_a_trial_first_charge_revenue_alert_is_worded_the_same_way(monkeypatch):
    """The never-paid trialist whose retry cleared: "first payment on this
    subscription" is true for them too, so one wording serves both."""
    h, _welcome = await _trial_whose_retry_cleared(monkeypatch)
    first_line = _revenue_alert(h)["text"].splitlines()[0]
    assert first_line == "💰 New Tapeline subscription — first payment on this subscription"
