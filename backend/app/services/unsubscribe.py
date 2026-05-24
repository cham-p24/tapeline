"""One-click unsubscribe via signed HMAC tokens.

Why HMAC and not a DB table:
  - Stateless — no per-user per-category row to maintain
  - Survives DB resets (token is self-verifying)
  - Single round-trip from email click to confirmation
  - Resend's List-Unsubscribe-Post one-click flow demands a stable URL
    that resolves in <300ms; an HMAC verify is ~microseconds, a DB
    lookup is milliseconds with cold-cache latency

Token format (URL-safe base64 of):
    "{user_id}|{category}|{hmac_hex}"

  user_id     u_<uuid> as stored on User.id
  category    "weekly_newsletter" | "trial_drip" | "re_engagement" |
              "daily_digest" | "alert_emails" | "all" — must match a key
              in app.services.email_prefs.categories_for_ui() OR the
              special sentinel "all" which clears every bit.
  hmac_hex    HMAC-SHA256 of "{user_id}|{category}" keyed by
              settings.session_secret (the same secret used for session
              cookies — already deployed, no new env var needed)

Verification recomputes the HMAC and compares constant-time. Unknown
category → reject. Missing session_secret → reject (the endpoint will
503 in that case rather than silently no-op).
"""
from __future__ import annotations

import base64
import hmac
import logging
from hashlib import sha256

from app.config import get_settings

logger = logging.getLogger(__name__)

# Valid category names. Keep in sync with categories_for_ui keys + the
# "all" sentinel. Anything outside this set is rejected by the verifier.
VALID_CATEGORIES = frozenset({
    "trial_drip",
    "re_engagement",
    "daily_digest",
    "alert_emails",
    "weekly_newsletter",
    "all",   # special: clears every bit + marketing_opt_in
})


def _secret() -> bytes | None:
    """Return the HMAC secret as bytes, or None if not configured."""
    s = get_settings()
    raw = (s.session_secret or "").strip()
    if not raw:
        return None
    return raw.encode("utf-8")


def make_token(user_id: str, category: str = "all") -> str | None:
    """Produce a URL-safe token the user can click in a List-Unsubscribe
    header. Returns None if the HMAC secret isn't configured (caller
    should omit the unsubscribe header rather than ship a broken link).
    """
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Unknown unsubscribe category: {category}")
    secret = _secret()
    if secret is None:
        return None
    payload = f"{user_id}|{category}".encode()
    sig = hmac.new(secret, payload, sha256).hexdigest()
    raw = f"{user_id}|{category}|{sig}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def verify_token(token: str) -> tuple[str, str] | None:
    """Parse + verify a token. Returns (user_id, category) on success
    or None on any failure — bad shape, unknown category, signature
    mismatch, missing secret. Caller treats None as "reject silently".
    """
    secret = _secret()
    if secret is None:
        return None
    try:
        # Re-pad for base64 decoding (we stripped = on encode).
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception:
        return None
    parts = raw.split("|")
    if len(parts) != 3:
        return None
    user_id, category, provided_sig = parts
    if category not in VALID_CATEGORIES:
        return None
    expected_sig = hmac.new(
        secret, f"{user_id}|{category}".encode(), sha256,
    ).hexdigest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None
    return user_id, category


def unsubscribe_url(user_id: str, category: str = "all") -> str | None:
    """Build the absolute https://tapeline.io/api/unsubscribe?token=... URL
    for inclusion in List-Unsubscribe headers. Returns None when the
    secret isn't configured — orchestrators should then omit the header
    rather than emit one that doesn't resolve."""
    token = make_token(user_id, category)
    if token is None:
        return None
    s = get_settings()
    base = (s.app_url or "https://tapeline.io").rstrip("/")
    return f"{base}/api/unsubscribe?token={token}"


def list_unsubscribe_headers(
    user_id: str, category: str = "all",
) -> dict[str, str]:
    """Return the two RFC 8058 / 2369 headers for a marketing email.

    Gmail renders a native "Unsubscribe" button next to the sender name
    when both headers are present and the URL resolves to a 200 on POST.
    Missing secret → empty dict (orchestrator ships the email without
    the header, deliverability degrades a bit but the email still
    sends).
    """
    url = unsubscribe_url(user_id, category)
    if url is None:
        return {}
    mailto = f"mailto:unsubscribe@tapeline.io?subject=unsub-{category}"
    return {
        "List-Unsubscribe": f"<{mailto}>, <{url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


async def apply_unsubscribe(session, user_id: str, category: str) -> bool:
    """Flip the right bit(s) on User. Returns True if state actually
    changed, False if it was already off / user not found / etc.

    `all`: clears every bit in email_prefs + sets marketing_opt_in=False
    `weekly_newsletter`: clears the bit + marketing_opt_in (since the
                         category itself IS the marketing consent)
    other:               clears just the named bit
    """
    from sqlalchemy import select

    from app.models import User
    from app.services.email_prefs import EmailPref, categories_for_ui

    r = await session.execute(select(User).where(User.id == user_id))
    user = r.scalar_one_or_none()
    if user is None:
        return False

    changed = False
    if category == "all":
        if int(user.email_prefs or 0) != 0:
            user.email_prefs = 0
            changed = True
        if user.marketing_opt_in:
            user.marketing_opt_in = False
            changed = True
    elif category == "weekly_newsletter":
        current = int(user.email_prefs or 0)
        bit = int(EmailPref.WEEKLY_NEWSLETTER)
        if current & bit:
            user.email_prefs = current & ~bit
            changed = True
        if user.marketing_opt_in:
            user.marketing_opt_in = False
            changed = True
    else:
        # Look up the bit for the named category.
        cat = next(
            (c for c in categories_for_ui() if c.key == category), None,
        )
        if cat is not None:
            current = int(user.email_prefs or 0)
            if current & cat.bit:
                user.email_prefs = current & ~cat.bit
                changed = True
    if changed:
        await session.commit()
        logger.info(
            "unsubscribe.applied user=%s category=%s", user_id, category,
        )
    return changed
