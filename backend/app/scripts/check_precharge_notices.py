"""Regression check — nobody gets charged without being told first.

Two events carry every pre-charge notice Tapeline sends:

    customer.subscription.trial_will_end   the FIRST charge, when a trial converts
    invoice.upcoming                       every renewal after that, plus the
                                           card-expiry guard that rides on it

Both are silent by construction. If either stops arriving, the symptom is an
absence — no email goes out, no error is raised, and the first anyone hears of
it is a chargeback or a "what is this charge" reply. Nothing else in the
system notices, which is exactly why this exists.

WHY NOW. `invoice.upcoming` was subscribed on 2026-08-30 (#705) and had fired
ZERO times as of 2026-09-02, because no renewal had come due yet. The
card-expiry guard added in #711 hangs off the same event. So the entire
pre-charge path — the reminder, the disclosure, and the card warning — was
live but unexercised, and the first real renewals were days away. An untested
path that only runs when money moves is worth a standing alarm rather than a
one-off look.

THE TWO-SIDED READ is the point. Checking only our own logs cannot tell
"Stripe never sent it" from "Stripe sent it and we dropped it", and those have
opposite fixes. So each finding is graded against both sides:

    Stripe's event log       did Stripe EMIT the notice event?
    stripe_webhook_events    did WE receive and record it?

    emitted, not recorded  => our endpoint is dropping deliveries (signature,
                              500s, subscription list) — the #639 archetype
    not emitted            => Stripe is not sending them (billing settings,
                              subscription config, endpoint unsubscribed)

READ-ONLY. It creates nothing, writes nothing, charges nothing, and emails no
customer — the only outbound message is a founder alert.
`tests/test_precharge_notice_check.py` enforces that at the AST level.

Exit 0 when healthy, 1 when something needs attention, so a scheduler can act
on the code alone. No customer email is read or printed anywhere — these logs
are world-readable on this public repo, and Stripe ids are enough to act on.
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import stripe
from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.models import StripeWebhookEvent
from app.services.stripe_compat import stripe_field

settings = get_settings()

if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key

DAY = 86400

#: A renewal this far ahead SHOULD be inside Stripe's notice lead time. Stripe
#: sets that lead time in Billing settings and it is measured in days, so a
#: renewal still outside it is reported as INFO, never as a failure — the
#: alternative is an alarm that fires on every healthy subscription.
LOOKAHEAD_DAYS = int(os.environ.get("PRECHARGE_LOOKAHEAD_DAYS", "5"))

#: A renewal that already happened this recently MUST have been preceded by a
#: notice. This is the window that actually alarms.
#:
#: Capped by Stripe's own retention: the Events API keeps 30 days, so a
#: lookback beyond that would read "no event" for every old renewal and cry
#: wolf forever. Kept well inside it.
LOOKBACK_DAYS = min(int(os.environ.get("PRECHARGE_LOOKBACK_DAYS", "10")), 21)

#: Statuses where a charge is still expected to happen.
LIVE_STATUSES = {"active", "trialing", "past_due"}

NOTICE_EVENTS = ("invoice.upcoming", "customer.subscription.trial_will_end")


def _period_end(sub: object) -> int | None:
    """Unix ts of the next charge.

    On API 2026-08-26.dahlia `current_period_end` lives on the subscription
    ITEM, not on the subscription — reading only the top level returns None for
    every live subscription and the check silently inspects nothing. Both are
    read, item first.
    """
    items = stripe_field(stripe_field(sub, "items"), "data") or []
    for it in items:
        ts = stripe_field(it, "current_period_end")
        if isinstance(ts, int):
            return ts
    ts = stripe_field(sub, "current_period_end")
    return ts if isinstance(ts, int) else None


def _customer_of(event: object) -> str | None:
    """The customer id an event concerns, across both notice shapes."""
    obj = stripe_field(stripe_field(event, "data"), "object")
    cust = stripe_field(obj, "customer")
    return cust if isinstance(cust, str) else None


async def _emitted_notices() -> tuple[dict[str, list[dict]], dict[str, int]]:
    """Every notice event Stripe emitted inside the retention window.

    Returns (by_customer, totals_by_type).
    """
    since = int((datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS + 2)).timestamp())
    by_customer: dict[str, list[dict]] = {}
    totals: dict[str, int] = {}
    for evt_type in NOTICE_EVENTS:
        seen = 0
        events = await asyncio.to_thread(
            stripe.Event.list, type=evt_type, created={"gte": since}, limit=100
        )
        for e in stripe_field(events, "data") or []:
            seen += 1
            cust = _customer_of(e)
            if cust:
                by_customer.setdefault(cust, []).append(
                    {
                        "id": stripe_field(e, "id"),
                        "type": evt_type,
                        "created": stripe_field(e, "created"),
                    }
                )
        totals[evt_type] = seen
    return by_customer, totals


async def _recorded_event_ids() -> set[str]:
    """Notice events WE processed — the id-dedup table the handler writes."""
    async with session_scope() as s:
        rows = await s.execute(
            select(StripeWebhookEvent.id).where(
                StripeWebhookEvent.event_type.in_(NOTICE_EVENTS)
            )
        )
        return {r for (r,) in rows.all()}


async def gather() -> dict:
    now = int(datetime.now(UTC).timestamp())
    subs = await asyncio.to_thread(
        stripe.Subscription.list, status="all", limit=100
    )
    emitted, totals = await _emitted_notices()
    recorded = await _recorded_event_ids()

    missed: list[dict] = []      # charged (or about to be) with no notice
    dropped: list[dict] = []     # Stripe emitted, we never recorded
    pending: list[dict] = []     # renewal near, notice not due yet — INFO
    healthy: list[dict] = []

    for sub in stripe_field(subs, "data") or []:
        status = stripe_field(sub, "status")
        if status not in LIVE_STATUSES:
            continue
        if stripe_field(sub, "cancel_at_period_end"):
            # No charge is coming, so no notice is owed.
            continue
        sub_id = stripe_field(sub, "id")
        cust = stripe_field(sub, "customer")
        end = _period_end(sub)
        if not end:
            continue

        days_out = (end - now) / DAY
        if not (-LOOKBACK_DAYS <= days_out <= LOOKAHEAD_DAYS):
            continue

        # Notices that landed in the run-up to THIS charge.
        window_start = end - (LOOKAHEAD_DAYS + 2) * DAY
        notices = [
            n for n in emitted.get(cust or "", [])
            if isinstance(n["created"], int) and window_start <= n["created"] <= end + DAY
        ]
        row = {
            "sub": sub_id,
            "customer": cust,
            "status": status,
            "renews": datetime.fromtimestamp(end, UTC).strftime("%Y-%m-%d"),
            "days_out": round(days_out, 1),
            "notices": [n["type"] for n in notices],
        }

        unrecorded = [n for n in notices if n["id"] not in recorded]
        if notices and unrecorded:
            dropped.append({**row, "unrecorded": [n["id"] for n in unrecorded]})
        elif notices:
            healthy.append(row)
        elif days_out < 0:
            missed.append(row)
        else:
            pending.append(row)

    return {
        "totals": totals,
        "recorded_count": len(recorded),
        "missed": missed,
        "dropped": dropped,
        "pending": pending,
        "healthy": healthy,
    }


def render(d: dict) -> tuple[str, str, bool]:
    """(subject, text, alert_worthy)."""
    lines: list[str] = []
    alert = False

    if d["missed"]:
        alert = True
        lines.append("MISSED — charged with no pre-charge notice:")
        for r in d["missed"]:
            lines.append(
                f"  {r['sub']} {r['customer']} status={r['status']} "
                f"renewed {r['renews']} ({abs(r['days_out'])}d ago) — NO notice event"
            )
        lines.append("")

    if d["dropped"]:
        alert = True
        lines.append("DROPPED — Stripe emitted the notice, we never recorded it:")
        for r in d["dropped"]:
            lines.append(
                f"  {r['sub']} {r['customer']} renews {r['renews']} "
                f"emitted={r['notices']} unrecorded={r['unrecorded']}"
            )
        lines.append("  => the endpoint is dropping deliveries: check signature,")
        lines.append("     500s in the handler, and the endpoint's enabled_events.")
        lines.append("")

    if d["pending"]:
        lines.append("PENDING — renewal near, notice not emitted yet (informational):")
        for r in d["pending"]:
            lines.append(
                f"  {r['sub']} {r['customer']} renews {r['renews']} "
                f"(in {r['days_out']}d)"
            )
        lines.append("")

    if d["healthy"]:
        lines.append("OK — notice sent and recorded:")
        for r in d["healthy"]:
            lines.append(
                f"  {r['sub']} {r['customer']} renews {r['renews']} {r['notices']}"
            )
        lines.append("")

    t = d["totals"]
    lines.append(
        "Stripe emitted in window: "
        + ", ".join(f"{k}={v}" for k, v in t.items())
        + f" | recorded locally (all time): {d['recorded_count']}"
    )

    if not any((d["missed"], d["dropped"], d["pending"], d["healthy"])):
        lines.append(
            "No subscription has a charge inside the checked window "
            f"(-{LOOKBACK_DAYS}d .. +{LOOKAHEAD_DAYS}d). Nothing to verify."
        )

    if alert:
        subject = (
            f"Tapeline ALERT — pre-charge notice gap "
            f"({len(d['missed'])} missed, {len(d['dropped'])} dropped)"
        )
    else:
        subject = "Tapeline — pre-charge notices healthy"
    return subject, "\n".join(lines), alert


async def main() -> int:
    if not settings.stripe_secret_key:
        print("precharge.skipped reason=no_stripe_key")
        return 0

    d = await gather()
    subject, text, alert = render(d)
    print(subject)
    print(text)

    if alert:
        from app.services.telegram import deliver_founder_alert

        await deliver_founder_alert(subject=subject, text=text)
        print("precharge.alert_delivered")
    return 1 if alert else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
