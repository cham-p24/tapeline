"""
Twilio SMS delivery — third notification channel after email and Telegram.

Premium-only feature. Twilio bills per-message (~$0.008 US, more elsewhere)
so SMS rules should be reserved for high-conviction events (HIGH CONVICTION
crossings, regime flips, congress trades on big positions). Email + Telegram
are better defaults for noisy alert types.

When TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER are unset,
send_sms() is a no-op (returns False). Caller should treat False as
"undelivered" so AlertEvent.delivered gets set correctly.
"""
from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TWILIO_API = "https://api.twilio.com/2010-04-01"

# Twilio caps message bodies at 1600 chars (10x the 160-char SMS standard;
# longer messages are split into segments billed individually).
MAX_BODY = 1600


async def send_sms(to_number: str, body: str) -> bool:
    """Send a single SMS via Twilio. Returns True on success."""
    sid = getattr(settings, "twilio_account_sid", "") or ""
    token = getattr(settings, "twilio_auth_token", "") or ""
    from_num = getattr(settings, "twilio_from_number", "") or ""

    if not (sid and token and from_num):
        logger.warning("sms.skipped reason=twilio_not_configured to=%s", to_number)
        return False

    payload = {
        "From": from_num,
        "To": to_number,
        "Body": body[:MAX_BODY],
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{TWILIO_API}/Accounts/{sid}/Messages.json",
                auth=(sid, token),
                data=payload,
            )
            if r.status_code in (200, 201):
                return True
            logger.warning(
                "sms.send_failed status=%s body=%s",
                r.status_code, r.text[:200],
            )
    except Exception:
        logger.exception("sms.send_failed_exception to=%s", to_number)
    return False


def normalize_phone(raw: str) -> str:
    """Loose E.164-style normalisation: strip non-digits, ensure leading +.

    Real validation should happen via Twilio's Lookup API on save (paid),
    but this catches the common typos (spaces, dashes, parens).
    """
    digits = "".join(c for c in raw if c.isdigit())
    if not digits:
        return ""
    return "+" + digits
