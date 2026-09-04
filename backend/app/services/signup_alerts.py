"""Tell the founder when signup is refusing people.

WHY THIS EXISTS
---------------
`POST /api/auth/signup` returned 400 "Bot challenge failed" for **every**
caller from 2026-08-10 to 2026-09-03 (#725). The frontend shipped an empty
Turnstile site key, so no widget rendered, so no token was ever submitted, so
`verify_turnstile` refused everyone. Nothing anywhere noticed.

It survived nearly a month because the only signal was a 400 the visitor saw
and the founder did not. The database looked healthy — 32 accounts — because
Google OAuth uses a different route entirely and kept working. The tell was
visible the whole time and nobody was looking at it: **32 accounts, exactly one
password_hash**.

A silent failure on the one path that creates customers is the most expensive
kind of bug this product can have, so it now sends mail.

WHAT IS AND IS NOT WORTH WAKING SOMEONE FOR
-------------------------------------------
`no_token` is the outage signature. It means the browser submitted the form
without a challenge response at all, which is what a missing/blank site key, a
blocked Cloudflare script, or a broken widget all look like. A crawler posting
the form bare looks the same, hence the throttle rather than a per-event send.

`token_rejected` means a token WAS produced and Cloudflare declined it —
ordinarily a bot, an expired token, or a replay. Reported at a lower volume
because it is the system working.

`cloudflare_unreachable` means siteverify timed out or errored. `verify_turnstile`
fails closed there, so every signup is blocked for as long as it lasts — the
same total outage as `no_token`, from a different cause.

The throttle is per-reason and in-process. Two machines can therefore send two
mails for one incident, which is the right trade: this is the alarm for a
month-long silent outage, and duplicate mail is a far cheaper failure than
none.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

# One mail per reason per window. Long enough that a crawler hammering the
# form cannot turn the alarm into noise, short enough that a real outage is
# re-reported the same day if it is still going.
THROTTLE_SECONDS = 6 * 60 * 60

_last_sent: dict[str, float] = {}

REASON_BLURB = {
    "no_token": (
        "The signup form was submitted with NO bot-challenge token at all. "
        "That is what a missing or blank NEXT_PUBLIC_TURNSTILE_SITE_KEY looks "
        "like, and it is exactly how signup was dead from 2026-08-10 to "
        "2026-09-03 (#725). It can also be a crawler posting the form bare, so "
        "check the signup page in a real browser before assuming an outage: "
        "if the Cloudflare widget is missing from the page, it is an outage."
    ),
    "token_rejected": (
        "A challenge token WAS submitted and Cloudflare rejected it. Usually a "
        "bot, an expired token, or a replay — i.e. the system working. Worth a "
        "look only if it repeats for real people."
    ),
    "cloudflare_unreachable": (
        "Cloudflare's siteverify call failed or timed out. Verification fails "
        "CLOSED, so while this lasts NOBODY can sign up with email and "
        "password. Check Cloudflare status."
    ),
}


def _should_send(reason: str, now: float | None = None) -> bool:
    """True at most once per reason per THROTTLE_SECONDS."""
    t = time.monotonic() if now is None else now
    last = _last_sent.get(reason)
    if last is not None and (t - last) < THROTTLE_SECONDS:
        return False
    _last_sent[reason] = t
    return True


def reset_throttle() -> None:
    """Test hook. Never called in production."""
    _last_sent.clear()


async def alert_signup_blocked(
    reason: str, *, email: str | None = None, client_ip: str | None = None
) -> bool:
    """Mail the founder that a signup was refused. Returns True if mail went.

    Never raises. This runs on the failure path of a request that is already
    about to return 400; an exception here would turn a bad-request into a
    500 and, worse, could mask the very thing it is reporting.
    """
    try:
        if not _should_send(reason):
            logger.info("signup_blocked.throttled reason=%s", reason)
            return False

        from app.config import get_settings
        from app.services.email import send_email

        settings = get_settings()
        to = getattr(settings, "owner_email", None) or "owner@tapeline.io"

        blurb = REASON_BLURB.get(reason, "Signup was refused by the bot check.")
        who = email or "(no email captured)"
        where = client_ip or "(no ip)"

        html = (
            "<p><strong>A signup attempt was refused by the bot check.</strong></p>"
            f"<p><strong>Reason:</strong> {reason}</p>"
            f"<p>{blurb}</p>"
            f"<p><strong>Email tried:</strong> {who}<br>"
            f"<strong>From IP:</strong> {where}</p>"
            "<p>Google sign-in uses a different route and is unaffected, which "
            "is why the account count can keep rising while email/password "
            "signup is completely dead. The quickest check is the number of "
            "users with a password_hash — if that is not moving, this path is "
            "not working.</p>"
            f"<p>You will not get another '{reason}' alert for "
            f"{THROTTLE_SECONDS // 3600} hours.</p>"
        )

        await send_email(
            to,
            f"Signup refused: {reason}",
            html,
            persona="alerts",
            skip_if_undeliverable=False,
        )
        logger.warning("signup_blocked.alert_sent reason=%s ip=%s", reason, where)
        return True
    except Exception:
        logger.exception("signup_blocked.alert_failed reason=%s", reason)
        return False
