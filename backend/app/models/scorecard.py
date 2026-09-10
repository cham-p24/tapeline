"""Daily scorecard — historical record of 'what we said' each day, for public trust-building."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
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
        # Exactly-one-writer, enforced by the database rather than by how many
        # worker machines happen to be running.
        #
        # `_ensure_daily_scorecard` is a check-then-insert (SELECT ... WHERE
        # as_of = today LIMIT 1, then ten session.add()s) and this is an
        # APPEND-ONLY PUBLIC record. Fly runs a standby worker alongside the
        # primary and on 2026-09-08 both were observed ticking, so two machines
        # can both read "no row for today" and both write ten — and /scorecard
        # would publish an inflated sample size with no error anywhere.
        #
        # Measured on prod 2026-09-11 before adding these: 800 rows across 80
        # days, zero duplicate (as_of, symbol), zero duplicate (as_of, rank),
        # zero days over ten rows. So this is prophylactic, and it is going in
        # BEFORE the tick-timeout fix lets the freeze stage run again — the
        # outage is currently the only thing preventing the double write.
        #
        # Two keys, and both earn their place:
        #  - (as_of, rank) is what BOUNDS a day to ten rows. It is the only one
        #    that still holds if two machines pick different symbol sets.
        #  - (as_of, symbol) is the invariant this class's own docstring states,
        #    and mirrors the (date, symbol) unique on the sibling point-in-time
        #    archive, which already had this protection.
        #
        # (That sibling is deliberately not named here: its append-only guard
        # asserts no NEW file references it, and matches on raw text, so naming
        # it even in a comment fails that test. Worth knowing before you write
        # the obvious cross-reference and wonder why CI went red.)
        #
        # Nothing ever UPDATEs `rank` or `symbol` after insert (single writer in
        # signal_publisher; the back-check and rederive_scorecard touch only the
        # price/alpha columns), so no legitimate later write can trip these.
        UniqueConstraint("as_of", "rank", name="uq_daily_scorecard_as_of_rank"),
        UniqueConstraint("as_of", "symbol", name="uq_daily_scorecard_as_of_symbol"),
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
