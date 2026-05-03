"""
Clerk JWT verification + current-user dependency.

Frontend attaches Clerk session token as `Authorization: Bearer <jwt>`.
In production we verify the signature against Clerk's JWKS before trusting
any claim. Dev mode has a bypass token for local testing without Clerk.
"""
from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.services.tier import Tier

logger = logging.getLogger(__name__)
settings = get_settings()

_JWKS_CACHE: tuple[float, dict[str, Any]] | None = None
_JWKS_TTL_SECONDS = 60 * 60  # 1 hour


async def _get_jwks() -> dict[str, Any]:
    """Fetch and cache Clerk's public JWKS."""
    global _JWKS_CACHE
    if _JWKS_CACHE and (time.time() - _JWKS_CACHE[0]) < _JWKS_TTL_SECONDS:
        return _JWKS_CACHE[1]

    issuer = getattr(settings, "clerk_issuer_url", None) or ""
    if not issuer:
        raise HTTPException(503, "CLERK_ISSUER_URL not configured")

    async with httpx.AsyncClient() as c:
        resp = await c.get(f"{issuer}/.well-known/jwks.json", timeout=10)
        resp.raise_for_status()
        jwks = resp.json()
    _JWKS_CACHE = (time.time(), jwks)
    return jwks


def _b64decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


async def verify_jwt(token: str) -> dict[str, Any]:
    """
    Verify a Clerk JWT against the cached JWKS and return its claims.

    Uses cryptography for RSA signature verification. Does NOT trust the
    payload unless the signature, issuer, and expiry all check out.
    """
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        header = json.loads(_b64decode(header_b64))
        payload = json.loads(_b64decode(payload_b64))
        signature = _b64decode(sig_b64)
    except Exception as exc:
        raise HTTPException(401, f"Malformed token: {exc}") from exc

    # Expiry check
    now = time.time()
    if payload.get("exp") and payload["exp"] < now:
        raise HTTPException(401, "Token expired")
    if payload.get("nbf") and payload["nbf"] > now + 30:
        raise HTTPException(401, "Token not yet valid")

    # Issuer check
    expected_issuer = getattr(settings, "clerk_issuer_url", None) or ""
    if expected_issuer and payload.get("iss") != expected_issuer:
        raise HTTPException(401, "Invalid issuer")

    # Signature check against the matching JWKS key
    kid = header.get("kid")
    jwks = await _get_jwks()
    keys = {k["kid"]: k for k in jwks.get("keys", [])}
    jwk = keys.get(kid)
    if jwk is None:
        raise HTTPException(401, "Unknown signing key")

    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

        n = int.from_bytes(_b64decode(jwk["n"]), "big")
        e = int.from_bytes(_b64decode(jwk["e"]), "big")
        public_key = RSAPublicNumbers(e, n).public_key()
        public_key.verify(
            signature,
            f"{header_b64}.{payload_b64}".encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except Exception as exc:
        raise HTTPException(401, f"Signature verification failed: {exc}") from exc

    return payload


async def current_user_optional(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """
    Resolve the current user from (in priority order):
      1. Native session cookie (tapeline_session) — used by default signup flow
      2. Authorization: Bearer dev-bypass  — dev-only convenience
      3. Authorization: Bearer <clerk-jwt> — used when Clerk is wired in prod

    Returns None if anonymous (= free tier, public endpoints only).
    """
    # 1. Cookie session (primary in native-auth mode)
    from app.services.session import SESSION_COOKIE, verify_session_token

    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        user_id = verify_session_token(cookie)
        if user_id:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user is not None:
                return user

    # 2. Bearer token
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.removeprefix("Bearer ")

    # Dev-only bypass
    if settings.app_env == "development" and token == "dev-bypass":
        result = await session.execute(select(User).where(User.id == "dev_user"))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(id="dev_user", email="dev@tapeline.io", name="Dev", tier="premium")
            session.add(user)
            await session.commit()
        return user

    # Production Clerk JWT
    try:
        claims = await verify_jwt(token)
    except HTTPException:
        return None
    user_id = claims.get("sub")
    if not user_id:
        return None
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def current_user_required(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await current_user_optional(request, session)
    if user is None:
        raise HTTPException(401, "Authentication required")
    return user


def require_tier(min_tier: Tier):
    """FastAPI dependency factory: ensures caller tier >= min_tier."""
    from app.services.tier import _ORDER

    async def dep(user: User = Depends(current_user_required)) -> User:
        if _ORDER[Tier(user.tier)] < _ORDER[min_tier]:
            raise HTTPException(
                403, f"This feature requires {min_tier.value} tier. Upgrade at /app/billing",
            )
        return user
    return dep
