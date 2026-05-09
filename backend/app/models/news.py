"""Market news cached from Polygon (or equivalent licensed source)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)  # Polygon article id
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    publisher: Mapped[str] = mapped_column(String(100), nullable=False)
    author: Mapped[str | None] = mapped_column(String(120), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Comma-separated tickers; indexed via LIKE searches (fine at MVP scale).
    # Widened from String(200) → String(2000) in migration 0014 after a
    # production incident where Benzinga round-up articles tagged 50+ symbols
    # broke the entire batch INSERT.
    tickers: Mapped[str] = mapped_column(String(2000), nullable=False, default="", index=True)

    # Simple sentiment score [-1, 1]; Polygon News provides this at Developer+ tier
    sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
