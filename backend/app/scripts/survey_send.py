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

TWO AUDIENCES
-------------
`--audience accounts` (default) mails rows in `users`. `--audience newsletter`
mails confirmed `newsletter_subscribers` who have NO account -- 14 of the 46
reachable addresses, and a population the account survey previously ignored
entirely. `--audience all` does both.

They get DIFFERENT copy and a different Q1 option list. Every account-holder
option presupposes a signup ("I signed up but haven't really used it"), so
sending that list to someone who never made an account asks a question with no
true answer. The newsletter variant also uses the newsletter list's own
unsubscribe token and headers, because those people are not `users` rows and
the shared user-keyed unsubscribe cannot address them.

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

from app.services.dblock import LOCK_SURVEY_REMINDER, one_machine_at_a_time

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


async def collect_newsletter(
    session, *, limit: int | None = None, only: str | None = None,
) -> tuple[list, list]:
    """(recipients, skipped) -- confirmed subscribers with NO user account.

    Anyone who also has an account is excluded here and reached through the
    account audience instead, so nobody is mailed twice. The join is on
    lowercased email because the two tables are populated by different code
    paths and neither normalises the other's casing.
    """
    from app.models import User
    from app.models.newsletter import NewsletterSubscriber

    stmt = select(NewsletterSubscriber)
    if only:
        stmt = stmt.where(NewsletterSubscriber.email == only)
    rows = (await session.execute(stmt)).scalars().all()

    accounts = {
        (e or "").lower()
        for e in (await session.execute(select(User.email))).scalars().all()
    }

    recipients, skipped = [], []
    for sub in rows:
        email = (sub.email or "").lower()
        if not email:
            skipped.append((sub, "no_email"))
        elif sub.status != "confirmed":
            skipped.append((sub, "status_" + str(sub.status)))
        elif email in accounts:
            skipped.append((sub, "has_account"))
        elif not sub.unsubscribe_token:
            # No token means no working opt-out for this list, and shipping a
            # non-transactional email without one is the thing the Spam Act is
            # actually about. Skip rather than send.
            skipped.append((sub, "no_unsubscribe_token"))
        else:
            recipients.append(sub)

    if limit is not None:
        recipients = recipients[:limit]
    return recipients, skipped


async def run_newsletter(
    *, send: bool, limit: int | None, only: str | None = None,
) -> dict:
    from app.config import get_settings
    from app.db import session_scope
    from app.services.email import render_customer_survey_email, send_email
    from app.services.newsletter import _list_unsubscribe_headers, _unsubscribe_url

    settings = get_settings()
    base = (settings.app_url or "https://tapeline.io").rstrip("/")
    survey_url = base + "/survey"
    if send and not base.startswith("https://"):
        raise SystemExit(
            "refusing to send: survey link is " + repr(base)
            + ", which is not a public https URL."
        )

    counts = {"sent": 0, "would_send": 0, "skipped": 0, "failed": 0}

    async with session_scope() as session:
        recipients, skipped = await collect_newsletter(session, limit=limit, only=only)
        counts["skipped"] = len(skipped)

        print("\n--- newsletter subscribers (no account) ---")
        if skipped:
            tally: dict[str, int] = {}
            for _r, reason in skipped:
                tally[reason] = tally.get(reason, 0) + 1
            print("skipped: " + ", ".join(k + "=" + str(v) for k, v in sorted(tally.items())))
        print("recipients: " + str(len(recipients)))

        for sub in recipients:
            if not send:
                counts["would_send"] += 1
                print("  WOULD SEND  " + sub.email)
                continue

            # The shared footer placeholder is only resolved for `users` rows,
            # so a newsletter recipient would otherwise get NO visible opt-out.
            # Append this list's own link, and ship its List-Unsubscribe header.
            unsub = _unsubscribe_url(sub.unsubscribe_token)
            html = render_customer_survey_email(
                "there", survey_url=survey_url, audience="newsletter",
            ) + (
                '<p style="margin:0;padding:0 24px 24px;font-size:11px;'
                'line-height:1.6;color:#8a8f98;font-family:-apple-system,'
                'BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">'
                '<a href="' + unsub + '" style="color:#8a8f98;'
                'text-decoration:underline;">Unsubscribe</a>'
                " \u2014 one click, no sign-in needed.</p>"
            )
            try:
                res = await send_email(
                    to=sub.email,
                    subject="Tapeline \u2014 four questions",
                    html=html,
                    persona="sales",
                    headers=_list_unsubscribe_headers(sub.unsubscribe_token),
                )
            except Exception:
                counts["failed"] += 1
                logger.exception("survey.newsletter_send_failed email=%s", sub.email)
                print("  FAILED      " + sub.email)
                continue

            if res.get("skipped"):
                counts["skipped"] += 1
                print("  SKIPPED     " + sub.email + " (" + str(res.get("reason")) + ")")
                continue

            counts["sent"] += 1
            print("  SENT        " + sub.email)

        if send:
            await session.commit()

    print("newsletter result: " + str(counts) + "\n")
    return counts


# ── The reminder, 2026-09-16 ────────────────────────────────────────────────
#
# Founder-authorised 2026-09-11: "go, one address for Waad, send Wed 16". Sent
# once, unattended, by .github/workflows/survey-reminder.yml at 13:07 UTC on
# 16 September — 9am New York. The original landed at midnight US Eastern.
#
# WHO: everyone who RECEIVED the original and has not visibly answered — account
# holders carrying SURVEY_TOKEN, plus the newsletter-only subscribers who existed
# when it went out. The 8 re_sunset accounts never received the original (the
# lifecycle governor blocked them), so they are out by construction: you cannot
# remind someone of an email they never got.
#
# WHY IT COMMITS PER RECIPIENT: it runs over `flyctl ssh`. If that session drops
# mid-run, an end-of-run commit would roll back every "already reminded" token
# AFTER the emails had gone out, and the next run would send them all again. The
# token is also appended in SQL rather than by rewriting `drip_state` from the
# copy read at collection time, so a drip the worker records mid-run survives.
#
# WHY THE NEWSLETTER HALF HAS A RUN-LEVEL GUARD: `newsletter_subscribers` has no
# per-row marker column, and the original newsletter send stamped nothing. So the
# newsletter phase runs only on the FIRST reminder run — no account yet carries
# REMINDER_TOKEN — and accounts always go first. A crash therefore under-sends
# rather than double-sends. --force-newsletter overrides it, for a human who has
# checked Resend first.
#
# WHY IT ALSO HOLDS A DATABASE LOCK: the per-recipient token makes a RETRY
# safe, and does nothing about two runs going at once — both read "not
# reminded" before either commits, and both send. The workflow's concurrency
# group stops two scheduled runs overlapping, but not a manual run started at
# the same moment. `dblock.one_machine_at_a_time` holds the lock on a session
# of its own, so the per-recipient commits do not release it (see
# `hold_xact_lock`). The loser returns an empty dict and sends nothing.
#
# WHY --quiet EXISTS: the workflow's log is world-readable on this public repo.
# With --quiet the run prints counts, never an address.

REMINDER_TOKEN = "survey_2026_09_r"

#: Newsletter subscribers created before this instant received the original.
#: Its account phase committed at 03:44:39 UTC and the newsletter phase ran
#: straight after; the newest of those 14 subscribers joined on 2026-09-07.
ORIGINAL_SEND_AT = "2026-09-11T03:44:00+00:00"

#: Founder decision 2026-09-11: remind ONE address for Waad. waadrabeemm@
#: ("Waad Rabeemm") and waadrabeema@ ("Waad20rabee Ma") registered 36 seconds
#: apart; the first-registered one is kept. Otherwise this would be the third
#: and fourth email one person received about this survey.
REMINDER_SKIP = frozenset({"waadrabeema@gmail.com"})

#: Resend reported this address "suppressed" for the original — a prior bounce
#: or complaint on Resend's side. The database cannot know, because
#: RESEND_WEBHOOK_SECRET is unset and bounces never reach
#: `email_undeliverable_at`. Resend would drop it again; skipping it keeps the
#: counts honest.
RESEND_SUPPRESSED = frozenset({"patelsp1@yahoo.com"})

_NOT_A_NAME = frozenset({"the", "mr", "mrs", "ms", "dr", "sir", "madam"})


def first_name(full: str | None) -> str:
    """The greeting name for the reminder.

    The original greeted with the whole stored name, so it went out as
    "Hi David Eley," / "Hi ELANGOVAN M," / "Hi The Best,". This takes the first
    word, softens ALL-CAPS, keeps any other casing as typed (so "McKay"
    survives), and falls back to "there" for a title word, a single letter, or
    anything containing a digit.
    """
    parts = (full or "").split()
    tok = parts[0] if parts else ""
    if len(tok) < 2 or any(ch.isdigit() for ch in tok) or tok.lower() in _NOT_A_NAME:
        return "there"
    return tok.capitalize() if tok.isupper() else tok


async def _answered(session) -> set[str]:
    """Addresses respondents chose to leave in the form.

    The form is otherwise anonymous by design, so this is the only way to know
    that someone already answered.
    """
    from app.models import SurveyResponse

    rows = (await session.execute(
        select(SurveyResponse.contact_email)
        .where(SurveyResponse.contact_email.is_not(None))
    )).scalars().all()
    return {e.lower() for e in rows if e}


async def collect_reminder_accounts(session) -> tuple[list, list]:
    """(recipients, skipped) — account holders who received the original."""
    from app.models import User
    from app.services.email_prefs import EmailPref, wants

    answered = await _answered(session)
    rows = (await session.execute(select(User))).scalars().all()

    recipients, skipped = [], []
    for u in rows:
        email = (u.email or "").lower()
        toks = _tokens(u)
        if SURVEY_TOKEN not in toks:
            continue  # never received the original: not part of this send at all
        if REMINDER_TOKEN in toks:
            skipped.append((u, "already_reminded"))
        elif email in REMINDER_SKIP:
            skipped.append((u, "duplicate_person"))
        elif email in INTERNAL_ADDRESSES or getattr(u, "is_admin", False):
            skipped.append((u, "internal"))
        elif getattr(u, "email_undeliverable_at", None) is not None:
            skipped.append((u, "undeliverable"))
        elif email in answered:
            skipped.append((u, "answered"))
        elif not wants(u, EmailPref.RE_ENGAGEMENT):
            skipped.append((u, "opted_out"))
        else:
            recipients.append(u)
    return recipients, skipped


async def collect_reminder_newsletter(session) -> tuple[list, list]:
    """(recipients, skipped) — newsletter-only subscribers who got the original."""
    from datetime import UTC, datetime

    cutoff = datetime.fromisoformat(ORIGINAL_SEND_AT)
    candidates, skipped = await collect_newsletter(session)
    answered = await _answered(session)

    recipients = []
    for sub in candidates:
        email = sub.email.lower()
        created = sub.created_at
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=UTC)  # SQLite hands back naive datetimes
        if created is None or created >= cutoff:
            skipped.append((sub, "joined_after_original"))
        elif email in RESEND_SUPPRESSED:
            skipped.append((sub, "resend_suppressed"))
        elif email in REMINDER_SKIP:
            skipped.append((sub, "duplicate_person"))
        elif email in answered:
            skipped.append((sub, "answered"))
        else:
            recipients.append(sub)
    return recipients, skipped


def _tally(skipped: list) -> str:
    counts: dict[str, int] = {}
    for _row, reason in skipped:
        counts[reason] = counts.get(reason, 0) + 1
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none"


@one_machine_at_a_time(LOCK_SURVEY_REMINDER, "survey_reminder", default_factory=dict)
async def run_reminder(
    *, send: bool, quiet: bool = False, force_newsletter: bool = False,
) -> dict:
    """Send (or dry-run) the one reminder. See the block comment above."""
    from sqlalchemy import case, or_, update

    from app.config import get_settings
    from app.db import session_scope
    from app.models import User
    from app.services.email import render_survey_reminder_email, send_email
    from app.services.lifecycle import worker_governor
    from app.services.newsletter import _list_unsubscribe_headers, _unsubscribe_url

    base = (get_settings().app_url or "https://tapeline.io").rstrip("/")
    survey_url = f"{base}/survey"
    if send and not base.startswith("https://"):
        raise SystemExit(
            f"refusing to send: survey link is {base!r}, which is not a public "
            f"https URL."
        )

    def show(line: str) -> None:
        if not quiet:
            print(line)

    counts = {
        "accounts_sent": 0, "newsletter_sent": 0, "would_send": 0,
        "governed": 0, "not_sent": 0, "failed": 0,
    }

    async with session_scope() as session:
        # Decided BEFORE anything is sent. Parsed in Python, not with LIKE:
        # `_` is a LIKE wildcard, so '%survey_2026_09_r%' also matches the
        # original token followed by a comma and an "r".
        states = (await session.execute(select(User.drip_state))).scalars().all()
        first_run = not any(
            REMINDER_TOKEN in {t for t in (d or "").split(",") if t} for d in states
        )
        run_news = first_run or force_newsletter

        accounts, a_skipped = await collect_reminder_accounts(session)
        news, n_skipped = await collect_reminder_newsletter(session)

        print(f"\n{'SENDING' if send else 'DRY RUN — nothing will be sent'}: survey reminder")
        print(f"link: {survey_url}")
        print(f"accounts:   {len(accounts)} to remind; skipped: {_tally(a_skipped)}")
        print(
            f"newsletter: {len(news) if run_news else 0} to remind; "
            f"skipped: {_tally(n_skipped)}"
            + ("" if run_news else "  (PHASE SKIPPED: an earlier reminder run already started)")
        )

        governor = worker_governor()
        for u in accounts:
            if not send:
                counts["would_send"] += 1
                show(f"  WOULD SEND  {u.email:<40} Hi {first_name(u.name)},")
                continue
            if not governor.allows(u):
                counts["governed"] += 1
                show(f"  GOVERNED    {u.email}")
                continue
            try:
                res = await send_email(
                    to=u.email,
                    subject="Tapeline — four questions",
                    html=render_survey_reminder_email(
                        first_name(u.name), survey_url=survey_url, audience="account",
                    ),
                    persona="sales",
                    unsubscribe_user_id=u.id,
                    unsubscribe_category="re_engagement",
                )
            except Exception:
                counts["failed"] += 1
                logger.exception("survey_reminder.send_failed user=%s", u.id)
                show(f"  FAILED      {u.email}")
                continue
            if res.get("skipped"):
                counts["not_sent"] += 1
                show(f"  NOT SENT    {u.email} ({res.get('reason')})")
                continue

            await session.execute(
                update(User)
                .where(User.id == u.id)
                .values(drip_state=case(
                    (or_(User.drip_state.is_(None), User.drip_state == ""), REMINDER_TOKEN),
                    else_=User.drip_state + "," + REMINDER_TOKEN,
                ))
                .execution_options(synchronize_session=False)
            )
            await session.commit()  # per recipient — see the block comment
            governor.record(u)
            counts["accounts_sent"] += 1
            show(f"  SENT        {u.email}")

        if run_news:
            for sub in news:
                if not send:
                    counts["would_send"] += 1
                    show(f"  WOULD SEND  {sub.email:<40} Hi there,")
                    continue
                # The shared footer placeholder only resolves for `users` rows,
                # so this list's own opt-out link and header are added here.
                unsub = _unsubscribe_url(sub.unsubscribe_token)
                html = render_survey_reminder_email(
                    "there", survey_url=survey_url, audience="newsletter",
                ) + (
                    '<p style="margin:0;padding:0 24px 24px;font-size:11px;'
                    'line-height:1.6;color:#8a8f98;font-family:-apple-system,'
                    'BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">'
                    f'<a href="{unsub}" style="color:#8a8f98;'
                    'text-decoration:underline;">Unsubscribe</a>'
                    " — one click, no sign-in needed.</p>"
                )
                try:
                    res = await send_email(
                        to=sub.email,
                        subject="Tapeline — four questions",
                        html=html,
                        persona="sales",
                        headers=_list_unsubscribe_headers(sub.unsubscribe_token),
                    )
                except Exception:
                    counts["failed"] += 1
                    # An id, never the address: this output can be public.
                    logger.exception("survey_reminder.newsletter_send_failed id=%s", sub.id)
                    show(f"  FAILED      {sub.email}")
                    continue
                if res.get("skipped"):
                    counts["not_sent"] += 1
                    show(f"  NOT SENT    {sub.email} ({res.get('reason')})")
                    continue
                counts["newsletter_sent"] += 1
                show(f"  SENT        {sub.email}")

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
    ap.add_argument(
        "--audience", choices=("accounts", "newsletter", "all"), default="accounts",
        help="who to mail. Newsletter subscribers with no account get different "
             "copy and a different Q1 option list.",
    )
    ap.add_argument(
        "--reminder", action="store_true",
        help="send the one 2026-09-16 reminder instead of the survey. It reaches "
             "only people who received the original; --audience is ignored.",
    )
    ap.add_argument(
        "--quiet", action="store_true",
        help="print counts only, never an address. REQUIRED wherever the output "
             "is public — the survey-reminder workflow passes it.",
    )
    ap.add_argument(
        "--force-newsletter", action="store_true",
        help="run the reminder's newsletter phase even though an earlier reminder "
             "run already started. Check Resend's log first.",
    )
    args = ap.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    if args.reminder:
        asyncio.run(run_reminder(
            send=args.send, quiet=args.quiet, force_newsletter=args.force_newsletter,
        ))
        return

    async def _go() -> None:
        if args.audience in ("accounts", "all"):
            await run(
                send=args.send,
                limit=args.limit,
                only=args.only,
                include_sunset=args.include_sunset,
            )
        if args.audience in ("newsletter", "all"):
            await run_newsletter(
                send=args.send, limit=args.limit, only=args.only,
            )

    asyncio.run(_go())


if __name__ == "__main__":
    main()
