"""Every significant charge gets a warning, not just the first one.

`customer.subscription.trial_will_end` warns before a trial converts. Nothing
warned before any charge AFTER that — including the annual renewal twelve
months later, which is the charge most likely to be forgotten and the one that
produces "I never agreed to this" disputes.

`render_annual_renewal_reminder_email` had existed since the retention work and
was reachable only from the admin preview harness: the template was written and
never given a trigger. `invoice.upcoming` is the trigger, and it carries the
amount Stripe is actually about to charge — which is the point, because a
grandfathered, discounted or proration-adjusted subscription renews at a figure
the sticker price does not know.

THE SHAPE HERE IS THE REAL ONE. The first version of these tests built invoice
lines as `{"price": {"recurring": {"interval": "year"}}}` and all seven passed
against a handler that could never have sent a single email. This Stripe
account is on API version 2026-08-26.dahlia (the webhook endpoint pins no
version, so it follows the account default), and on that version an invoice
line has NO `price` key at all — it carries `pricing.price_details.price`, a
bare ID string with no `recurring` block. The fixtures below are built from a
payload captured off the live account, and the interval is derived from
`period`, which every API version carries. Same failure archetype as the #635
checkout outage: a mock accepting a shape the vendor does not produce.
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

DAY = 86400


def _sign(payload: bytes) -> str:
    ts = int(time.time())
    sig = hmac.new(
        WEBHOOK_SECRET.encode(), f"{ts}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={sig}"


def _line_dahlia(*, start: int, end: int, amount: int = 19900) -> dict:
    """An invoice line EXACTLY as API 2026-08-26.dahlia sends it.

    Copied from a real upcoming invoice on the live account. Note what is
    absent: there is no `price` key, and nothing anywhere in the line states an
    interval. `pricing.price_details.price` is an ID with no `recurring`.
    """
    return {
        "id": f"il_tmp_{uuid.uuid4().hex[:16]}",
        "object": "line_item",
        "amount": amount,
        "currency": "usd",
        "description": "1 x Tapeline Premium Annual (at $199.00 / year)",
        "discount_amounts": [],
        "discountable": True,
        "discounts": [],
        "livemode": True,
        "metadata": {"billing_period": "annual", "tier": "premium"},
        "parent": {
            "invoice_item_details": None,
            "subscription_item_details": {
                "invoice_item": None,
                "proration": False,
                "subscription": f"sub_{uuid.uuid4().hex[:16]}",
                "subscription_item": f"si_{uuid.uuid4().hex[:14]}",
            },
            "type": "subscription_item_details",
        },
        "period": {"start": start, "end": end},
        "pricing": {
            "price_details": {
                "price": f"price_{uuid.uuid4().hex[:16]}",
                "product": f"prod_{uuid.uuid4().hex[:12]}",
            },
            "type": "price_details",
            "unit_amount_decimal": str(amount),
        },
        "quantity": 1,
        "subtotal": amount,
        "taxes": [],
    }


def _line_legacy(*, start: int, end: int, interval: str = "year") -> dict:
    """A pre-dahlia line, which DID carry an expanded `price` object.

    Kept so the handler is shown to work on both shapes: it must not depend on
    either one's pricing block.
    """
    return {
        "id": f"il_{uuid.uuid4().hex[:16]}",
        "object": "line_item",
        "amount": 19900,
        "currency": "usd",
        "period": {"start": start, "end": end},
        "price": {
            "id": f"price_{uuid.uuid4().hex[:16]}",
            "object": "price",
            "recurring": {"interval": interval, "interval_count": 1},
            "unit_amount": 19900,
        },
        "quantity": 1,
    }


def _invoice(
    *,
    customer: str,
    amount_due: int | None = 19900,
    period_days: int = 365,
    billing_reason: str = "subscription_cycle",
    currency: str = "usd",
    legacy_shape: bool = False,
    extra_lines: list[dict] | None = None,
    due_in_days: int = 7,
) -> dict:
    """An invoice.upcoming payload, shaped as Stripe actually delivers it."""
    due = int((datetime.now(UTC) + timedelta(days=due_in_days)).timestamp())
    start = due
    end = due + period_days * DAY
    build = _line_legacy if legacy_shape else _line_dahlia
    lines = [build(start=start, end=end)]
    lines.extend(extra_lines or [])
    return {
        "id": f"upcoming_in_{uuid.uuid4().hex[:16]}",
        "object": "invoice",
        "customer": customer,
        "amount_due": amount_due,
        "currency": currency,
        "billing_reason": billing_reason,
        "next_payment_attempt": due,
        "period_end": due,
        "lines": {"object": "list", "data": lines},
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
    smaller to call — and going through the route is the better test anyway: it
    exercises signature verification and the event-id dedup alongside the
    branch itself. Sends are captured rather than made.
    """
    # Patch the settings objects the code path ACTUALLY reads, which are the
    # module-level `settings = get_settings()` bindings in webhooks.py and
    # billing.py — not whatever get_settings() returns now. Several inbox tests
    # call `get_settings.cache_clear()`, after which get_settings() hands back a
    # NEW Settings while those module globals still point at the instance cached
    # at import time. Patching the fresh one left the route reading an unset
    # secret and returning 503: green alone, red in the full suite. They are
    # normally the same object; both are patched so this holds even if that
    # stops being true.
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
        # `AttributeError: object` when the key is absent — before any of our
        # code runs. A payload built without it fails in the vendor library,
        # not in the handler under test.
        "object": "event",
        "api_version": "2026-08-26.dahlia",
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
async def test_the_shape_stripe_actually_sends_produces_an_email(monkeypatch):
    """THE TEST THAT MATTERS. No `price` key anywhere in the line.

    This is the exact line shape captured from the live account. A handler that
    reads the interval out of a pricing block sends nothing here, which is what
    the first version of this feature did while passing seven tests.
    """
    user = await _user()
    try:
        inv = _invoice(customer=user.stripe_customer_id)
        assert "price" not in inv["lines"]["data"][0], (
            "the fixture drifted back to the old shape; it must reproduce what "
            "API 2026-08-26.dahlia really sends"
        )
        sent = await _handle(monkeypatch, inv)
        assert len(sent) == 1, (
            "no email for the shape Stripe actually delivers — the handler is "
            "reading a field that no longer exists on the invoice line"
        )
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_the_older_line_shape_also_works(monkeypatch):
    """Version independence, from the other direction.

    Pre-dahlia lines carry an expanded `price`. Both shapes carry `period`,
    which is why the handler reads that and nothing else.
    """
    user = await _user()
    try:
        sent = await _handle(
            monkeypatch,
            _invoice(customer=user.stripe_customer_id, legacy_shape=True),
        )
        assert len(sent) == 1, "an older-shaped invoice line stopped working"
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_an_annual_renewal_gets_a_warning(monkeypatch):
    user = await _user()
    try:
        sent = await _handle(monkeypatch, _invoice(customer=user.stripe_customer_id))
        assert len(sent) == 1, "no pre-renewal notice was sent for an annual renewal"
        body = sent[0]["html"]
        # The amount must come from the INVOICE, not the sticker price.
        assert "199.00" in body, f"charged amount not stated: {sent[0]['subject']}"
        assert "renew" in body.lower()
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
            "the email quoted something other than the invoice's amount_due — a "
            "grandfathered or coupon'd customer would be told the wrong price"
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
async def test_a_charge_already_covered_by_the_trial_notice_is_skipped(monkeypatch):
    """Two emails for one payment is the failure this guard prevents.

    An annual trialist converting on 14 Sep gets `trial_will_end` ~3 days
    before, stating that same date and amount. Stripe ALSO fires
    invoice.upcoming for that first invoice, and its billing_reason is not
    reliably `subscription_create` — so the overlap is decided from our own
    `trial_ends_at`, which is copied from the subscription's trial_end.
    """
    due = datetime.now(UTC) + timedelta(days=7)
    user = await _user(trial_ends_at=due)
    try:
        sent = await _handle(
            monkeypatch, _invoice(customer=user.stripe_customer_id, due_in_days=7)
        )
        assert sent == [], (
            "the trial's converting charge got a second warning on top of "
            "trial_will_end; the customer receives two emails for one payment"
        )
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_the_renewal_a_year_after_the_trial_is_still_warned(monkeypatch):
    """The other half of that guard: it must expire, not silence forever."""
    user = await _user(trial_ends_at=datetime.now(UTC) - timedelta(days=358))
    try:
        sent = await _handle(monkeypatch, _invoice(customer=user.stripe_customer_id))
        assert len(sent) == 1, (
            "a past trial_ends_at suppressed the real renewal notice a year "
            "later — the exact charge this feature exists to warn about"
        )
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_the_trials_own_first_invoice_is_skipped(monkeypatch):
    """Belt and braces alongside the trial_ends_at check."""
    user = await _user()
    try:
        sent = await _handle(
            monkeypatch,
            _invoice(
                customer=user.stripe_customer_id,
                billing_reason="subscription_create",
            ),
        )
        assert sent == [], "an invoice marked subscription_create was warned about"
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_monthly_renewals_are_not_reminded(monkeypatch):
    """Deliberate. Twelve reminders a year trains people to ignore billing mail.

    The surprise risk — and the regulatory expectation — lives in the long
    intervals. If this ever needs to include monthly, the threshold is one
    number.
    """
    user = await _user()
    try:
        sent = await _handle(
            monkeypatch,
            _invoice(customer=user.stripe_customer_id, period_days=31, amount_due=1999),
        )
        assert sent == [], "a monthly renewal generated a reminder"
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_a_six_month_plan_is_reminded(monkeypatch):
    """The cut is at the length of the billed period, not the word 'annual'.

    181 days is the SHORTEST possible six-month span (1 Feb to 1 Aug in a
    non-leap year), so the 180-day threshold cannot clip a real half-yearly
    plan.
    """
    user = await _user()
    try:
        sent = await _handle(
            monkeypatch,
            _invoice(
                customer=user.stripe_customer_id, period_days=181, amount_due=9900
            ),
        )
        assert len(sent) == 1, "a 6-month plan should still be warned about"
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_a_proration_line_does_not_hide_the_annual_line(monkeypatch):
    """Mid-cycle plan changes add short lines beside the real subscription one.

    Reading only the first line would classify this invoice as a few days'
    proration and skip a genuine annual renewal.
    """
    user = await _user()
    try:
        now = int(datetime.now(UTC).timestamp())
        proration = _line_dahlia(start=now, end=now + 3 * DAY, amount=430)
        inv = _invoice(customer=user.stripe_customer_id, extra_lines=[proration])
        # Put the short proration FIRST, which is the case that would break a
        # handler reading lines[0].
        inv["lines"]["data"].reverse()
        sent = await _handle(monkeypatch, inv)
        assert len(sent) == 1, (
            "a proration line ahead of the annual line suppressed the notice"
        )
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_an_unknown_customer_does_not_raise(monkeypatch):
    """Webhooks must ack. An exception here becomes a Stripe retry storm."""
    sent = await _handle(monkeypatch, _invoice(customer="cus_does_not_exist"))
    assert sent == []
