"""Emailed sign-in codes + trusted-device memory.

Adds a second factor to password sign-in WITHOUT making every login depend on
email deliverability: a 6-digit code is required only when the browser is not
recognised. A successful code sets a signed "trusted device" cookie, and that
browser signs in normally for TRUSTED_DEVICE_DAYS afterwards.

How it plugs into the existing flow: the TOTP two-step
(/signin -> {mfa_required, mfa_token} -> /2fa) already exists, so an email code
reuses that exact challenge token and endpoint rather than adding a parallel
path. TOTP keeps precedence — a user with an authenticator app is never asked
for an emailed code.

Design notes:

- **Codes are HMAC'd, not bcrypt'd.** A 6-digit code is only 1e6 candidates, so
  a slow hash buys little; what matters is that a DB leak alone can't reveal or
  verify codes, which the keyed HMAC gives us (an attacker also needs
  SESSION_SECRET). The real defence is the short TTL, single use, and the
  per-account attempt cap on /2fa. bcrypt at ~190ms per verify would also make
  the attempt cap itself a CPU-exhaustion lever.
- **user_id is bound into the HMAC input**, so a stolen row can't be replayed
  against a different account.
- **The trusted-device cookie carries session_epoch.** Bumping the epoch
  (sign-out-everywhere, password reset) therefore revokes every remembered
  device for free — no separate table to sweep.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings
from app.services.session import _session_secret

settings = get_settings()

# How long an emailed code stays valid. Long enough to survive slow mail
# delivery + the user switching apps to read it, short enough that a code
# sitting in an unattended inbox stops working quickly.
CODE_TTL_MINUTES = 10

# How long a browser stays trusted after a successful code.
TRUSTED_DEVICE_DAYS = 30

TRUSTED_DEVICE_COOKIE = "tapeline_device"

# Cap on codes ISSUED per account per window — stops someone who knows a
# victim's password (or is just hammering /signin) from mail-bombing them.
# Verification attempts are capped separately by the existing 2fa:{user_id}
# bucket in routers/auth.py.
CODE_ISSUE_MAX = 5
CODE_ISSUE_WINDOW_SECONDS = 900


def generate_code() -> str:
    """A fresh 6-digit numeric code, zero-padded.

    secrets.randbelow (not random) — this is an auth credential. Zero-padding
    matters: "004821" must stay six characters so the user types what they see.
    """
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str, user_id: str) -> str:
    """Keyed hash of a code, bound to the account it was issued for.

    Returns hex sha256 HMAC. Constant-time comparison happens in verify_code.
    """
    msg = f"{user_id}:{code.strip()}".encode()
    return hmac.new(_session_secret().encode(), msg, hashlib.sha256).hexdigest()


def verify_code(code: str, user_id: str, stored_hash: str) -> bool:
    """Constant-time check of a submitted code against a stored hash."""
    return hmac.compare_digest(hash_code(code, user_id), stored_hash)


def code_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(minutes=CODE_TTL_MINUTES)


# ── Trusted device ──────────────────────────────────────────────────────────

def issue_trusted_device_token(user_id: str, session_epoch: int) -> str:
    """Signed token proving THIS browser already passed an emailed code.

    Carries session_epoch so 'sign out everywhere' / password reset (both of
    which bump the epoch) also stop this device being trusted.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "purpose": "trusted_device",
        "epoch": session_epoch,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=TRUSTED_DEVICE_DAYS)).timestamp()),
        "nonce": secrets.token_hex(8),
    }
    return jwt.encode(payload, _session_secret(), algorithm="HS256")


def is_trusted_device(token: str | None, user_id: str, session_epoch: int) -> bool:
    """True if `token` is a live trust token for this user at this epoch."""
    if not token:
        return False
    try:
        payload = jwt.decode(token, _session_secret(), algorithms=["HS256"])
    except Exception:
        # Expired, tampered, or signed with a rotated secret — all mean
        # "not trusted", which just costs the user one emailed code.
        return False
    if payload.get("purpose") != "trusted_device":
        return False
    if payload.get("sub") != user_id:
        return False
    # An epoch bump (sign-out-everywhere / password reset) revokes trust.
    return payload.get("epoch") == session_epoch


def trusted_device_cookie_kwargs() -> dict:
    """Cookie settings for the trust marker.

    Mirrors session_cookie_kwargs (same host/https posture so it behaves
    identically across the apex + api subdomain) but with its own name and a
    much longer lifetime. httponly: JS never needs to read it.
    """
    kwargs: dict = {
        "key": TRUSTED_DEVICE_COOKIE,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.app_env != "development",
        "max_age": TRUSTED_DEVICE_DAYS * 24 * 3600,
        "path": "/",
    }
    if settings.app_env != "development":
        try:
            from urllib.parse import urlparse
            host = urlparse(settings.app_url).hostname or ""
            if host.startswith("www."):
                host = host[4:]
            if host:
                kwargs["domain"] = host
        except Exception:
            pass
    return kwargs


def mask_email(email: str) -> str:
    """'christian@gmail.com' -> 'c*******@gmail.com'.

    Shown on the code-entry screen so the user knows WHICH inbox to check
    without the page leaking the full address to someone who only has the
    password.
    """
    try:
        local, _, domain = email.partition("@")
        if not domain:
            return "your email"
        if len(local) <= 1:
            return f"{local}***@{domain}"
        return f"{local[0]}{'*' * max(3, len(local) - 1)}@{domain}"
    except Exception:
        return "your email"
