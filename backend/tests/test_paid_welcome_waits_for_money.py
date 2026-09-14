""""You're in" and the founder's revenue alert wait for money to arrive.

THE INCIDENT. The welcome-to-paid email ("You're in — welcome to Tapeline
Premium") and `notify_founder_new_subscription` used to fire the first time a
subscription reached `status == "active"`. At the end of a card-required trial
Stripe sets the subscription active about an hour BEFORE it attempts the first
invoice. On 2026-09-12 and again on 2026-09-14 a trial customer was told they
were in, the founder was told about a sale, and then the first charge was
declined. A welcome for a charge that did not happen is a false statement to a
customer about their money.

THE RULE. Both fire when the subscription's first invoice with
`amount_paid > 0` succeeds (`invoice.payment_succeeded`, which is the invoice
event the live webhook endpoint is subscribed to), exactly once per
subscription, with the amount taken from the invoice.

THE SHAPES ARE THE REAL ONES. Every event below goes through the real
`/api/webhooks/stripe` route with a locally computed Stripe signature, so
`stripe.Webhook.construct_event` — the vendor code production runs — accepts
it first. The invoice payloads follow what this account actually delivers on
API 2026-04-22.dahlia (read off live events, read-only, on 2026-09-14): there
is NO top-level `subscription` on an invoice; the id and the checkout metadata
live at `parent.subscription_details`, and invoice lines carry
`pricing.price_details.price` rather than a `price` object. A fixture with a
top-level `subscription` would pass against a handler that finds nothing in
production.

The one thing that is stood in for is Stripe's paid-invoice history
(`subscription_has_other_paid_invoice`), which the handler consults only for a
non-`subscription_create` invoice on a subscription with no latch. The stand-in
answers from the invoices this test has actually paid, which is what Stripe's
list returns; the function itself is tested against real SDK objects at the end
of this file.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import stripe
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import StripeWebhookEvent, Subscription, User

WEBHOOK_SECRET = "whsec_test_secret_for_paid_welcome"
PRICE_PREMIUM_MONTHLY = "price_test_premium_monthly_welcome"
PRICE_PRO_MONTHLY = "price_test_pro_monthly_welcome"
DAY = 86400


def _sign(payload: bytes) -> str:
    ts = int(time.time())
    sig = hmac.new(
        WEBHOOK_SECRET.encode(), f"{ts}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={sig}"


def _now() -> int:
    return int(datetime.now(UTC).timestamp())


# ── payload builders ────────────────────────────────────────────────────────

def _subscription(
    *,
    sub_id: str,
    customer: str,
    user_id: str,
    status: str,
    tier: str = "premium",
    price_id: str = PRICE_PREMIUM_MONTHLY,
    unit_amount: int = 1999,
    trial_end: int | None = None,
) -> dict[str, Any]:
    """A subscription as `customer.subscription.*` delivers it.

    Items still carry an expanded `price` on this account's API version, and
    `current_period_end` lives on the ITEM (the basil move).
    """
    now = _now()
    return {
        "id": sub_id,
        "object": "subscription",
        "customer": customer,
        "status": status,
        "cancel_at_period_end": False,
        "canceled_at": None,
        "pause_collection": None,
        "trial_start": now if trial_end else None,
        "trial_end": trial_end,
        "start_date": now,
        "metadata": {"user_id": user_id, "tier": tier, "billing_period": "monthly"},
        "items": {
            "object": "list",
            "data": [
                {
                    "id": f"si_{uuid.uuid4().hex[:14]}",
                    "object": "subscription_item",
                    "current_period_end": (trial_end or now) + 30 * DAY,
                    "price": {
                        "id": price_id,
                        "object": "price",
                        "unit_amount": unit_amount,
                        "currency": "usd",
                        "recurring": {"interval": "month", "interval_count": 1},
                    },
                }
            ],
        },
    }


def _invoice(
    *,
    sub_id: str,
    customer: str,
    user_id: str,
    amount_paid: int,
    billing_reason: str,
    status: str = "paid",
    amount_due: int | None = None,
    tier: str = "premium",
    price_id: str = PRICE_PREMIUM_MONTHLY,
    currency: str = "usd",
    attempt_count: int = 1,
    next_payment_attempt: int | None = None,
    period_start: int | None = None,
) -> dict[str, Any]:
    """An invoice as API 2026-04-22.dahlia delivers it: no top-level
    `subscription`, metadata under `parent.subscription_details`, and lines
    with `pricing.price_details.price` instead of a `price` object."""
    start = period_start if period_start is not None else _now()
    end = start + 30 * DAY
    meta = {"billing_period": "monthly", "tier": tier, "user_id": user_id}
    inv_id = f"in_{uuid.uuid4().hex[:24]}"
    return {
        "id": inv_id,
        "object": "invoice",
        "customer": customer,
        "status": status,
        "billing_reason": billing_reason,
        "amount_paid": amount_paid,
        "amount_due": amount_paid if amount_due is None else amount_due,
        "amount_remaining": 0 if status == "paid" else (amount_due or 0),
        "currency": currency,
        "attempt_count": attempt_count,
        "next_payment_attempt": next_payment_attempt,
        "metadata": {},
        "period_start": start,
        "period_end": start,
        "parent": {
            "type": "subscription_details",
            "quote_details": None,
            "subscription_details": {"metadata": meta, "subscription": sub_id},
        },
        "lines": {
            "object": "list",
            "data": [
                {
                    "id": f"il_{uuid.uuid4().hex[:16]}",
                    "object": "line_item",
                    "amount": amount_due if amount_due is not None else amount_paid,
                    "currency": currency,
                    "invoice": inv_id,
                    "metadata": meta,
                    "parent": {
                        "type": "subscription_item_details",
                        "invoice_item_details": None,
                        "subscription_item_details": {
                            "invoice_item": None,
                            "proration": False,
                            "subscription": sub_id,
                            "subscription_item": f"si_{uuid.uuid4().hex[:14]}",
                        },
                    },
                    "period": {"start": start, "end": end},
                    "pricing": {
                        "type": "price_details",
                        "price_details": {
                            "price": price_id,
                            "product": f"prod_{uuid.uuid4().hex[:12]}",
                        },
                        "unit_amount_decimal": str(amount_due or amount_paid),
                    },
                    "quantity": 1,
                }
            ],
        },
    }


def _checkout_session(*, user_id: str, customer: str, sub_id: str, amount_total: int) -> dict:
    return {
        "id": f"cs_{uuid.uuid4().hex[:24]}",
        "object": "checkout.session",
        "client_reference_id": user_id,
        "customer": customer,
        "subscription": sub_id,
        "mode": "subscription",
        "amount_total": amount_total,
        "currency": "usd",
        "status": "complete",
    }


# ── harness ─────────────────────────────────────────────────────────────────

class Harness:
    """Delivers signed events through the real route and records what the
    handler tried to send. Nothing leaves the process."""

    def __init__(self, monkeypatch) -> None:
        from app.routers import webhooks as webhooks_mod
        from app.services import billing as billing_mod

        self.sent: list[dict] = []
        self.alerts: list[dict] = []
        # sub_id -> [(invoice_id, amount_paid)] of invoices Stripe holds as paid
        self.paid: dict[str, list[tuple[str, int]]] = {}
        self.history_calls: list[str] = []
        self.history_unavailable = False

        for mod in (webhooks_mod, billing_mod):
            monkeypatch.setattr(mod.settings, "stripe_webhook_secret", WEBHOOK_SECRET, raising=False)
            monkeypatch.setattr(mod.settings, "stripe_price_premium_monthly", PRICE_PREMIUM_MONTHLY, raising=False)
            monkeypatch.setattr(mod.settings, "stripe_price_pro_monthly", PRICE_PRO_MONTHLY, raising=False)

        async def _capture_email(to, subject, html, **kw):
            self.sent.append({"to": to, "subject": subject, "html": html, **kw})
            return {"ok": True}

        async def _capture_alert(**kw):
            self.alerts.append(kw)

        async def _history(sub_id, invoice_id):
            self.history_calls.append(sub_id)
            if self.history_unavailable:
                return None
            return any(
                iid != invoice_id and amt > 0 for iid, amt in self.paid.get(sub_id, [])
            )

        async def _noop(*a, **kw):
            return None

        monkeypatch.setattr("app.services.email.send_email", _capture_email, raising=True)
        monkeypatch.setattr(
            "app.services.telegram.notify_founder_new_subscription", _capture_alert, raising=True,
        )
        monkeypatch.setattr(webhooks_mod, "subscription_has_other_paid_invoice", _history, raising=True)
        # Belt and braces: no analytics or ad-platform event can leave a test.
        monkeypatch.setattr("app.services.meta_capi.is_configured", lambda: False, raising=True)
        monkeypatch.setattr("app.services.analytics.is_configured", lambda: False, raising=True)
        monkeypatch.setattr("app.services.meta_capi.track_start_trial", _noop, raising=True)

    async def deliver(self, evt_type: str, obj: dict, *, event_id: str | None = None) -> dict:
        if evt_type == "invoice.payment_succeeded":
            sub_id = obj["parent"]["subscription_details"]["subscription"]
            entry = (obj["id"], obj["amount_paid"])
            if entry not in self.paid.setdefault(sub_id, []):
                self.paid[sub_id].append(entry)
        event = {
            "id": event_id or f"evt_{uuid.uuid4().hex}",
            # construct_event reads event.object before any handler code runs.
            "object": "event",
            "api_version": "2026-04-22.dahlia",
            "created": _now(),
            "type": evt_type,
            "data": {"object": obj},
        }
        payload = json.dumps(event).encode()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(
                "/api/webhooks/stripe",
                content=payload,
                headers={"stripe-signature": _sign(payload), "content-type": "application/json"},
            )
        assert r.status_code == 200, f"webhook must ack, got {r.status_code}: {r.text}"
        return r.json()

    @property
    def welcomes(self) -> list[dict]:
        return [s for s in self.sent if s["subject"].startswith("You're in")]


async def _user(*, linked: bool = True, tier: str = "free") -> dict[str, str | None]:
    uid = f"u_{uuid.uuid4().hex}"
    customer = f"cus_{uuid.uuid4().hex[:14]}"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.test", name="Welcome probe",
            tier=tier, password_hash="x", drip_state="",
            stripe_customer_id=customer if linked else None,
        ))
    return {"id": uid, "customer": customer, "email": f"{uid}@example.test"}


async def _latch_exists(sub_id: str) -> bool:
    async with session_scope() as s:
        row = (await s.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.id == f"paid_start:{sub_id}")
        )).scalar_one_or_none()
    return row is not None


async def _trial_through_declined_first_charge(h: Harness, u: dict) -> tuple[str, dict]:
    """A card-required trial, exactly as Stripe sequences it, up to the decline.

    trialing (+$0 trial invoice) -> trial ends -> active (no charge yet) ->
    the first invoice's payment fails -> past_due.
    """
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    trial_end = _now() + 30 * DAY
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}

    await h.deliver("customer.subscription.created", _subscription(**kw, status="trialing", trial_end=trial_end))
    await h.deliver("invoice.payment_succeeded", _invoice(**kw, amount_paid=0, billing_reason="subscription_create"))
    # Trial over: Stripe sets it active ~1h BEFORE attempting the charge.
    await h.deliver("customer.subscription.updated", _subscription(**kw, status="active", trial_end=trial_end))
    first_charge = _invoice(
        **kw, amount_paid=0, amount_due=1999, status="open",
        billing_reason="subscription_cycle", next_payment_attempt=_now() + 2 * DAY,
    )
    await h.deliver("invoice.payment_failed", first_charge)
    await h.deliver("customer.subscription.updated", _subscription(**kw, status="past_due", trial_end=trial_end))
    return sub_id, first_charge


# ── the incident ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trial_active_then_declined_sends_no_welcome_and_no_alert(monkeypatch):
    h = Harness(monkeypatch)
    u = await _user()
    await _trial_through_declined_first_charge(h, u)

    assert h.welcomes == [], (
        "a customer was told \"You're in\" before any money arrived — the "
        "subscription went active and the first charge was then declined"
    )
    assert h.alerts == [], "the founder was alerted to a sale whose charge was declined"
    # The emails that SHOULD have gone out still did.
    subjects = [s["subject"] for s in h.sent]
    assert any("trial has started" in s for s in subjects)
    assert any("payment didn't go through" in s for s in subjects)


@pytest.mark.asyncio
async def test_first_charge_clearing_through_dunning_sends_exactly_one(monkeypatch):
    h = Harness(monkeypatch)
    u = await _user()
    sub_id, first_charge = await _trial_through_declined_first_charge(h, u)
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}
    # "Exactly one" alone would pass against the old trigger, which had already
    # sent its one welcome at `active`. It has to be none until the money.
    assert h.welcomes == [] and h.alerts == []

    # Stripe's retry succeeds on the same invoice.
    paid = dict(first_charge, status="paid", amount_paid=1999, attempt_count=2)
    await h.deliver("invoice.payment_succeeded", paid)
    await h.deliver("customer.subscription.updated", _subscription(**kw, status="active"))

    assert len(h.welcomes) == 1, f"expected one welcome at the successful charge, got {len(h.welcomes)}"
    assert h.welcomes[0]["to"] == u["email"]
    assert "Premium" in h.welcomes[0]["subject"]
    assert "$19.99" in h.welcomes[0]["html"]
    assert len(h.alerts) == 1, f"expected one founder alert, got {len(h.alerts)}"
    assert h.alerts[0]["amount"] == pytest.approx(19.99)
    assert h.alerts[0]["tier"] == "premium"
    assert await _latch_exists(sub_id)

    # The next month's renewal is not a new subscription.
    renewal = _invoice(
        **kw, amount_paid=1999, billing_reason="subscription_cycle",
        period_start=_now() + 30 * DAY,
    )
    await h.deliver("invoice.payment_succeeded", renewal)
    assert len(h.welcomes) == 1 and len(h.alerts) == 1, "a renewal re-sent the welcome"


@pytest.mark.asyncio
async def test_redelivered_payment_succeeded_does_not_send_twice(monkeypatch):
    h = Harness(monkeypatch)
    u = await _user()
    _sub_id, first_charge = await _trial_through_declined_first_charge(h, u)
    assert h.welcomes == [] and h.alerts == []

    paid = dict(first_charge, status="paid", amount_paid=1999, attempt_count=2)
    event_id = f"evt_{uuid.uuid4().hex}"
    first = await h.deliver("invoice.payment_succeeded", paid, event_id=event_id)
    again = await h.deliver("invoice.payment_succeeded", paid, event_id=event_id)

    assert first.get("replay") is not True
    assert again.get("replay") is True
    assert len(h.welcomes) == 1
    assert len(h.alerts) == 1


# ── direct paid checkout (no trial) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_direct_paid_checkout_checkout_event_first_sends_exactly_one(monkeypatch):
    h = Harness(monkeypatch)
    u = await _user(linked=False)
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}
    pro = {"tier": "pro", "price_id": PRICE_PRO_MONTHLY}

    await h.deliver("checkout.session.completed", _checkout_session(
        user_id=u["id"], customer=u["customer"], sub_id=sub_id, amount_total=999,
    ))
    await h.deliver("customer.subscription.created", _subscription(**kw, **pro, status="active", unit_amount=999))
    assert h.welcomes == [] and h.alerts == [], "welcomed before the invoice was paid"
    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, **pro, amount_paid=999, billing_reason="subscription_create",
    ))

    assert len(h.welcomes) == 1
    assert "Pro" in h.welcomes[0]["subject"]
    assert "$9.99" in h.welcomes[0]["html"]
    assert len(h.alerts) == 1 and h.alerts[0]["amount"] == pytest.approx(9.99)
    # A subscription_create invoice is the first by definition — no history call.
    assert h.history_calls == []


@pytest.mark.asyncio
async def test_direct_paid_checkout_invoice_event_first_sends_exactly_one(monkeypatch):
    """Stripe does not order events. The invoice can land before
    checkout.session.completed has linked the customer to the account."""
    h = Harness(monkeypatch)
    u = await _user(linked=False)
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}
    pro = {"tier": "pro", "price_id": PRICE_PRO_MONTHLY}

    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, **pro, amount_paid=999, billing_reason="subscription_create",
    ))
    assert len(h.welcomes) == 1, (
        "the paid invoice arrived before the customer was linked and nobody "
        "was welcomed — resolve the user from the subscription metadata"
    )
    assert h.welcomes[0]["to"] == u["email"]
    assert "Pro" in h.welcomes[0]["subject"]
    assert len(h.alerts) == 1

    await h.deliver("customer.subscription.created", _subscription(**kw, **pro, status="active", unit_amount=999))
    await h.deliver("checkout.session.completed", _checkout_session(
        user_id=u["id"], customer=u["customer"], sub_id=sub_id, amount_total=999,
    ))
    assert len(h.welcomes) == 1 and len(h.alerts) == 1, "a later event sent a second welcome"


# ── $0 invoices ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_zero_dollar_invoice_never_welcomes_and_never_claims_the_latch(monkeypatch):
    """A 100%-off referral month: active, first invoice paid for $0. Not money.
    The first invoice that DOES carry money still gets its one welcome."""
    h = Harness(monkeypatch)
    u = await _user()
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}

    await h.deliver("customer.subscription.created", _subscription(**kw, status="active"))
    await h.deliver("invoice.payment_succeeded", _invoice(**kw, amount_paid=0, billing_reason="subscription_create"))
    assert h.welcomes == [] and h.alerts == []
    assert not await _latch_exists(sub_id), "a $0 invoice claimed the once-per-subscription latch"

    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, amount_paid=1999, billing_reason="subscription_cycle", period_start=_now() + 30 * DAY,
    ))
    assert len(h.welcomes) == 1 and len(h.alerts) == 1


@pytest.mark.asyncio
async def test_amount_and_currency_come_from_the_invoice_not_the_price(monkeypatch):
    """A discounted first charge: the price says $19.99, the customer paid $11.99."""
    h = Harness(monkeypatch)
    u = await _user(linked=False)
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}

    await h.deliver("customer.subscription.created", _subscription(**kw, status="active", unit_amount=1999))
    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, amount_paid=1199, amount_due=1199, billing_reason="subscription_create", currency="aud",
    ))

    assert len(h.welcomes) == 1
    html = h.welcomes[0]["html"]
    assert "$11.99 AUD" in html, "the welcome did not state what the invoice charged"
    assert "19.99" not in html, "the welcome quoted the list price instead of the charge"
    assert h.alerts[0]["amount"] == pytest.approx(11.99)
    assert str(h.alerts[0]["currency"]).lower() == "aud"


# ── subscriptions paid for before this rule existed ─────────────────────────

@pytest.mark.asyncio
async def test_an_already_paying_subscription_is_not_welcomed_at_renewal(monkeypatch):
    """One live Pro subscription paid on 2026-08-29 has no latch row. Its first
    renewal arrives as customer.subscription.updated (active) plus a paid
    subscription_cycle invoice. Neither is a new sale."""
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

    await h.deliver("customer.subscription.updated", _subscription(**kw, **pro, status="active", unit_amount=999))
    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, **pro, amount_paid=999, billing_reason="subscription_cycle",
    ))

    assert h.welcomes == [], "a month-old subscriber was welcomed as new at renewal"
    assert h.alerts == [], "a renewal was reported to the founder as a new subscription"
    assert await _latch_exists(sub_id), "the established subscription was not latched"

    calls = len(h.history_calls)
    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, **pro, amount_paid=999, billing_reason="subscription_cycle", period_start=_now() + 30 * DAY,
    ))
    assert len(h.history_calls) == calls, "Stripe's history was consulted again after latching"
    assert h.welcomes == [] and h.alerts == []


@pytest.mark.asyncio
async def test_a_trial_already_welcomed_by_the_old_trigger_is_not_welcomed_again(monkeypatch):
    """The two trial customers from the incident already received "You're in"
    at `active`, and the old trigger wrote their `paid_start:` latch row. If
    their first charge now clears through dunning, Stripe's history shows no
    earlier paid invoice — so only the latch stops a second welcome."""
    h = Harness(monkeypatch)
    u = await _user()
    sub_id, first_charge = await _trial_through_declined_first_charge(h, u)
    async with session_scope() as s:
        s.add(StripeWebhookEvent(id=f"paid_start:{sub_id}", event_type="paid_start"))

    await h.deliver("invoice.payment_succeeded", dict(first_charge, status="paid", amount_paid=1999))

    assert h.welcomes == [], "a customer already told \"You're in\" was told it again"
    assert h.alerts == []
    assert h.history_calls == [], "the latch should short-circuit before Stripe is asked"


@pytest.mark.asyncio
async def test_unavailable_history_sends_nothing_and_claims_nothing(monkeypatch):
    h = Harness(monkeypatch)
    u = await _user()
    sub_id, first_charge = await _trial_through_declined_first_charge(h, u)
    h.history_unavailable = True

    await h.deliver("invoice.payment_succeeded", dict(first_charge, status="paid", amount_paid=1999))

    assert h.welcomes == [] and h.alerts == []
    assert not await _latch_exists(sub_id)


# ── the history lookup itself, against real SDK objects ─────────────────────

def _invoice_list(*invoices: dict) -> stripe.ListObject:
    """What stripe.Invoice.list returns: a ListObject of Invoice objects —
    neither of which has `.get()`."""
    return stripe.ListObject.construct_from(
        {
            "object": "list",
            "url": "/v1/invoices",
            "has_more": False,
            "data": [dict({"object": "invoice"}, **inv) for inv in invoices],
        },
        "sk_test_not_a_real_key",
    )


@pytest.mark.asyncio
async def test_history_finds_an_earlier_paid_invoice(monkeypatch):
    from app.services import billing

    calls: list[dict] = []

    def _list(**kw):
        calls.append(kw)
        return _invoice_list(
            {"id": "in_now", "status": "paid", "amount_paid": 999},
            {"id": "in_before", "status": "paid", "amount_paid": 999},
        )

    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test_not_a_real_key", raising=False)
    monkeypatch.setattr(stripe.Invoice, "list", _list)

    assert await billing.subscription_has_other_paid_invoice("sub_x", "in_now") is True
    assert calls == [{"subscription": "sub_x", "status": "paid", "limit": 100}]
    # The fixture is the vendor's type, not a dict that happens to have .get().
    sample = _invoice_list({"id": "in_1", "status": "paid", "amount_paid": 1})["data"][0]
    assert isinstance(sample, stripe.Invoice) and not isinstance(sample, dict)


@pytest.mark.asyncio
async def test_history_ignores_zero_dollar_invoices_and_the_current_one(monkeypatch):
    from app.services import billing

    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test_not_a_real_key", raising=False)
    monkeypatch.setattr(stripe.Invoice, "list", lambda **kw: _invoice_list(
        {"id": "in_now", "status": "paid", "amount_paid": 1999},
        {"id": "in_trial", "status": "paid", "amount_paid": 0},
    ))

    assert await billing.subscription_has_other_paid_invoice("sub_x", "in_now") is False


@pytest.mark.asyncio
async def test_history_is_none_when_stripe_cannot_be_asked(monkeypatch):
    from app.services import billing

    monkeypatch.setattr(billing.settings, "stripe_secret_key", "", raising=False)
    assert await billing.subscription_has_other_paid_invoice("sub_x", "in_now") is None

    def _boom(**kw):
        raise stripe.error.APIConnectionError("network down")

    monkeypatch.setattr(billing.settings, "stripe_secret_key", "sk_test_not_a_real_key", raising=False)
    monkeypatch.setattr(stripe.Invoice, "list", _boom)
    assert await billing.subscription_has_other_paid_invoice("sub_x", "in_now") is None
