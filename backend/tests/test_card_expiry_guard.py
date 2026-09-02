"""The card on file must not be dead on the day Stripe tries the renewal.

WHAT THIS REPLACED. `routers/webhooks.py` carried a `customer.source.expiring`
branch from the retention work onward. It had never executed, and could not
have: that event is emitted for legacy Card *Sources* attached to a Customer,
and this account has none. Checked against the live account on 2026-09-02 —
all four customers return `sources.total_count = 0` with `default_source =
None`, hold exactly one PaymentMethod each, and the single charge on the
account carries `source=None`. Checkout in mode="subscription" mints
PaymentMethods, and nothing in this codebase creates a Source. The live
endpoint (we_1TWeuYJ23wFFL5Y3Kn54dZ2p) was never subscribed to it either, so
enabling it would have bought a branch that still never ran.

The risk it was written for is real, though, and it is the expensive kind: an
annual subscriber is charged once every twelve months, so a card that expired
somewhere in between fails silently and takes a paying customer with it. Two
of the four live subscriptions are $199/yr. The guard therefore moved onto
`invoice.upcoming`, which IS subscribed, fires before every renewal, and
carries the timestamp of the charge.

THE SHAPES HERE ARE REAL. Every fixture below is copied from a payload pulled
off the live account, which runs API 2026-08-26.dahlia. Three things that
version does which a hand-written fixture gets wrong, and which this file
pins:

  * `invoice["subscription"]` is NULL. The id moved to
    `parent.subscription_details.subscription`. Resolving the payment method
    without that hop lands on the customer default, which is null on all four
    live customers, so the guard would silently never fire.
  * `invoice["default_payment_method"]` is null too — nothing pins a method to
    an invoice here.
  * A PaymentMethod is not necessarily a card. One live subscriber pays by
    Link, whose PaymentMethod has `card: null` and no expiry anywhere on it.

Behaviour is proven by executing the path — the resolver against stubbed
vendor calls returning real objects, and the webhook end-to-end through the
actual route. No test in this file reads source code.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import stripe
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.routers import webhooks as webhooks_router
from app.services import billing as billing_mod
from app.services import email as email_module
from app.services.billing import card_is_dead_by, card_on_file_for_invoice

DAY = 86400


# ── real captured objects ────────────────────────────────────────────────────
#
# pm_1UANGsJ23wFFL5Y3221yHlDK and pm_1U9cbkJ23wFFL5Y3T2m95zry as the live
# account returned them, trimmed to the keys the resolver reads plus enough
# neighbours to keep the shape honest.

PM_CARD = {
    "id": "pm_1UANGsJ23wFFL5Y3221yHlDK",
    "object": "payment_method",
    "allow_redisplay": "limited",
    "card": {
        "brand": "visa",
        "checks": {"cvc_check": "pass"},
        "country": "US",
        "display_brand": "visa",
        "exp_month": 4,
        "exp_year": 2029,
        "fingerprint": "YqyeOLNJx1Lei8C2",
        "funding": "debit",
        "generated_from": None,
        "last4": "8810",
        "networks": {"available": ["visa"], "preferred": None},
        "regulated_status": "unregulated",
        "wallet": None,
    },
    "created": 1788152198,
    "customer": "cus_VAihb2pQYbzltR",
    "livemode": True,
    "metadata": {},
    "type": "card",
}

# NOTE: no "card" key at all, not `card: {}`. Link is how one of the four live
# subscribers pays, so this branch is not defensive programming.
PM_LINK = {
    "id": "pm_1U9cbkJ23wFFL5Y3T2m95zry",
    "object": "payment_method",
    "allow_redisplay": "limited",
    "created": 1787972825,
    "customer": "cus_V9wU3CR1phpG29",
    "link": {"email": "llegrandconsulting@gmail.com"},
    "livemode": True,
    "metadata": {},
    "type": "link",
}


def _upcoming(
    customer: str,
    *,
    due_in_days: int = 3,
    period_days: int = 365,
    sub_id: str | None = "sub_1UANGvJ23wFFL5Y3JdIDhrCv",
    default_payment_method: str | None = None,
) -> dict:
    """An invoice.upcoming payload as 2026-08-26.dahlia delivers it.

    Copied from `stripe.Invoice.create_preview` against the live annual
    subscription. The line carries no `price` key and the subscription id sits
    only under `parent`.
    """
    due = int((datetime.now(UTC) + timedelta(days=due_in_days)).timestamp())
    return {
        "id": f"upcoming_in_{_uuid.uuid4().hex[:16]}",
        "object": "invoice",
        "customer": customer,
        "amount_due": 19900,
        "currency": "usd",
        "billing_reason": "upcoming",
        "next_payment_attempt": due,
        "period_end": due,
        "period_start": due - period_days * DAY,
        "default_payment_method": default_payment_method,
        "default_source": None,
        "subscription": None,
        "parent": {
            "type": "subscription_details",
            "quote_details": None,
            "subscription_details": {
                "subscription": sub_id,
                "metadata": {"billing_period": "annual", "tier": "premium"},
            },
        },
        "lines": {
            "object": "list",
            "data": [
                {
                    "id": f"il_tmp_{_uuid.uuid4().hex[:16]}",
                    "object": "line_item",
                    "amount": 19900,
                    "currency": "usd",
                    "description": "1 x Tapeline Premium Annual (at $199.00 / year)",
                    "livemode": True,
                    "period": {"start": due, "end": due + period_days * DAY},
                    "pricing": {
                        "type": "price_details",
                        "price_details": {
                            "price": f"price_{_uuid.uuid4().hex[:16]}",
                            "product": f"prod_{_uuid.uuid4().hex[:12]}",
                        },
                        "unit_amount_decimal": "19900",
                    },
                    "quantity": 1,
                    "subtotal": 19900,
                    "taxes": [],
                }
            ],
        },
    }


class _Stripe:
    """Stand in for the vendor calls the resolver makes, returning real shapes.

    Records what was asked for so the resolution ORDER can be asserted, not
    just its answer.
    """

    def __init__(self, *, sub=None, pm=None, customer=None, raises=None):
        self._sub, self._pm, self._customer, self._raises = sub, pm, customer, raises
        self.asked: list[tuple[str, str]] = []

    def install(self, monkeypatch):
        monkeypatch.setattr(billing_mod.settings, "stripe_secret_key", "sk_test_x")
        monkeypatch.setattr(stripe.Subscription, "retrieve", self._sub_retrieve)
        monkeypatch.setattr(stripe.PaymentMethod, "retrieve", self._pm_retrieve)
        monkeypatch.setattr(stripe.Customer, "retrieve", self._cust_retrieve)
        return self

    def _sub_retrieve(self, sub_id, *a, **kw):
        self.asked.append(("subscription", sub_id))
        if self._raises == "subscription":
            raise stripe.error.APIConnectionError("boom")
        return self._sub

    def _pm_retrieve(self, pm_id, *a, **kw):
        self.asked.append(("payment_method", pm_id))
        if self._raises == "payment_method":
            raise stripe.error.APIConnectionError("boom")
        return self._pm

    def _cust_retrieve(self, cust_id, *a, **kw):
        self.asked.append(("customer", cust_id))
        if self._raises == "customer":
            raise stripe.error.APIConnectionError("boom")
        return self._customer


# ═════════════════════════════════════════════════════════════════════════════
# card_is_dead_by — the month-end boundary
# ═════════════════════════════════════════════════════════════════════════════

def _ts(y: int, m: int, d: int) -> float:
    return datetime(y, m, d, 12, 0, tzinfo=UTC).timestamp()


def test_card_is_alive_on_the_last_day_of_its_expiry_month():
    # A card marked 09/2026 is good through 2026-09-30. Warning this customer
    # would be warning someone whose card works.
    assert card_is_dead_by({"exp_month": 9, "exp_year": 2026}, _ts(2026, 9, 30)) is False


def test_card_is_dead_on_the_first_of_the_next_month():
    assert card_is_dead_by({"exp_month": 9, "exp_year": 2026}, _ts(2026, 10, 1)) is True


def test_december_expiry_rolls_the_year():
    card = {"exp_month": 12, "exp_year": 2026}
    assert card_is_dead_by(card, _ts(2026, 12, 31)) is False
    assert card_is_dead_by(card, _ts(2027, 1, 1)) is True


def test_far_future_card_is_never_dead():
    # The real card on the live annual sub: 04/2029, renewing Sep 2027.
    assert card_is_dead_by(PM_CARD["card"], _ts(2027, 9, 14)) is False


def test_missing_or_junk_expiry_is_not_treated_as_dead():
    # Silence beats a false alarm — see the Link case below.
    assert card_is_dead_by({}, _ts(2026, 10, 1)) is False
    assert card_is_dead_by({"exp_month": None, "exp_year": None}, _ts(2026, 10, 1)) is False
    assert card_is_dead_by({"exp_month": 13, "exp_year": 2026}, _ts(2027, 6, 1)) is False
    assert card_is_dead_by({"exp_month": "x", "exp_year": "y"}, _ts(2027, 6, 1)) is False


# ═════════════════════════════════════════════════════════════════════════════
# card_on_file_for_invoice — the resolution hops
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_resolves_through_parent_subscription_details(monkeypatch):
    """The hop that a hand-written fixture would miss.

    `invoice["subscription"]` is null on dahlia; the id is under `parent`. If
    this hop is dropped the resolver falls to the customer default, which is
    null on every live customer, and the guard silently never fires.
    """
    st = _Stripe(
        sub={"id": "sub_1UANGvJ23wFFL5Y3JdIDhrCv",
             "default_payment_method": PM_CARD["id"]},
        pm=PM_CARD,
    ).install(monkeypatch)

    card = await card_on_file_for_invoice(_upcoming("cus_VAihb2pQYbzltR"))

    assert card == {"brand": "visa", "last4": "8810", "exp_month": 4, "exp_year": 2029}
    assert st.asked == [
        ("subscription", "sub_1UANGvJ23wFFL5Y3JdIDhrCv"),
        ("payment_method", PM_CARD["id"]),
    ]


@pytest.mark.asyncio
async def test_invoice_level_default_wins_and_skips_the_subscription_hop(monkeypatch):
    st = _Stripe(pm=PM_CARD).install(monkeypatch)
    card = await card_on_file_for_invoice(
        _upcoming("cus_VAihb2pQYbzltR", default_payment_method=PM_CARD["id"])
    )
    assert card is not None
    assert st.asked == [("payment_method", PM_CARD["id"])]


@pytest.mark.asyncio
async def test_falls_back_to_the_customer_default(monkeypatch):
    st = _Stripe(
        sub={"id": "s", "default_payment_method": None},
        customer={"id": "cus_VAihb2pQYbzltR",
                  "invoice_settings": {"default_payment_method": PM_CARD["id"]}},
        pm=PM_CARD,
    ).install(monkeypatch)
    card = await card_on_file_for_invoice(_upcoming("cus_VAihb2pQYbzltR"))
    assert card is not None
    assert [k for k, _ in st.asked] == ["subscription", "customer", "payment_method"]


@pytest.mark.asyncio
async def test_link_payment_method_yields_no_card(monkeypatch):
    """A real live subscriber pays by Link. It has no card and cannot expire."""
    _Stripe(
        sub={"id": "s", "default_payment_method": PM_LINK["id"]}, pm=PM_LINK
    ).install(monkeypatch)
    assert await card_on_file_for_invoice(_upcoming("cus_V9wU3CR1phpG29")) is None


@pytest.mark.asyncio
async def test_legacy_source_id_is_not_chased(monkeypatch):
    """`default_source` holds a Source id, which PaymentMethod.retrieve cannot
    load. Chasing it would rebuild the dead branch this replaced."""
    st = _Stripe(
        sub={"id": "s", "default_payment_method": "card_1AbcLegacySource"}
    ).install(monkeypatch)
    assert await card_on_file_for_invoice(_upcoming("cus_x")) is None
    assert ("payment_method", "card_1AbcLegacySource") not in st.asked


@pytest.mark.asyncio
@pytest.mark.parametrize("where", ["subscription", "payment_method", "customer"])
async def test_stripe_failures_return_none_rather_than_raise(monkeypatch, where):
    """This runs inside the renewal-notice path. A card lookup that blows up
    must not take the renewal email down with it."""
    st = _Stripe(
        sub={"id": "s", "default_payment_method": None if where == "customer" else PM_CARD["id"]},
        customer={"id": "c", "invoice_settings": {"default_payment_method": PM_CARD["id"]}},
        pm=PM_CARD,
        raises=where,
    ).install(monkeypatch)
    assert await card_on_file_for_invoice(_upcoming("cus_x")) is None
    assert st.asked  # it really did try


@pytest.mark.asyncio
async def test_no_stripe_key_is_a_quiet_none(monkeypatch):
    monkeypatch.setattr(billing_mod.settings, "stripe_secret_key", "")
    assert await card_on_file_for_invoice(_upcoming("cus_x")) is None


# ═════════════════════════════════════════════════════════════════════════════
# End to end, through the real webhook route
# ═════════════════════════════════════════════════════════════════════════════

class _Capture:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, to, subject, html, persona=None, **_kw):
        self.calls.append({"to": to, "subject": subject, "html": html})
        return {"id": "test-msg"}

    def subjects(self, addr: str) -> list[str]:
        return [c["subject"] for c in self.calls if c["to"] == addr]


async def _user(**over) -> tuple[str, str, str]:
    uid = f"cardexp_{_uuid.uuid4().hex}"
    cust = f"cus_{_uuid.uuid4().hex[:18]}"
    fields = {
        "id": uid, "email": f"{uid}@example.com", "name": "Card probe",
        "tier": "premium", "password_hash": "x", "drip_state": "",
        "stripe_customer_id": cust,
    }
    fields.update(over)
    async with session_scope() as s:
        s.add(User(**fields))
        await s.commit()
    return uid, fields["email"], cust


async def _drip_state(uid: str) -> str:
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        return u.drip_state or ""


async def _fire(monkeypatch, invoice: dict) -> httpx.Response:
    event = {
        "id": f"evt_{_uuid.uuid4().hex}",
        "type": "invoice.upcoming",
        "data": {"object": invoice},
    }
    monkeypatch.setattr(webhooks_router.settings, "stripe_webhook_secret", "whsec_test")
    monkeypatch.setattr(webhooks_router, "parse_webhook", lambda body, sig: event)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.post(
            "/api/webhooks/stripe", content=b"{}", headers={"stripe-signature": "x"},
        )


def _card_is(monkeypatch, card: dict | None):
    async def _resolve(_invoice):
        return card
    monkeypatch.setattr(webhooks_router, "card_on_file_for_invoice", _resolve)


DEAD = {"brand": "visa", "last4": "8810", "exp_month": 6, "exp_year": 2026}
ALIVE = {"brand": "visa", "last4": "8810", "exp_month": 4, "exp_year": 2029}


@pytest.mark.asyncio
async def test_dead_card_warns_and_names_the_renewal(monkeypatch):
    _, email, cust = await _user()
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    _card_is(monkeypatch, DEAD)

    r = await _fire(monkeypatch, _upcoming(cust))
    assert r.status_code == 200

    subjects = cap.subjects(email)
    assert len(subjects) == 1, f"expected exactly one email, got {subjects}"
    assert "card expires" in subjects[0].lower()
    html = next(c["html"] for c in cap.calls if c["to"] == email)
    assert "8810" in html
    assert "06/2026" in html
    # The card email carries the renewal disclosure, which is what lets it
    # replace the routine reminder rather than arrive next to it.
    assert "$199.00 USD" in html
    assert datetime.now(UTC).strftime("%Y") in html or "20" in html


@pytest.mark.asyncio
async def test_dead_card_suppresses_the_routine_renewal_reminder(monkeypatch):
    """One charge, one email. Both notices are about the same renewal."""
    _, email, cust = await _user()
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    _card_is(monkeypatch, DEAD)
    await _fire(monkeypatch, _upcoming(cust))
    assert not any("renews on" in s for s in cap.subjects(email))


@pytest.mark.asyncio
async def test_live_card_sends_the_ordinary_reminder_and_no_card_warning(monkeypatch):
    uid, email, cust = await _user()
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    _card_is(monkeypatch, ALIVE)

    await _fire(monkeypatch, _upcoming(cust))

    subjects = cap.subjects(email)
    assert len(subjects) == 1
    assert "renews on" in subjects[0]
    assert "cardexp" not in await _drip_state(uid)


@pytest.mark.asyncio
async def test_monthly_gets_the_card_warning_even_though_reminders_are_skipped(monkeypatch):
    """The annual-only gate is about reminder NOISE. An imminent decline is
    not noise at any interval, so the guard sits outside that gate."""
    _, email, cust = await _user()
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    _card_is(monkeypatch, DEAD)

    await _fire(monkeypatch, _upcoming(cust, period_days=31))

    assert [s for s in cap.subjects(email) if "card expires" in s.lower()]


@pytest.mark.asyncio
async def test_monthly_with_a_live_card_stays_silent(monkeypatch):
    _, email, cust = await _user()
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    _card_is(monkeypatch, ALIVE)
    await _fire(monkeypatch, _upcoming(cust, period_days=31))
    assert cap.subjects(email) == []


@pytest.mark.asyncio
async def test_warned_once_per_card_not_once_per_cycle(monkeypatch):
    """A distinct second event for the same unchanged card must not re-nag.

    Exact redeliveries are already stopped by the StripeWebhookEvent id-dedup;
    this covers the monthly subscriber who gets a genuinely new invoice.upcoming
    every cycle with the same dead card still on file.
    """
    uid, email, cust = await _user()
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    _card_is(monkeypatch, DEAD)

    await _fire(monkeypatch, _upcoming(cust, period_days=31))
    assert "cardexp620268810" in await _drip_state(uid)
    first = len(cap.subjects(email))

    await _fire(monkeypatch, _upcoming(cust, period_days=31))
    assert len(cap.subjects(email)) == first, "second event re-sent the warning"


@pytest.mark.asyncio
async def test_a_new_card_earns_a_new_warning(monkeypatch):
    """Dedup is keyed to the card, so replacing it re-arms the guard."""
    _, email, cust = await _user(drip_state="cardexp620268810")
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    _card_is(monkeypatch, {**DEAD, "last4": "1111"})

    await _fire(monkeypatch, _upcoming(cust))
    assert [s for s in cap.subjects(email) if "card expires" in s.lower()]


@pytest.mark.asyncio
async def test_link_customer_is_never_warned(monkeypatch):
    """card_on_file_for_invoice returns None for Link; the guard must go quiet
    and let the ordinary reminder through."""
    uid, email, cust = await _user()
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    _card_is(monkeypatch, None)

    await _fire(monkeypatch, _upcoming(cust))

    subjects = cap.subjects(email)
    assert not [s for s in subjects if "card expires" in s.lower()]
    assert "cardexp" not in await _drip_state(uid)


@pytest.mark.asyncio
async def test_unknown_customer_is_a_clean_noop(monkeypatch):
    cap = _Capture()
    monkeypatch.setattr(email_module, "send_email", cap)
    _card_is(monkeypatch, DEAD)
    r = await _fire(monkeypatch, _upcoming(f"cus_{_uuid.uuid4().hex[:18]}"))
    assert r.status_code == 200
    assert cap.calls == []


@pytest.mark.asyncio
async def test_a_skipped_send_leaves_the_token_unstamped(monkeypatch):
    """Mirrors the dunning branch: an undelivered email must not consume the
    one warning this card gets."""
    uid, _, cust = await _user()

    async def _skip(to, subject, html, persona=None, **_kw):
        return {"skipped": True}

    monkeypatch.setattr(email_module, "send_email", _skip)
    _card_is(monkeypatch, DEAD)

    await _fire(monkeypatch, _upcoming(cust))
    assert "cardexp" not in await _drip_state(uid)
