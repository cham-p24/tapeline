"""GET /api/congress — recent congressional trades. Premium-only.

Pre-2026-05-16 this route was anonymous-readable, which leaked the
Premium-only Congress feed to anyone hitting the API directly even
though the frontend gates the /app/congress page. Fixed by requiring
auth + checking the canonical `congress.feed` flag from services/tier.

2026-07-18 — GET /api/congress/preview added. The full feed 403s for
Free/Pro, which meant /app/congress rendered an upgrade card floating
over a literally empty table: the "blur as tease" showed nothing at
all. The preview returns the 3 most recently disclosed REAL trades
plus the real total row count, so the page can render populated rows
and state the true held-back count. Mirrors routers/squeeze.py's
free-taste pattern.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import CongressTrade, User
from app.services.auth import current_user_required
from app.services.tier import Tier, has_feature

router = APIRouter()

# How many disclosures the FREE preview returns. Deliberately tiny — enough to
# prove the feed is real and populated, nowhere near enough to replace the
# Premium feed.
FREE_CONGRESS_PREVIEW_LIMIT = 3


def _serialize(r: CongressTrade) -> dict:
    return {
        "id": r.id,
        "politician": r.politician,
        "chamber": r.chamber,
        "party": r.party,
        "symbol": r.symbol,
        "direction": r.direction,
        "amount_min": r.amount_min,
        "amount_max": r.amount_max,
        "trade_date": r.trade_date.isoformat(),
        "disclosed_at": r.disclosed_at.isoformat(),
    }


@router.get("/preview")
async def congress_preview(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
) -> dict:
    """Read-only 3 most-recent disclosures — a FREE taste of the Congress feed.

    Requires login (not anonymous) so this never re-opens the public scrape
    surface the main feed was locked down to close in 2026-05.

    `total_disclosures` is a real COUNT(*) over the table so the frontend's
    locked section can state the true held-back number rather than inventing
    one. If the table is empty the count is 0 and the UI omits the number.
    """
    stmt = (
        select(CongressTrade)
        .order_by(desc(CongressTrade.disclosed_at))
        .limit(FREE_CONGRESS_PREVIEW_LIMIT)
    )
    rows = (await session.execute(stmt)).scalars().all()
    total_disclosures = (
        await session.execute(select(func.count()).select_from(CongressTrade))
    ).scalar_one()
    return {
        "count": len(rows),
        "preview": True,
        "limit": FREE_CONGRESS_PREVIEW_LIMIT,
        "total_disclosures": total_disclosures,
        "items": [_serialize(r) for r in rows],
    }


@router.get("")
async def list_congress(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    if not has_feature(Tier(user.tier), "congress.feed"):
        raise HTTPException(403, "Congressional trades are a Premium feature")
    stmt = (
        select(CongressTrade)
        .order_by(desc(CongressTrade.disclosed_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return {
        "count": len(rows),
        "items": [_serialize(r) for r in rows],
    }
