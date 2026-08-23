"""The `customer.subscription.trial_will_end` branch must actually RUN.

It is the ONLY pre-charge notice a card-on-file trialist ever gets:
`run_daily_drip` filters `User.stripe_customer_id.is_(None)`
(services/email.py), and a card-required trial always has a customer id, so
that cohort receives no drip. If this branch dies, Stripe charges $19.99 (or
$9.99) three days later with no warning email of any kind — the exact
chargeback pattern the handler's own comment says the product cannot defend.

It WAS dead. `UTC` was bound only by function-local
`from datetime import UTC, datetime` statements inside the
`customer.subscription.created/updated` branch, which made `UTC` a local for
the WHOLE function body — so the read in this mutually-exclusive branch was an
unbound local:

    UnboundLocalError: cannot access local variable 'UTC' where it is not
    associated with a value

`except Exception` swallowed it, leaving only a `stripe.trial_will_end_email_error`
log line in production.

The pre-existing test asserted only that certain STRINGS appear in the source
file, so it passed the entire time the branch was raising. These tests invoke
the handler and assert an email was actually rendered and sent.
"""
from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import StripeWebhookEvent, User
from app.routers import webhooks as webhooks_router


async def _post_stripe_event(monkeypatch, event: dict) -> httpx.Response:
    monkeypatch.setattr(webhooks_router, "parse_webhook", lambda body, sig: event)
    monkeypatch.setattr(webhooks_router.settings, "stripe_webhook_secret", "whsec_test")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.post(
            "/api/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "sig"},
        )


def _event(customer_id: str, event_id: str, trial_end: int | None) -> dict:
    obj: dict = {
        "id": f"sub_{uuid.uuid4().hex[:12]}",
        "customer": customer_id,
        "status": "trialing",
        "items": {
            "data": [
                {
                    "price": {
                        "id": "price_test",
                        "unit_amount": 1999,
                        "currency": "usd",
                        "recurring": {"interval": "month"},
                    }
                }
            ]
        },
    }
    if trial_end is not None:
        obj["trial_end"] = trial_end
    return {
        "id": event_id,
        "type": "customer.subscription.trial_will_end",
        "data": {"object": obj},
    }


@pytest.fixture
async def trialist():
    cid = f"cus_{uuid.uuid4().hex[:12]}"
    uid = str(uuid.uuid4())
    async with session_scope() as s:
        s.add(
            User(
                id=uid,
                email=f"trial-{uuid.uuid4().hex[:8]}@example.com",
                tier="premium",
                stripe_customer_id=cid,
            )
        )
        await s.commit()
    yield uid, cid
    async with session_scope() as s:
        await s.execute(delete(User).where(User.id == uid))
        await s.commit()


@pytest.mark.asyncio
async def test_trial_will_end_actually_sends_the_precharge_email(monkeypatch, trialist):
    """THE regression. Before the fix this raised UnboundLocalError, the
    blanket `except Exception` swallowed it, and no email was ever sent."""
    uid, cid = trialist
    sent: list[dict] = []

    import app.services.email as email_mod

    async def _capture(*args, **kwargs):
        sent.append({"args": args, "kwargs": kwargs})
        return True

    monkeypatch.setattr(email_mod, "send_email", _capture)

    eid = f"evt_{uuid.uuid4().hex[:12]}"
    # 2026-09-06T00:00:00Z — a concrete instant, so the date label is derived
    # from Stripe's own trial_end rather than from anything we guess.
    trial_end = 1788652800
    try:
        r = await _post_stripe_event(monkeypatch, _event(cid, eid, trial_end))
        assert r.status_code == 200, r.text
        assert sent, (
            "no pre-charge email was sent for customer.subscription.trial_will_end "
            "— the branch raised and the blanket except swallowed it, so a "
            "card-on-file trialist gets charged with zero notice"
        )
    finally:
        async with session_scope() as s:
            await s.execute(
                delete(StripeWebhookEvent).where(StripeWebhookEvent.id == eid)
            )
            await s.commit()


@pytest.mark.asyncio
async def test_trial_will_end_survives_a_missing_trial_end(monkeypatch, trialist):
    """Stripe may omit trial_end. The handler has a fallback label for that, and
    it must still send rather than fall into the error path."""
    uid, cid = trialist
    sent: list[dict] = []

    import app.services.email as email_mod

    async def _capture(*args, **kwargs):
        sent.append({"args": args, "kwargs": kwargs})
        return True

    monkeypatch.setattr(email_mod, "send_email", _capture)

    eid = f"evt_{uuid.uuid4().hex[:12]}"
    try:
        r = await _post_stripe_event(monkeypatch, _event(cid, eid, None))
        assert r.status_code == 200, r.text
        assert sent, "no email sent when Stripe omitted trial_end"
    finally:
        async with session_scope() as s:
            await s.execute(
                delete(StripeWebhookEvent).where(StripeWebhookEvent.id == eid)
            )
            await s.commit()


def test_webhooks_module_has_no_function_local_UTC_shadowing():
    """Structural guard against the whole CLASS of this bug.

    Python makes a name function-local for the ENTIRE body if it is bound
    anywhere in it, so one `from datetime import UTC` inside a single branch
    silently breaks every OTHER branch that reads UTC. Keep the import at module
    scope; a future branch adding a local one re-creates the outage.
    """
    import ast
    import pathlib

    src = pathlib.Path("app/routers/webhooks.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    offenders: list[str] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for n in ast.walk(fn):
            if isinstance(n, ast.ImportFrom) and n.module == "datetime":
                for a in n.names:
                    if (a.asname or a.name) == "UTC":
                        offenders.append(f"{fn.name}() line {n.lineno}")
    assert not offenders, (
        "function-local `UTC` import(s) found — these shadow the module-level "
        "import for the WHOLE function, so any other branch reading UTC raises "
        "UnboundLocalError: " + ", ".join(offenders)
    )
