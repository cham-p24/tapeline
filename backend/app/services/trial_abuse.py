"""
Trial-abuse prevention.

Two layers stacked on top of the existing honeypot + disposable-email +
Turnstile defences:

1. **Email normalisation.** Gmail (and a few other providers) treat
   `bob+anything@gmail.com` and `b.o.b@gmail.com` as the same inbox. Without
   normalisation, a single attacker can mint unlimited trial accounts using
   tag variations. We normalise at signup-check time so the uniqueness
   constraint on `users.email` rejects duplicates regardless of dot/tag
   permutations.

2. **IP-based signup rate limit.** Tracks signups per IP address in a sliding
   24-hour window in memory. If an IP has already created N (default 3)
   accounts, the next signup attempt 429s. Resets on worker restart — fine
   for the abuse profile we're worried about (drive-by trial farming, not
   coordinated APT). Move to Redis-backed when concurrent fly machines
   exceed one.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


# Email providers that ignore dots and/or +tags in the local part. Updated as
# new providers reveal their address-rewriting rules. Source of truth is the
# provider's own documentation — kept conservative.
_DOTS_AND_PLUS = {
    "gmail.com", "googlemail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com",  # Microsoft strips +tags
}
_PLUS_ONLY = {
    "fastmail.com", "fastmail.fm",
    "icloud.com", "me.com", "mac.com",  # iCloud accepts +tags but doesn't strip dots
    "protonmail.com", "proton.me", "pm.me",
    "yahoo.com",
}


def normalise_email(email: str) -> str:
    """Return the canonical form of an email address.

    For Gmail / Outlook style providers: strip dots in the local part and
    drop everything from `+` onwards. For others that accept `+tags`: just
    drop the `+tag`. For everything else: leave the local part alone.

    Always lowercases the whole address.

    Examples:
        normalise_email("Bob.Smith+launch@gmail.com")   -> "bobsmith@gmail.com"
        normalise_email("alice+spam@fastmail.com")      -> "alice@fastmail.com"
        normalise_email("Carol@example.com")            -> "carol@example.com"
    """
    email = email.strip().lower()
    if "@" not in email:
        return email
    local, _, domain = email.partition("@")
    if domain in _DOTS_AND_PLUS:
        local = local.split("+", 1)[0].replace(".", "")
    elif domain in _PLUS_ONLY:
        local = local.split("+", 1)[0]
    return f"{local}@{domain}"


# ---- IP-based signup rate limit ---------------------------------------------

# Sliding 24h window. Key = IP. Value = deque of unix-epoch timestamps.
# Memory bound: an attacker can fill at most MAX_PER_IP_PER_24H * (number of
# unique IPs) entries; in practice the deque self-prunes on each insert so
# steady-state memory is tiny.
_signup_log: dict[str, deque[float]] = defaultdict(deque)

WINDOW_SECONDS = 24 * 60 * 60
MAX_PER_IP_PER_24H = 3


def signup_allowed(ip: str | None) -> bool:
    """True if this IP can create another account right now.

    Returns True (allowed) when ip is None — falls back to the existing
    layers (honeypot, disposable-email, Turnstile, application-wide rate
    limit) which all run before this check. Better to err on the side of
    letting a legitimate user through than to deny because we couldn't
    read X-Forwarded-For.
    """
    if not ip:
        return True
    now = time.time()
    cutoff = now - WINDOW_SECONDS
    bucket = _signup_log[ip]
    # Prune expired timestamps off the left of the deque.
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    return len(bucket) < MAX_PER_IP_PER_24H


def record_signup(ip: str | None) -> None:
    """Record a successful signup for IP-rate-limit accounting."""
    if not ip:
        return
    _signup_log[ip].append(time.time())


def signup_count_24h(ip: str | None) -> int:
    """Diagnostic — how many signups has this IP made in the last 24h?"""
    if not ip:
        return 0
    now = time.time()
    cutoff = now - WINDOW_SECONDS
    bucket = _signup_log[ip]
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    return len(bucket)


# ---- Device-fingerprint sliding window --------------------------------------
#
# Frontend computes a homemade 16-char fingerprint (lib/fingerprint.ts) and
# sends it with the signup payload. We keep a 30-day sliding window of
# fingerprints that have signed up, so the same browser can't trial-farm
# even with VPN + new email + email-normalisation bypass.
#
# In-memory + per-process — fine while we're on a single Fly machine. Move
# to Redis-backed when concurrent machines exceed one (same constraint as
# `_signup_log`).

_FP_WINDOW_SECONDS = 30 * 24 * 60 * 60
_fingerprint_log: dict[str, deque[float]] = defaultdict(deque)


def fingerprint_allowed(fp: str | None, *, max_in_window: int = 1) -> bool:
    """True if this device fingerprint can create another trial right now.

    Returns True (allowed) when fp is empty/None — the fingerprint is best-
    effort (canvas may be blocked, fp generation may have failed). Honeypot
    + Turnstile + IP cap + email normalisation all run alongside this.
    """
    if not fp:
        return True
    now = time.time()
    cutoff = now - _FP_WINDOW_SECONDS
    bucket = _fingerprint_log[fp]
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    return len(bucket) < max_in_window


def record_fingerprint_signup(fp: str | None) -> None:
    """Record a successful signup keyed by device fingerprint."""
    if not fp:
        return
    _fingerprint_log[fp].append(time.time())


# ---- Abuse-rate health check ------------------------------------------------
#
# Run weekly to detect how much trial-farming is actually happening. This is
# the "measure before you fix" step — only escalate to FingerprintJS / SMS
# verification / card-required if the ratios below show real abuse.
#
# Pure SQL fallback if you'd rather run it in psql / DBeaver:
#
#   SELECT
#       COUNT(*)                                              AS total_signups,
#       COUNT(DISTINCT email)                                 AS distinct_emails,
#       COUNT(DISTINCT split_part(email, '@', 2))             AS distinct_domains,
#       COUNT(*) FILTER (WHERE stripe_customer_id IS NOT NULL) AS converted
#   FROM users
#   WHERE created_at > NOW() - INTERVAL '30 days';
#
# Healthy ratio: total_signups / distinct_emails ≈ 1.0 (every email unique
# after normalisation). Drift toward 1.1+ = abusers slipping through. Conversion
# rate < 5% sustained = a different problem (product/positioning, not abuse).


async def signup_health(session, days: int = 30) -> dict[str, int | float]:
    """Aggregate signup health over the last N days.

    Returns a dict suitable for dropping into a weekly review dashboard or
    JSON response. All counts use the *normalised* email so dot/+tag-only
    duplicates are visible as "duplicate of an existing canonical address".
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func, select

    from app.models import User

    cutoff = datetime.now(UTC) - timedelta(days=days)

    total_q = await session.execute(
        select(func.count()).select_from(User).where(User.created_at >= cutoff)
    )
    total = total_q.scalar() or 0

    distinct_emails_q = await session.execute(
        select(func.count(func.distinct(User.email))).where(User.created_at >= cutoff)
    )
    distinct_emails = distinct_emails_q.scalar() or 0

    converted_q = await session.execute(
        select(func.count()).select_from(User).where(
            User.created_at >= cutoff,
            User.stripe_customer_id.is_not(None),
        )
    )
    converted = converted_q.scalar() or 0

    # Email-uniqueness ratio. >1.0 indicates duplicates that escaped the
    # normaliser (different providers, e.g. Gmail vs Hotmail vs ProtonMail).
    uniq_ratio = round(total / distinct_emails, 3) if distinct_emails > 0 else 0.0
    conv_rate = round(100 * converted / total, 1) if total > 0 else 0.0

    return {
        "window_days": days,
        "total_signups": total,
        "distinct_emails": distinct_emails,
        "uniqueness_ratio": uniq_ratio,
        "converted": converted,
        "conversion_pct": conv_rate,
    }
