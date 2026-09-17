"""Meta Conversions API: the money events, and the browser keys they carry.

Items P1-P5 of docs/META_CONVERSION_BLUEPRINT_2026-09-13.md §2.3, founder-
approved 2026-09-14. What each one pins:

P4  A trial checkout charges $0 (read-only check of every completed checkout
    on the live account, 2026-09-17: 4 of 4 trial checkouts had amount_total
    0, amount_subtotal 0, no discount). It used to be reported to Meta as a
    Purchase and to GA4 as a purchase, both worth $0, on day 0 - a duplicate
    of StartTrial that also misstated value. A trial checkout now sends
    neither. A direct paid checkout still sends both, with the amount.

P5  The first real charge of a subscription that started with a trial sends
    Meta `Subscribe` (action_source system_generated, value = amount_paid) and
    a GA4 purchase with the real value - once per subscription, on its own
    latch, never for a direct paid checkout (already counted at checkout).

P1  The browser's IP address and user agent are captured on the requests the
    visitor's own browser sends straight to api.tapeline.io (email signup, the
    OAuth callback, POST /api/billing/checkout), stored as the latest values,
    and sent on CompleteRegistration, StartTrial, Purchase and Subscribe. The
    Stripe webhook request is Stripe's, so its IP and user agent never are.
    Behind its own switch, META_CAPI_SEND_IP_UA, off by default: it is a new
    category of data, and the privacy policy promises account holders 14
    days' notice of one.

P2  `_fbp` is stored (signup body, OAuth start, checkout body) and sent.

P3  The most recent click id wins: an `_fbc` cookie or a newer fbclid sent
    with the checkout request is sent in preference to the first-touch
    `signup_fbclid`, which is left exactly as it was.

Everything goes through the real routes: Stripe events are signed locally and
verified by `stripe.Webhook.construct_event`, signups and checkouts are real
HTTP requests. The Meta and GA4 HTTP layers are replaced by recorders, and the
two Stripe reads the first-charge path makes (the subscription's trial, its
paid-invoice history) are stood in for.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, ClassVar
from urllib.parse import urlencode

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import StripeWebhookEvent, User
from app.services import analytics, meta_capi
from app.services.session import SESSION_COOKIE, issue_session_token

WEBHOOK_SECRET = "whsec_test_secret_for_meta_money_events"
PRICE_PREMIUM_MONTHLY = "price_test_premium_monthly_capi"
PRICE_PRO_MONTHLY = "price_test_pro_monthly_capi"
DAY = 86400

BROWSER_IP = "203.0.113.24"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CapiProbe/1.0"
BROWSER_FBP = "fb.1.1757900000000.1234567890"
BROWSER_FBC = "fb.1.1757950000000.IwAR0-LatestClick"
STRIPE_IP = "198.51.100.77"
STRIPE_UA = "Stripe/1.0 (+https://stripe.com/docs/webhooks)"


# ── recorders ───────────────────────────────────────────────────────────────

class _MetaRecorder:
    """Stands in for the `httpx` name inside services/meta_capi only."""

    payloads: ClassVar[list[dict]] = []

    class AsyncClient:  # mirrors httpx
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None, **k):
            _MetaRecorder.payloads.append(json)
            return SimpleNamespace(status_code=200, text="{}")


class _Ga4Recorder:
    payloads: ClassVar[list[dict]] = []

    class AsyncClient:  # mirrors httpx
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, params=None, json=None, **k):
            _Ga4Recorder.payloads.append(json)
            return SimpleNamespace(status_code=204)


def meta_events(name: str) -> list[dict]:
    return [e for p in _MetaRecorder.payloads for e in p["data"] if e["event_name"] == name]


def ga4_purchases() -> list[dict]:
    return [
        ev["params"] for p in _Ga4Recorder.payloads for ev in p["events"]
        if ev["name"] == "purchase"
    ]


@pytest.fixture
def meta_on(monkeypatch):
    monkeypatch.setenv("META_PIXEL_ID", "123456789")
    monkeypatch.setenv("META_CAPI_ACCESS_TOKEN", "tok_test")
    monkeypatch.delenv("META_CAPI_TEST_EVENT_CODE", raising=False)
    _MetaRecorder.payloads = []
    monkeypatch.setattr(meta_capi, "httpx", _MetaRecorder)


@pytest.fixture
def meta_off(monkeypatch):
    monkeypatch.delenv("META_PIXEL_ID", raising=False)
    monkeypatch.delenv("META_CAPI_ACCESS_TOKEN", raising=False)
    _MetaRecorder.payloads = []
    monkeypatch.setattr(meta_capi, "httpx", _MetaRecorder)


@pytest.fixture
def ip_ua_on(monkeypatch):
    """The separate switch for the browser's IP address and user agent."""
    monkeypatch.setenv("META_CAPI_SEND_IP_UA", "1")


@pytest.fixture(autouse=True)
def _ip_ua_off_unless_asked(monkeypatch):
    monkeypatch.delenv("META_CAPI_SEND_IP_UA", raising=False)


@pytest.fixture
def ga4_on(monkeypatch):
    monkeypatch.setenv("GA4_MEASUREMENT_ID", "G-TESTCAPI1")
    monkeypatch.setenv("GA4_API_SECRET", "ga4-secret")
    _Ga4Recorder.payloads = []
    monkeypatch.setattr(analytics, "httpx", _Ga4Recorder)


# ── Stripe payloads (the dahlia shapes test_paid_welcome_waits_for_money uses) ─

def _now() -> int:
    return int(datetime.now(UTC).timestamp())


def _subscription(*, sub_id: str, customer: str, user_id: str, status: str,
                  trial_end: int | None = None) -> dict[str, Any]:
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
        "metadata": {"user_id": user_id, "tier": "premium", "billing_period": "monthly"},
        "items": {"object": "list", "data": [{
            "id": f"si_{uuid.uuid4().hex[:14]}",
            "object": "subscription_item",
            "current_period_end": (trial_end or now) + 30 * DAY,
            "price": {
                "id": PRICE_PREMIUM_MONTHLY, "object": "price", "unit_amount": 1999,
                "currency": "usd", "recurring": {"interval": "month", "interval_count": 1},
            },
        }]},
    }


def _invoice(*, sub_id: str, customer: str, user_id: str | None, amount_paid: int,
             billing_reason: str, unit_amount: int = 1999,
             price_id: str = PRICE_PREMIUM_MONTHLY, tier: str = "premium") -> dict[str, Any]:
    start = _now()
    meta = {"billing_period": "monthly", "tier": tier}
    if user_id is not None:
        meta["user_id"] = user_id
    inv_id = f"in_{uuid.uuid4().hex[:24]}"
    return {
        "id": inv_id,
        "object": "invoice",
        "customer": customer,
        "status": "paid",
        "billing_reason": billing_reason,
        "amount_paid": amount_paid,
        "amount_due": amount_paid,
        "amount_remaining": 0,
        "subtotal": unit_amount,
        "total": amount_paid,
        "currency": "usd",
        "attempt_count": 1,
        "metadata": {},
        "parent": {
            "type": "subscription_details",
            "quote_details": None,
            "subscription_details": {"metadata": meta, "subscription": sub_id},
        },
        "lines": {"object": "list", "data": [{
            "id": f"il_{uuid.uuid4().hex[:16]}",
            "object": "line_item",
            "amount": unit_amount,
            "currency": "usd",
            "invoice": inv_id,
            "metadata": meta,
            "period": {"start": start, "end": start + 30 * DAY},
            "pricing": {
                "type": "price_details",
                "price_details": {"price": price_id, "product": "prod_capi"},
                "unit_amount_decimal": str(unit_amount),
            },
            "quantity": 1,
        }]},
    }


def _checkout(*, user_id: str, customer: str, sub_id: str, amount_total: int,
              amount_subtotal: int, discount: int = 0) -> dict[str, Any]:
    return {
        "id": f"cs_{uuid.uuid4().hex[:24]}",
        "object": "checkout.session",
        "client_reference_id": user_id,
        "customer": customer,
        "subscription": sub_id,
        "mode": "subscription",
        "amount_subtotal": amount_subtotal,
        "amount_total": amount_total,
        "total_details": {"amount_discount": discount, "amount_shipping": 0, "amount_tax": 0},
        "currency": "usd",
        "status": "complete",
    }


class Stripe:
    """Signs and delivers events through the real route, and stands in for the
    two Stripe reads the first-charge path makes."""

    def __init__(self, monkeypatch) -> None:
        from app.routers import webhooks as webhooks_mod
        from app.services import billing as billing_mod

        for mod in (webhooks_mod, billing_mod):
            monkeypatch.setattr(mod.settings, "stripe_webhook_secret", WEBHOOK_SECRET, raising=False)
            monkeypatch.setattr(mod.settings, "stripe_price_premium_monthly", PRICE_PREMIUM_MONTHLY, raising=False)
            monkeypatch.setattr(mod.settings, "stripe_price_pro_monthly", PRICE_PRO_MONTHLY, raising=False)

        self.trial: dict[str, bool | None] = {}
        self.trial_calls: list[str] = []
        self.paid: dict[str, list[tuple[str, int]]] = {}

        async def _history(sub_id, invoice_id):
            return any(i != invoice_id and a > 0 for i, a in self.paid.get(sub_id, []))

        async def _started_with_trial(sub_id):
            self.trial_calls.append(sub_id)
            return self.trial.get(sub_id)

        async def _quiet(*a, **k):
            return {"ok": True}

        monkeypatch.setattr(webhooks_mod, "subscription_has_other_paid_invoice", _history)
        # raising=False: the stand-in is installed whether or not the handler
        # has grown this lookup yet, so a missing feature fails an assertion.
        monkeypatch.setattr(webhooks_mod, "subscription_started_with_trial", _started_with_trial, raising=False)
        monkeypatch.setattr("app.services.email.send_email", _quiet)
        monkeypatch.setattr("app.services.telegram.notify_founder_new_subscription", _quiet)
        monkeypatch.setattr("app.services.telegram.deliver_founder_alert", _quiet)

    async def deliver(self, evt_type: str, obj: dict, *, event_id: str | None = None,
                      headers: dict[str, str] | None = None) -> dict:
        if evt_type == "invoice.payment_succeeded":
            sub_id = obj["parent"]["subscription_details"]["subscription"]
            entry = (obj["id"], obj["amount_paid"])
            if entry not in self.paid.setdefault(sub_id, []):
                self.paid[sub_id].append(entry)
        payload = json.dumps({
            "id": event_id or f"evt_{uuid.uuid4().hex}",
            "object": "event",
            "api_version": "2026-04-22.dahlia",
            "created": _now(),
            "type": evt_type,
            "data": {"object": obj},
        }).encode()
        ts = int(time.time())
        sig = hmac.new(WEBHOOK_SECRET.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/webhooks/stripe", content=payload,
                headers={
                    "stripe-signature": f"t={ts},v1={sig}",
                    "content-type": "application/json",
                    **(headers or {}),
                },
            )
        assert r.status_code == 200, r.text
        return r.json()


async def _user(*, linked: bool = True, signup_fbclid: str | None = None) -> dict[str, str]:
    uid = f"u_{uuid.uuid4().hex}"
    customer = f"cus_{uuid.uuid4().hex[:14]}"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.test", name="Capi probe", tier="free",
            password_hash="x", drip_state="",
            stripe_customer_id=customer if linked else None,
            signup_fbclid=signup_fbclid,
        ))
    return {"id": uid, "customer": customer, "email": f"{uid}@example.test"}


async def _row(uid: str) -> User:
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


async def _latch(latch_id: str) -> bool:
    async with session_scope() as s:
        return (await s.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.id == latch_id)
        )).scalar_one_or_none() is not None


def _sha(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


async def _checkout_request(monkeypatch, uid: str, *, body: dict | None = None,
                            ip: str | None = BROWSER_IP, ua: str | None = BROWSER_UA) -> httpx.Response:
    """POST /api/billing/checkout as the signed-in visitor's browser would."""
    from app.routers import billing as billing_router

    async def _fake_session(**kwargs):
        return "https://checkout.stripe.test/session"

    monkeypatch.setattr(billing_router, "create_checkout_session", _fake_session)
    headers: dict[str, str] = {}
    if ip:
        headers["Fly-Client-IP"] = ip
    if ua:
        headers["User-Agent"] = ua
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        cookies={SESSION_COOKIE: issue_session_token(uid, 0)},
    ) as c:
        r = await c.post(
            "/api/billing/checkout",
            json={"tier": "premium", "billing_period": "monthly", "start_trial": True, **(body or {})},
            headers=headers,
        )
    assert r.status_code == 200, r.text
    return r


# ── P4: a trial checkout is not a purchase ──────────────────────────────────

async def test_a_trial_checkout_sends_no_purchase_to_meta_or_ga4(monkeypatch, meta_on, ga4_on):
    st = Stripe(monkeypatch)
    u = await _user(linked=False)
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"

    await st.deliver("checkout.session.completed", _checkout(
        user_id=u["id"], customer=u["customer"], sub_id=sub_id,
        amount_total=0, amount_subtotal=0,
    ))

    assert meta_events("Purchase") == [], "a $0 trial checkout was reported to Meta as a Purchase"
    assert ga4_purchases() == [], "a $0 trial checkout was reported to GA4 as a purchase"
    assert not await _latch(f"ga4_purchase:{sub_id}"), (
        "nothing was sent, so nothing may be latched as sent"
    )


async def test_a_direct_paid_checkout_still_sends_purchase_with_its_value(monkeypatch, meta_on, ga4_on):
    st = Stripe(monkeypatch)
    u = await _user(linked=False)
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"

    await st.deliver("checkout.session.completed", _checkout(
        user_id=u["id"], customer=u["customer"], sub_id=sub_id,
        amount_total=999, amount_subtotal=999,
    ))

    purchases = meta_events("Purchase")
    assert len(purchases) == 1
    assert purchases[0]["custom_data"]["value"] == 9.99
    assert purchases[0]["custom_data"]["currency"] == "USD"
    assert [p["value"] for p in ga4_purchases()] == [9.99]


# ── P5: Subscribe at the first real charge ──────────────────────────────────

async def _trial_to_first_charge(st: Stripe, u: dict, *, sub_id: str, amount: int = 1999,
                                 metadata_user_id: str | None = None,
                                 customer: str | None = None) -> dict:
    trial_end = _now() + 30 * DAY
    kw = {"sub_id": sub_id, "customer": customer or u["customer"], "user_id": metadata_user_id or u["id"]}
    st.trial[sub_id] = True
    await st.deliver("customer.subscription.created", _subscription(**kw, status="trialing", trial_end=trial_end))
    await st.deliver("invoice.payment_succeeded", _invoice(**kw, amount_paid=0, billing_reason="subscription_create"))
    await st.deliver("customer.subscription.updated", _subscription(**kw, status="active", trial_end=trial_end))
    first = _invoice(**kw, amount_paid=amount, billing_reason="subscription_cycle")
    await st.deliver("invoice.payment_succeeded", first)
    return first


async def test_a_trial_first_paid_charge_sends_subscribe_and_a_ga4_purchase_once(monkeypatch, meta_on, ga4_on):
    st = Stripe(monkeypatch)
    u = await _user()
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"

    first = await _trial_to_first_charge(st, u, sub_id=sub_id)

    subs = meta_events("Subscribe")
    assert len(subs) == 1, f"expected one Subscribe at the first real charge, got {len(subs)}"
    ev = subs[0]
    assert ev["action_source"] == "system_generated"
    assert ev["event_id"] == meta_capi.event_id_for("subscribe", sub_id)
    assert ev["custom_data"] == {"value": 19.99, "currency": "USD"}
    assert ev["user_data"]["em"] == [_sha(u["email"])]
    assert ev["user_data"]["external_id"] == [_sha(u["id"])]
    assert "event_source_url" not in ev, "no browser page exists for an automatic charge"
    wire = json.dumps(_MetaRecorder.payloads)
    assert sub_id not in wire and first["id"] not in wire, "a raw Stripe id reached Meta"

    assert [p["value"] for p in ga4_purchases()] == [19.99], (
        "GA4 must get exactly one purchase, at the real charge, with the real value"
    )

    # A renewal is not a first charge, and a redelivery is not a new event.
    renewal = _invoice(sub_id=sub_id, customer=u["customer"], user_id=u["id"],
                       amount_paid=1999, billing_reason="subscription_cycle")
    event_id = f"evt_{uuid.uuid4().hex}"
    await st.deliver("invoice.payment_succeeded", renewal, event_id=event_id)
    await st.deliver("invoice.payment_succeeded", renewal, event_id=event_id)
    assert len(meta_events("Subscribe")) == 1
    assert len(ga4_purchases()) == 1


async def test_subscribe_has_its_own_latch_not_the_checkout_purchase_one(monkeypatch, meta_on, ga4_on):
    """Trials started before this change were latched `ga4_purchase:` by the
    $0 checkout Purchase, and trials welcomed under the old status trigger
    hold `paid_start:` without having been charged. Neither latch may
    suppress their real first charge."""
    st = Stripe(monkeypatch)
    u = await _user()
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    async with session_scope() as s:
        s.add(StripeWebhookEvent(id=f"ga4_purchase:{sub_id}", event_type="ga4_purchase"))
        s.add(StripeWebhookEvent(id=f"paid_start:{sub_id}", event_type="paid_start"))

    await _trial_to_first_charge(st, u, sub_id=sub_id)

    assert len(meta_events("Subscribe")) == 1
    assert [p["value"] for p in ga4_purchases()] == [19.99]


async def test_a_direct_paid_checkout_is_never_counted_again_at_its_invoices(monkeypatch, meta_on, ga4_on):
    st = Stripe(monkeypatch)
    u = await _user(linked=False)
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}
    st.trial[sub_id] = False

    await st.deliver("checkout.session.completed", _checkout(
        user_id=u["id"], customer=u["customer"], sub_id=sub_id, amount_total=999, amount_subtotal=999,
    ))
    await st.deliver("customer.subscription.created", _subscription(**kw, status="active"))
    await st.deliver("invoice.payment_succeeded", _invoice(
        **kw, amount_paid=999, unit_amount=999, billing_reason="subscription_create",
        price_id=PRICE_PRO_MONTHLY, tier="pro",
    ))
    await st.deliver("invoice.payment_succeeded", _invoice(
        **kw, amount_paid=999, unit_amount=999, billing_reason="subscription_cycle",
        price_id=PRICE_PRO_MONTHLY, tier="pro",
    ))

    assert len(meta_events("Purchase")) == 1
    assert meta_events("Subscribe") == [], "a direct paid checkout was counted a second time"
    assert [p["value"] for p in ga4_purchases()] == [9.99]
    # Settled at its paid create invoice, so neither invoice needed Stripe.
    assert st.trial_calls == [], "a direct paid checkout was sent to the trial lookup"
    assert await _latch(f"first_charge_conversion:{sub_id}")


async def test_a_discounted_first_month_that_was_not_a_trial_sends_no_subscribe(monkeypatch, meta_on, ga4_on):
    """A 100%-off referral month also charges $0 at checkout. It is not a trial:
    it keeps its (zero) Purchase and its later first charge is no Subscribe."""
    st = Stripe(monkeypatch)
    u = await _user(linked=False)
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}
    st.trial[sub_id] = False

    await st.deliver("checkout.session.completed", _checkout(
        user_id=u["id"], customer=u["customer"], sub_id=sub_id,
        amount_total=0, amount_subtotal=1999, discount=1999,
    ))
    await st.deliver("invoice.payment_succeeded", _invoice(**kw, amount_paid=0, billing_reason="subscription_create"))
    await st.deliver("invoice.payment_succeeded", _invoice(**kw, amount_paid=1999, billing_reason="subscription_cycle"))

    assert len(meta_events("Purchase")) == 1
    assert meta_events("Subscribe") == []
    assert len(ga4_purchases()) == 1


async def test_a_zero_dollar_invoice_sends_nothing_and_claims_nothing(monkeypatch, meta_on, ga4_on):
    st = Stripe(monkeypatch)
    u = await _user()
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    st.trial[sub_id] = True

    await st.deliver("invoice.payment_succeeded", _invoice(
        sub_id=sub_id, customer=u["customer"], user_id=u["id"],
        amount_paid=0, billing_reason="subscription_cycle",
    ))

    assert meta_events("Subscribe") == [] and ga4_purchases() == []
    assert st.trial_calls == [], "a $0 invoice must not cost a Stripe read"
    async with session_scope() as s:
        rows = (await s.execute(
            select(StripeWebhookEvent.id).where(StripeWebhookEvent.id.like(f"%{sub_id}%"))
        )).scalars().all()
    assert rows == []


async def test_subscribe_finds_the_account_through_subscription_metadata(monkeypatch, meta_on):
    """The duplicate-checkout case: this subscription's customer is no longer
    the one linked on the account, but its metadata still names the owner."""
    st = Stripe(monkeypatch)
    u = await _user()
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"

    await _trial_to_first_charge(st, u, sub_id=sub_id, customer=f"cus_{uuid.uuid4().hex[:14]}")

    subs = meta_events("Subscribe")
    assert len(subs) == 1
    assert subs[0]["user_data"]["em"] == [_sha(u["email"])]


async def test_when_stripe_cannot_say_whether_it_was_a_trial_nothing_is_sent_or_claimed(monkeypatch, meta_on, ga4_on):
    st = Stripe(monkeypatch)
    u = await _user()
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    kw = {"sub_id": sub_id, "customer": u["customer"], "user_id": u["id"]}
    st.trial[sub_id] = None

    await st.deliver("invoice.payment_succeeded", _invoice(**kw, amount_paid=1999, billing_reason="subscription_cycle"))

    assert st.trial_calls == [sub_id], "the first charge never asked Stripe whether it followed a trial"
    assert meta_events("Subscribe") == [] and ga4_purchases() == []
    async with session_scope() as s:
        rows = (await s.execute(
            select(StripeWebhookEvent.id).where(StripeWebhookEvent.id.like(f"%conversion%{sub_id}%"))
        )).scalars().all()
    assert rows == []


async def test_an_established_subscription_is_not_reported_at_renewal(monkeypatch, meta_on, ga4_on):
    """A trial that converted before this shipped has an earlier paid invoice;
    its renewal is not a first charge."""
    st = Stripe(monkeypatch)
    u = await _user()
    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    st.trial[sub_id] = True
    st.paid[sub_id] = [("in_earlier_paid", 1999)]

    await st.deliver("invoice.payment_succeeded", _invoice(
        sub_id=sub_id, customer=u["customer"], user_id=u["id"],
        amount_paid=1999, billing_reason="subscription_cycle",
    ))

    assert st.trial_calls == [sub_id], "the renewal never reached the first-charge decision"
    assert meta_events("Subscribe") == [] and ga4_purchases() == []


# ── P1-P3: browser keys, captured from the browser, sent on every event ─────

def _patch_signup_gates(monkeypatch) -> None:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


async def test_email_signup_sends_and_stores_the_browsers_ip_user_agent_and_fbp(monkeypatch, meta_on, ip_ua_on):
    _patch_signup_gates(monkeypatch)
    email = f"capi-{uuid.uuid4().hex[:10]}@example.com"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/auth/signup",
            json={"email": email, "password": "TestPassword!2026", "fbp": BROWSER_FBP},
            headers={"Fly-Client-IP": BROWSER_IP, "User-Agent": BROWSER_UA},
        )
    assert r.status_code == 200, r.text

    reg = meta_events("CompleteRegistration")
    assert len(reg) == 1
    ud = reg[0]["user_data"]
    # Unhashed, as Meta requires, and exactly the browser's.
    assert ud.get("client_ip_address") == BROWSER_IP
    assert ud.get("client_user_agent") == BROWSER_UA
    assert ud.get("fbp") == BROWSER_FBP

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
    assert getattr(row, "meta_client_ip", None) == BROWSER_IP
    assert getattr(row, "meta_client_user_agent", None) == BROWSER_UA
    assert getattr(row, "meta_fbp", None) == BROWSER_FBP, "_fbp was forwarded once and dropped"


async def test_oauth_signup_sends_and_stores_the_browsers_ip_user_agent_and_fbp(monkeypatch, meta_on, ip_ua_on):
    import app.routers.oauth as oauth_module

    monkeypatch.setattr(oauth_module.settings, "oauth_google_client_id", "test-cid")
    monkeypatch.setattr(oauth_module.settings, "oauth_google_client_secret", "test-secret")
    email = f"capi-oauth-{uuid.uuid4().hex[:10]}@example.com"

    class _Resp:
        def __init__(self, payload):
            self._payload, self.status_code, self.text = payload, 200, ""

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **k):
            return _Resp({"access_token": "fake", "id_token": None})

        async def get(self, url, **k):
            return _Resp({"email": email, "name": "Capi OAuth"})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        started = await c.get("/api/auth/oauth/google/start", params={"fbp": BROWSER_FBP})
    attr = [h.split(";")[0] for h in started.headers.get_list("set-cookie") if h.startswith("oauth_attr_google=")]

    monkeypatch.setattr(oauth_module, "httpx", SimpleNamespace(AsyncClient=_Client))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/auth/oauth/google/callback",
            params={"code": "c", "state": "st"},
            headers={
                "cookie": "; ".join(["oauth_state_google=st", *attr]),
                # The callback is a top-level navigation from Google straight
                # to api.tapeline.io, so these are the visitor's own.
                "Fly-Client-IP": BROWSER_IP,
                "User-Agent": BROWSER_UA,
            },
        )
    assert r.status_code == 307, r.text

    reg = meta_events("CompleteRegistration")
    assert len(reg) == 1
    ud = reg[0]["user_data"]
    assert ud.get("client_ip_address") == BROWSER_IP
    assert ud.get("client_user_agent") == BROWSER_UA
    assert ud.get("fbp") == BROWSER_FBP
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
    assert getattr(row, "meta_client_ip", None) == BROWSER_IP
    assert getattr(row, "meta_fbp", None) == BROWSER_FBP


async def test_checkout_stores_the_latest_keys_and_leaves_signup_fbclid_alone(monkeypatch, meta_on, ip_ua_on):
    u = await _user(linked=False, signup_fbclid="FirstTouchClick")

    await _checkout_request(monkeypatch, u["id"], body={"fbp": BROWSER_FBP, "fbc": BROWSER_FBC})
    row = await _row(u["id"])
    assert getattr(row, "meta_client_ip", None) == BROWSER_IP
    assert getattr(row, "meta_client_user_agent", None) == BROWSER_UA
    assert getattr(row, "meta_fbp", None) == BROWSER_FBP
    assert getattr(row, "meta_fbc", None) == BROWSER_FBC
    assert row.signup_fbclid == "FirstTouchClick", "first-touch attribution was overwritten"

    # Only the LATEST values are kept.
    await _checkout_request(monkeypatch, u["id"], ip="2001:db8::7", ua="Mozilla/5.0 SecondBrowser")
    row = await _row(u["id"])
    assert getattr(row, "meta_client_ip", None) == "2001:db8::7"
    assert getattr(row, "meta_client_user_agent", None) == "Mozilla/5.0 SecondBrowser"


async def test_start_trial_carries_the_checkout_browsers_keys_never_the_webhooks(monkeypatch, meta_on, ip_ua_on):
    st = Stripe(monkeypatch)
    u = await _user(linked=False, signup_fbclid="FirstTouchClick")
    await _checkout_request(monkeypatch, u["id"], body={"fbp": BROWSER_FBP, "fbc": BROWSER_FBC})

    sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    await st.deliver(
        "customer.subscription.created",
        _subscription(sub_id=sub_id, customer=u["customer"], user_id=u["id"],
                      status="trialing", trial_end=_now() + 30 * DAY),
        # The webhook request is Stripe's. Nothing about it describes the buyer.
        headers={"Fly-Client-IP": STRIPE_IP, "User-Agent": STRIPE_UA},
    )

    trials = meta_events("StartTrial")
    assert len(trials) == 1
    ud = trials[0]["user_data"]
    assert ud.get("client_ip_address") == BROWSER_IP
    assert ud.get("client_user_agent") == BROWSER_UA
    assert ud.get("fbp") == BROWSER_FBP
    assert ud.get("fbc") == BROWSER_FBC, "the latest click id must win over first-touch"
    wire = json.dumps(_MetaRecorder.payloads)
    assert STRIPE_IP not in wire and STRIPE_UA not in wire


async def test_purchase_and_subscribe_carry_the_stored_keys(monkeypatch, meta_on, ip_ua_on):
    st = Stripe(monkeypatch)

    buyer = await _user(linked=False)
    await _checkout_request(monkeypatch, buyer["id"], body={"fbp": BROWSER_FBP, "fbc": BROWSER_FBC})
    await st.deliver(
        "checkout.session.completed",
        _checkout(user_id=buyer["id"], customer=buyer["customer"], sub_id=f"sub_{uuid.uuid4().hex[:24]}",
                  amount_total=999, amount_subtotal=999),
        headers={"Fly-Client-IP": STRIPE_IP, "User-Agent": STRIPE_UA},
    )
    purchase = meta_events("Purchase")
    assert len(purchase) == 1
    assert purchase[0]["user_data"].get("client_ip_address") == BROWSER_IP
    assert purchase[0]["user_data"].get("client_user_agent") == BROWSER_UA
    assert purchase[0]["user_data"].get("fbp") == BROWSER_FBP
    assert purchase[0]["user_data"].get("fbc") == BROWSER_FBC

    trialist = await _user(linked=False)
    await _checkout_request(monkeypatch, trialist["id"], body={"fbp": BROWSER_FBP, "fbc": BROWSER_FBC})
    await _trial_to_first_charge(st, trialist, sub_id=f"sub_{uuid.uuid4().hex[:24]}")
    subs = meta_events("Subscribe")
    assert len(subs) == 1
    assert subs[0]["user_data"].get("client_ip_address") == BROWSER_IP
    assert subs[0]["user_data"].get("client_user_agent") == BROWSER_UA
    assert subs[0]["user_data"].get("fbp") == BROWSER_FBP
    assert subs[0]["user_data"].get("fbc") == BROWSER_FBC


async def test_a_newer_fbclid_at_checkout_wins_over_first_touch(monkeypatch, meta_on):
    st = Stripe(monkeypatch)
    u = await _user(linked=False, signup_fbclid="FirstTouchClick")

    # The same click the account signed up with is not newer: its first-touch
    # value (stamped with the signup time) stays the one used.
    await _checkout_request(monkeypatch, u["id"], body={"fbclid": "FirstTouchClick"})
    assert getattr(await _row(u["id"]), "meta_fbc", "unset") is None

    # No `_fbc` cookie (the pixel was blocked), but the browser holds a click
    # id newer than the one the account signed up with.
    await _checkout_request(monkeypatch, u["id"], body={"fbclid": "NewerClick"})
    stored = getattr(await _row(u["id"]), "meta_fbc", None)
    # Sending it again does not restamp it as a fresh click.
    await _checkout_request(monkeypatch, u["id"], body={"fbclid": "NewerClick"})
    assert getattr(await _row(u["id"]), "meta_fbc", None) == stored
    await st.deliver("customer.subscription.created", _subscription(
        sub_id=f"sub_{uuid.uuid4().hex[:24]}", customer=u["customer"], user_id=u["id"],
        status="trialing", trial_end=_now() + 30 * DAY,
    ))

    fbc = meta_events("StartTrial")[0]["user_data"].get("fbc") or ""
    assert fbc.startswith("fb.1.") and fbc.endswith(".NewerClick"), fbc
    assert (await _row(u["id"])).signup_fbclid == "FirstTouchClick"


async def test_malformed_or_non_browser_values_are_neither_stored_nor_sent(monkeypatch, meta_on, ip_ua_on):
    st = Stripe(monkeypatch)
    u = await _user(linked=False, signup_fbclid="FirstTouchClick")

    # No Fly-Client-IP: the resolver falls back to the ASGI peer, 127.0.0.1.
    # A user agent too long for its column is dropped, not truncated.
    await _checkout_request(
        monkeypatch, u["id"], ip=None, ua="Mozilla/5.0 " + "x" * 1100,
        body={"fbp": "not-a-pixel-cookie", "fbc": "fb.1.<script>"},
    )
    row = await _row(u["id"])
    assert getattr(row, "meta_client_ip", "unset") is None
    assert getattr(row, "meta_client_user_agent", "unset") is None
    assert getattr(row, "meta_fbp", "unset") is None
    assert getattr(row, "meta_fbc", "unset") is None

    await st.deliver("customer.subscription.created", _subscription(
        sub_id=f"sub_{uuid.uuid4().hex[:24]}", customer=u["customer"], user_id=u["id"],
        status="trialing", trial_end=_now() + 30 * DAY,
    ))
    ud = meta_events("StartTrial")[0]["user_data"]
    assert "client_ip_address" not in ud and "client_user_agent" not in ud and "fbp" not in ud
    assert (ud.get("fbc") or "").endswith(".FirstTouchClick"), "first-touch stays the fallback"


async def test_nothing_is_stored_while_meta_is_not_configured(monkeypatch, meta_off, ip_ua_on):
    u = await _user(linked=False)

    await _checkout_request(monkeypatch, u["id"], body={"fbp": BROWSER_FBP, "fbc": BROWSER_FBC})

    row = await _row(u["id"])
    for column in ("meta_client_ip", "meta_client_user_agent", "meta_fbp", "meta_fbc"):
        assert hasattr(row, column), f"users.{column} does not exist"
        assert getattr(row, column) is None, f"{column} stored with no Meta destination to use it"
    assert _MetaRecorder.payloads == []


async def test_ip_and_user_agent_wait_for_their_own_switch(monkeypatch, meta_on):
    """Merging and deploying must not start collecting a new category of data
    before account holders have had the notice the privacy policy promises."""
    st = Stripe(monkeypatch)
    _patch_signup_gates(monkeypatch)
    email = f"capi-dark-{uuid.uuid4().hex[:10]}@example.com"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/auth/signup",
            json={"email": email, "password": "TestPassword!2026", "fbp": BROWSER_FBP},
            headers={"Fly-Client-IP": BROWSER_IP, "User-Agent": BROWSER_UA},
        )
    assert r.status_code == 200, r.text
    ud = meta_events("CompleteRegistration")[0]["user_data"]
    assert "client_ip_address" not in ud and "client_user_agent" not in ud
    assert ud.get("fbp") == BROWSER_FBP, "_fbp is not behind the IP/UA switch"
    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
    assert row.meta_client_ip is None and row.meta_client_user_agent is None

    # Values stored while the switch was on stop being sent once it is off.
    u = await _user(linked=False)
    monkeypatch.setenv("META_CAPI_SEND_IP_UA", "1")
    await _checkout_request(monkeypatch, u["id"], body={"fbp": BROWSER_FBP})
    assert (await _row(u["id"])).meta_client_ip == BROWSER_IP
    monkeypatch.delenv("META_CAPI_SEND_IP_UA")
    await st.deliver("customer.subscription.created", _subscription(
        sub_id=f"sub_{uuid.uuid4().hex[:24]}", customer=u["customer"], user_id=u["id"],
        status="trialing", trial_end=_now() + 30 * DAY,
    ))
    ud = meta_events("StartTrial")[0]["user_data"]
    assert "client_ip_address" not in ud and "client_user_agent" not in ud
    assert ud.get("fbp") == BROWSER_FBP


# ── the service contract ────────────────────────────────────────────────────

async def test_ip_and_user_agent_go_on_the_wire_unhashed_and_only_when_present(meta_on):
    await meta_capi.send_event(
        event_name="CompleteRegistration", event_id="e_1",
        client_ip_address="2001:db8::1", client_user_agent=BROWSER_UA,
    )
    await meta_capi.send_event(event_name="CompleteRegistration", event_id="e_2")
    with_keys, without = (p["data"][0]["user_data"] for p in _MetaRecorder.payloads)
    # Strings, not hashed lists: Meta matches these verbatim.
    assert with_keys["client_ip_address"] == "2001:db8::1"
    assert with_keys["client_user_agent"] == BROWSER_UA
    assert "client_ip_address" not in without and "client_user_agent" not in without


async def test_subscribe_event_shape(meta_on):
    ok = await meta_capi.track_subscribe(
        user_id="u_sub", subscription_id="sub_RAWSTRIPEID", email="s@example.com",
        value=199.0, currency="USD", fbp=BROWSER_FBP,
    )
    assert ok is True
    ev = _MetaRecorder.payloads[0]["data"][0]
    assert ev["event_name"] == "Subscribe"
    assert ev["action_source"] == "system_generated"
    assert ev["event_id"] == meta_capi.event_id_for("subscribe", "sub_RAWSTRIPEID")
    assert ev["event_id"].startswith("subscribe.")
    assert ev["custom_data"] == {"value": 199.0, "currency": "USD"}
    assert "sub_RAWSTRIPEID" not in json.dumps(_MetaRecorder.payloads)


def test_the_stripe_webhook_module_never_reads_a_browser_key_off_its_request():
    """The webhook request is Stripe's. Parsed, so comments and docstrings
    (which name these functions to explain the rule) cannot trip it."""
    import ast
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "webhooks.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned_calls = {"remember_browser", "client_context", "client_ip"}
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if name in banned_calls:
                offenders.append(f"line {node.lineno}: {name}()")
        # A docstring is an Expr(Constant) and is skipped; a header lookup is not.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and str(arg.value).lower() in {
                    "user-agent", "fly-client-ip", "x-forwarded-for", "cf-connecting-ip",
                }:
                    offenders.append(f"line {node.lineno}: .get({arg.value!r})")
    assert offenders == [], offenders


def test_oauth_start_carries_fbp_in_the_attribution_cookie():
    import app.routers.oauth as oauth_module

    cleaned = oauth_module._clean_attribution({"fbp": BROWSER_FBP, "fbclid": "x"})
    assert cleaned.get("fbp") == BROWSER_FBP
    assert urlencode(cleaned)  # round-trips through the cookie encoding
