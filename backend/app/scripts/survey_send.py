"""Send the September 2026 customer survey.

Founder-instructed 2026-09-08: "send my customers all a survey."

WHAT THIS SENDS AND WHY IT CONTAINS NO OFFER
--------------------------------------------
A four-item survey invitation. No price, no offer, no upgrade ask, no deadline,
no incentive. That is not modesty — it is the basis on which the message is
lawful to send at all. The Spam Act 2003 consent basis here is an existing
account relationship plus a message that promotes nothing (see
`docs/growth/CUSTOMER_SURVEY_2026_09.md` §7.1). Put a price in it and that
argument collapses.

AUDIENCE, AND WHY IT IS SMALLER THAN THE ACCOUNT COUNT
------------------------------------------------------
Excluded, in this order, each for a stated reason:

  * `is_admin` and the internal addresses — the founder's own two accounts and
    an external contractor. Not customers.
  * `email_undeliverable_at` — a bounce or a spam complaint already on record.
  * `re_sunset` — the terminal token from the re-engagement series. These
    accounts received two touches and stayed dormant, and
    `services/lifecycle.LIFECYCLE_SUPPRESSED_TOKENS` suppresses them from every
    non-transactional send. A survey is non-transactional. Overriding the
    governor for a 23-person list would risk the deliverability of the digest
    and the trial drip for the accounts that do pay. `--include-sunset` exists
    for a deliberate founder override and is not the default.
  * per-category opt-out via `wants(u, EmailPref.RE_ENGAGEMENT)` — a survey is
    re-engagement, not a trial drip, so that is the honest category to gate on.
    NOTE this gate was decorative in every previous broadcast script (both
    passed the prefs int rather than the User, so it returned True for
    everyone); it was fixed in #782 and THIS is the first send where it
    actually fires.
  * the survey token, so a second run cannot double-send.

DELIBERATELY NOT DEDUPLICATED BY PERSON
---------------------------------------
`waadrabeemm@` and `waadrabeema@` registered 36 seconds apart and are almost
certainly one human. The script does not try to guess that. Mailing one address
twice is a worse failure than mailing two addresses that happen to share an
owner, and a heuristic that collapses similar addresses would eventually eat
two colleagues at the same company.

SAFETY
------
  * DRY RUN BY DEFAULT. `--send` is required to transmit anything.
  * `--only <email>` sends to exactly one address — use it for a self-test
    before any customer sees this.
  * `--limit` caps a first live run.
  * Refuses to send unless `APP_URL` is a public https URL. The survey link is
    built from it, this script is run by hand against the PRODUCTION database
    from a machine whose APP_URL is `localhost:3000`, and a dry run is exactly
    where a wrong-but-plausible link looks fine. Learned from the free-month
    send, which rendered a localhost checkout link for 26 customers.
  * Honours the shared lifecycle frequency governor.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from sqlalchemy import select

logger = logging.getLogger(__name__)

SURVEY_TOKEN = "survey_2026_09"

#: Accounts that are not customers. The founder's own two and the external ads
#: contractor. Kept as an explicit list rather than a domain rule because
#: `@tapeline.io` alone would miss the personal gmail, and a "looks internal"
#: heuristic on a 23-person list is more likely to drop a real customer than to
#: catch anything.
INTERNAL_ADDRESSES = frozenset({
    "owner@tapeline.io",
    "cpiyatilaka@gmail.com",
    "zanek@hackd.tech",
})

#: The terminal re-engagement token. Duplicated from services/lifecycle so the
#: audience rule is readable in one place; the assertion in `collect` keeps them
#: from drifting apart.
SUNSET_TOKEN = "re_sunset"


def _tokens(user) -> set[str]:
    """Parse `User.drip_state` — a COMMA-SEPARATED TOKEN STRING, not JSON.

    Same helper and the same reason as `free_month_offer._tokens`: an audit that
    json.loads()'d this column concluded no email had ever been sent, and
    assigning a dict to it raises at COMMIT, i.e. after the mail is already
    delivered.
    """
    raw = (user.drip_state or "").strip()
    return {t for t in raw.split(",") if t} if raw else set()


def _add_token(user, token: str) -> None:
    user.drip_state = ",".join(sorted(_tokens(user) | {token}))


async def collect(
    session,
    *,
    limit: int | None = None,
    only: str | None = None,
    include_sunset: bool = False,
) -> tuple[list, list]:
    """(recipients, skipped) — read-only."""
    from app.models import User
    from app.services.email_prefs import EmailPref, wants
    from app.services.lifecycle import RE_SUNSET_TOKEN

    # Guard against the constant above drifting from the one that actually
    # drives suppression.
    assert SUNSET_TOKEN == RE_SUNSET_TOKEN, (
        f"sunset token drifted: {SUNSET_TOKEN!r} != {RE_SUNSET_TOKEN!r}"
    )

    stmt = select(User)
    if only:
        stmt = stmt.where(User.email == only)
    rows = (await session.execute(stmt)).scalars().all()

    recipients, skipped = [], []
    for u in rows:
        email = (u.email or "").lower()
        if not email:
            skipped.append((u, "no_email"))
        elif getattr(u, "is_admin", False):
            skipped.append((u, "admin"))
        elif email in INTERNAL_ADDRESSES:
            skipped.append((u, "internal"))
        elif getattr(u, "email_undeliverable_at", None) is not None:
            skipped.append((u, "undeliverable"))
        elif SURVEY_TOKEN in _tokens(u):
            skipped.append((u, "already_surveyed"))
        elif SUNSET_TOKEN in _tokens(u) and not include_sunset:
            skipped.append((u, "sunset"))
        elif not wants(u, EmailPref.RE_ENGAGEMENT):
            skipped.append((u, "opted_out"))
        else:
            recipients.append(u)

    if limit is not None:
        recipients = recipients[:limit]
    return recipients, skipped


async def run(
    *,
    send: bool,
    limit: int | None,
    only: str | None = None,
    include_sunset: bool = False,
) -> dict:
    from app.config import get_settings
    from app.db import session_scope
    from app.services.email import render_customer_survey_email, send_email
    from app.services.lifecycle import worker_governor

    settings = get_settings()
    base = (settings.app_url or "https://tapeline.io").rstrip("/")
    survey_url = f"{base}/survey"

    # See the module docstring: the dry run is where a localhost link looks
    # fine, so the check belongs on the send path.
    if send and not base.startswith("https://"):
        raise SystemExit(
            f"refusing to send: survey link is {base!r}, which is not a public "
            f"https URL. Set APP_URL=https://tapeline.io for this run — "
            f"otherwise every recipient gets a link they cannot open."
        )

    counts = {"sent": 0, "would_send": 0, "skipped": 0, "failed": 0}

    async with session_scope() as session:
        recipients, skipped = await collect(
            session, limit=limit, only=only, include_sunset=include_sunset,
        )
        counts["skipped"] = len(skipped)

        print(f"\n{'SENDING' if send else 'DRY RUN — nothing will be sent'}")
        print(f"link: {survey_url}")
        if include_sunset:
            print("WARNING: --include-sunset is on; suppressed dormant accounts "
                  "are in the audience.")
        print()

        if skipped:
            tally: dict[str, int] = {}
            for _u, reason in skipped:
                tally[reason] = tally.get(reason, 0) + 1
            print("skipped: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
            print()

        print(f"recipients: {len(recipients)}")
        governor = worker_governor()

        for u in recipients:
            if not send:
                counts["would_send"] += 1
                print(f"  WOULD SEND  {u.email:<40} tier={u.tier}")
                continue

            if not governor.allows(u):
                counts["skipped"] += 1
                print(f"  GOVERNED    {u.email}")
                continue

            try:
                res = await send_email(
                    to=u.email,
                    subject="Tapeline — four questions",
                    html=render_customer_survey_email(
                        u.name or "there", survey_url=survey_url,
                    ),
                    persona="sales",
                    unsubscribe_user_id=u.id,
                    unsubscribe_category="re_engagement",
                )
            except Exception:
                counts["failed"] += 1
                logger.exception("survey.send_failed user=%s", u.id)
                print(f"  FAILED      {u.email}")
                continue

            if res.get("skipped"):
                counts["skipped"] += 1
                print(f"  SKIPPED     {u.email} ({res.get('reason')})")
                continue

            _add_token(u, SURVEY_TOKEN)
            governor.record(u)
            counts["sent"] += 1
            print(f"  SENT        {u.email:<40} tier={u.tier}")

        if send:
            await session.commit()

    print(f"\nresult: {counts}\n")
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--send", action="store_true", help="actually transmit")
    ap.add_argument("--limit", type=int, default=None, help="cap recipients")
    ap.add_argument(
        "--only", default=None,
        help="restrict to ONE email address — use for the first live self-test.",
    )
    ap.add_argument(
        "--include-sunset", action="store_true",
        help="override the re_sunset suppression. Founder decision only.",
    )
    args = ap.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run(
        send=args.send,
        limit=args.limit,
        only=args.only,
        include_sunset=args.include_sunset,
    ))


if __name__ == "__main__":
    main()
