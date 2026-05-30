"""TOTP two-factor auth helpers.

Self-contained so the 2FA feature touches one service file. Covers:
  - TOTP secret generation + verification (pyotp)
  - otpauth:// provisioning URI + QR rendering (segno → inline SVG)
  - single-use recovery codes (generate + sha256 hashing)
  - the short-lived "MFA challenge" JWT used by the two-step signin flow

Both pyotp and segno are pure-Python with no system-library deps, so they
install cleanly on Fly.io without extra build steps.
"""
from __future__ import annotations

import hashlib
import io
import secrets
from datetime import UTC, datetime, timedelta

import jwt
import pyotp
import segno

from app.services.session import _session_secret

ISSUER = "Tapeline"
RECOVERY_CODE_COUNT = 10
MFA_TOKEN_MINUTES = 5  # how long the post-password challenge token is valid


# ── TOTP ────────────────────────────────────────────────────────────────────

def generate_totp_secret() -> str:
    """A fresh base32 secret for a new authenticator enrolment."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    """otpauth:// URI an authenticator app reads from the QR code."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def verify_totp(secret: str, code: str) -> bool:
    """True if `code` is a valid 6-digit TOTP for `secret`.

    valid_window=1 accepts the adjacent 30s steps either side of now, which
    absorbs modest clock skew between the user's phone and our server.
    """
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit():
        return False
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=1)
    except Exception:
        return False


def qr_svg(uri: str) -> str:
    """Render an otpauth URI as an inline SVG string.

    Rendered server-side so the frontend needs no QR library. Forced
    black-on-white (not transparent) so it stays scannable on our dark
    theme — the settings page wraps it in a white box too. `xmldecl=False`
    drops the <?xml?> prolog so the markup drops straight into the DOM via
    dangerouslySetInnerHTML.
    """
    qr = segno.make(uri, error="m")
    buf = io.BytesIO()
    qr.save(
        buf,
        kind="svg",
        scale=5,
        border=2,
        dark="#000000",
        light="#ffffff",
        xmldecl=False,
    )
    return buf.getvalue().decode("utf-8")


# ── Recovery codes ───────────────────────────────────────────────────────────

def generate_recovery_codes(n: int = RECOVERY_CODE_COUNT) -> list[str]:
    """Plaintext recovery codes, shown to the user exactly once. Dash-grouped
    for legibility, e.g. "a1b2c-d3e4f"."""
    codes: list[str] = []
    for _ in range(n):
        raw = secrets.token_hex(5)  # 10 hex chars
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def normalise_recovery_code(code: str) -> str:
    """Canonical form for hashing/compare: lowercase, no dashes/whitespace.
    Lets the user type the code with or without the dash, any case."""
    return code.strip().lower().replace("-", "").replace(" ", "")


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(normalise_recovery_code(code).encode()).hexdigest()


# ── MFA challenge token (two-step signin) ────────────────────────────────────
#
# After a correct password, signin returns one of these instead of a session
# cookie when the account has 2FA on. The client posts it back to
# /api/auth/2fa alongside a live code. It's signed with the same secret as the
# session cookie but carries purpose="mfa" + a 5-minute expiry, and
# verify_session_token() explicitly rejects purpose=="mfa" so it can never be
# replayed as a full session.

def issue_mfa_token(user_id: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "purpose": "mfa",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=MFA_TOKEN_MINUTES)).timestamp()),
        "nonce": secrets.token_hex(8),
    }
    return jwt.encode(payload, _session_secret(), algorithm="HS256")


def verify_mfa_token(token: str) -> str | None:
    """Return the user_id if the challenge token is valid + unexpired, else None."""
    try:
        payload = jwt.decode(token, _session_secret(), algorithms=["HS256"])
    except Exception:
        return None
    if payload.get("purpose") != "mfa":
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None
