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

TWO AMOUNTS. The invoice's `amount_paid` is what was charged today; the paid
line's unit amount is the plan's price per period. A discounted first charge
rendered as "$10.00 USD per month · Next charge: …" promises a price the next
undiscounted invoice breaks, so the email and the founder alert label them
separately.

THE SHAPES ARE THE REAL ONES. Every event below goes through the real
`/api/webhooks/stripe` route with a locally computed Stripe signature, so
`stripe.Webhook.construct_event` — the vendor code production runs — accepts
it first and builds a real `stripe.Event` (the harness records that it did).
The invoice payloads follow what the live endpoint delivers on API
2026-04-22.dahlia (read off live events, read-only, on 2026-09-14 and
2026-09-15; the endpoint's version, not the SDK's 2026-08-26.dahlia): there is
NO top-level `subscription` on an invoice; the id and the checkout metadata
live at `parent.subscription_details`, and invoice lines carry
`pricing.price_details.price` and `pricing.unit_amount_decimal` (a decimal
string, "0" on a trial line) rather than a `price` object. A fixture with a
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
PRICE_PREMIUM_ANNUAL = "price_test_premium_annual_welcome"
PRICE_PRO_ANNUAL = "price_test_pro_annual_welcome"
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
    user_id: str | None,
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
    billing_period: str = "monthly",
    period_days: int = 30,
    unit_amount: int | None = None,
    discount: int = 0,
) -> dict[str, Any]:
    """An invoice as API 2026-04-22.dahlia delivers it: no top-level
    `subscription`, metadata under `parent.subscription_details`, and lines
    with `pricing.price_details.price` + `pricing.unit_amount_decimal` instead
    of a `price` object.

    `unit_amount` is the plan's price on the line (before discounts);
    `discount` is modelled the way Stripe itemises a coupon — a line
    `discount_amounts` entry plus the invoice's `total_discount_amounts` —
    with `amount_paid` the discounted total. `user_id=None` leaves it out of
    the subscription metadata (a subscription created outside Checkout)."""
    start = period_start if period_start is not None else _now()
    end = start + period_days * DAY
    meta = {"billing_period": billing_period, "tier": tier}
    if user_id is not None:
        meta["user_id"] = user_id
    inv_id = f"in_{uuid.uuid4().hex[:24]}"
    due = amount_paid if amount_due is None else amount_due
    unit = unit_amount if unit_amount is not None else due + discount
    discount_id = f"di_{uuid.uuid4().hex[:14]}" if discount else None
    discount_amounts = [{"amount": discount, "discount": discount_id}] if discount else []
    return {
        "id": inv_id,
        "object": "invoice",
        "customer": customer,
        "status": status,
        "billing_reason": billing_reason,
        "amount_paid": amount_paid,
        "amount_due": due,
        "amount_remaining": 0 if status == "paid" else (amount_due or 0),
        "subtotal": unit,
        "total": due,
        "discounts": [discount_id] if discount_id else [],
        "total_discount_amounts": discount_amounts,
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
                    "amount": unit,
                    "currency": currency,
                    "discount_amounts": discount_amounts,
                    "discounts": [discount_id] if discount_id else [],
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
                        "unit_amount_decimal": str(unit),
                    },
                    "quantity": 1,
                    "subtotal": unit,
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
        from app.services import telegram as telegram_mod

        self.sent: list[dict] = []
        self.alerts: list[dict] = []
        # Every founder message as it would actually be worded ({subject, text}).
        self.founder_messages: list[dict] = []
        # The type construct_event returned for each delivery.
        self.verified_event_types: list[type] = []
        # sub_id -> [(invoice_id, amount_paid)] of invoices Stripe holds as paid
        self.paid: dict[str, list[tuple[str, int]]] = {}
        self.history_calls: list[str] = []
        self.history_unavailable = False

        for mod in (webhooks_mod, billing_mod):
            monkeypatch.setattr(mod.settings, "stripe_webhook_secret", WEBHOOK_SECRET, raising=False)
            monkeypatch.setattr(mod.settings, "stripe_price_premium_monthly", PRICE_PREMIUM_MONTHLY, raising=False)
            monkeypatch.setattr(mod.settings, "stripe_price_pro_monthly", PRICE_PRO_MONTHLY, raising=False)
            monkeypatch.setattr(mod.settings, "stripe_price_premium_annual", PRICE_PREMIUM_ANNUAL, raising=False)
            monkeypatch.setattr(mod.settings, "stripe_price_pro_annual", PRICE_PRO_ANNUAL, raising=False)

        async def _capture_email(to, subject, html, **kw):
            self.sent.append({"to": to, "subject": subject, "html": html, **kw})
            return {"ok": True}

        real_notify = telegram_mod.notify_founder_new_subscription

        async def _capture_alert(**kw):
            # Record the arguments, then let the REAL formatter word the
            # message, so the founder's text is asserted as sent.
            self.alerts.append(kw)
            await real_notify(**kw)

        async def _capture_founder_message(*, subject, text):
            self.founder_messages.append({"subject": subject, "text": text})

        real_construct = stripe.Webhook.construct_event

        def _recording_construct(*a, **kw):
            event = real_construct(*a, **kw)
            self.verified_event_types.append(type(event))
            return event

        monkeypatch.setattr(stripe.Webhook, "construct_event", _recording_construct)
        monkeypatch.setattr(telegram_mod, "deliver_founder_alert", _capture_founder_message, raising=True)

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

    @property
    def unannounced(self) -> list[dict]:
        """Founder messages saying a paid invoice went out with no welcome."""
        return [m for m in self.founder_messages if "no welcome sent" in m["subject"]]


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
    before = len(h.sent)
    await h.deliver("invoice.payment_succeeded", paid)
    at_the_charge = [s["subject"] for s in h.sent[before:]]
    await h.deliver("customer.subscription.updated", _subscription(**kw, status="active"))

    assert len(h.welcomes) == 1, f"expected one welcome at the successful charge, got {len(h.welcomes)}"
    assert h.welcomes[0]["to"] == u["email"]
    assert "Premium" in h.welcomes[0]["subject"]
    assert "$19.99" in h.welcomes[0]["html"]
    assert len(h.alerts) == 1, f"expected one founder alert, got {len(h.alerts)}"
    assert h.alerts[0]["amount"] == pytest.approx(19.99)
    assert h.alerts[0]["tier"] == "premium"
    assert await _latch_exists(sub_id)
    # ONE billing email for one charge: the welcome replaces the dunning
    # all-clear here.
    assert len(at_the_charge) == 1 and at_the_charge[0].startswith("You're in"), at_the_charge
    async with session_scope() as s:
        drip = (await s.execute(select(User.drip_state).where(User.id == u["id"]))).scalar_one()
    assert not any(t.startswith("dun") for t in (drip or "").split(",")), (
        "the dunning tokens must still be cleared when the welcome replaces the all-clear"
    )

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
async def test_a_discounted_charge_is_stated_as_charged_today_not_as_the_plan_price(monkeypatch):
    """A 40%-off first charge on Premium monthly: the line bills the $19.99
    price, a coupon takes $8.00 off, the invoice collects $11.99 (in AUD, so
    the currency is provably the invoice's).

    The welcome used to render amount_paid as the recurring price — "$11.99
    AUD per month · Next charge: …" — and month four is $19.99. The charge
    and the plan price are different facts and get different labels."""
    h = Harness(monkeypatch)
    u = await _user(linked=False)
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}

    await h.deliver("customer.subscription.created", _subscription(**kw, status="active", unit_amount=1999))
    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, amount_paid=1199, unit_amount=1999, discount=800,
        billing_reason="subscription_create", currency="aud",
    ))

    assert len(h.welcomes) == 1
    html = h.welcomes[0]["html"]
    assert "Charged today: $11.99 AUD" in html, "the welcome did not state what the invoice charged"
    assert "$11.99 AUD per" not in html, "the discounted charge was rendered as a recurring price"
    assert "$19.99 AUD per month, before any discount or credit" in html, (
        "the plan price must be stated separately and labelled as pre-discount"
    )
    assert h.alerts[0]["amount"] == pytest.approx(11.99)
    assert h.alerts[0]["plan_price"] == pytest.approx(19.99)
    assert str(h.alerts[0]["currency"]).lower() == "aud"
    text = h.founder_messages[-1]["text"]
    assert "charged today: 11.99 AUD" in text
    assert "11.99 AUD per" not in text and "· 11.99" not in text, text
    assert "plan price: 19.99 AUD per month before any discount or credit" in text, text


@pytest.mark.asyncio
async def test_discounted_first_charge_after_a_trial_through_a_verified_stripe_event(monkeypatch):
    """The live path this PR exists for, with a founder-friends-style 50% coupon:
    trial -> active -> the first cycle invoice is paid at $10.00 against a
    $19.99 price. Delivered as a signed payload that Stripe's own
    construct_event turns into a real `stripe.Event` before any handler code
    runs."""
    h = Harness(monkeypatch)
    u = await _user()
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    trial_end = _now() + 30 * DAY
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}

    await h.deliver("customer.subscription.created", _subscription(**kw, status="trialing", trial_end=trial_end))
    await h.deliver("invoice.payment_succeeded", _invoice(**kw, amount_paid=0, billing_reason="subscription_create"))
    await h.deliver("customer.subscription.updated", _subscription(**kw, status="active", trial_end=trial_end))
    assert h.welcomes == [] and h.alerts == []

    first = _invoice(
        **kw, amount_paid=1000, unit_amount=1999, discount=999,
        billing_reason="subscription_cycle", period_start=trial_end,
    )
    await h.deliver("invoice.payment_succeeded", first)

    assert h.verified_event_types and all(t is stripe.Event for t in h.verified_event_types), (
        h.verified_event_types
    )
    assert len(h.welcomes) == 1
    html = h.welcomes[0]["html"]
    assert "Charged today: $10.00 USD" in html
    assert "$10.00 USD per month" not in html, "a 50%-off charge was quoted as the monthly price"
    assert "Tapeline Premium · $10.00" not in html
    assert "Plan price: $19.99 USD per month, before any discount or credit." in html
    next_charge = datetime.fromtimestamp(trial_end + 30 * DAY, UTC).strftime("%b %d, %Y")
    assert f"Next charge: {next_charge}." in html
    assert len(h.alerts) == 1
    text = h.founder_messages[-1]["text"]
    assert "charged today: 10.00 USD" in text
    assert "(monthly) · 10.00" not in text and "10.00 USD per" not in text, text
    assert "plan price: 19.99 USD per month before any discount or credit" in text, text


@pytest.mark.asyncio
async def test_an_undiscounted_charge_states_the_plan_price_once(monkeypatch):
    h = Harness(monkeypatch)
    u = await _user(linked=False)
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}

    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, amount_paid=1999, billing_reason="subscription_create",
    ))

    html = h.welcomes[0]["html"]
    assert "Tapeline Premium · $19.99 USD per month" in html
    assert "Charged today: $19.99 USD." in html
    assert "before any discount" not in html
    assert "before any discount" not in h.founder_messages[-1]["text"]


@pytest.mark.asyncio
async def test_an_annual_first_charge_states_the_year_the_prorated_refund_and_the_line_period_end(monkeypatch):
    """The billing period picks the refund promise — monthly refunds in full,
    annual refunds the prorated remainder — and the next-charge date comes from
    the paid line's period. Both were unpinned: hard-coding "monthly" or
    dropping the date passed every earlier test."""
    h = Harness(monkeypatch)
    u = await _user(linked=False)
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}
    start = _now()

    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, amount_paid=19900, price_id=PRICE_PREMIUM_ANNUAL, billing_period="annual",
        period_days=365, period_start=start, billing_reason="subscription_create",
    ))

    assert len(h.welcomes) == 1
    html = h.welcomes[0]["html"]
    assert "Tapeline Premium · $199.00 USD per year" in html
    assert "per month" not in html
    assert "refund the remainder, prorated" in html
    assert "refund in full" not in html, "an annual customer was promised a full refund"
    next_charge = datetime.fromtimestamp(start + 365 * DAY, UTC).strftime("%b %d, %Y")
    assert f"Next charge: {next_charge}." in html
    assert h.alerts[0]["billing_period"] == "annual"


@pytest.mark.asyncio
async def test_a_plan_changed_after_checkout_is_welcomed_under_the_plan_it_pays_for(monkeypatch):
    """Checkout stamped premium/annual into the subscription metadata; the
    customer switched to Pro monthly before the first charge. Metadata is never
    rewritten, and the account can still hold the old tier when the invoice
    lands first, so the invoice's own price names the plan."""
    h = Harness(monkeypatch)
    u = await _user(linked=False, tier="premium")
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}

    await h.deliver("invoice.payment_succeeded", _invoice(
        **kw, tier="premium", billing_period="annual",
        price_id=PRICE_PRO_MONTHLY, amount_paid=999, billing_reason="subscription_create",
    ))

    assert len(h.welcomes) == 1
    assert h.welcomes[0]["subject"] == "You're in — welcome to Tapeline Pro", h.welcomes[0]["subject"]
    html = h.welcomes[0]["html"]
    assert "Tapeline Pro · $9.99 USD per month" in html
    assert "refund in full" in html
    assert h.alerts[0]["tier"] == "pro"
    assert h.alerts[0]["billing_period"] == "monthly"


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
    # They were already welcomed, so the all-clear is the one email this charge gets.
    assert any(s["subject"].startswith("Payment received") for s in h.sent)


@pytest.mark.asyncio
async def test_unavailable_history_welcomes_nobody_claims_nothing_and_tells_the_founder(monkeypatch):
    """Nothing to the customer and no latch — but the money did arrive. With no
    latch, the next renewal's history shows this invoice paid and claims the
    latch silently, so without a message now this sale is never announced."""
    h = Harness(monkeypatch)
    u = await _user()
    sub_id, first_charge = await _trial_through_declined_first_charge(h, u)
    h.history_unavailable = True

    await h.deliver("invoice.payment_succeeded", dict(first_charge, status="paid", amount_paid=1999))

    assert h.welcomes == [] and h.alerts == []
    assert not await _latch_exists(sub_id)
    assert len(h.unannounced) == 1, h.founder_messages
    msg = h.unannounced[0]
    assert "19.99 USD" in msg["subject"] and "charged: 19.99 USD" in msg["text"]
    assert u["email"] in msg["text"]
    assert "invoice history could not be read" in msg["text"]
    assert not any("New Tapeline subscription" in m["subject"] for m in h.founder_messages)


@pytest.mark.asyncio
async def test_a_paid_first_invoice_with_no_matching_account_tells_the_founder(monkeypatch):
    """A subscription made outside Checkout: no linked customer, no user_id in
    its metadata, no Subscription row. No welcome can be addressed and no
    latch is claimed, so the founder is told about the money directly."""
    h = Harness(monkeypatch)
    customer = f"cus_{uuid.uuid4().hex[:14]}"
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"

    await h.deliver("invoice.payment_succeeded", _invoice(
        sub_id=sub_id, customer=customer, user_id=None, amount_paid=14900,
        unit_amount=14900, price_id="price_test_hand_sold_team",
        billing_reason="subscription_create",
    ))

    assert h.welcomes == [] and h.alerts == []
    assert not await _latch_exists(sub_id)
    assert len(h.unannounced) == 1, h.founder_messages
    text = h.unannounced[0]["text"]
    assert "charged: 149.00 USD" in text
    assert "not matched to a Tapeline account" in text
    assert customer in text and sub_id in text


# ── the renderer ────────────────────────────────────────────────────────────

def test_the_welcome_makes_no_freshness_or_coverage_claims():
    """This email goes out at the moment of a real charge. "Every score
    live-updating, every alert channel on, the full universe scanner unlocked"
    was not true: prices are delayed, push is opt-in, paid plans list up to
    1,000 scanner rows."""
    from app.services.email import render_subscription_started_email

    html = render_subscription_started_email(
        "Sam", tier="premium", billing_period="monthly",
        plan_price_cents=1999, charged_today_cents=1999,
    )
    low = html.lower()
    for claim in ("live-updating", "every alert channel", "full universe", "full data feed is live", "the moment"):
        assert claim not in low, f"welcome still claims {claim!r}"
    # "your payment", not "your first payment": a returning customer's
    # win-back subscription is welcomed too (test_never_paid_billing_copy.py).
    assert "your payment went through" in low


def test_plan_price_line_reads_the_line_in_both_payload_shapes():
    """dahlia: `pricing.unit_amount_decimal` (a string in the webhook JSON, a
    Decimal on an SDK object), no `price` key. Pre-basil: `price.unit_amount`."""
    from decimal import Decimal

    from app.routers.webhooks import _line_plan_price_cents, _line_price_id

    dahlia = {"pricing": {"price_details": {"price": "price_a"}, "unit_amount_decimal": "1999"}, "quantity": 1}
    sdk = stripe.StripeObject.construct_from(
        {"pricing": {"price_details": {"price": "price_a"}, "unit_amount_decimal": Decimal("1999")}, "quantity": 2},
        "sk_test_not_a_real_key",
    )
    legacy = {"price": {"id": "price_b", "unit_amount": 999}, "quantity": 1}
    trial = {"pricing": {"price_details": {"price": "price_a"}, "unit_amount_decimal": "0"}, "quantity": 1}

    assert (_line_price_id(dahlia), _line_plan_price_cents(dahlia)) == ("price_a", 1999)
    assert (_line_price_id(sdk), _line_plan_price_cents(sdk)) == ("price_a", 3998)
    assert (_line_price_id(legacy), _line_plan_price_cents(legacy)) == ("price_b", 999)
    assert _line_plan_price_cents(trial) is None, "a $0 trial line is not a quotable price"
    assert _line_plan_price_cents({}) is None


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
