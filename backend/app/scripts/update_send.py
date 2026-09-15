"""Send the September 2026 product update — once, unattended. HELD.

NOT YET AUTHORISED. The copy and the send date both wait on the founder. The
workflow that runs this, .github/workflows/product-update-send.yml, schedules
the send the moment it is merged, so the PR carrying it stays open until the
founder has approved both.

WHAT IT SAYS
------------
What changed in the week to 11 September, including what broke: the ~24-hour
scoring freeze, the permanent 9 September gap in the public record, the universe
growing from ~2,000 to ~11,500, crypto, and the 7 September score correction.
Account holders also get one sentence the newsletter list does not: the
open-access month ended on 8 September. The copy lives in
`services/email.render_product_update_email`, where the copy linter reads it.

It promotes nothing — no price, no offer, no upgrade ask, no deadline — for the
same reason the survey did not: the consent basis for a non-transactional email
to this list is an existing relationship plus a message that sells nothing.

WHO RECEIVES IT
---------------
Account holders (`users`), minus these, each for a stated reason:
  * no address; the founder's accounts and the ads contractor
    (`survey_send.INTERNAL_ADDRESSES`) and admins — not customers;
  * `email_undeliverable_at` — a bounce or complaint already on record;
  * `survey_send.RESEND_SUPPRESSED` — Resend drops it anyway, and counting it as
    sent would make the result line lie;
  * `re_sunset` — suppressed from every non-transactional send by the lifecycle
    governor (checked here too, so it shows up as a counted reason);
  * opted out of `EmailPref.RE_ENGAGEMENT` — a product update to someone who is
    not being actively mailed is re-engagement, the honest category to gate on;
  * already carrying UPDATE_TOKEN — so a second run is a no-op;
  * a `drip_state` too full to take the token (`_room_for_token`) — an email
    that cannot be recorded is an email a retry would send again.

Newsletter-only subscribers: confirmed, with a working unsubscribe token, whose
address belongs to NO account in any casing (`survey_send.collect_newsletter`),
and not Resend-suppressed. Deduplicating against EVERY account — not only the
eligible ones — is deliberate: someone who opted their account out of
re-engagement must not be reached through the mailing list instead.

WHY IT CANNOT DOUBLE-SEND
-------------------------
Five layers, because each one covers a failure the others do not.

  1. PER-RECIPIENT COMMIT. It runs over `flyctl ssh`. If that session drops
     mid-run, an end-of-run commit would roll back every token AFTER the emails
     had gone, and the next run would send them all again. The token is
     appended in SQL, not written back from the copy of `drip_state` read at
     collection time, so a drip the worker records mid-run survives.
  2. "ALREADY SENT" IS PARSED IN PYTHON, never with SQL LIKE. `_` is a LIKE
     wildcard, so '%product_update_2026_09%' would also match tokens this job
     never wrote.
  3. THE NEWSLETTER HALF RUNS ON THE FIRST RUN ONLY. `newsletter_subscribers`
     has no per-row marker (`last_sent_at` belongs to the daily digest, which
     would stop sending if this job wrote it). So accounts always go first, and
     the newsletter phase runs only when no account carried the token before
     this run AND this run stamped at least one. The second condition closes a
     hole the survey reminder's guard has: a run that stamps no account leaves
     no trace, so without it a re-run would mail the list a second time. A crash
     therefore under-sends rather than double-sends. `--force-newsletter` is
     for a human who has checked Resend's log first.
  4. AN ERROR AFTER THE REQUEST LEFT IS STAMPED, NOT RETRIED. `send_email`
     posts to Resend with a 10-second timeout and then raise_for_status(). A
     read timeout, a connection dropped mid-response, or a 5xx can all arrive
     after Resend has queued the email. Treating those as failures left the
     account unstamped, and the retry this docstring recommends mailed them a
     second time (reproduced: ReadTimeout on the first call, two deliveries
     across two runs). So `_outcome_unknown` errors are stamped and counted
     as `unknown`, apart from `failed`: `failed` means Resend never had it
     (connect error, 4xx, anything raised before the POST) and a retry is the
     fix; `unknown` means check Resend's log, and a retry will not resend.
  5. A DATABASE LOCK. The token makes a RETRY safe and does nothing about two
     runs at once — both read "not sent" before either commits. The workflow's
     concurrency group stops two scheduled runs overlapping, not a manual
     `flyctl ssh` started at the same moment. `dblock.one_machine_at_a_time`
     holds LOCK_PRODUCT_UPDATE on a session of its own, so the per-recipient
     commits do not release it. The loser returns {} and sends nothing.

SAFETY
------
  * DRY RUN BY DEFAULT. `--send` is required to transmit anything.
  * `--quiet` prints counts, never an address. The workflow's log is
    world-readable on this public repo. It also routes every log line through
    a formatter that redacts address-shaped text: `send_email` logs `to=` at
    WARNING when there is no Resend key and at ERROR when its undeliverable
    check fails, and with no logging configured Python prints WARNING and
    above straight to stderr, which is the same public log.
  * Refuses to send unless APP_URL is a public https URL (the scorecard link is
    built from it), and unless SESSION_SECRET can sign an unsubscribe link —
    without it every account holder's footer and plain-text part would carry
    no working opt-out.
  * The shared lifecycle governor is consulted, but it is NOT a frequency cap
    here. Its send ledger (`lifecycle._GLOBAL_LEDGER`) is an in-memory dict
    per process, and this runs in a fresh `flyctl ssh` process, so the 20-hour
    gap and the weekly cap see none of the worker's sends. What it can still
    enforce is global opt-out (email_prefs == 0), undeliverable and sunset,
    which `collect_accounts` already excludes with a counted reason; it is a
    second layer for those, and a test pins that layer. Spacing from the
    worker's own digests is done by the send TIME instead: see the header of
    .github/workflows/product-update-send.yml, and the test that reads the
    worker's send hours from its source.

AN OUTAGE STOPS THE RUN; A RUN THAT FELL SHORT EXITS NON-ZERO
-------------------------------------------------------------
Layer 4 stamps every unknown outcome, so if Resend answered 5xx or timed out on
every call, the run would stamp the whole audience and mail nobody. So
UNKNOWN_OUTCOME_LIMIT unknown outcomes in a row (no delivery between them) stop
the account phase: the accounts after them are not attempted, carry no stamp,
and are counted as `accounts_held` for a re-run. On a first run the newsletter
half is HELD too, even under --force-newsletter. On a re-run it is left alone
without an instruction to force it, because the earlier run may already have
mailed the list. Ported from the survey reminder (#831), with its review's fix.

Nobody watches the 17:07 run, so `main` exits 1 — printing `refused:` or a
`FELL SHORT:` line, counts only — when the lock was refused or any FELL_SHORT
count is non-zero. A dry run, and a re-run that finds everyone stamped, exit 0.

Usage:
    python -m app.scripts.update_send                   # dry run
    python -m app.scripts.update_send --send --quiet    # what the workflow runs
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys

from sqlalchemy import select

from app.scripts.survey_send import (
    INTERNAL_ADDRESSES,
    RESEND_SUPPRESSED,
    SUNSET_TOKEN,
    collect_newsletter,
    first_name,
)
from app.services.dblock import LOCK_PRODUCT_UPDATE, one_machine_at_a_time

logger = logging.getLogger(__name__)

UPDATE_TOKEN = "product_update_2026_09"

#: Invisible on the page — the link text is derived without the query string —
#: and lets the scorecard's traffic from this one email be told apart.
SCORECARD_UTM = "utm_source=email&utm_medium=email&utm_campaign=product_update_2026_09"

#: Unknown outcomes in a row that stop the account phase. See "AN OUTAGE STOPS
#: THE RUN" in the module docstring.
UNKNOWN_OUTCOME_LIMIT = 2

#: Counts meaning an eligible person was not knowably reached by this run. Any
#: of them non-zero makes `main` exit 1.
FELL_SHORT = ("failed", "unknown", "not_sent", "accounts_held", "newsletter_held")


def _state_tokens(drip_state: str | None) -> set[str]:
    """`User.drip_state` is a COMMA-SEPARATED TOKEN STRING, not JSON.

    Takes the raw column, not a User, so the first-run check can read
    `select(User.drip_state)` without loading every row as an object.
    """
    return {t for t in (drip_state or "").split(",") if t}


async def collect_accounts(session) -> tuple[list, list]:
    """(recipients, skipped) — read-only. See the module docstring for why."""
    from app.models import User
    from app.services.email_prefs import EmailPref, wants

    rows = (await session.execute(select(User))).scalars().all()
    recipients, skipped = [], []
    for u in rows:
        email = (u.email or "").lower()
        toks = _state_tokens(u.drip_state)
        if not email:
            skipped.append((u, "no_email"))
        elif UPDATE_TOKEN in toks:
            skipped.append((u, "already_sent"))
        elif email in INTERNAL_ADDRESSES or getattr(u, "is_admin", False):
            skipped.append((u, "internal"))
        elif getattr(u, "email_undeliverable_at", None) is not None:
            skipped.append((u, "undeliverable"))
        elif email in RESEND_SUPPRESSED:
            skipped.append((u, "resend_suppressed"))
        elif SUNSET_TOKEN in toks:
            skipped.append((u, "sunset"))
        elif not wants(u, EmailPref.RE_ENGAGEMENT):
            skipped.append((u, "opted_out"))
        elif not _room_for_token(u.drip_state):
            skipped.append((u, "no_room_for_token"))
        else:
            recipients.append(u)
    return recipients, skipped


def _room_for_token(drip_state: str | None) -> bool:
    """Whether appending UPDATE_TOKEN still fits `users.drip_state`.

    The column is VARCHAR(255) and this has already bitten once: weekly tokens
    overran it and Postgres raised StringDataRightTruncation on commit (see
    email.run_weekly_newsletter). Here the stamp is written AFTER the email is
    delivered and outside the send's try, so an overflow would abort the run
    with that person mailed but unstamped — and every retry would mail them
    again. Skipping them, counted, is the only order that cannot double-send.
    SQLite does not enforce the length, so the test suite could never see the
    failure; the capacity is read from the model rather than restated here.
    """
    from sqlalchemy import String

    from app.models import User

    # Narrowed with isinstance so mypy knows `.length` exists (a bare
    # TypeEngine does not declare it). Text subclasses String with
    # length=None, i.e. no limit, so a future Text column never blocks a send.
    col_type = User.__table__.c.drip_state.type
    capacity = col_type.length if isinstance(col_type, String) else None
    if capacity is None:
        return True
    current = drip_state or ""
    needed = len(current) + (1 if current else 0) + len(UPDATE_TOKEN)
    return needed <= capacity


async def collect_newsletter_only(session) -> tuple[list, list]:
    """(recipients, skipped) — confirmed subscribers who have no account."""
    candidates, skipped = await collect_newsletter(session)
    recipients = []
    for sub in candidates:
        if sub.email.lower() in RESEND_SUPPRESSED:
            skipped.append((sub, "resend_suppressed"))
        else:
            recipients.append(sub)
    return recipients, skipped


def _outcome_unknown(exc: BaseException) -> bool:
    """Whether Resend may have accepted the email even though the send raised.

    True only for errors that can happen AFTER the request reached Resend: a
    timeout or broken connection while writing the request or reading the
    response, a malformed response, or a 5xx (a gateway can answer 502/504
    after the upstream queued the email). False for anything that proves
    Resend never took it: a connect or pool timeout, a refused connection, a
    4xx rejection, or an error raised before the POST, such as a render bug.
    See layer 4 in the module docstring for why the distinction matters.
    """
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (
        httpx.ReadTimeout, httpx.WriteTimeout,
        httpx.ReadError, httpx.WriteError, httpx.CloseError,
        httpx.RemoteProtocolError, httpx.DecodingError,
    ))


async def _stamp(session, user_id: str) -> None:
    """Append UPDATE_TOKEN in SQL and commit at once — layers 1 and 2."""
    from sqlalchemy import case, or_, update

    from app.models import User

    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(drip_state=case(
            (or_(User.drip_state.is_(None), User.drip_state == ""), UPDATE_TOKEN),
            else_=User.drip_state + "," + UPDATE_TOKEN,
        ))
        .execution_options(synchronize_session=False)
    )
    await session.commit()


def _tally(skipped: list) -> str:
    counts: dict[str, int] = {}
    for _row, reason in skipped:
        counts[reason] = counts.get(reason, 0) + 1
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none"


@one_machine_at_a_time(LOCK_PRODUCT_UPDATE, "product_update", default_factory=dict)
async def run(*, send: bool, quiet: bool = False, force_newsletter: bool = False) -> dict:
    """Send (or dry-run) the product update. See the module docstring."""
    from app.config import get_settings
    from app.db import session_scope
    from app.models import User
    from app.services.email import (
        PRODUCT_UPDATE_SUBJECT,
        render_product_update_email,
        render_product_update_text,
        send_email,
    )
    from app.services.lifecycle import worker_governor
    from app.services.newsletter import _list_unsubscribe_headers, _unsubscribe_url
    from app.services.unsubscribe import unsubscribe_url

    base = (get_settings().app_url or "https://tapeline.io").rstrip("/")
    scorecard_url = f"{base}/scorecard?{SCORECARD_UTM}"
    if send and not base.startswith("https://"):
        raise SystemExit(
            f"refusing to send: the scorecard link is {base!r}, which is not a "
            f"public https URL."
        )
    if send and unsubscribe_url("u_probe", "re_engagement") is None:
        raise SystemExit(
            "refusing to send: SESSION_SECRET is not set, so no account holder's "
            "unsubscribe link can be signed."
        )

    def show(line: str) -> None:
        if not quiet:
            print(line)

    counts = {
        "accounts_sent": 0, "newsletter_sent": 0, "would_send": 0,
        "governed": 0, "not_sent": 0, "failed": 0, "unknown": 0,
        "accounts_held": 0, "newsletter_held": 0,
    }
    # Accounts this run stamped, whether delivered or outcome-unknown. Layer 3
    # asks whether a re-run could tell this run happened, and either kind of
    # stamp answers yes; `accounts_sent` alone would not count the second.
    stamped = 0
    # Unknown outcomes since the last delivery, and whether they stopped the run.
    unknown_streak = 0
    stopped = False

    async with session_scope() as session:
        # Decided BEFORE anything is sent, and parsed in Python — see layer 2.
        states = (await session.execute(select(User.drip_state))).scalars().all()
        first_run = not any(UPDATE_TOKEN in _state_tokens(d) for d in states)

        accounts, a_skipped = await collect_accounts(session)
        news, n_skipped = await collect_newsletter_only(session)

        print(f"\n{'SENDING' if send else 'DRY RUN — nothing will be sent'}: product update")
        print(f"link: {scorecard_url}")
        print(f"accounts:   {len(accounts)} to send; skipped: {_tally(a_skipped)}")
        print(f"newsletter: {len(news)} eligible; skipped: {_tally(n_skipped)}")

        governor = worker_governor()
        for position, u in enumerate(accounts, start=1):
            greeting = first_name(u.name)
            if not send:
                counts["would_send"] += 1
                show(f"  WOULD SEND  {u.email:<40} Hi {greeting},")
                continue
            if not governor.allows(u):
                counts["governed"] += 1
                show(f"  GOVERNED    {u.email}")
                continue
            try:
                res = await send_email(
                    to=u.email,
                    subject=PRODUCT_UPDATE_SUBJECT,
                    html=render_product_update_email(
                        greeting, scorecard_url=scorecard_url, audience="account",
                    ),
                    text=render_product_update_text(
                        greeting, scorecard_url=scorecard_url, audience="account",
                        unsubscribe_url=unsubscribe_url(u.id, "re_engagement") or "",
                    ),
                    persona="sales",
                    unsubscribe_user_id=u.id,
                    unsubscribe_category="re_engagement",
                )
            except Exception as exc:
                if not _outcome_unknown(exc):
                    counts["failed"] += 1
                    # An id, never the address: this output can be public.
                    logger.exception("product_update.send_failed user=%s", u.id)
                    show(f"  FAILED      {u.email}")
                    continue
                # Resend may have it — layer 4. Stamped below like a delivery.
                logger.warning(
                    "product_update.send_outcome_unknown user=%s stamped=yes",
                    u.id, exc_info=True,
                )
                outcome = "unknown"
            else:
                if res.get("skipped"):
                    counts["not_sent"] += 1
                    show(f"  NOT SENT    {u.email} ({res.get('reason')})")
                    continue
                outcome = "sent"

            await _stamp(session, u.id)  # per recipient — layer 1
            governor.record(u)
            stamped += 1
            if outcome == "sent":
                unknown_streak = 0
                counts["accounts_sent"] += 1
                show(f"  SENT        {u.email}")
                continue
            unknown_streak += 1
            counts["unknown"] += 1
            show(f"  UNKNOWN     {u.email} (stamped; check Resend's log)")
            if unknown_streak >= UNKNOWN_OUTCOME_LIMIT:
                stopped = True
                counts["accounts_held"] = len(accounts) - position
                print(
                    f"STOPPED: {unknown_streak} sends in a row had an unknown outcome, "
                    f"so Resend looks unhealthy. {counts['accounts_held']} account(s) "
                    "after them were not attempted and carry no stamp: re-run once "
                    "Resend is healthy."
                )
                break

        # Layer 3 and the outage stop. Dry runs report what the first real run would do.
        if stopped and first_run:
            run_news, why = False, (
                "HELD: the account phase stopped on unknown outcomes. Check Resend's "
                "log, then run with --force-newsletter over flyctl ssh"
            )
            counts["newsletter_held"] = len(news)
        elif stopped:
            run_news, why = False, (
                "SKIPPED: the account phase stopped, and an earlier run already stamped "
                "accounts. Whether the list was mailed is in that run's log "
                "('newsletter phase: running' means it was); do not force it blind"
            )
        elif force_newsletter:
            run_news, why = True, "FORCED by --force-newsletter"
        elif not first_run:
            run_news, why = False, (
                "SKIPPED: an earlier run already stamped accounts. If that run printed "
                "'newsletter phase: HELD' or never reached this line, the list was never "
                "mailed: check Resend's log, then run with --force-newsletter once"
            )
        elif send and stamped == 0:
            run_news, why = False, (
                "SKIPPED: this run stamped no account, so a re-run could not tell "
                "the list had been mailed"
            )
            counts["newsletter_held"] = len(news)
        else:
            run_news, why = True, "running"
        print(f"newsletter phase: {why}")

        if run_news:
            for sub in news:
                if not send:
                    counts["would_send"] += 1
                    show(f"  WOULD SEND  {sub.email:<40} Hi there,")
                    continue
                unsub = _unsubscribe_url(sub.unsubscribe_token)
                try:
                    res = await send_email(
                        to=sub.email,
                        subject=PRODUCT_UPDATE_SUBJECT,
                        html=render_product_update_email(
                            "there", scorecard_url=scorecard_url,
                            audience="newsletter", newsletter_unsubscribe_url=unsub,
                        ),
                        text=render_product_update_text(
                            "there", scorecard_url=scorecard_url,
                            audience="newsletter", unsubscribe_url=unsub,
                        ),
                        persona="sales",
                        headers=_list_unsubscribe_headers(sub.unsubscribe_token),
                    )
                except Exception as exc:
                    # No per-row marker to stamp (layer 3), so the two kinds
                    # differ only in the count — which is what tells the
                    # operator whether Resend's log needs checking.
                    if _outcome_unknown(exc):
                        counts["unknown"] += 1
                        logger.warning(
                            "product_update.newsletter_outcome_unknown id=%s",
                            sub.id, exc_info=True,
                        )
                        show(f"  UNKNOWN     {sub.email} (check Resend's log)")
                    else:
                        counts["failed"] += 1
                        logger.exception("product_update.newsletter_send_failed id=%s", sub.id)
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


#: Anything shaped like local@domain. Deliberately loose: redacting a
#: non-address that happens to contain "@" costs nothing in a count-only log,
#: and missing a real address costs a customer's privacy.
_ADDRESS_SHAPED = re.compile(r"[^\s<>\"'(),;:\[\]]+@[^\s<>\"'(),;:\[\]]+")


class RedactAddresses(logging.Formatter):
    """Formats a record — traceback included — then removes address-shaped text."""

    def format(self, record: logging.LogRecord) -> str:
        return _ADDRESS_SHAPED.sub("<address>", super().format(record))


def configure_quiet_logging() -> logging.Handler:
    """Route every log line through RedactAddresses. See SAFETY in the docstring."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(RedactAddresses("%(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.WARNING)
    return handler


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--send", action="store_true", help="actually transmit")
    ap.add_argument(
        "--quiet", action="store_true",
        help="print counts only, never an address. REQUIRED wherever the output "
             "is public — the product-update workflow passes it.",
    )
    ap.add_argument(
        "--force-newsletter", action="store_true",
        help="run the newsletter phase even though it would otherwise be skipped. "
             "Check Resend's log first.",
    )
    args = ap.parse_args(argv)

    if args.quiet:
        configure_quiet_logging()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    counts = asyncio.run(run(
        send=args.send, quiet=args.quiet, force_newsletter=args.force_newsletter,
    ))
    if counts == {}:
        # The lock's loss value; without this line a refused run's log is silent.
        print("\nrefused: another product update run holds the lock; this run sent nothing.\n")
        sys.exit(1)
    short = {k: counts[k] for k in FELL_SHORT if counts.get(k)}
    if short:
        # Counts only, never an address: this log is public.
        print(f"FELL SHORT: {short} — exiting 1 so this run shows red. Read the "
              "result line before re-running.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
