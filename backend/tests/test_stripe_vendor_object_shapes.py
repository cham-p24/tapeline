"""The webhook path must work against REAL Stripe SDK objects, not dict mocks.

Why this file exists. Two production-fatal bugs shipped because every existing
webhook test monkeypatches `parse_webhook` to return a plain Python dict:

1. `stripe.Event` is not a dict. In stripe-python >= 12 `StripeObject`'s MRO is
   ('StripeObject', 'object') and it defines no `get`/`keys`/`items`. So
   `event["type"]` works but `event.get("id")` raises `AttributeError: get`.
   routers/webhooks.py calls `.get(...)` ~34 times starting immediately after
   the signature check, so EVERY real delivery 500'd.

2. `current_period_end` was moved off the Subscription onto the subscription
   ITEM in API 2025-04-30.basil. The installed SDK pins 2026-03-25.dahlia, so
   `sub["current_period_end"]` raised KeyError on every subscription webhook.

Both are the #635 archetype: a mock that accepts a shape the vendor rejects.
A dict mock cannot catch either, because a dict has `.get()` and whatever keys
the fixture author typed. These tests therefore build a genuine `stripe.Event`
through `stripe.Webhook.construct_event` with a locally computed signature —
the same call production makes — so the vendor's real object semantics are on
the tested path.

Do not "simplify" these by substituting a dict. The dict is the bug.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import pytest
import stripe

WEBHOOK_SECRET = "whsec_test_secret_for_shape_tests"


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _subscription_event(**overrides: Any) -> dict[str, Any]:
    """A realistically shaped customer.subscription.created event.

    Note current_period_end lives on the ITEM, matching what Stripe actually
    sends on the pinned API version — NOT on the subscription.
    """
    sub: dict[str, Any] = {
        "id": "sub_test_1",
        "object": "subscription",
        "customer": "cus_test_1",
        "status": "active",
        "cancel_at_period_end": False,
        "items": {
            "object": "list",
            "data": [
                {
                    "id": "si_test_1",
                    "object": "subscription_item",
                    "current_period_end": 1790000000,
                    "price": {
                        "id": "price_test_pro_monthly",
                        "object": "price",
                        "recurring": {"interval": "month"},
                        "unit_amount": 999,
                        "currency": "usd",
                    },
                }
            ],
        },
    }
    sub.update(overrides)
    return {
        "id": "evt_test_1",
        "object": "event",
        "type": "customer.subscription.created",
        "data": {"object": sub},
    }


# ── The SDK contract these bugs violated ────────────────────────────────────

def test_stripe_object_is_not_a_dict() -> None:
    """Pin the vendor fact that both bugs depended on.

    If a future SDK makes StripeObject dict-like again this test fails, which
    is the correct prompt to re-read the coercion in parse_webhook rather than
    to discover the change through a production 500.
    """
    from stripe._stripe_object import StripeObject

    assert not issubclass(StripeObject, dict)
    assert not hasattr(StripeObject, "get")


def test_real_stripe_event_has_no_get() -> None:
    """The precise failure: __getitem__ works, .get() raises."""
    payload = json.dumps(_subscription_event()).encode()
    event = stripe.Webhook.construct_event(payload, _sign(payload), WEBHOOK_SECRET)

    assert event["type"] == "customer.subscription.created"  # works
    with pytest.raises(AttributeError):
        event.get("id")  # what webhooks.py:222 used to do


def test_current_period_end_is_not_on_the_subscription_object() -> None:
    """Pin the field move, so a revert to sub['current_period_end'] fails here."""
    import stripe._subscription as sub_mod
    import stripe._subscription_item as item_mod

    assert "current_period_end" not in sub_mod.Subscription.__doc__ or True  # doc-agnostic
    assert hasattr(item_mod.SubscriptionItem, "__annotations__")
    # The authoritative check: the SDK declares it on the item, not the sub.
    assert "current_period_end" in item_mod.SubscriptionItem.__annotations__
    assert "current_period_end" not in sub_mod.Subscription.__annotations__


# ── parse_webhook must hand downstream code something with .get() ───────────

def test_parse_webhook_returns_a_plain_dict(monkeypatch) -> None:
    from app.services import billing

    monkeypatch.setattr(billing.settings, "stripe_webhook_secret", WEBHOOK_SECRET, raising=False)
    payload = json.dumps(_subscription_event()).encode()

    event = billing.parse_webhook(payload, _sign(payload))

    assert type(event) is dict, f"parse_webhook returned {type(event).__name__}, not dict"
    # The operations routers/webhooks.py actually performs.
    assert event.get("id") == "evt_test_1"
    assert event.get("type") == "customer.subscription.created"
    assert event["data"]["object"].get("customer") == "cus_test_1"
    assert event["data"]["object"].get("nonexistent") is None
    assert event["data"]["object"].get("nonexistent", "fallback") == "fallback"


def test_parse_webhook_still_rejects_a_bad_signature(monkeypatch) -> None:
    """Coercing to a dict must not weaken verification.

    The whole safety of reading json.loads(payload) rests on construct_event
    having verified the HMAC over those exact bytes first.
    """
    from fastapi import HTTPException

    from app.services import billing

    monkeypatch.setattr(billing.settings, "stripe_webhook_secret", WEBHOOK_SECRET, raising=False)
    payload = json.dumps(_subscription_event()).encode()

    with pytest.raises(HTTPException) as exc:
        billing.parse_webhook(payload, _sign(payload, secret="whsec_the_wrong_secret"))
    assert exc.value.status_code == 400


def test_parse_webhook_rejects_a_tampered_body(monkeypatch) -> None:
    """Sign one body, deliver another — must not be accepted."""
    from fastapi import HTTPException

    from app.services import billing

    monkeypatch.setattr(billing.settings, "stripe_webhook_secret", WEBHOOK_SECRET, raising=False)
    signed = json.dumps(_subscription_event()).encode()
    tampered = json.dumps(_subscription_event(customer="cus_attacker")).encode()

    with pytest.raises(HTTPException) as exc:
        billing.parse_webhook(tampered, _sign(signed))
    assert exc.value.status_code == 400


# ── subscription_payload must survive the field move ────────────────────────

def test_subscription_payload_reads_period_end_from_the_item(monkeypatch) -> None:
    from app.services import billing

    monkeypatch.setattr(
        billing.settings, "stripe_price_pro_monthly", "price_test_pro_monthly", raising=False,
    )
    monkeypatch.setattr(billing.settings, "stripe_webhook_secret", WEBHOOK_SECRET, raising=False)

    payload = json.dumps(_subscription_event()).encode()
    event = billing.parse_webhook(payload, _sign(payload))

    p = billing.subscription_payload(event["data"]["object"])
    assert p["current_period_end"] is not None
    assert p["current_period_end"].timestamp() == 1790000000
    assert p["billing_period"] == "monthly"
    assert p["cancel_at_period_end"] is False


def test_subscription_payload_accepts_a_real_stripe_object(monkeypatch) -> None:
    """Belt and braces: even if something hands it the SDK object directly,
    subscription_payload must not raise — `.get()` is unavailable there."""
    from app.services import billing

    monkeypatch.setattr(
        billing.settings, "stripe_price_pro_monthly", "price_test_pro_monthly", raising=False,
    )
    payload = json.dumps(_subscription_event()).encode()
    sdk_event = stripe.Webhook.construct_event(payload, _sign(payload), WEBHOOK_SECRET)

    p = billing.subscription_payload(sdk_event["data"]["object"])
    assert p["tier"] == "pro"
    assert p["current_period_end"].timestamp() == 1790000000


def test_subscription_payload_tolerates_a_missing_period_end(monkeypatch) -> None:
    """A missing renewal date must degrade one email line, not 500 the webhook
    that grants the paid tier."""
    from app.services import billing

    monkeypatch.setattr(
        billing.settings, "stripe_price_pro_monthly", "price_test_pro_monthly", raising=False,
    )
    evt = _subscription_event()
    del evt["data"]["object"]["items"]["data"][0]["current_period_end"]

    p = billing.subscription_payload(evt["data"]["object"])
    assert p["current_period_end"] is None
    assert p["tier"] == "pro"  # the part that grants access still works


def test_subscription_payload_reads_legacy_period_end_on_the_subscription(monkeypatch) -> None:
    """Pre-basil payloads (and older fixtures) keep working."""
    from app.services import billing

    monkeypatch.setattr(
        billing.settings, "stripe_price_pro_monthly", "price_test_pro_monthly", raising=False,
    )
    evt = _subscription_event()
    del evt["data"]["object"]["items"]["data"][0]["current_period_end"]
    evt["data"]["object"]["current_period_end"] = 1795000000

    p = billing.subscription_payload(evt["data"]["object"])
    assert p["current_period_end"].timestamp() == 1795000000
