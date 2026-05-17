"""User watchlists."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Baseline score when added — "smart alert" fires when current score drifts meaningfully
    baseline_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    alert_threshold_delta: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)

    # Last time the smart-alert evaluator fired an email/Telegram/push for
    # this item. Used to debounce: while a ticker stays above the threshold,
    # we re-fire at most once every 24h (the EOD digest carries the steady-
    # state cadence; this column ensures we don't spam mid-day).
    last_alert_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
