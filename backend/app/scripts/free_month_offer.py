"""Grant + announce the one-month-free Premium offer to card-less accounts.

Founder-authorised 2026-08-31: "everyone that's not a card they going one
month free premium once they enter their card details."

ORDER OF OPERATIONS IS THE WHOLE POINT
--------------------------------------
The credit is granted BEFORE the email is sent, in that order, per account.
An email promising a free month to someone who has no credit on their row is
a false promise on a financial product — so the grant is what makes the copy
true, and it must not be possible to send without it. If the grant fails, the
send for that account is skipped.

HOW THE OFFER IS HONOURED (no new billing code)
-----------------------------------------------
`users.referral_credit_months` is already read at checkout by
`routers/billing.py`, which mints a one-shot 100%-off Stripe coupon for that
many months via `services/billing.create_checkout_session`. The credit is then
consumed in `routers/webhooks.py` on `customer.subscription.created`, so an
abandoned checkout cannot burn it. Granting 1 makes "a month on us" redeemable
through the exact path that has already taken a real payment.

WHY THE LINK POINTS AT DIRECT SUBSCRIBE, NOT THE TRIAL
------------------------------------------------------
`referral_credit_months` is passed to checkout regardless of `start_trial`, so
a never-trialled account clicking the trial path would get 14 trial days AND a
100%-off month — roughly 44 free days, which is not what was authorised and
not what the email says. Pointing every recipient at `/app/billing` (direct
subscribe) makes the copy exactly true for both audiences: one month, free.

AUDIENCE
--------
Accounts with no `stripe_customer_id`, excluding admins, the undeliverable
list, and anyone who has opted out of the trial-drip category. Both the
never-trialled and the legacy-trial cohorts are included — unlike the trial
invite, this offer is a coupon on a subscription, so `already_trialed` is not
a bar to it.

SAFETY
------
  * DRY RUN BY DEFAULT; `--send` is required to write or transmit anything.
  * Idempotent twice over: a `drip_state` token per account, and the grant is
    skipped for anyone who already holds credit.
  * `--limit` caps a first live run.
  * Honours the shared lifecycle governor and the undeliverable list.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from sqlalchemy import select

logger = logging.getLogger(__name__)

OFFER_TOKEN = "free_month_2026_08"
CREDIT_MONTHS = 1


def _tokens(user) -> set[str]:
    """Parse `User.drip_state`, which is a COMMA-SEPARATED TOKEN STRING.

    Not JSON. `models/user.py` declares it `String(255)` and every existing
    drip writes it as `",".join(sorted(tokens))` — e.g.
    `"11,13,3,7,act_alert,expired,post3,weekly_2026W36"`.

    This mattered twice, both times badly:

      * An audit that json.loads()'d this column got {} for every row and
        concluded no email had ever been sent. In fact 25 of 31 accounts carry
        tokens; the drips have been running for weeks.
      * Assigning a dict here raises `cannot adapt type 'dict'` at COMMIT —
        after the email has already gone out. That happened on the first live
        self-test: the mail was delivered and the credit grant rolled back,
        leaving a promise with nothing behind it.
    """
    raw = (user.drip_state or "").strip()
    return {t for t in raw.split(",") if t} if raw else set()


def _add_token(user, token: str) -> None:
    """Append a token, preserving the sorted comma-joined format."""
    user.drip_state = ",".join(sorted(_tokens(user) | {token}))


async def collect(
    session, *, limit: int | None = None, only: str | None = None,
) -> tuple[list, list]:
    """(recipients, skipped) — read-only.

    `only` restricts to a single address. That exists so the first LIVE run can
    go to the founder's own inbox and be read end-to-end — rendering, the
    unsubscribe link, and whether the checkout link actually applies the
    coupon — before 25 customers see it. `--limit` cannot do this: it takes the
    first N rows, which are real customers.
    """
    from app.models import User
    from app.services.email_prefs import EmailPref, wants

    stmt = select(User).where(User.stripe_customer_id.is_(None))
    if only:
        stmt = stmt.where(User.email == only)
    rows = (await session.execute(stmt)).scalars().all()

    recipients, skipped = [], []
    for u in rows:
        if getattr(u, "is_admin", False):
            skipped.append((u, "admin"))
        elif getattr(u, "email_undeliverable_at", None) is not None:
            skipped.append((u, "undeliverable"))
        elif OFFER_TOKEN in _tokens(u):
            skipped.append((u, "already_offered"))
        elif not wants(u.email_prefs, EmailPref.TRIAL_DRIP):
            skipped.append((u, "opted_out"))
        else:
            recipients.append(u)

    if limit is not None:
        recipients = recipients[:limit]
    return recipients, skipped


async def run(*, send: bool, limit: int | None, only: str | None = None) -> dict:
    from app.config import get_settings
    from app.db import session_scope
    from app.services.email import render_free_month_offer_email, send_email
    from app.services.lifecycle import worker_governor

    settings = get_settings()
    base = (settings.app_url or "https://tapeline.io").rstrip("/")
    checkout_url = f"{base}/app/billing?offer=freemonth"

    # THE GUARD THAT SAVED THIS SEND. This script is run by hand from the
    # founder's machine against the PRODUCTION database, but `app_url` comes
    # from the local environment — which is http://localhost:3000 here. The
    # first dry run duly rendered a localhost link. Twenty-six customers would
    # have received an offer pointing at a machine only the founder can reach.
    #
    # A dry run cannot catch this by itself, because a dry run is exactly where
    # a wrong-but-plausible URL looks fine. So the check is on the SEND path.
    if send and not base.startswith("https://"):
        raise SystemExit(
            f"refusing to send: checkout link is {base!r}, which is not a public "
            f"https URL. Set APP_URL=https://tapeline.io for this run — "
            f"otherwise every recipient gets a link they cannot open."
        )

    counts = {"granted": 0, "sent": 0, "would_send": 0, "skipped": 0, "failed": 0}

    async with session_scope() as session:
        recipients, skipped = await collect(session, limit=limit, only=only)
        counts["skipped"] = len(skipped)

        print(f"\n{'SENDING' if send else 'DRY RUN — nothing granted, nothing sent'}")
        print(f"offer: {CREDIT_MONTHS} month(s) of Premium free at checkout")
        print(f"link:  {checkout_url}\n")

        if skipped:
            tally: dict[str, int] = {}
            for _u, reason in skipped:
                tally[reason] = tally.get(reason, 0) + 1
            print("skipped: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
            print()

        print(f"recipients: {len(recipients)}")
        governor = worker_governor()

        for u in recipients:
            existing = u.referral_credit_months or 0

            if not send:
                counts["would_send"] += 1
                print(
                    f"  WOULD GRANT+SEND  {u.email:<38} "
                    f"tier={u.tier:<7} credit {existing}->{max(existing, CREDIT_MONTHS)}"
                )
                continue

            if not governor.allows(u):
                counts["skipped"] += 1
                print(f"  GOVERNED          {u.email}")
                continue

            # GRANT FIRST — the email is only true once the credit exists.
            if existing < CREDIT_MONTHS:
                u.referral_credit_months = CREDIT_MONTHS
                counts["granted"] += 1
            await session.flush()

            try:
                res = await send_email(
                    to=u.email,
                    subject="A month of Premium, on us",
                    html=render_free_month_offer_email(
                        u.name or "there", checkout_url=checkout_url,
                    ),
                    persona="sales",
                    unsubscribe_user_id=u.id,
                    unsubscribe_category="trial_drip",
                )
            except Exception:
                counts["failed"] += 1
                logger.exception("free_month.send_failed user=%s", u.id)
                print(f"  FAILED            {u.email} (credit kept)")
                continue

            if res.get("skipped"):
                counts["skipped"] += 1
                print(f"  SKIPPED           {u.email} ({res.get('reason')})")
                continue

            _add_token(u, OFFER_TOKEN)
            governor.record(u)
            counts["sent"] += 1
            print(f"  GRANTED+SENT      {u.email:<38} tier={u.tier}")

        if send:
            await session.commit()

    print(f"\nresult: {counts}\n")
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--send", action="store_true", help="grant credits and transmit")
    ap.add_argument("--limit", type=int, default=None, help="cap recipients")
    ap.add_argument(
        "--only", default=None,
        help="restrict to ONE email address — use for the first live self-test.",
    )
    args = ap.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run(send=args.send, limit=args.limit, only=args.only))


if __name__ == "__main__":
    main()
