"""One-time catch-up send for accounts the lifecycle drips can never reach.

WHY THIS SCRIPT EXISTS
----------------------
Verified against production on 2026-08-31: **not one email had ever been sent
to any of the 30 accounts.** Zero drip tokens, despite 20 lifecycle programs
being wired to the worker and running daily.

The cause is not a bug. Every drip stage has an age window bounded on BOTH
ends — `run_free_trial_invite_drip` fires at 3–6 days after signup, then again
at 12–16 days — and the docstring says why: an unbounded window means a worker
that was down for a fortnight wakes up and mails a backlog all at once. Correct
for a forward-flowing funnel. But every account that existed before that code
shipped aged out of every window permanently.

So this is a deliberate one-shot, run by hand, that reaches those accounts
once and then can never reach them again.

TWO AUDIENCES, BECAUSE THE TRUTH DIFFERS
----------------------------------------
This is the part that matters most, and it is why this is not one query:

  A. **never_trialled** — free, no Stripe customer, and `_trial_ineligible_reason`
     returns None. These accounts CAN start the card-required 14-day trial, so
     the trial-invite copy is true for them.

  B. **legacy_trial** — free accounts carrying a LEGACY `trial_ends_at` from the
     pre-#536 auto-granted no-card trial. `billing._trial_ineligible_reason`
     returns "already_trialed" for these (one trial per account, forever), so
     **inviting them to start a trial would be false advertising** on a
     financial product. They get copy that offers what they can actually do:
     subscribe directly.

Eligibility is decided by importing the app's own
`billing._trial_ineligible_reason` rather than reimplementing the rule here.
Two copies of a truth condition drift, and the drifted copy is the one that
writes a false promise into an email.

SAFETY
------
  * DRY RUN BY DEFAULT. `--send` is required to transmit anything.
  * Every send stamps a `drip_state` token, so a second run is a no-op even
    with `--send`. The stamp is written only on a real, non-skipped send.
  * Respects `EmailPref.TRIAL_DRIP`, the undeliverable suppression list, and
    the shared lifecycle governor — a recipient who received another lifecycle
    email recently is skipped, not stacked on.
  * `--limit` caps the blast radius of a first live run.
  * Skips accounts young enough that the normal drip will reach them, so
    nobody gets both this and the automated stage.

Usage:
    python -m app.scripts.catchup_send                  # dry run, shows everything
    python -m app.scripts.catchup_send --limit 5 --send # send to 5, for real
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

logger = logging.getLogger(__name__)

#: Written to User.drip_state on a successful send. Presence of the key is the
#: idempotency guarantee — this script will never mail the same account twice.
CATCHUP_TOKEN = "catchup_2026_08"

#: Accounts younger than this are left alone: `run_free_trial_invite_drip`
#: still has them inside (or ahead of) its 3–6 and 12–16 day windows, and
#: double-messaging is the documented failure mode here — the three most
#: engaged early users received six to ten automated touches each and none
#: converted.
FORWARD_FLOW_GRACE_DAYS = 20


def _drip_state(user) -> dict:
    raw = user.drip_state
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {}
    return raw if isinstance(raw, dict) else {}


async def collect(session, *, limit: int | None = None) -> dict[str, list]:
    """Resolve the two audiences. Read-only: no writes, no sends."""
    from app.models import User
    from app.routers.billing import _trial_ineligible_reason
    from app.services.email_prefs import EmailPref, wants

    cutoff = datetime.now(UTC) - timedelta(days=FORWARD_FLOW_GRACE_DAYS)

    rows = (
        await session.execute(
            select(User).where(
                User.tier == "free",
                User.stripe_customer_id.is_(None),
                User.created_at < cutoff,
            )
        )
    ).scalars().all()

    buckets: dict[str, list] = {"never_trialled": [], "legacy_trial": [], "skipped": []}

    for u in rows:
        state = _drip_state(u)
        if CATCHUP_TOKEN in state:
            buckets["skipped"].append((u, "already_caught_up"))
            continue
        if getattr(u, "email_undeliverable_at", None) is not None:
            buckets["skipped"].append((u, "undeliverable"))
            continue
        if not wants(u.email_prefs, EmailPref.TRIAL_DRIP):
            buckets["skipped"].append((u, "opted_out_of_trial_drip"))
            continue

        reason = _trial_ineligible_reason(u)
        if reason is None:
            buckets["never_trialled"].append(u)
        elif reason == "already_trialed":
            buckets["legacy_trial"].append(u)
        else:
            # lifetime / has_billing_account / already_paid_tier — not a
            # conversion target, and the copy would be wrong for all three.
            buckets["skipped"].append((u, reason))

    if limit is not None:
        for key in ("never_trialled", "legacy_trial"):
            buckets[key] = buckets[key][:limit]
    return buckets


def _render(user, bucket: str) -> tuple[str, str]:
    """(subject, html) for one recipient. Reuses the shipped, lint-clean copy."""
    from app.services.email import (
        render_free_tier_changelog_email,
        render_free_trial_invite_email,
    )
    from app.services.tier import PROMO_OPEN_ACCESS_UNTIL, free_open_access

    name = user.name or "there"
    if bucket == "never_trialled":
        html = render_free_trial_invite_email(
            name,
            open_access=free_open_access(),
            open_access_until=f"{PROMO_OPEN_ACCESS_UNTIL:%B} {PROMO_OPEN_ACCESS_UNTIL.day}",
        )
        return "What else your Tapeline account can do", html

    # legacy_trial — a trial is NOT available to these accounts, so the copy
    # must not offer one. The changelog email describes what has shipped and
    # points at the public record; it promises nothing they cannot have.
    return "What's changed in Tapeline", render_free_tier_changelog_email(name)


async def run(*, send: bool, limit: int | None) -> dict:
    from app.db import session_scope
    from app.services.email import send_email
    from app.services.lifecycle import worker_governor

    counts = {"sent": 0, "would_send": 0, "skipped": 0, "failed": 0}

    async with session_scope() as session:
        buckets = await collect(session, limit=limit)

        print(f"\n{'SENDING' if send else 'DRY RUN — nothing will be sent'}")
        print(f"grace: accounts younger than {FORWARD_FLOW_GRACE_DAYS}d left to the drip\n")

        counts["skipped"] = len(buckets["skipped"])
        if buckets["skipped"]:
            tally: dict[str, int] = {}
            for _u, reason in buckets["skipped"]:
                tally[reason] = tally.get(reason, 0) + 1
            print("skipped:")
            for reason, n in sorted(tally.items(), key=lambda x: -x[1]):
                print(f"  {reason}: {n}")
            print()

        governor = worker_governor()

        for bucket in ("never_trialled", "legacy_trial"):
            users = buckets[bucket]
            if not users:
                continue
            offer = (
                "card-required 14-day trial"
                if bucket == "never_trialled"
                else "direct subscription (already trialled — cannot re-trial)"
            )
            print(f"{bucket} — {len(users)} recipient(s); offer: {offer}")

            for u in users:
                age = (datetime.now(UTC) - u.created_at).days if u.created_at else "?"
                subject, html = _render(u, bucket)

                if not send:
                    counts["would_send"] += 1
                    print(f"  WOULD SEND  {u.email:<38} age={age}d  subj={subject!r}")
                    continue

                if not governor.allows(u):
                    counts["skipped"] += 1
                    print(f"  GOVERNED    {u.email:<38} (recent lifecycle email)")
                    continue

                try:
                    res = await send_email(
                        to=u.email,
                        subject=subject,
                        html=html,
                        persona="sales",
                        unsubscribe_user_id=u.id,
                        unsubscribe_category="trial_drip",
                    )
                except Exception:
                    counts["failed"] += 1
                    logger.exception("catchup.send_failed user=%s", u.id)
                    print(f"  FAILED      {u.email}")
                    continue

                if res.get("skipped"):
                    counts["skipped"] += 1
                    print(f"  SKIPPED     {u.email:<38} ({res.get('reason')})")
                    continue

                # Stamp only after a real send, so a skipped attempt retries.
                state = _drip_state(u)
                state[CATCHUP_TOKEN] = datetime.now(UTC).isoformat()
                u.drip_state = state
                governor.record(u)
                counts["sent"] += 1
                print(f"  SENT        {u.email:<38} age={age}d")

            print()

        if send:
            await session.commit()

    print(f"result: {counts}\n")
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--send", action="store_true",
        help="actually transmit. Without this the script only reports.",
    )
    ap.add_argument(
        "--limit", type=int, default=None,
        help="cap recipients per audience — use on a first live run.",
    )
    args = ap.parse_args()

    # psycopg's async mode cannot run on Windows' default ProactorEventLoop.
    # The worker runs on Linux so this never bites in production, but this
    # script is meant to be run by hand from the founder's Windows machine.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run(send=args.send, limit=args.limit))


if __name__ == "__main__":
    main()
