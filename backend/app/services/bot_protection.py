"""
Bot / abuse mitigation layer.

Three lines of application-level defense:

1. **Honeypot field** on signup forms — invisible <input name="company">
   that bots reliably fill. Empty for humans, filled for bots.
2. **Disposable-email block** — rejects throwaway addresses commonly used
   for trial abuse. Built-in subset (~60 domains); extend as needed.
3. **Cloudflare Turnstile** — privacy-friendly CAPTCHA. Optional, env-gated.
   When `cloudflare_turnstile_secret_key` is unset this is a no-op pass-through
   so dev never breaks; in production with the key set, missing/invalid tokens
   are rejected.

Cloudflare Bot Fight Mode (free, on the proxy) is the recommended baseline
once the domain is moved behind Cloudflare. This module is defense-in-depth
on top of that — useful especially for direct API access that bypasses the
edge proxy.
"""
from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Common disposable / throwaway email domains.
# Not exhaustive — disposable-email-domains package on PyPI tracks ~10k entries.
# This subset blocks the highest-traffic abuse vectors with zero deps.
DISPOSABLE_EMAIL_DOMAINS: set[str] = {
    "10minutemail.com", "10minutemail.net", "20minutemail.com",
    "anonmails.de", "armyspy.com",
    "burnermail.io",
    "cuvox.de",
    "dayrep.com", "discard.email", "dropmail.me",
    "einrot.com", "email-fake.com", "emailondeck.com",
    "fakeinbox.com", "fakemail.net", "fakemailgenerator.com",
    "fake-mail.live", "fleckens.hu",
    "getairmail.com", "getnada.com",
    "guerrillamail.com", "guerrillamail.net", "guerrillamail.org",
    "guerrillamailblock.com", "gustr.com",
    "harakirimail.com",
    "instant-mail.de",
    "jourrapide.com",
    "mailinator.com", "mailinator.net", "mailnesia.com", "maildrop.cc",
    "mintemail.com", "moakt.com", "mohmal.com", "mvrht.com", "mytemp.email",
    "rhyta.com",
    "sharklasers.com", "spambog.com", "spamgourmet.com", "spam4.me", "superrito.com",
    "teleworm.us", "tempinbox.com", "tempmail.com", "tempmail.net",
    "tempmail.org", "tempmail.dev", "tempmailo.com", "tempr.email",
    "throwaway.email", "throwawaymail.com",
    "trashmail.com", "trashmail.de", "trashmail.net",
    "wegwerfmail.de", "wegwerfmail.net", "wegwerfmail.org",
    "yopmail.com", "yopmail.net", "yopmail.fr",
}


def is_disposable_email(email: str) -> bool:
    """True if the email domain is on the disposable-providers list."""
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].lower().strip()
    return domain in DISPOSABLE_EMAIL_DOMAINS


def is_honeypot_tripped(value: str | None) -> bool:
    """Honeypot fields should be empty for humans. Bots fill them."""
    return bool(value and value.strip())


async def verify_turnstile(token: str | None, remote_ip: str | None) -> bool:
    """
    Verify a Cloudflare Turnstile token.

    Returns True if Turnstile is not configured (pass-through for dev).
    Returns True if the token is valid.
    Returns False otherwise.
    """
    secret = getattr(settings, "cloudflare_turnstile_secret_key", "") or ""
    if not secret:
        return True  # not configured = no enforcement
    if not token:
        return False  # configured but no token submitted

    payload: dict[str, str] = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data=payload,
            )
            data = r.json()
            return bool(data.get("success"))
    except Exception:
        logger.exception("turnstile.verify_failed")
        return False
