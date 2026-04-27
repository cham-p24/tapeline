"""Public-roadmap voting — paid users vote on what ships next."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RoadmapVote(Base):
    """One row per (user, roadmap item) pair. Compound unique constraint
    means each user can vote at most once per item. Items are slug-keyed
    so the frontend roadmap page can hardcode the items list and the
    backend just tracks votes by slug.
    """
    __tablename__ = "roadmap_votes"
    __table_args__ = (UniqueConstraint("user_id", "item_slug", name="uq_roadmap_votes_user_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    item_slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    voted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
