"""One-click checkout links for conversion emails, via signed HMAC tokens.

The trial-drip emails (day-13 "ends tomorrow", T+0 "expired", T+3, T+30) are
the only touchpoint that reaches a bounced trial user — and their CTA used to
land on /app/billing behind the login wall. A no-card trial user who signed up
two weeks ago has usually forgotten their password, so the exact moment they
decide to pay is the moment we ask them to run a password reset. This module
removes that wall: the email button carries a signed token, and GET
/api/billing/email-checkout verifies it and 303s straight into Stripe Checkout
for that user's account — no password, Apple/Google Pay available.

Security model (deliberately weaker than a login link, on purpose):
  - The token does NOT grant a session. It can do exactly one thing: open a
    Stripe Checkout page bound to the token's user. Worst case for a leaked /
    forwarded email: someone else pays for the user's subscription.
  - HMAC-SHA256 keyed by settings.session_secret (same pattern + secret as
    services/unsubscribe.py — already deployed, no new env var).
  - Expiry baked into the signed payload. Default TTL covers the decision
    window after the email lands; an expired link degrades to /pricing, never
    an error page.

Token format (URL-safe base64 of):
    "{user_id}|email_checkout|{expires_epoch}|{hmac_hex}"
"""
from __future__ import annotations

import base64
import hmac
import logging
import time
from hashlib import sha256

from app.config import get_settings

logger = logging.getLogger(__name__)

_PURPOSE = "email_checkout"

# How long an emailed checkout link stays valid. The day-13 email lands ~24h
# before expiry and the decision tail runs a couple of weeks (T+3, T+30 touches
# mint their own fresh tokens at send time), so 14 days per link is plenty
# without leaving effectively-immortal payment links in old inboxes.
TOKEN_TTL_DAYS = 14

# The four (tier, period) combos the emails link to. Key format "{tier}_{period}"
CHECKOUT_COMBOS: tuple[tuple[str, str], ...] = (
    ("pro", "monthly"),
    ("pro", "annual"),
    ("premium", "monthly"),
    ("premium", "annual"),
)


def _secret() -> bytes | None:
    raw = (get_settings().session_secret or "").strip()
    if not raw:
        return None
    return raw.encode("utf-8")


def make_checkout_token(
    user_id: str, ttl_days: int = TOKEN_TTL_DAYS, _now: float | None = None
) -> str | None:
    """Signed, expiring, purpose-scoped token for one user. None when the
    HMAC secret isn't configured (caller falls back to the /app/billing URL
    rather than shipping a broken link)."""
    secret = _secret()
    if secret is None:
        return None
    expires = int((_now if _now is not None else time.time()) + ttl_days * 86400)
    payload = f"{user_id}|{_PURPOSE}|{expires}".encode()
    sig = hmac.new(secret, payload, sha256).hexdigest()
    raw = f"{user_id}|{_PURPOSE}|{expires}|{sig}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def verify_checkout_token(token: str, _now: float | None = None) -> str | None:
    """Return the user_id on success, None on ANY failure (bad shape, wrong
    purpose, expired, signature mismatch, missing secret)."""
    secret = _secret()
    if secret is None:
        return None
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception:
        return None
    parts = raw.split("|")
    if len(parts) != 4:
        return None
    user_id, purpose, expires_s, provided_sig = parts
    if purpose != _PURPOSE:
        return None
    try:
        expires = int(expires_s)
    except ValueError:
        return None
    if (_now if _now is not None else time.time()) > expires:
        return None
    expected_sig = hmac.new(
        secret, f"{user_id}|{_PURPOSE}|{expires}".encode(), sha256
    ).hexdigest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None
    return user_id


def email_checkout_urls(user_id: str) -> dict[str, str] | None:
    """Build the one-click checkout URL per (tier, period) combo, or None when
    the secret isn't configured. URLs go through the app domain (Next.js
    proxies /api/* to the backend — same routing as unsubscribe links)."""
    token = make_checkout_token(user_id)
    if token is None:
        return None
    base = (get_settings().app_url or "https://tapeline.io").rstrip("/")
    return {
        f"{tier}_{period}": (
            f"{base}/api/billing/email-checkout"
            f"?token={token}&tier={tier}&period={period}"
        )
        for tier, period in CHECKOUT_COMBOS
    }
