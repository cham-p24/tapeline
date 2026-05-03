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


def issue_session_token(user_id: str) -> str:
    """Issue a signed JWT used as the session cookie payload."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=SESSION_DAYS)).timestamp()),
        "nonce": secrets.token_hex(8),
    }
    return jwt.encode(payload, _session_secret(), algorithm="HS256")


def verify_session_token(token: str) -> str | None:
    """Return user_id if the cookie is valid, else None."""
    try:
        payload = jwt.decode(token, _session_secret(), algorithms=["HS256"])
    except Exception:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


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
