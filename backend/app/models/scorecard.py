"""Daily scorecard — historical record of 'what we said' each day, for public trust-building."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DailyScorecardEntry(Base):
    """One row per (date, symbol) — the top-10 tickers we flagged that day + how they performed."""
    __tablename__ = "daily_scorecard"

    # Composite index serves the symbol-filtered read (GET /api/scorecard/symbol/{symbol}):
    # the equality predicate on `symbol` plus the `ORDER BY as_of DESC` are both satisfied
    # from one B-tree, so the per-ticker history query stops full-scanning as the table grows.
    __table_args__ = (
        Index("ix_daily_scorecard_symbol_as_of", "symbol", "as_of"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..10
    score_at_flag: Mapped[float] = mapped_column(Float, nullable=False)
    price_at_flag: Mapped[float] = mapped_column(Float, nullable=False)

    # Populated by a next-day job that compares performance
    price_next_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct_1d_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    spy_change_pct_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    alpha_vs_spy: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
