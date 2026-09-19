"""Cross-reference every account's LOCAL billing state against LIVE Stripe.

READ-ONLY. It creates nothing, writes nothing, cancels nothing. Every finding
is reported for a human to act on, because every possible "fix" here moves
money or changes what someone is entitled to.

WHY
---
Local `User.tier` and Stripe's subscription state are two records of the same
fact, kept in step by exactly one mechanism: the webhook. That webhook 500'd on
every real delivery for an unknown period (#639 — `stripe.Event` is not a dict
in stripe-python >= 12), and the Checkout Session before it 502'd for 37 days
(#635). Both are fixed, but nothing has ever checked whether the two records
actually AGREE for the accounts that existed while they were broken.

The asymmetry that matters: being charged and not getting the product is a
much worse failure than getting the product free. So `PAID_NOT_GRANTED` is
reported first and loudest.

FINDINGS
--------
  PAID_NOT_GRANTED   Stripe has an active/trialing subscription; local tier is
                     free. Someone is paying for nothing. This is #639's exact
                     signature.
  GRANTED_NOT_PAID   Local tier is paid; Stripe has no live subscription.
                     Often legitimate (admin, lifetime, hand-comped) — those
                     are labelled, not flagged.
  PAST_DUE           Subscription exists but Stripe cannot collect. Silent
                     churn unless dunning is handled.
  TIER_MISMATCH      Both sides live, but on different plans.
  ORPHAN_CUSTOMER    Local stripe_customer_id points at a customer Stripe does
                     not have (deleted, or a test/live key swap).
  TRIAL_LAPSED       Trial end is in the past, still on a paid tier, with no
                     subscription behind it.
  DUPLICATE_CUSTOMER Two Stripe customers share one email — a double-billing
                     risk the moment both subscribe.

Emails are masked and Stripe ids are hashed in the output: this runs in the
Actions log of a PUBLIC repository, which anyone can read.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import traceback
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.models import User
from app.services.stripe_compat import stripe_field as _f

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("billing_audit")
# stripe-python logs every request at INFO on the "stripe" logger, and the URL
# carries the customer id (".../v1/customers/cus_…",
# ".../v1/subscriptions?customer=cus_…"). Under the INFO root handler above
# that went straight into the public Actions log: the 14 Sep 2026 run printed
# each customer's raw id four times this way. Nothing of the audit's own is
# lost: a failed Stripe call still raises into this script, which reports it
# through _scrub().
logging.getLogger("stripe").setLevel(logging.WARNING)

settings = get_settings()

#: Stripe statuses that mean "this person currently has the product".
LIVE_STATUSES = {"active", "trialing", "past_due"}
PAID_TIERS = {"pro", "premium"}


def _mask_email(email: str | None) -> str:
    if not email:
        return "(none)"
    name, _, domain = email.partition("@")
    head = name[:2] if len(name) > 2 else name[:1]
    return f"{head}***@{domain}" if domain else f"{head}***"


def _mask_stripe_id(obj_id: str | None) -> str:
    """A Stripe object id as a short one-way hash, e.g. `cus#1a2b3c4d5e`.

    Stable, so the same account can be followed from one weekly run to the
    next, and the operator can match a finding by hashing the ids they can
    already read in the database. One-way, so the public log never carries an
    id that works in the Stripe dashboard or API.
    """
    if not obj_id:
        return "(none)"
    prefix = obj_id.split("_", 1)[0] if "_" in obj_id else "id"
    return f"{prefix}#{hashlib.sha256(obj_id.encode()).hexdigest()[:10]}"


#: Stripe object ids that identify a customer or their billing. Free text
#: (an exception message quotes the id it failed on) is scrubbed with this.
_STRIPE_ID = re.compile(r"\b(?:cus|sub|pm|pi|ch)_[A-Za-z0-9]{6,}\b")


def _scrub(text: object) -> str:
    """`str(text)` with every Stripe object id in it hashed."""
    return _STRIPE_ID.sub(lambda m: _mask_stripe_id(m.group(0)), str(text))


def _price_to_tier(price_id: str) -> str | None:
    """Map a Stripe price id back to the tier it grants."""
    mapping = {
        settings.stripe_price_pro_monthly: "pro",
        settings.stripe_price_pro_annual: "pro",
        settings.stripe_price_premium_monthly: "premium",
        settings.stripe_price_premium_annual: "premium",
    }
    return mapping.get(price_id)


async def _subscriptions_for(customer_id: str) -> list[Any]:  # type: ignore[valid-type]
    import stripe

    subs = await asyncio.to_thread(
        stripe.Subscription.list, customer=customer_id, status="all", limit=100
    )
    return list(_f(subs, "data", []) or [])


async def _revenue() -> None:
    """Has any money ACTUALLY been collected?

    A subscription status of `active` is strong evidence but not proof — it is
    a status string, and this session has twice drawn a wrong conclusion from
    partial evidence. A PAID INVOICE with `amount_paid > 0` is the fact itself:
    Stripe issues one only when a charge succeeded.

    Trials invoice at $0, so amount_paid is what separates "someone entered a
    card" from "someone was charged".
    """
    import stripe

    logger.info("")
    logger.info("revenue (paid invoices, amount_paid > 0)")
    try:
        invoices = await asyncio.to_thread(stripe.Invoice.list, status="paid", limit=100)
    except Exception as exc:
        logger.error("  could not list invoices — %s", _scrub(exc))
        return

    data = _f(invoices, "data", []) or []
    rows = [i for i in data if int(_f(i, "amount_paid", 0) or 0) > 0]
    if not rows:
        logger.info(
            "  none. %d paid invoice(s) exist but every one is $0 — cards are "
            "on file and trials are running, but nobody has been charged yet.",
            len(data),
        )
        return

    total = 0
    for inv in rows:
        amt = int(_f(inv, "amount_paid", 0) or 0)
        total += amt
        created = _f(inv, "created", 0)
        when = (
            datetime.fromtimestamp(int(created), UTC).strftime("%Y-%m-%d")
            if created else "?"
        )
        logger.warning(
            "  %s  %s %s  %s",
            when,
            f"{amt / 100:.2f}",
            str(_f(inv, "currency", "?")).upper(),
            _mask_email(str(_f(inv, "customer_email", "") or "") or None),
        )
    logger.warning("  TOTAL COLLECTED: %.2f across %d invoice(s)", total / 100, len(rows))


async def _audit() -> None:
    import stripe

    stripe.api_key = settings.stripe_secret_key
    if not stripe.api_key:
        logger.error("STRIPE_SECRET_KEY is not set — cannot audit.")
        return
    logger.info(
        "mode: %s", "LIVE" if stripe.api_key.startswith("sk_live_") else "TEST"
    )

    async with session_scope() as s:
        users = (await s.execute(select(User))).scalars().all()
    logger.info("accounts: %d", len(users))
    logger.info("")

    findings: dict[str, list[str]] = defaultdict(list)
    now = datetime.now(UTC)
    emails_by_customer: dict[str, str] = {}
    # Live subscriptions already set to stop. NOT a "finding": nothing is
    # broken and there is nothing to reconcile. It is the single most important
    # fact about the business in this table, and this script reported "No
    # discrepancies" on 2026-09-03 while THREE OF FIVE customers were on their
    # way out — including the only one who has ever paid. Correct, and useless.
    churn: list[tuple[str, str, str, datetime | None]] = []

    for u in users:
        who = _mask_email(getattr(u, "email", None))
        local_tier = (getattr(u, "tier", "") or "free").lower()
        cust = getattr(u, "stripe_customer_id", None)
        cust_ref = _mask_stripe_id(cust)  # what the public log may carry
        is_admin = bool(getattr(u, "is_admin", False))
        # Hand-comped / lifetime accounts legitimately hold a paid tier with no
        # subscription. Treat them as explained rather than as findings.
        exempt = is_admin or bool(getattr(u, "is_lifetime", False))

        if not cust:
            if local_tier in PAID_TIERS and not exempt:
                trial_end = getattr(u, "trial_ends_at", None)
                if trial_end and trial_end.replace(tzinfo=UTC) < now:
                    findings["TRIAL_LAPSED"].append(
                        f"{who} tier={local_tier} trial ended {trial_end:%Y-%m-%d}, "
                        f"no customer"
                    )
                else:
                    findings["GRANTED_NOT_PAID"].append(
                        f"{who} tier={local_tier} (no stripe customer)"
                    )
            continue

        try:
            customer = await asyncio.to_thread(stripe.Customer.retrieve, cust)
        except Exception as exc:
            findings["ORPHAN_CUSTOMER"].append(f"{who} {cust_ref} — {_scrub(exc)}")
            continue
        if _f(customer, "deleted"):
            findings["ORPHAN_CUSTOMER"].append(f"{who} {cust_ref} — deleted in Stripe")
            continue

        cust_email = str(_f(customer, "email", "") or "")
        if cust_email:
            emails_by_customer[cust] = cust_email

        subs = await _subscriptions_for(cust)
        live = [s for s in subs if str(_f(s, "status", "")) in LIVE_STATUSES]
        statuses = sorted({str(_f(s, "status", "?")) for s in subs}) or ["none"]

        stripe_tier: str | None = None
        for sub in live:
            items = _f(_f(sub, "items"), "data", []) or []
            for it in items:
                pid = str(_f(_f(it, "price"), "id", ""))
                stripe_tier = _price_to_tier(pid) or stripe_tier

        for sub in live:
            if _f(sub, "cancel_at_period_end"):
                ends_ts = _f(sub, "cancel_at") or _f(sub, "current_period_end")
                if not ends_ts:
                    # API 2025-04-30.basil moved current_period_end onto the
                    # subscription ITEM. Same shape that caused #639.
                    items = _f(_f(sub, "items"), "data", []) or []
                    ends_ts = _f(items[0], "current_period_end") if items else None
                ends = (
                    datetime.fromtimestamp(int(ends_ts), UTC)
                    if isinstance(ends_ts, (int, float)) and not isinstance(ends_ts, bool)
                    else None
                )
                churn.append((who, str(_f(sub, "status", "?")), local_tier, ends))

        if any(str(_f(s, "status", "")) == "past_due" for s in live):
            findings["PAST_DUE"].append(f"{who} {cust_ref} — Stripe cannot collect")

        if live and local_tier not in PAID_TIERS:
            findings["PAID_NOT_GRANTED"].append(
                f"{who} {cust_ref} stripe={statuses} but local tier={local_tier}"
            )
        elif live and stripe_tier and stripe_tier != local_tier:
            findings["TIER_MISMATCH"].append(
                f"{who} local={local_tier} stripe={stripe_tier}"
            )
        elif not live and local_tier in PAID_TIERS and not exempt:
            findings["GRANTED_NOT_PAID"].append(
                f"{who} tier={local_tier} stripe_subs={statuses}"
            )

        logger.info(
            "  %-26s local=%-8s customer=%s subs=%s",
            who, local_tier, cust_ref, ",".join(statuses),
        )

    # Duplicate customers by email — a double-billing risk once both subscribe.
    by_email: dict[str, list[str]] = defaultdict(list)
    for cid, em in emails_by_customer.items():
        by_email[em.lower()].append(cid)
    for em, cids in by_email.items():
        if len(cids) > 1:
            findings["DUPLICATE_CUSTOMER"].append(
                f"{_mask_email(em)} -> {len(cids)} customers: "
                f"{', '.join(_mask_stripe_id(c) for c in cids)}"
            )

    logger.info("")
    logger.info("=" * 66)
    logger.info("CANCELLING — live subscriptions already set to stop")
    if churn:
        for who, status, tier_, ends in sorted(
            churn, key=lambda c: c[3] or datetime.max.replace(tzinfo=UTC)
        ):
            when = f"{ends:%Y-%m-%d}" if ends else "date unknown"
            days = f" ({(ends - now).days:+d}d)" if ends else ""
            logger.warning(
                "  %-26s %-8s %-9s access ends %s%s", who, tier_, status, when, days
            )
        logger.warning(
            "  %d of %d subscription(s) will not renew.",
            len(churn), sum(1 for u in users if getattr(u, "stripe_customer_id", None)),
        )
    else:
        logger.info("  none — every live subscription is set to renew.")
    logger.info("")
    logger.info("=" * 66)
    # Worst first: being charged without receiving the product outranks
    # everything else here.
    order = [
        "PAID_NOT_GRANTED",
        "PAST_DUE",
        "TIER_MISMATCH",
        "ORPHAN_CUSTOMER",
        "DUPLICATE_CUSTOMER",
        "TRIAL_LAPSED",
        "GRANTED_NOT_PAID",
    ]
    total = 0
    for key in order:
        rows = findings.get(key, [])
        total += len(rows)
        if not rows:
            logger.info("%-19s none", key)
            continue
        logger.warning("%-19s %d", key, len(rows))
        for r in rows:
            logger.warning("    %s", r)

    logger.info("")
    if total == 0:
        logger.info(
            "No discrepancies. Every account's local tier agrees with Stripe."
        )
    else:
        logger.warning(
            "%d finding(s). Nothing was changed — each fix moves money or "
            "changes entitlement, so it is a human decision.", total,
        )


async def _main() -> None:
    await _audit()
    await _revenue()


def main() -> None:
    """Entry point. An uncaught Stripe error's message can quote the id it
    failed on ("No such customer: 'cus_…'"), and Python would print that
    traceback raw into the public log. Scrub it; still exit non-zero so the
    Actions run goes red exactly as before."""
    try:
        asyncio.run(_main())
    except Exception:
        logger.error(_scrub(traceback.format_exc()))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
