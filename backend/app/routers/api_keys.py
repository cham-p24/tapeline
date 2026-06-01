"""/api/api-keys — Premium API-key management (session-authenticated).

The in-app surface a Premium user uses to mint, list, and revoke the keys that
authenticate against `/api/v1/*`. Distinct from `services/api_keys.py` (which
does the minting + request-time authentication) — this router is the CRUD UI
backend, gated by the normal cookie/JWT session, not by an API key.

    POST   /api/api-keys   {name}   → mint (Premium-only, MAX_KEYS_PER_USER cap)
    GET    /api/api-keys            → list the caller's keys (never the secret)
    DELETE /api/api-keys/{id}       → revoke (hard delete; the key stops working)

The full secret is returned exactly once, in the POST response. Every other
response carries only the identifying `prefix`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ApiKey, User
from app.services.api_keys import MAX_KEYS_PER_USER, generate_key, new_key_id
from app.services.auth import current_user_required, require_tier
from app.services.tier import Tier, effective_limit

router = APIRouter()


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


def _public_row(k: ApiKey, daily_limit: int) -> dict:
    """Serialise a key WITHOUT its secret. `daily_limit` is the owner's current
    per-day cap so the UI can render "X / limit used today"."""
    # The stored counter only means "today" if its day-stamp is today; a stale
    # stamp (key unused since a prior day) reads as 0 used so far today.
    from datetime import UTC, datetime

    used_today = k.requests_today if k.requests_day == datetime.now(UTC).strftime("%Y-%m-%d") else 0
    return {
        "id": k.id,
        "name": k.name,
        "prefix": k.prefix,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "requests_today": used_today,
        "daily_limit": daily_limit,
        "request_count_total": k.request_count_total,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    }


@router.get("")
async def list_api_keys(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = (
        await session.execute(
            select(ApiKey).where(ApiKey.user_id == user.id).order_by(desc(ApiKey.created_at))
        )
    ).scalars().all()
    daily_limit = effective_limit(user, "api_requests_per_day")
    return {
        "count": len(rows),
        "daily_limit": daily_limit,
        "max_keys": MAX_KEYS_PER_USER,
        "items": [_public_row(k, daily_limit) for k in rows],
    }


@router.post("")
async def create_api_key(
    body: ApiKeyCreate,
    user: User = Depends(require_tier(Tier.PREMIUM)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "name required")

    current = (
        await session.execute(
            select(func.count()).select_from(ApiKey).where(ApiKey.user_id == user.id)
        )
    ).scalar() or 0
    if current >= MAX_KEYS_PER_USER:
        raise HTTPException(
            409,
            f"You already have the maximum of {MAX_KEYS_PER_USER} API keys. "
            "Revoke one before creating another.",
        )

    raw, prefix, key_hash = generate_key()
    row = ApiKey(id=new_key_id(), user_id=user.id, name=name, prefix=prefix, key_hash=key_hash)
    session.add(row)
    await session.commit()
    await session.refresh(row)

    daily_limit = effective_limit(user, "api_requests_per_day")
    # The ONLY response that includes the plaintext key.
    return {**_public_row(row, daily_limit), "key": raw}


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = (
        await session.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Not found")
    await session.delete(row)
    await session.commit()
    return {"ok": True}
