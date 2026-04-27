"""Public roadmap voting — paid users get a vote on what ships next."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import RoadmapVote, User
from app.services.auth import current_user_optional, current_user_required
from app.services.tier import Tier

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/votes")
async def vote_counts(
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(current_user_optional),
) -> dict:
    """
    Aggregate vote count per item slug. Public endpoint — anyone can see
    the totals. If the requester is signed in, also returns which items
    they've personally voted on.
    """
    result = await session.execute(
        select(RoadmapVote.item_slug, func.count(RoadmapVote.id))
        .group_by(RoadmapVote.item_slug)
    )
    counts: dict[str, int] = {row[0]: row[1] for row in result.all()}

    my_votes: list[str] = []
    if user is not None:
        my_r = await session.execute(
            select(RoadmapVote.item_slug).where(RoadmapVote.user_id == user.id)
        )
        my_votes = [r[0] for r in my_r.all()]

    return {"counts": counts, "my_votes": my_votes}


class VoteBody(BaseModel):
    item_slug: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-z0-9_\-]+$")


@router.post("/vote")
async def cast_vote(
    body: VoteBody,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Vote for a roadmap item. Premium-only — voting is part of the
    Premium subscriber benefit (signals that the product evolves
    based on the people paying for it).
    """
    if Tier(user.tier) != Tier.PREMIUM:
        raise HTTPException(403, "Roadmap voting is a Premium feature")

    vote = RoadmapVote(user_id=user.id, item_slug=body.item_slug)
    session.add(vote)
    try:
        await session.commit()
        logger.info("roadmap.vote user=%s slug=%s", user.id, body.item_slug)
    except IntegrityError:
        # User already voted for this item — treat as a no-op success
        await session.rollback()
        return {"ok": True, "duplicate": True}
    return {"ok": True}


@router.delete("/vote")
async def unvote(
    item_slug: str,  # query param, e.g. ?item_slug=mobile-scanner
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Withdraw a previously-cast vote. Query-param-keyed so DELETE has no body."""
    await session.execute(
        delete(RoadmapVote).where(
            RoadmapVote.user_id == user.id,
            RoadmapVote.item_slug == item_slug,
        )
    )
    await session.commit()
    return {"ok": True}
