"""Shadow-test the paid path against LIVE Stripe, without taking any money.

WHY THIS EXISTS
---------------
Two bugs made the paid path non-functional for over a month each, and both
were invisible to the test suite:

  * #635 — every Checkout Session 400'd on an invalid parameter and the API
    returned 502, from 2026-07-18 to 2026-08-25. A permissive mock let a
    wrong-but-plausible Stripe field pass tests for 37 days while production
    was dead.
  * #639 — the webhook that GRANTS the paid tier 500'd on every real Stripe
    delivery, because `stripe.Event` is not a dict in stripe-python >= 12.
    All nine webhook tests monkeypatched `parse_webhook` to return a plain
    dict, so the shape that broke was the one shape never exercised.

Both are fixed and covered by tests that drive real vendor objects. When this
script was written, no account had ever completed a checkout, so "fixed" rested
on tests rather than on Stripe having accepted anything.

That is no longer true: the first real payment landed 2026-08-29 ($9.99, one
Pro subscription), which proves the checkout AND the tier-granting webhook both
work in production. This script keeps its value as a PREFLIGHT — it re-proves
the path on demand without waiting for a customer, and without taking money.
See `billing_audit.py` for the after-the-fact reconciliation.

WHAT "SHADOW" MEANS HERE — read before running
----------------------------------------------
NO MONEY MOVES. Creating a Checkout Session is a preflight: it mints a URL
and nothing else. No charge, no PaymentIntent, no Customer, no subscription —
those exist only once a human completes the hosted page. This script then
EXPIRES the session it created, so the URL it generated cannot be used by
anyone afterwards.

It calls the REAL `billing.create_checkout_session`, not a copy, because the
whole point is to exercise the exact kwargs production sends. A reimplementation
here would reintroduce the #635 blind spot in a new place.

What it CANNOT prove: that a real card is accepted, that Stripe fires the
webhook, or that the tier is granted end-to-end. Those need a human with a
card. This proves the half that was broken twice.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("stripe_preflight")

settings = get_settings()

#: (label, configured price id) for every plan the checkout can be asked for.
PRICE_FIELDS = [
    ("pro monthly", "stripe_price_pro_monthly"),
    ("pro annual", "stripe_price_pro_annual"),
    ("premium monthly", "stripe_price_premium_monthly"),
    ("premium annual", "stripe_price_premium_annual"),
]


def _f(obj: object, name: str, default: object = None) -> object:
    """Read a field off a Stripe vendor object.

    NOT `.get()`. In stripe-python >= 12 a `StripeObject` is not a dict
    subclass — its MRO is ('StripeObject', 'object') and it defines no `get` —
    so `obj.get("x")` raises AttributeError. That is precisely the #639
    production bug this script exists to guard against, and mypy caught this
    file committing it before it ever ran. `__getitem__` and attribute access
    both work; this uses them.
    """
    try:
        return obj[name]  # type: ignore[index]
    except Exception:
        return getattr(obj, name, default)


def _mask(s: str) -> str:
    """Enough to identify a key, never enough to use it."""
    return f"{s[:7]}…{s[-4:]}" if len(s) > 14 else "(set)"


async def _check_account() -> bool:
    import stripe

    stripe.api_key = settings.stripe_secret_key
    if not stripe.api_key:
        logger.error("STRIPE_SECRET_KEY is not set — nothing to test.")
        return False

    live = stripe.api_key.startswith("sk_live_")
    logger.info("key      : %s  (%s MODE)", _mask(stripe.api_key), "LIVE" if live else "TEST")
    try:
        acct = await asyncio.to_thread(stripe.Account.retrieve)
    except Exception as exc:
        logger.error("account  : UNREACHABLE — %s", exc)
        return False

    logger.info(
        "account  : %s  charges_enabled=%s payouts_enabled=%s",
        _f(acct, "id"), _f(acct, "charges_enabled"), _f(acct, "payouts_enabled"),
    )
    if not _f(acct, "charges_enabled"):
        logger.error(
            "  charges_enabled is FALSE — Stripe will not accept a payment on "
            "this account no matter what the app sends. Onboarding is "
            "incomplete."
        )
    return True


async def _check_prices() -> bool:
    """Every configured price id must exist, be active, and be recurring.

    A one-off price silently produces a checkout that charges once and never
    renews — a subscription product's worst kind of quiet wrong.
    """
    import stripe

    ok = True
    for label, field in PRICE_FIELDS:
        pid = getattr(settings, field, "")
        if not pid:
            logger.error("price %-16s NOT CONFIGURED (%s)", label, field)
            ok = False
            continue
        try:
            p = await asyncio.to_thread(stripe.Price.retrieve, pid)
        except Exception as exc:
            logger.error("price %-16s %s -> ERROR %s", label, pid, exc)
            ok = False
            continue

        rec = _f(p, "recurring") or {}
        amount_raw = _f(p, "unit_amount")
        amount = int(amount_raw) if isinstance(amount_raw, (int, float)) else 0
        problems = []
        if not _f(p, "active"):
            problems.append("INACTIVE")
        if not rec:
            problems.append("NOT RECURRING")
        logger.info(
            "price %-16s %s  %s %s / %s  %s",
            label, pid,
            f"{amount / 100:.2f}", str(_f(p, "currency") or "?").upper(),
            _f(rec, "interval", "once"),
            " ".join(problems) or "ok",
        )
        if problems:
            ok = False
    return ok


async def _shadow_checkout() -> bool:
    """Create a REAL Checkout Session through the app's own code path, then
    expire it. This is the call that 502'd for 37 days."""
    import stripe

    from app.services.billing import create_checkout_session

    logger.info("")
    logger.info("shadow checkout (no charge; session is expired immediately)")

    passed = True
    for tier in ("pro", "premium"):
        for period in ("monthly", "annual"):
            try:
                url = await create_checkout_session(
                    user_id="preflight-shadow-user",
                    user_email="preflight@tapeline.io",
                    tier=tier,
                    billing_period=period,
                    success_url="https://tapeline.io/app/billing?preflight=1",
                    cancel_url="https://tapeline.io/pricing?preflight=1",
                    # Short window; it is expired below regardless.
                    expires_in_minutes=30,
                    trial_end=datetime.now(UTC) + timedelta(days=14),
                )
            except Exception as exc:
                logger.error("  %-8s %-8s FAILED  %s", tier, period, exc)
                passed = False
                continue

            sid = url.rsplit("/", 1)[-1].split("#")[0] if url else ""
            logger.info("  %-8s %-8s OK      session=%s", tier, period, sid[:24])

            # Expire it so the URL this script minted can never be completed.
            try:
                sessions = await asyncio.to_thread(
                    stripe.checkout.Session.list, limit=1
                )
                data = _f(sessions, "data")
                newest = data[0] if isinstance(data, list) and data else None
                if newest is not None and _f(newest, "status") == "open":
                    await asyncio.to_thread(
                        stripe.checkout.Session.expire, str(_f(newest, "id"))
                    )
                    logger.info("           expired %s", str(_f(newest, "id"))[:24])
            except Exception as exc:
                logger.warning(
                    "           could not expire the session (%s) — it will "
                    "lapse on its own in 30 minutes", exc,
                )
    return passed


async def _check_webhook_parsing() -> bool:
    """Prove `parse_webhook` handles a REAL signed Stripe event.

    This is #639's failure mode, and it can be exercised without Stripe
    sending anything: sign a payload with the configured webhook secret
    exactly as Stripe would, then run it through the real parser. Nothing is
    dispatched and nothing is written — this stops at the parse.
    """
    import hashlib
    import hmac
    import json
    import time

    from app.services.billing import parse_webhook

    secret = settings.stripe_webhook_secret
    if not secret:
        logger.error("STRIPE_WEBHOOK_SECRET is not set — the webhook would 400.")
        return False

    payload = json.dumps({
        "id": "evt_preflight",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_preflight", "object": "checkout.session"}},
    }).encode()
    ts = int(time.time())
    sig = hmac.new(
        secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256
    ).hexdigest()

    try:
        event = parse_webhook(payload, f"t={ts},v1={sig}")
    except Exception as exc:
        logger.error("webhook parse: FAILED — %s", exc)
        return False

    # The #639 regression was `.get()` raising AttributeError on stripe.Event.
    try:
        assert event.get("type") == "checkout.session.completed"
        assert (event.get("data") or {}).get("object", {}).get("id") == "cs_preflight"
    except Exception as exc:
        logger.error("webhook parse: returned an object that cannot .get() — %s", exc)
        return False

    logger.info("webhook parse: OK (signature verified, .get() works)")
    return True


async def _check_card_wall() -> None:
    """Report how the card gate currently classifies real accounts."""
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import User
    from app.services.tier import CARD_GATE_START, must_add_card

    async with session_scope() as s:
        users = (await s.execute(select(User))).scalars().all()

    gated = [u for u in users if must_add_card(u)]
    with_card = [u for u in users if getattr(u, "stripe_customer_id", None)]
    logger.info("")
    logger.info("card wall (CARD_GATE_START=%s)", CARD_GATE_START)
    logger.info("  accounts total        : %d", len(users))
    logger.info("  would see the wall    : %d", len(gated))
    logger.info("  grandfathered/exempt  : %d", len(users) - len(gated))
    logger.info("  have a stripe customer: %d", len(with_card))
    if not with_card:
        logger.warning(
            "  NO account has a stripe_customer_id — no checkout has ever "
            "been completed. The paid path is still unproven end-to-end."
        )


async def _main() -> None:
    logger.info("=" * 62)
    if not await _check_account():
        return
    prices_ok = await _check_prices()
    checkout_ok = await _shadow_checkout()
    webhook_ok = await _check_webhook_parsing()
    await _check_card_wall()
    logger.info("")
    logger.info("=" * 62)
    logger.info(
        "prices=%s  shadow_checkout=%s  webhook_parse=%s",
        "ok" if prices_ok else "FAIL",
        "ok" if checkout_ok else "FAIL",
        "ok" if webhook_ok else "FAIL",
    )
    logger.info(
        "Still unproven by this script: a real card being accepted, Stripe "
        "firing the webhook, and the tier actually being granted. Those need "
        "a human with a card."
    )


if __name__ == "__main__":
    asyncio.run(_main())
