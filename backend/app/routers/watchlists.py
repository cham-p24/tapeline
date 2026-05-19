"""/api/watchlists — multi-list CRUD (Phase A).

This sits alongside the legacy `/api/watchlist` (singular) endpoints in
`routers/watchlist.py`. The legacy endpoints stay unchanged — they
operate on items, and now auto-resolve the user's default list when no
`list_id` is passed (a follow-up PR extends them with a `list_id`
query/body field).

Endpoints here manage the LISTS themselves, not their items:

    GET    /api/watchlists                 → list user's lists
    POST   /api/watchlists      {name}     → create new list (cap-enforced)
    PATCH  /api/watchlists/{id} {name}     → rename
    DELETE /api/watchlists/{id}            → delete (cascades to items)

Tier cap: `watchlists` key in services/tier.py (Free=1, Pro=5, Premium=20).
Enforced server-side via `effective_limit(user, "watchlists")` per D2's
"hard 403 with upgrade message" decision in the execution plan.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User, Watchlist, WatchlistItem
from app.services.auth import current_user_required
from app.services.tier import Tier, effective_limit

router = APIRouter()


class WatchlistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class WatchlistRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


async def _serialise_with_counts(
    session: AsyncSession, user_id: str
) -> list[dict]:
    """Return user's lists in display order with per-list item counts.

    One query for lists, one for counts — fine for the cap range
    (Premium=20 lists max). If this grows, switch to a single LEFT JOIN
    + GROUP BY.
    """
    lists_q = await session.execute(
        select(Watchlist)
        .where(Watchlist.user_id == user_id)
        .order_by(Watchlist.sort_order, Watchlist.id)
    )
    lists = lists_q.scalars().all()
    if not lists:
        return []
    counts_q = await session.execute(
        select(WatchlistItem.watchlist_id, func.count())
        .where(WatchlistItem.user_id == user_id)
        .group_by(WatchlistItem.watchlist_id)
    )
    counts = {wid: n for wid, n in counts_q.all() if wid is not None}
    return [
        {
            "id": w.id,
            "name": w.name,
            "sort_order": w.sort_order,
            "item_count": counts.get(w.id, 0),
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in lists
    ]


@router.get("")
async def list_watchlists(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    items = await _serialise_with_counts(session, user.id)
    return {"count": len(items), "items": items}


@router.post("")
async def create_watchlist(
    body: WatchlistCreate,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "name required")

    # Cap check — per D2: hard 403 with upgrade message, matches the
    # existing watchlist_tickers + saved_scans enforcement pattern.
    cap = effective_limit(user, "watchlists")
    existing_q = await session.execute(
        select(func.count()).select_from(Watchlist).where(Watchlist.user_id == user.id)
    )
    current = existing_q.scalar() or 0
    if current >= cap:
        tier = Tier(user.tier).value
        raise HTTPException(
            403,
            f"Watchlist count limit reached ({cap} on {tier}). "
            f"Delete a list first, or upgrade for more.",
        )

    # Uniqueness on (user_id, name) — surface as 409 instead of letting
    # the DB IntegrityError bubble.
    dup_q = await session.execute(
        select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.name == name)
    )
    if dup_q.scalar_one_or_none() is not None:
        raise HTTPException(409, f"A list named {name!r} already exists")

    # New list goes to the end of the user's sort order.
    next_order = current  # existing count happens to equal next available slot
    w = Watchlist(user_id=user.id, name=name, sort_order=next_order)
    session.add(w)
    await session.commit()
    await session.refresh(w)
    return {
        "id": w.id,
        "name": w.name,
        "sort_order": w.sort_order,
        "item_count": 0,
        "created_at": w.created_at.isoformat() if w.created_at else None,
    }


@router.patch("/{list_id}")
async def rename_watchlist(
    list_id: int,
    body: WatchlistRename,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "name required")

    res = await session.execute(
        select(Watchlist).where(Watchlist.id == list_id, Watchlist.user_id == user.id)
    )
    wl = res.scalar_one_or_none()
    if wl is None:
        raise HTTPException(404, "Not found")

    # Same uniqueness check as create.
    if wl.name != name:
        dup_q = await session.execute(
            select(Watchlist).where(
                Watchlist.user_id == user.id,
                Watchlist.name == name,
                Watchlist.id != list_id,
            )
        )
        if dup_q.scalar_one_or_none() is not None:
            raise HTTPException(409, f"A list named {name!r} already exists")

    wl.name = name
    await session.commit()
    return {"id": wl.id, "name": wl.name}


@router.delete("/{list_id}")
async def delete_watchlist(
    list_id: int,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    res = await session.execute(
        select(Watchlist).where(Watchlist.id == list_id, Watchlist.user_id == user.id)
    )
    wl = res.scalar_one_or_none()
    if wl is None:
        raise HTTPException(404, "Not found")
    # Items cascade via FK ON DELETE CASCADE (migration 0022).
    await session.delete(wl)
    await session.commit()
    return {"ok": True}
