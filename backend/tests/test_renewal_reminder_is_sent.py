"""Every significant charge gets a warning, not just the first one.

`customer.subscription.trial_will_end` warns before a trial converts. Nothing
warned before any charge AFTER that — including the annual renewal twelve
months later, which is the charge most likely to be forgotten and the one that
produces "I never agreed to this" disputes.

`render_annual_renewal_reminder_email` had existed since the retention work and
was reachable only from the admin preview harness: the template was written and
never given a trigger. `invoice.upcoming` is the trigger, and it carries the
amount Stripe is actually about to charge — which is the point, because a
grandfathered, discounted or proration-adjusted subscription renews at a
figure the sticker price does not know.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.main import app
from app.models import User

WEBHOOK_SECRET = "whsec_test_secret_for_renewal_tests"


def _sign(payload: bytes) -> str:
    ts = int(time.time())
    sig = hmac.new(
        WEBHOOK_SECRET.encode(), f"{ts}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={sig}"


def _invoice(
    *,
    customer: str,
    amount_due: int | None = 19900,
    interval: str = "year",
    interval_count: int = 1,
    billing_reason: str = "subscription_cycle",
    currency: str = "usd",
) -> dict:
    """A Stripe invoice.upcoming payload, shaped as the handler reads it."""
    when = int((datetime.now(UTC) + timedelta(days=7)).timestamp())
    return {
        "customer": customer,
        "amount_due": amount_due,
        "currency": currency,
        "billing_reason": billing_reason,
        "next_payment_attempt": when,
        "period_end": when,
        "lines": {
            "data": [
                {
                    "price": {
                        "recurring": {
                            "interval": interval,
                            "interval_count": interval_count,
                        }
                    }
                }
            ]
        },
    }


async def _user(**over) -> User:
    uid = f"u_{uuid.uuid4().hex}"
    fields = {
        "id": uid,
        "email": f"{uid}@example.test",
        "name": "Renewal probe",
        "tier": "premium",
        "password_hash": "x",
        "drip_state": "",
        "stripe_customer_id": f"cus_{uuid.uuid4().hex[:18]}",
    }
    fields.update(over)
    async with session_scope() as s:
        s.add(User(**fields))
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


async def _cleanup(user: User) -> None:
    async with session_scope() as s:
        await s.execute(delete(User).where(User.id == user.id))


async def _handle(monkeypatch, invoice: dict) -> list[dict]:
    """POST a properly signed invoice.upcoming through the REAL endpoint.

    The handler lives inline in the stripe_webhook route, so there is nothing
    smaller to call — and going through the route is the better test anyway:
    it exercises signature verification and the event-id dedup alongside the
    branch itself. Sends are captured rather than made.
    """
    # Patch the settings objects the code path ACTUALLY reads, which are the
    # module-level `settings = get_settings()` bindings in webhooks.py and
    # billing.py — not whatever get_settings() returns now. Several inbox
    # tests call `get_settings.cache_clear()`, after which get_settings()
    # hands back a NEW Settings while those module globals still point at the
    # instance cached at import time. Patching the fresh one left the route
    # reading an unset secret and returning 503: green alone, red in the full
    # suite. They are normally the same object; both are patched so this holds
    # even if that stops being true.
    from app.routers import webhooks as webhooks_mod
    from app.services import billing as billing_mod

    for mod in (webhooks_mod, billing_mod):
        monkeypatch.setattr(
            mod.settings, "stripe_webhook_secret", WEBHOOK_SECRET, raising=False
        )

    sent: list[dict] = []

    async def _capture(to, subject, html, **kw):
        sent.append({"to": to, "subject": subject, "html": html, **kw})
        return {"ok": True}

    monkeypatch.setattr("app.services.email.send_email", _capture, raising=True)

    event = {
        "id": f"evt_{uuid.uuid4().hex}",
        # `"object": "event"` is not decoration. stripe-python's
        # construct_event reads `event.object` to sort v1 from v2 events
        # (_webhook.py:36), and StripeObject.__getattr__ raises
        # `AttributeError: object` when the key is absent — before any of
        # our code runs. A payload built without it fails in the vendor
        # library, not in the handler under test.
        "object": "event",
        "api_version": "2024-06-20",
        "type": "invoice.upcoming",
        "data": {"object": invoice},
    }
    payload = json.dumps(event).encode()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/webhooks/stripe",
            content=payload,
            headers={
                "stripe-signature": _sign(payload),
                "content-type": "application/json",
            },
        )
    assert r.status_code == 200, f"webhook must ack, got {r.status_code}: {r.text}"
    return sent


@pytest.mark.asyncio
async def test_an_annual_renewal_gets_a_warning(monkeypatch):
    user = await _user()
    try:
        sent = await _handle(
            monkeypatch, _invoice(customer=user.stripe_customer_id)
        )
        assert len(sent) == 1, "no pre-renewal notice was sent for an annual renewal"
        body = sent[0]["html"]
        # The amount must come from the INVOICE, not the sticker price.
        assert "199.00" in body, f"the charged amount is not stated: {sent[0]['subject']}"
        assert "renews" in body.lower()
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_the_amount_comes_from_the_invoice_not_the_price_list(monkeypatch):
    """A discounted or grandfathered subscription renews at its own figure."""
    user = await _user()
    try:
        sent = await _handle(
            monkeypatch,
            _invoice(customer=user.stripe_customer_id, amount_due=14900),
        )
        assert len(sent) == 1
        assert "149.00" in sent[0]["html"], (
            "the email quoted something other than the invoice's amount_due — "
            "a grandfathered or coupon'd customer would be told the wrong price"
        )
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_an_unknown_amount_does_not_invent_one(monkeypatch):
    """Quoting a wrong number is worse than quoting none.

    The renderer takes amount_label=None and points at billing instead.
    """
    user = await _user()
    try:
        sent = await _handle(
            monkeypatch,
            _invoice(customer=user.stripe_customer_id, amount_due=None),
        )
        assert len(sent) == 1
        body = sent[0]["html"]
        assert "$0.00" not in body and "$None" not in body, (
            "an unknown amount rendered as a number"
        )
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_the_trials_own_first_invoice_is_skipped(monkeypatch):
    """trial_will_end already owns that moment — two warnings for one charge."""
    user = await _user()
    try:
        sent = await _handle(
            monkeypatch,
            _invoice(
                customer=user.stripe_customer_id,
                billing_reason="subscription_create",
            ),
        )
        assert sent == [], (
            "the trial's first charge got a second warning; the customer would "
            "receive two emails about one payment"
        )
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_monthly_renewals_are_not_reminded(monkeypatch):
    """Deliberate. Twelve reminders a year trains people to ignore billing mail.

    The surprise risk — and the regulatory expectation — lives in the long
    intervals. If this ever needs to include monthly, the guard is one line.
    """
    user = await _user()
    try:
        sent = await _handle(
            monkeypatch,
            _invoice(
                customer=user.stripe_customer_id,
                interval="month",
                amount_due=1999,
            ),
        )
        assert sent == [], "a monthly renewal generated a reminder"
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_a_six_month_plan_is_reminded(monkeypatch):
    """The cut is at the interval length, not at the word 'annual'."""
    user = await _user()
    try:
        sent = await _handle(
            monkeypatch,
            _invoice(
                customer=user.stripe_customer_id,
                interval="month",
                interval_count=6,
                amount_due=9900,
            ),
        )
        assert len(sent) == 1, "a 6-month plan should still be warned about"
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_an_unknown_customer_does_not_raise(monkeypatch):
    """Webhooks must ack. An exception here becomes a Stripe retry storm."""
    sent = await _handle(monkeypatch, _invoice(customer="cus_does_not_exist"))
    assert sent == []
