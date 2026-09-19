"""Money arriving on a subscription that is already marked as started is never
silent to the founder.

THE GAP. `_welcome_on_first_paid_invoice` sends the customer welcome and
`notify_founder_new_subscription` once per subscription, latched on
`paid_start:{subscription}`. When that latch is already held it returned
before saying anything to anyone. That is right for the customer (no second
"You're in"), but it also meant the founder was never told the money arrived.

The case that matters: two card-required trials were latched by the old
`status == "active"` trigger BEFORE their first charge, and the first charge
was then declined. When a Stripe retry finally clears, that is the first money
either subscription has ever paid, and the handler said nothing to the
founder. The customer gets the dunning all-clear; the founder had to find out
by running billing_audit by hand. Routine renewals were silent the same way,
and so was the first renewal of a subscription paid for before the latch
existed (the "Stripe history shows an earlier paid invoice" path).

THE RULE. Every subscription invoice with `amount_paid > 0` that does not get
the new-subscription alert gets an internal payment-received note to the
founder, once per invoice (latched on `paid_invoice_alert:{invoice}` in
stripe_webhook_events, claimed before sending). It never claims to be a new
sale, and no customer email is added or changed.

Every event goes through the real `/api/webhooks/stripe` route with a locally
computed Stripe signature, using the harness and dahlia-shaped payload builders
from test_paid_welcome_waits_for_money.py.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import stripe
from sqlalchemy import select

from app.db import session_scope
from app.models import StripeWebhookEvent, Subscription
from tests.test_paid_welcome_waits_for_money import (
    DAY,
    PRICE_PRO_MONTHLY,
    Harness,
    _invoice,
    _now,
    _subscription,
    _user,
)

PAYMENT_RECEIVED = "Tapeline payment received"


def _payment_notes(h: Harness) -> list[dict]:
    return [m for m in h.founder_messages if PAYMENT_RECEIVED in m["subject"]]


def _new_sale_notes(h: Harness) -> list[dict]:
    return [m for m in h.founder_messages if "New Tapeline subscription" in m["subject"]]


async def _invoice_latch_exists(invoice_id: str) -> bool:
    async with session_scope() as s:
        row = (await s.execute(
            select(StripeWebhookEvent).where(
                StripeWebhookEvent.id == f"paid_invoice_alert:{invoice_id}"
            )
        )).scalar_one_or_none()
    return row is not None


async def _trial_latched_then_declined_twice(h: Harness, u: dict) -> tuple[str, dict]:
    """The live state on 2026-09-18: a card-required trial the old trigger
    latched at `active`, whose first charge Stripe has declined twice, each
    decline sending the customer a failed-payment email (a `dun{n}` token)."""
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    trial_end = _now() - 2 * 3600
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}

    await h.deliver("customer.subscription.created", _subscription(**kw, status="trialing", trial_end=trial_end))
    await h.deliver("invoice.payment_succeeded", _invoice(**kw, amount_paid=0, billing_reason="subscription_create"))
    await h.deliver("customer.subscription.updated", _subscription(**kw, status="active", trial_end=trial_end))
    # What the old status trigger wrote at `active`, before any money.
    async with session_scope() as s:
        s.add(StripeWebhookEvent(id=f"paid_start:{sub_id}", event_type="paid_start"))
    charge = _invoice(
        **kw, amount_paid=0, amount_due=1999, status="open", period_start=trial_end,
        billing_reason="subscription_cycle", next_payment_attempt=_now() + 2 * DAY,
    )
    await h.deliver("invoice.payment_failed", charge)
    await h.deliver("customer.subscription.updated", _subscription(**kw, status="past_due", trial_end=trial_end))
    charge = dict(charge, attempt_count=2, next_payment_attempt=_now() + 3 * DAY)
    await h.deliver("invoice.payment_failed", charge)
    return sub_id, charge


# ── the live case: a retry clears on a latched, never-paid trial ────────────

@pytest.mark.asyncio
async def test_a_retry_clearing_on_a_latched_trial_tells_the_founder_once(monkeypatch):
    h = Harness(monkeypatch)
    u = await _user()
    sub_id, charge = await _trial_latched_then_declined_twice(h, u)
    assert h.founder_messages == [], h.founder_messages

    sent_before = len(h.sent)
    paid = dict(charge, status="paid", amount_paid=1999, attempt_count=3, next_payment_attempt=None)
    await h.deliver("invoice.payment_succeeded", paid)

    notes = _payment_notes(h)
    assert len(notes) == 1, (
        "a first charge cleared on a subscription the old trigger had already "
        f"latched, and the founder was told nothing: {h.founder_messages}"
    )
    note = notes[0]
    assert "19.99 USD" in note["subject"] and u["email"] in note["subject"]
    text = note["text"]
    assert "charged: 19.99 USD" in text
    assert u["email"] in text
    assert "billing reason: subscription_cycle" in text
    assert "paid on attempt 3" in text
    assert "failed-payment emails sent before this payment: 2" in text
    assert "already marked as started" in text
    assert sub_id in text and paid["id"] in text and u["customer"] in text
    # It is not reported as a new sale, and the new-sale path did not run.
    assert _new_sale_notes(h) == [] and h.alerts == []
    assert h.welcomes == []
    assert h.history_calls == [], "the latch should still short-circuit before Stripe is asked"
    # The customer's emails are unchanged: the all-clear, and nothing else.
    assert [m["subject"] for m in h.sent[sent_before:]] == ["Payment received — you're all set"]
    assert all(m["to"] == u["email"] for m in h.sent)
    assert await _invoice_latch_exists(paid["id"])
    assert h.verified_event_types and all(t is stripe.Event for t in h.verified_event_types)


@pytest.mark.asyncio
async def test_one_invoice_under_two_event_ids_tells_the_founder_once(monkeypatch):
    """The event-id dedup stops a redelivery of ONE event. A second, distinct
    event for the same paid invoice gets past it; the per-invoice latch does not."""
    h = Harness(monkeypatch)
    u = await _user()
    _sub_id, charge = await _trial_latched_then_declined_twice(h, u)
    paid = dict(charge, status="paid", amount_paid=1999, attempt_count=3, next_payment_attempt=None)

    first = await h.deliver("invoice.payment_succeeded", paid)
    second = await h.deliver("invoice.payment_succeeded", paid)

    assert first.get("replay") is not True and second.get("replay") is not True
    assert len(_payment_notes(h)) == 1, h.founder_messages


@pytest.mark.asyncio
async def test_an_exact_redelivery_tells_the_founder_once(monkeypatch):
    h = Harness(monkeypatch)
    u = await _user()
    _sub_id, charge = await _trial_latched_then_declined_twice(h, u)
    paid = dict(charge, status="paid", amount_paid=1999, attempt_count=3, next_payment_attempt=None)
    event_id = f"evt_{uuid.uuid4().hex}"

    await h.deliver("invoice.payment_succeeded", paid, event_id=event_id)
    again = await h.deliver("invoice.payment_succeeded", paid, event_id=event_id)

    assert again.get("replay") is True
    assert len(_payment_notes(h)) == 1, h.founder_messages


# ── renewals ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_each_renewal_after_the_first_charge_tells_the_founder_once(monkeypatch):
    """The first charge is the new-sale alert; every later paid invoice is one
    payment-received note — once per INVOICE, not once per subscription."""
    h = Harness(monkeypatch)
    u = await _user()
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}

    await h.deliver("customer.subscription.created", _subscription(**kw, status="active"))
    await h.deliver("invoice.payment_succeeded", _invoice(**kw, amount_paid=1999, billing_reason="subscription_create"))
    assert len(_new_sale_notes(h)) == 1 and _payment_notes(h) == []

    month_2 = _invoice(**kw, amount_paid=1999, billing_reason="subscription_cycle", period_start=_now() + 30 * DAY)
    await h.deliver("invoice.payment_succeeded", month_2)
    month_3 = _invoice(**kw, amount_paid=1999, billing_reason="subscription_cycle", period_start=_now() + 60 * DAY)
    await h.deliver("invoice.payment_succeeded", month_3)

    notes = _payment_notes(h)
    assert len(notes) == 2, h.founder_messages
    assert month_2["id"] in notes[0]["text"] and month_3["id"] in notes[1]["text"]
    assert all("paid on attempt" not in n["text"] for n in notes), "a first-attempt charge is not a retry"
    assert all("failed-payment emails" not in n["text"] for n in notes)
    assert len(_new_sale_notes(h)) == 1 and len(h.welcomes) == 1, "a renewal was announced as a new sale"


@pytest.mark.asyncio
async def test_the_first_renewal_of_an_established_unlatched_subscription_tells_the_founder(monkeypatch):
    """Paid before the latch existed, so Stripe's history decides it is not a
    first charge and the latch is claimed silently. The money still arrived."""
    h = Harness(monkeypatch)
    u = await _user(tier="pro")
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}
    pro = {"tier": "pro", "price_id": PRICE_PRO_MONTHLY}
    async with session_scope() as s:
        s.add(Subscription(
            id=sub_id, user_id=u["id"], status="active", tier="pro",
            current_period_end=datetime.now(UTC) + timedelta(hours=1),
            cancel_at_period_end=False, billing_period="monthly",
        ))
    h.paid[sub_id] = [(f"in_{uuid.uuid4().hex[:24]}", 999)]  # the charge a month ago

    renewal = _invoice(**kw, **pro, amount_paid=999, billing_reason="subscription_cycle")
    await h.deliver("invoice.payment_succeeded", renewal)

    notes = _payment_notes(h)
    assert len(notes) == 1, h.founder_messages
    assert "charged: 9.99 USD" in notes[0]["text"]
    assert "earlier paid invoice" in notes[0]["text"]
    assert _new_sale_notes(h) == [] and h.welcomes == []

    # The next renewal takes the latched path: still exactly one note each.
    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, **pro, amount_paid=999, billing_reason="subscription_cycle", period_start=_now() + 30 * DAY,
    ))
    assert len(_payment_notes(h)) == 2, h.founder_messages


# ── what is not money ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_zero_dollar_invoice_on_a_latched_subscription_tells_nobody(monkeypatch):
    """A 100%-off referral month on a subscription that is already paying."""
    h = Harness(monkeypatch)
    u = await _user()
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}
    async with session_scope() as s:
        s.add(StripeWebhookEvent(id=f"paid_start:{sub_id}", event_type="paid_start"))

    free_month = _invoice(**kw, amount_paid=0, billing_reason="subscription_cycle")
    await h.deliver("invoice.payment_succeeded", free_month)

    assert h.founder_messages == [], h.founder_messages
    assert not await _invoice_latch_exists(free_month["id"])


# ── the formatter ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_note_never_calls_itself_a_new_subscription_or_a_first_payment(monkeypatch):
    """It cannot know which it is without asking Stripe, so it says both are
    possible and points at where to look."""
    from app.services import telegram

    captured: list[dict] = []

    async def _capture(*, subject, text):
        captured.append({"subject": subject, "text": text})

    monkeypatch.setattr(telegram, "deliver_founder_alert", _capture, raising=True)
    await telegram.notify_founder_payment_received(
        why="this subscription was already marked as started",
        amount=19.99, currency="usd", email=None, billing_reason=None,
        attempt_count=None, failed_payment_emails=0,
        customer=None, subscription=None, invoice=None,
    )

    assert len(captured) == 1
    msg = captured[0]
    assert msg["subject"] == "💰 Tapeline payment received — 19.99 USD — unmatched account"
    text = msg["text"]
    assert "not matched to a Tapeline account" in text
    assert "billing reason: -" in text and "stripe invoice: -" in text
    lowered = (msg["subject"] + text).lower()
    assert "new tapeline subscription" not in lowered
    assert "first payment received" not in lowered
    assert "renewal" in lowered and "first real payment" in lowered
