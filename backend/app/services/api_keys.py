"""API-key minting + authentication for the Premium `/api/v1/*` surface.

Three responsibilities:

  1. `generate_key()` — mint a fresh secret. Returns (raw, prefix, key_hash).
     The caller persists prefix + key_hash and shows `raw` to the user ONCE.
  2. `authenticate_api_key()` — resolve a presented key to its owner, enforce
     the Premium tier gate + the rolling daily quota, and bump usage counters.
  3. `api_key_user` — a FastAPI dependency that reads the key off the request
     (`X-API-Key:` header, or `Authorization: Bearer tl_live_...`) and returns
     the authenticated `User`.

Keys look like `tl_live_<32 hex>`. We hash with sha256 — these are
high-entropy random tokens (128 bits), not low-entropy passwords, so a fast
hash is the right call (no need for bcrypt/argon2 work factors; there's
nothing to brute-force against a 2^128 space, and we want O(1) auth on every
API call). We store only the hash + a 16-char identifying prefix.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ApiKey, User
from app.services.tier import effective_limit, has_feature

_KEY_PREFIX = "tl_live_"
# Number of random bytes -> 2x hex chars. 16 bytes = 128 bits = 32 hex chars.
_KEY_BYTES = 16
# Identifying prefix length: "tl_live_" (8) + first 8 hex of the body = 16.
_PREFIX_LEN = 16
# Max live keys per user — generous for real use, caps runaway minting.
MAX_KEYS_PER_USER = 10
# Feature flag gating both minting and authentication (Premium).
API_FEATURE = "api.access"


def hash_key(raw: str) -> str:
    """sha256 hex of the full key. The only form of the secret we persist."""
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_key() -> tuple[str, str, str]:
    """Mint a new key. Returns (raw, prefix, key_hash).

    `raw` is `tl_live_<32 hex>` (40 chars) and is shown to the user exactly
    once. `prefix` is its first 16 chars (stored in clear for identification).
    `key_hash` is sha256(raw).
    """
    raw = f"{_KEY_PREFIX}{secrets.token_hex(_KEY_BYTES)}"
    return raw, raw[:_PREFIX_LEN], hash_key(raw)


def new_key_id() -> str:
    """Opaque row id, `ak_<24 hex>`."""
    return f"ak_{secrets.token_hex(12)}"


def looks_like_key(raw: str | None) -> bool:
    """Cheap shape check before a DB hit — avoids hashing junk."""
    return bool(raw) and raw.startswith(_KEY_PREFIX) and len(raw) == len(_KEY_PREFIX) + _KEY_BYTES * 2


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


async def authenticate_api_key(session: AsyncSession, raw: str | None) -> tuple[User, ApiKey]:
    """Resolve `raw` to (User, ApiKey), enforcing tier + daily quota + usage.

    Raises:
      401 — missing / malformed / unknown key (or orphaned row).
      403 — owner is no longer on a tier with API access (e.g. downgraded).
      429 — the key's owner has spent their daily request quota.

    On success bumps `requests_today` / `request_count_total` / `last_used_at`
    and commits. The quota window is the UTC calendar day; `requests_today`
    rolls to 0 on the first call of a new day.
    """
    if not looks_like_key(raw):
        raise HTTPException(401, "Missing or malformed API key. Pass it as 'X-API-Key: tl_live_...'.")

    # looks_like_key guarantees a well-formed non-None key string here.
    key_hash = hash_key(raw or "")
    row = (
        await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(401, "Invalid API key.")

    user = (
        await session.execute(select(User).where(User.id == row.user_id))
    ).scalar_one_or_none()
    if user is None:
        # Orphaned key (owner deleted) — treat as invalid, don't 500.
        raise HTTPException(401, "Invalid API key.")

    if not has_feature(user.tier, API_FEATURE):
        raise HTTPException(403, "API access requires the Premium plan. Upgrade at /app/billing.")

    cap = effective_limit(user, "api_requests_per_day")
    today = _today()
    if row.requests_day != today:
        row.requests_day = today
        row.requests_today = 0
    if row.requests_today >= cap:
        raise HTTPException(
            429,
            f"Daily API quota of {cap:,} requests reached for this key. Resets at 00:00 UTC.",
        )

    row.requests_today += 1
    row.request_count_total += 1
    row.last_used_at = datetime.now(UTC)
    await session.commit()
    return user, row


def _extract_key(request: Request) -> str | None:
    """Pull the key from `X-API-Key`, else an `Authorization: Bearer tl_live_…`.

    We only treat a Bearer token as a key when it carries our prefix — that
    keeps it from colliding with the cookie/JWT session auth used elsewhere.
    """
    header = request.headers.get("X-API-Key")
    if header:
        return header.strip()
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ").strip()
        if token.startswith(_KEY_PREFIX):
            return token
    return None


async def api_key_context(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> tuple[User, ApiKey]:
    """FastAPI dependency returning BOTH the owner and the key row.

    Use when an endpoint needs the key's quota counters (e.g. `/api/v1/me`).
    Authenticates exactly once — depend on EITHER this OR `api_key_user` in a
    given handler, never both, or the request would be billed twice.
    """
    return await authenticate_api_key(session, _extract_key(request))


async def api_key_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """FastAPI dependency for `/api/v1/*` — returns the authenticated User."""
    user, _key = await authenticate_api_key(session, _extract_key(request))
    return user
