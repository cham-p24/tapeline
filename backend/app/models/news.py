"""Market news cached from Polygon (or equivalent licensed source)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import ColumnElement

from app.db import Base

# Prefix stamped on every synthetic headline minted by
# news_feed._mock_news ("mock-{symbol}-{uuid}"). It is the ONLY deterministic
# mock marker: the mock path reuses real publisher names (Reuters, Bloomberg,
# …) so `publisher` can't be trusted as a discriminator. The boot-time purge in
# workers/signal_publisher.py deletes these rows, but a future _mock_news
# fallback could re-mint them; this prefix is the read-path invariant's anchor.
MOCK_ID_PREFIX = "mock-"


def exclude_mock_clause() -> ColumnElement[bool]:
    """WHERE clause that drops fabricated mock headlines from any read.

    LEGAL invariant: mock headlines include analyst-style "Buy"/"Overweight"
    lines (see news_feed._MOCK_HEADLINES). Tapeline publishes transparent
    historical model output, never fabricated recommendations — so NO public
    news read path may ever serve a `mock-` row, even if the write-path boot
    purge (workers/signal_publisher.py) hasn't run or a future fallback
    re-mints them. Apply on every public NewsItem query::

        stmt = select(NewsItem).where(exclude_mock_clause())

    Defence-in-depth, not a substitute for the write-path purge.
    """
    return NewsItem.id.notlike(f"{MOCK_ID_PREFIX}%")


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
