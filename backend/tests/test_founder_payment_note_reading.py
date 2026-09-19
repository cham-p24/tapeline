"""The founder's payment-received note says only what its path and billing
reason allow.

`_welcome_on_first_paid_invoice` reaches the internal payment-received note
(`notify_founder_payment_received`) by two paths, and they know different
things:

* LATCHED. The subscription's `paid_start:` row was already held, so Stripe's
  invoice history was never read. A `subscription_cycle` payment here is a
  renewal, or the first real payment on a trial that was marked as started
  before its first charge went through, and only the subscription's invoices
  in Stripe tell those apart. So on this path, and only here, the note keeps
  that two-way reading.
* STRIPE HISTORY. No latch, but Stripe returned an earlier paid invoice on the
  subscription. This payment CANNOT be the first one, so a closing line that
  offered "the first real payment on a trial" sent the reader looking for
  something that could not be there.

The billing reason narrows it further. `subscription_update` is a charge from
a change to the subscription (an upgrade, a plan or quantity change, a
proration), not a renewal, so a note that called it "a renewal, or ..." was
incomplete. `subscription_create` is the subscription's first invoice.

The failed-payment count is read from the account's `dun{n}` dunning tokens.
Those record only the Stripe attempt number, not which subscription or invoice
failed, so a per-subscription count cannot be taken from them. The line says
it is account-wide rather than implying it is about this payment. The count
for this invoice alone is the "paid on attempt N" line.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db import session_scope
from app.models import StripeWebhookEvent, Subscription
from app.services import telegram
from tests.test_founder_told_of_paid_started_subscription import (
    _payment_notes,
    _trial_latched_then_declined_twice,
)
from tests.test_paid_welcome_waits_for_money import (
    PRICE_PRO_MONTHLY,
    Harness,
    _invoice,
    _user,
)

LATCHED = "latched"
STRIPE_HISTORY = "stripe_history"
TWO_WAY_HEDGE = "first real payment on a trial"


def _closing(text: str) -> str:
    return text.splitlines()[-1]


async def _established_subscription(h: Harness, u: dict) -> tuple[str, dict]:
    """A Pro subscription paid for before the `paid_start:` latch existed:
    no latch row, one earlier paid invoice in Stripe's history."""
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    async with session_scope() as s:
        s.add(Subscription(
            id=sub_id, user_id=u["id"], status="active", tier="pro",
            current_period_end=datetime.now(UTC) + timedelta(hours=1),
            cancel_at_period_end=False, billing_period="monthly",
        ))
    h.paid[sub_id] = [(f"in_{uuid.uuid4().hex[:24]}", 999)]
    return sub_id, {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}


async def _latched_subscription(u: dict) -> tuple[str, dict]:
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    async with session_scope() as s:
        s.add(StripeWebhookEvent(id=f"paid_start:{sub_id}", event_type="paid_start"))
    return sub_id, {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}


# ── through the real webhook route ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_renewal_stripe_shows_was_paid_before_is_not_offered_as_a_first_payment(monkeypatch):
    h = Harness(monkeypatch)
    u = await _user(tier="pro")
    _sub_id, kw = await _established_subscription(h, u)

    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, tier="pro", price_id=PRICE_PRO_MONTHLY, amount_paid=999,
        billing_reason="subscription_cycle",
    ))

    notes = _payment_notes(h)
    assert len(notes) == 1, h.founder_messages
    closing = _closing(notes[0]["text"])
    assert TWO_WAY_HEDGE not in closing, closing
    assert "not a first payment" in closing.lower(), closing
    assert "renewal" in closing, closing


@pytest.mark.asyncio
async def test_an_upgrade_stripe_shows_was_paid_before_is_called_a_change_not_a_renewal(monkeypatch):
    h = Harness(monkeypatch)
    u = await _user(tier="pro")
    _sub_id, kw = await _established_subscription(h, u)

    # Pro -> Premium mid-period: Stripe invoices the prorated difference.
    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, amount_paid=1000, billing_reason="subscription_update",
    ))

    notes = _payment_notes(h)
    assert len(notes) == 1, h.founder_messages
    text = notes[0]["text"]
    closing = _closing(text)
    assert "billing reason: subscription_update" in text
    assert TWO_WAY_HEDGE not in closing, closing
    assert "can be a renewal" not in closing.lower(), closing
    assert "not a first payment" in closing.lower(), closing
    assert "change to the subscription" in closing, closing


@pytest.mark.asyncio
async def test_a_plan_change_charge_on_a_latched_subscription_is_not_read_as_a_renewal(monkeypatch):
    h = Harness(monkeypatch)
    u = await _user()
    _sub_id, kw = await _latched_subscription(u)

    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, amount_paid=1000, billing_reason="subscription_update",
    ))

    notes = _payment_notes(h)
    assert len(notes) == 1, h.founder_messages
    closing = _closing(notes[0]["text"])
    assert "can be a renewal" not in closing.lower(), closing
    assert "change to the subscription" in closing, closing
    # The latch alone cannot rule out that it is the first money.
    assert "first real payment" in closing, closing
    assert h.history_calls == [], "the latched path does not ask Stripe"


@pytest.mark.asyncio
async def test_a_retry_clearing_on_a_latched_trial_keeps_both_readings(monkeypatch):
    """The case the two-way reading exists for: it is still the right one here."""
    h = Harness(monkeypatch)
    u = await _user()
    _sub_id, charge = await _trial_latched_then_declined_twice(h, u)

    paid = dict(charge, status="paid", amount_paid=1999, attempt_count=3, next_payment_attempt=None)
    await h.deliver("invoice.payment_succeeded", paid)

    notes = _payment_notes(h)
    assert len(notes) == 1, h.founder_messages
    text = notes[0]["text"]
    closing = _closing(text)
    assert "renewal" in closing and TWO_WAY_HEDGE in closing, closing
    assert "failed-payment emails sent to this account before this payment: 2" in text
    assert "whole account" in text


# ── the formatter: every path x billing reason ──────────────────────────────

async def _note(monkeypatch, *, path: str, billing_reason: str | None, failed: int = 0) -> str:
    captured: list[dict] = []

    async def _capture(*, subject, text):
        captured.append({"subject": subject, "text": text})

    monkeypatch.setattr(telegram, "deliver_founder_alert", _capture, raising=True)
    await telegram.notify_founder_payment_received(
        path=path, amount=19.99, currency="usd", email=None,
        billing_reason=billing_reason, attempt_count=None,
        failed_payment_emails=failed, customer=None, subscription=None, invoice=None,
    )
    assert len(captured) == 1
    return captured[0]["text"]


def test_the_two_paths_are_named_by_the_formatter():
    assert telegram.PAYMENT_NOTE_LATCHED == LATCHED
    assert telegram.PAYMENT_NOTE_STRIPE_HISTORY == STRIPE_HISTORY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "billing_reason",
    ["subscription_cycle", "subscription_update", "subscription_create",
     "subscription_threshold", "manual", None],
)
async def test_the_stripe_history_path_never_offers_a_first_payment(monkeypatch, billing_reason):
    text = await _note(monkeypatch, path=STRIPE_HISTORY, billing_reason=billing_reason)
    closing = _closing(text)
    assert "not a first payment" in closing.lower(), closing
    assert "first real payment" not in closing, closing
    assert "earlier paid invoice" in text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "billing_reason", "must", "must_not"),
    [
        (STRIPE_HISTORY, "subscription_cycle", ["renewal"], ["change to the subscription"]),
        (STRIPE_HISTORY, "subscription_update", ["change to the subscription", "upgrade", "proration"],
         ["can be a renewal"]),
        (STRIPE_HISTORY, None, ["the invoice in Stripe"], []),
        (LATCHED, "subscription_cycle", ["renewal", TWO_WAY_HEDGE, "invoices in Stripe"],
         ["change to the subscription"]),
        (LATCHED, "subscription_update", ["change to the subscription", "first real payment"],
         ["can be a renewal"]),
        (LATCHED, "subscription_create", ["first invoice", "first payment"],
         ["renewal"]),
        (LATCHED, "subscription_threshold", ["subscription_threshold", "first real payment"], []),
        (LATCHED, None, ["renewal", "change to the subscription", "first real payment"], []),
    ],
)
async def test_the_closing_line_fits_the_path_and_billing_reason(
    monkeypatch, path, billing_reason, must, must_not,
):
    closing = _closing(await _note(monkeypatch, path=path, billing_reason=billing_reason))
    for phrase in must:
        assert phrase in closing, (phrase, closing)
    for phrase in must_not:
        assert phrase not in closing, (phrase, closing)


@pytest.mark.asyncio
async def test_the_failed_payment_count_says_it_is_account_wide(monkeypatch):
    text = await _note(monkeypatch, path=LATCHED, billing_reason="subscription_cycle", failed=3)
    line = next(ln for ln in text.splitlines() if ln.startswith("failed-payment emails"))
    assert line == (
        "failed-payment emails sent to this account before this payment: 3 "
        "(counted across the whole account, not only this subscription)"
    )


@pytest.mark.asyncio
async def test_no_failed_payment_line_when_there_were_none(monkeypatch):
    text = await _note(monkeypatch, path=LATCHED, billing_reason="subscription_cycle", failed=0)
    assert "failed-payment emails" not in text


@pytest.mark.asyncio
async def test_an_unknown_path_falls_back_to_the_hedged_reading(monkeypatch):
    """Never assert more than is known: an unrecognised path reads as LATCHED,
    the path that claims least."""
    text = await _note(monkeypatch, path="something-new", billing_reason="subscription_cycle")
    closing = _closing(text)
    assert TWO_WAY_HEDGE in closing and "not a first payment" not in closing.lower()
