"""TOTP two-factor auth helpers.

Self-contained so the 2FA feature touches one service file. Covers:
  - TOTP secret generation + verification (pyotp), with a spent-time-step
    guard so a code can't be replayed inside its own validity window
  - otpauth:// provisioning URI + QR rendering (segno → inline SVG)
  - single-use recovery codes (80-bit, bcrypt-hashed; legacy sha256 rows are
    still accepted on the verify path so nobody is locked out)
  - the short-lived "MFA challenge" JWT used by the two-step signin flow

Both pyotp and segno are pure-Python with no system-library deps, so they
install cleanly on Fly.io without extra build steps.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import re
import secrets
from datetime import UTC, datetime, timedelta

import jwt
import pyotp
import segno

from app.services.session import _session_secret, hash_password, verify_password

ISSUER = "Tapeline"
RECOVERY_CODE_COUNT = 10
MFA_TOKEN_MINUTES = 5  # how long the post-password challenge token is valid

# Entropy per recovery code, in bytes. 10 bytes = 80 bits.
#
# Was 5 bytes (40 bits), which is only 1.1e12 candidates — a commodity GPU
# does >1e10 raw SHA-256/s, so the whole keyspace fell in about two minutes,
# and because the old hash was unsalted ONE such pass resolved every row in
# the table simultaneously. 80 bits puts brute force out of reach even before
# bcrypt's work factor is applied.
RECOVERY_CODE_BYTES = 10


# ── TOTP ────────────────────────────────────────────────────────────────────

def generate_totp_secret() -> str:
    """A fresh base32 secret for a new authenticator enrolment."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    """otpauth:// URI an authenticator app reads from the QR code."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def verify_totp_step(
    secret: str, code: str, last_step: int | None = None,
) -> int | None:
    """Return the TOTP time-step `code` belongs to, or None if it isn't valid.

    Replaces a bare `pyotp.verify(code, valid_window=1)`, which returned a bool
    and recorded nothing. A ±1 window means a single 6-digit code is acceptable
    for ~90 seconds, so with no record of what had been spent the same code
    could be replayed — including by an attacker who watched the real owner use
    it (real-time phishing proxy, shoulder-surf, shared-screen recording) and
    then signed in with it themselves.

    `last_step` is the caller's User.totp_last_step. Any step at or below it has
    already been spent and is refused, which restores the one-time property.
    Pass None for "never completed a challenge" — NOT 0, which would wrongly
    reject the genuine first login of a clock set to the epoch.

    The caller MUST persist the returned step to users.totp_last_step in the
    same transaction that acts on the successful verification.

    The ±1 window itself is kept: it absorbs modest clock skew between the
    user's phone and our server, and burning the step is what makes it safe.
    """
    if not secret or not code:
        return None
    code = code.strip().replace(" ", "")
    if not code.isdigit():
        return None
    try:
        totp = pyotp.TOTP(secret)
        now = datetime.now(UTC)
        now_step = totp.timecode(now)
        for offset in (-1, 0, 1):
            step = now_step + offset
            if last_step is not None and step <= int(last_step):
                continue  # already spent
            if hmac.compare_digest(totp.at(now, counter_offset=offset), code):
                return step
    except Exception:
        return None
    return None


def verify_totp(secret: str, code: str) -> bool:
    """True if `code` is a valid 6-digit TOTP for `secret`.

    NO REPLAY GUARD — this is the window check only. Any caller that mints a
    session or changes account state must use verify_totp_step() and persist
    the returned step instead.
    """
    return verify_totp_step(secret, code, None) is not None


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
    """Plaintext recovery codes, shown to the user exactly once.

    80 bits each (see RECOVERY_CODE_BYTES), dash-grouped in fives for
    legibility: "a1b2c-d3e4f-5a6b7-c8d9e". normalise_recovery_code strips the
    dashes, so the user may type them or not.
    """
    codes: list[str] = []
    width = RECOVERY_CODE_BYTES * 2  # hex chars
    for _ in range(n):
        raw = secrets.token_hex(RECOVERY_CODE_BYTES)
        codes.append("-".join(raw[i:i + 5] for i in range(0, width, 5)))
    return codes


def normalise_recovery_code(code: str) -> str:
    """Canonical form for hashing/compare: lowercase, no dashes/whitespace.
    Lets the user type the code with or without the dash, any case."""
    return code.strip().lower().replace("-", "").replace(" ", "")


def hash_recovery_code(code: str) -> str:
    """Hash a recovery code for storage — bcrypt, per-row salt.

    Was an unsalted single-round sha256, which meant one GPU pass over the
    shared 40-bit keyspace cracked every row in mfa_recovery_codes at once.
    bcrypt is salted and stretched, so each row now costs its own full attack.

    A bcrypt hash is exactly 60 chars and the column is String(64), so this
    needed no migration. Codes already stored as sha256 are still accepted on
    the verify path — see verify_recovery_code — so nobody is locked out.
    """
    return hash_password(normalise_recovery_code(code))


def legacy_sha256_recovery_hash(code: str) -> str:
    """The pre-bcrypt storage format. Verify-only: never write this again."""
    return hashlib.sha256(normalise_recovery_code(code).encode()).hexdigest()


_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def verify_recovery_code(code: str, stored_hash: str | None) -> bool:
    """Check a typed code against ONE stored hash, in either format.

    Format is detected from the stored value, not from configuration: a 64-char
    lowercase hex digest is a legacy sha256 row, anything else (bcrypt is 60
    chars and starts "$2b$") goes through bcrypt. That keeps every recovery
    code minted before this change working exactly as it did.

    Callers must loop the user's unused rows — bcrypt salts per row, so there
    is no indexed hash lookup any more.
    """
    if not code or not stored_hash:
        return False
    normalised = normalise_recovery_code(code)
    if _SHA256_HEX.match(stored_hash):
        return hmac.compare_digest(
            hashlib.sha256(normalised.encode()).hexdigest(), stored_hash,
        )
    return verify_password(normalised, stored_hash)


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
