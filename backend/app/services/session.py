"""
Native session auth — cookie-based JWT with HS256 signing.

Used when Clerk is not configured (dev + early launch). When Clerk's keys
are set, the Clerk flow takes precedence and this is a fallback.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings

settings = get_settings()
SESSION_COOKIE = "tapeline_session"
SESSION_DAYS = 30


def _session_secret() -> str:
    """Derive a deterministic session-signing secret. If SESSION_SECRET is set,
    use it; else derive one from STRIPE_WEBHOOK_SECRET or fall back to a fixed
    dev string. Production MUST set SESSION_SECRET explicitly."""
    s = getattr(settings, "session_secret", None) or ""
    if s:
        return s
    # Deterministic derivation so restarting doesn't invalidate dev sessions
    base = (settings.stripe_webhook_secret or "tapeline-dev-secret") + "|session"
    return hashlib.sha256(base.encode()).hexdigest()


def hash_password(plain: str) -> str:
    if len(plain) < 8:
        raise ValueError("Password must be at least 8 characters")
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def issue_session_token(user_id: str, session_epoch: int | None = 0) -> str:
    """Issue a signed JWT used as the session cookie payload.

    `session_epoch` is the caller's User.session_epoch at mint time. It is the
    revocation dimension: bumping the column invalidates every token minted
    before the bump (see decode_session_token / session_epoch_matches).
    Callers that mint a session MUST pass the user's current value.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=SESSION_DAYS)).timestamp()),
        "nonce": secrets.token_hex(8),
        "epoch": int(session_epoch or 0),
    }
    return jwt.encode(payload, _session_secret(), algorithm="HS256")


def decode_session_token(token: str) -> tuple[str, int] | None:
    """Return (user_id, epoch_claim) if the cookie's signature + exp are good.

    Deliberately does NO database access — it is on the hot path for every
    authenticated request. The epoch claim is returned so the caller, which
    already has to load the User row anyway, can compare it without paying for
    a second query. See services/auth.current_user_optional.

    A token minted before the epoch existed carries no "epoch" claim and reads
    as 0, which matches the column's default of 0 — so introducing this did not
    invalidate a single outstanding session.
    """
    try:
        payload = jwt.decode(token, _session_secret(), algorithms=["HS256"])
    except Exception:
        return None
    # The 5-minute 2FA challenge token (services/mfa.issue_mfa_token) is signed
    # with this same secret but carries purpose="mfa". It must never be accepted
    # as a full session — defence-in-depth even though it's never set as a cookie.
    if payload.get("purpose") == "mfa":
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str):
        return None
    raw_epoch = payload.get("epoch", 0)
    try:
        epoch = int(raw_epoch)
    except (TypeError, ValueError):
        return None
    return sub, epoch


def verify_session_token(token: str) -> str | None:
    """Return user_id if the cookie's signature + exp are valid, else None.

    NOTE: this checks the token in isolation and therefore does NOT enforce
    revocation. Every caller must additionally compare the epoch claim against
    the loaded user's session_epoch — use decode_session_token +
    session_epoch_matches. Kept for callers that only need the subject.
    """
    decoded = decode_session_token(token)
    return decoded[0] if decoded else None


def session_epoch_matches(stored: int | None, claimed_epoch: int) -> bool:
    """True when a token's epoch claim still matches the user's stored epoch.

    NULL/absent on either side reads as 0 so pre-existing rows and pre-existing
    tokens both land on the same value and stay valid.
    """
    return int(stored or 0) == int(claimed_epoch or 0)


def session_cookie_kwargs() -> dict:
    """Cookie settings safe for both dev (http localhost) and prod (https).

    Prod note: explicitly set domain=".tapeline.io" so the cookie is shared
    between the API subdomain (api.tapeline.io) and the frontend (tapeline.io).
    Without this, the cookie set by the API would only be visible to api.tapeline.io
    and the Next.js middleware on tapeline.io couldn't see it for auth checks.
    """
    kwargs = {
        "key": SESSION_COOKIE,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.app_env != "development",
        "max_age": SESSION_DAYS * 24 * 3600,
        "path": "/",
    }
    # In prod, derive the cookie domain from APP_URL host so the cookie is
    # shared across the apex + api subdomain.
    if settings.app_env != "development":
        try:
            from urllib.parse import urlparse
            host = urlparse(settings.app_url).hostname or ""
            # Strip leading "www." if present so we set the eTLD+1 form
            if host.startswith("www."):
                host = host[4:]
            if host:
                kwargs["domain"] = host  # e.g. "tapeline.io" → covers tapeline.io + *.tapeline.io
        except Exception:
            pass
    return kwargs


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
