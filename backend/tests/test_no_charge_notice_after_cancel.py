"""A cancelled trial must never be told a charge is coming.

`customer.subscription.trial_will_end` is scheduled off `trial_end`, and
Stripe sends it regardless of `cancel_at_period_end` — a subscription set to
cancel is still `trialing` right up to the date. The pre-charge email states as
fact that "the card you added is charged <amount> and Premium continues".

So without a guard, someone who has already cancelled is told we are about to
take their money. That is false, it is alarming, and it is the shortest path
from a polite non-customer to a chargeback or a complaint — on a product whose
entire pitch is that it does not misstate things.

Not hypothetical. Account created 2026-09-03 13:04 added a card for the
$199/year trial and cancelled at 13:07, three minutes later. Its trial runs to
09-17, so this event fires on 09-14. The fixtures below are that subscription's
real shape.

Nothing is sent instead of a corrected email: they asked to stop, they already
have the cancellation confirmation, and the one thing this email exists to
prevent — an unexpected charge — cannot happen to them.
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

WEBHOOK_SECRET = "whsec_test_secret_for_cancel_guard"


def _sign(payload: bytes) -> str:
    ts = int(time.time())
    sig = hmac.new(
        WEBHOOK_SECRET.encode(), f"{ts}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={sig}"


def _subscription(
    *,
    customer: str,
    cancel_at_period_end: bool = False,
    canceled_at: int | None = None,
    unit_amount: int = 19900,
    interval: str = "year",
) -> dict:
    """A trialing subscription as `trial_will_end` delivers it.

    Subscription items DO still carry an expanded `price` on this account's
    API version — unlike invoice LINES, which lost it. Verified against the
    live objects rather than assumed; see
    tests/test_renewal_reminder_is_sent.py for the invoice-side trap.
    """
    trial_end = int((datetime.now(UTC) + timedelta(days=3)).timestamp())
    return {
        "id": f"sub_{uuid.uuid4().hex[:16]}",
        "object": "subscription",
        "customer": customer,
        "status": "trialing",
        "trial_end": trial_end,
        "cancel_at_period_end": cancel_at_period_end,
        "canceled_at": canceled_at,
        "items": {
            "object": "list",
            "data": [
                {
                    "id": f"si_{uuid.uuid4().hex[:14]}",
                    "object": "subscription_item",
                    "price": {
                        "id": f"price_{uuid.uuid4().hex[:16]}",
                        "object": "price",
                        "unit_amount": unit_amount,
                        "currency": "usd",
                        "recurring": {"interval": interval, "interval_count": 1},
                    },
                }
            ],
        },
    }


async def _user() -> User:
    uid = f"u_{uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.test", name="Cancel probe",
            tier="premium", password_hash="x", drip_state="",
            stripe_customer_id=f"cus_{uuid.uuid4().hex[:18]}",
        ))
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


async def _cleanup(user: User) -> None:
    async with session_scope() as s:
        await s.execute(delete(User).where(User.id == user.id))


async def _deliver(monkeypatch, sub: dict) -> list[dict]:
    """POST a signed trial_will_end through the real endpoint."""
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
        # Required: construct_event reads event.object before our code runs.
        "object": "event",
        "api_version": "2026-08-26.dahlia",
        "type": "customer.subscription.trial_will_end",
        "data": {"object": sub},
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
async def test_a_cancelled_trial_is_not_told_it_will_be_charged(monkeypatch):
    """The live case: card added, cancelled three minutes later."""
    user = await _user()
    try:
        sent = await _deliver(
            monkeypatch,
            _subscription(
                customer=user.stripe_customer_id,
                cancel_at_period_end=True,
                canceled_at=int(datetime.now(UTC).timestamp()),
            ),
        )
        assert sent == [], (
            "a subscriber who already cancelled was emailed that their card "
            f"is about to be charged: {sent[0]['subject'] if sent else ''}"
        )
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_cancel_at_period_end_alone_is_enough_to_suppress(monkeypatch):
    """`canceled_at` can be null while the cancellation is still scheduled."""
    user = await _user()
    try:
        sent = await _deliver(
            monkeypatch,
            _subscription(
                customer=user.stripe_customer_id, cancel_at_period_end=True
            ),
        )
        assert sent == []
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_a_live_trial_still_gets_its_warning(monkeypatch):
    """The guard must not silence the case this email exists for.

    A card-required trialist is invisible to run_daily_drip (it filters on
    `stripe_customer_id IS NULL`), so this is their ONLY pre-charge notice.
    Suppressing it would recreate the exact failure the branch was built to
    prevent: money taken with no warning.
    """
    user = await _user()
    try:
        sent = await _deliver(
            monkeypatch, _subscription(customer=user.stripe_customer_id)
        )
        assert len(sent) == 1, "a live trial got no pre-charge warning"
        body = sent[0]["html"]
        assert "199.00" in body
        assert "charged" in body.lower()
    finally:
        await _cleanup(user)


@pytest.mark.asyncio
async def test_the_amount_is_still_read_off_the_subscription(monkeypatch):
    """Subscription ITEMS still carry an expanded price on this API version.

    Invoice lines do not — that difference silently killed the renewal
    reminder before it shipped. Pinned here so a future refactor that
    "unifies" the two readers is caught by a test rather than by a customer.
    """
    user = await _user()
    try:
        sent = await _deliver(
            monkeypatch,
            _subscription(
                customer=user.stripe_customer_id, unit_amount=1999, interval="month"
            ),
        )
        assert len(sent) == 1
        assert "19.99" in sent[0]["html"], "the quoted amount is not the real one"
    finally:
        await _cleanup(user)
