"""Stateless connect tokens for the browser extension.

WHY A TOKEN AND NOT THE SESSION COOKIE
--------------------------------------
`tapeline_session` is `SameSite=Lax`. The web app can use it against
api.tapeline.io because tapeline.io and api.tapeline.io share a registrable
domain and are therefore *same-site*. A browser extension is a different site
entirely (`chrome-extension://…`), so Lax withholds the cookie from its
background fetches. Loosening the cookie to `SameSite=None` for one feature
would weaken CSRF posture across the whole product, so the extension gets its
own bearer credential instead.

WHY STATELESS
-------------
No new table and no migration: the token carries the user id and the user's
`session_epoch`, signed with the same HMAC secret the unsubscribe links use.
Binding to the epoch is what makes it revocable — "sign out everywhere" bumps
`session_epoch`, which invalidates every extension token that user ever minted,
using machinery that already exists.

Tokens also carry an issue date and expire, so a token pasted into an extension
on a shared machine does not live forever.
"""
from __future__ import annotations

import base64
import hmac
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256

from app.config import get_settings

# Long enough that a user is not re-connecting constantly, short enough that an
# abandoned install stops working within a season.
TOKEN_DAYS = 180
_PREFIX = "tlx_"


def _secret() -> bytes | None:
    raw = (get_settings().session_secret or "").strip()
    return raw.encode("utf-8") if raw else None


def _sign(secret: bytes, payload: str) -> str:
    return hmac.new(secret, payload.encode(), sha256).hexdigest()


def make_token(user_id: str, session_epoch: int) -> str | None:
    """Mint a connect token, or None when the signing secret is unconfigured.

    Callers must treat None as "cannot connect right now" rather than issuing
    an unsigned credential.
    """
    secret = _secret()
    if secret is None:
        return None
    issued = date.today().isoformat()
    payload = f"{user_id}|{int(session_epoch)}|{issued}"
    raw = f"{payload}|{_sign(secret, payload)}".encode()
    return _PREFIX + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def parse_token(token: str | None) -> tuple[str, int] | None:
    """Verify shape, signature and expiry. Returns (user_id, session_epoch).

    Returns None on every failure mode — wrong prefix, bad base64, tampered
    signature, malformed or expired date. The caller rejects without
    distinguishing, so a probe learns nothing from the response.
    """
    secret = _secret()
    if secret is None or not token or not token.startswith(_PREFIX):
        return None
    body = token[len(_PREFIX) :]
    try:
        pad = "=" * (-len(body) % 4)
        raw = base64.urlsafe_b64decode(body + pad)
        # Base64 is malleable at the tail: when the payload length is not a
        # multiple of 3, the final character carries "don't care" low bits, so
        # several distinct characters decode to the SAME bytes. Without this
        # check a token whose last character has been altered still decodes to
        # a valid payload and passes the HMAC — the signature covers the
        # decoded payload, not the string that encoded it.
        #
        # That is not privilege escalation (the decoded identity is unchanged),
        # but it means one session can be expressed as several distinct token
        # strings, which defeats anything that treats the token string as an
        # identifier — a revocation list, a dedupe key, a rate-limit bucket.
        # Requiring the canonical encoding makes the string and the identity
        # one-to-one.
        #
        # It also removes a latent, date-dependent test flake: the payload
        # embeds today's date, so whether the tail character has spare bits
        # changes with the length of the encoded payload — making
        # test_tampered_signature_is_rejected pass or fail depending on the day
        # it runs.
        if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != body:
            return None
        decoded = raw.decode()
        user_id, epoch_s, issued, sig = decoded.split("|")
    except Exception:
        return None

    expected = _sign(secret, f"{user_id}|{epoch_s}|{issued}")
    if not hmac.compare_digest(sig, expected):
        return None

    try:
        issued_at = datetime.fromisoformat(issued).replace(tzinfo=UTC)
    except ValueError:
        return None
    if datetime.now(UTC) - issued_at > timedelta(days=TOKEN_DAYS):
        return None

    try:
        return user_id, int(epoch_s)
    except ValueError:
        return None
