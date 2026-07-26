"""Personal watchlist track record — per-user daily snapshot + next-day-vs-SPY.

The public `daily_scorecard` (models/scorecard.py) freezes the ALGO's top-10 each
session and back-checks it. This table is the Premium, per-user analogue: for
every ticker in a Premium user's watchlist we freeze the same (score, price,
signal) each trading-day close and the same daily back-check job fills the
next-day return, SPY's move, and the alpha — so a user gets an on-the-record
track record for THEIR chosen names, whether or not they ever hit the public
top-10.

Deliberately NOT one shared row per symbol: the snapshot is keyed on
(user_id, symbol, as_of) because a symbol can be freshly added to one user's
watchlist and long-held in another's, and each user's "since I added it" story
is theirs. The back-check dedupes the vendor fetch per (symbol, as_of) so the
row count doesn't cost extra API calls.

Columns mirror DailyScorecardEntry so the frontend can reuse the same
ScorecardEntry-shaped row renderer; `user_id` + `signal_at_flag` are the only
additions (the public scorecard stores neither).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WatchlistTrackRecordEntry(Base):
    """One frozen (user, symbol, session) snapshot + its next-day back-check."""

    __tablename__ = "watchlist_track_record"

    __table_args__ = (
        # A given user snapshots a symbol at most once per session.
        UniqueConstraint(
            "user_id", "symbol", "as_of", name="uq_wl_trackrecord_user_symbol_asof"
        ),
        # The per-user read (GET /api/watchlist/track-record) filters by user_id
        # and orders by as_of desc per symbol — this covers both.
        Index("ix_wl_trackrecord_user_asof", "user_id", "as_of"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(60), ForeignKey("users.id"), nullable=False, index=True
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)

    score_at_flag: Mapped[float] = mapped_column(Float, nullable=False)
    price_at_flag: Mapped[float] = mapped_column(Float, nullable=False)
    # The public scorecard doesn't persist the signal; the personal view shows
    # it, so we keep it at flag time (nullable — a ticker can lack a signal).
    signal_at_flag: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Populated by the next-day back-check (services/watchlist_trackrecord.py).
    price_next_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct_1d_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    spy_change_pct_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    alpha_vs_spy: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
