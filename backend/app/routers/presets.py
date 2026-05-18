"""/api/presets — saved scanner filter presets (Phase A).

A `ScannerPreset` is a JSON-encoded blob of filter state (sector, score
range, signal, etc.) that the user has saved on /app/scanner so they
can re-apply with one click. Pro+ feature, gated by the existing
`saved_scans` tier cap (Free=0, Pro=10, Premium=100).

Endpoints:

    GET    /api/presets             → list user's presets
    POST   /api/presets  {name, filters_json}  → create (cap-enforced)
    DELETE /api/presets/{id}        → delete

Filter blob shape is intentionally opaque — frontend serialises with
`JSON.stringify`, we store as Text, and the scanner page parses it
back on apply. New filter dimensions added later require zero backend
changes; old presets gracefully lack the new keys.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ScannerPreset, User
from app.services.auth import current_user_required
from app.services.tier import Tier, effective_limit

router = APIRouter()


class PresetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    # 8KB upper bound is comfortable for any realistic filter blob; the
    # column itself is sa.Text so prod can hold more. Pydantic's max_length
    # is the public contract.
    filters_json: str = Field(..., min_length=2, max_length=8000)


@router.get("")
async def list_presets(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    res = await session.execute(
        select(ScannerPreset)
        .where(ScannerPreset.user_id == user.id)
        .order_by(desc(ScannerPreset.created_at))
    )
    rows = res.scalars().all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": p.id,
                "name": p.name,
                "filters_json": p.filters_json,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in rows
        ],
    }


@router.post("")
async def create_preset(
    body: PresetCreate,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "name required")

    # `saved_scans` cap (Free=0 → blocks all creation; Pro=10; Premium=100).
    # Same pattern as the watchlist tickers / watchlists caps.
    cap = effective_limit(user, "saved_scans")
    count_q = await session.execute(
        select(func.count()).select_from(ScannerPreset).where(ScannerPreset.user_id == user.id)
    )
    current = count_q.scalar() or 0
    if current >= cap:
        tier = Tier(user.tier).value
        raise HTTPException(
            403,
            f"Saved-scans limit reached ({cap} on {tier}). "
            f"Delete a preset first, or upgrade for more.",
        )

    # (user_id, name) uniqueness — return 409 instead of 500 on conflict.
    dup_q = await session.execute(
        select(ScannerPreset).where(
            ScannerPreset.user_id == user.id, ScannerPreset.name == name
        )
    )
    if dup_q.scalar_one_or_none() is not None:
        raise HTTPException(409, f"A preset named {name!r} already exists")

    p = ScannerPreset(user_id=user.id, name=name, filters_json=body.filters_json)
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return {
        "id": p.id,
        "name": p.name,
        "filters_json": p.filters_json,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.delete("/{preset_id}")
async def delete_preset(
    preset_id: int,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    res = await session.execute(
        select(ScannerPreset).where(
            ScannerPreset.id == preset_id, ScannerPreset.user_id == user.id
        )
    )
    p = res.scalar_one_or_none()
    if p is None:
        raise HTTPException(404, "Not found")
    await session.delete(p)
    await session.commit()
    return {"ok": True}
