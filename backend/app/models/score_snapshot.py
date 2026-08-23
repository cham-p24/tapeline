"""Point-in-time daily archive of every scored ticker — APPEND-ONLY.

Why this table exists: `tickers` is a live, denormalized snapshot that gets
overwritten on every scoring tick. Every trading day that passes without a
point-in-time capture is universe history that can never be regenerated — and a
reconstructable "what did the model say on date X" record is the hard gate
before any data-licensing conversation. `daily_scorecard` only freezes the
filtered top-10; this table freezes the FULL scored universe.

IMMUTABILITY CONTRACT: rows are inserted once (ON CONFLICT DO NOTHING on the
(snapshot_date, symbol) unique key) and never updated or deleted by any code
path. There is deliberately no updated_at / onupdate here. A retro-corrected
archive is worthless as a licensing record; if a day's capture is wrong, it
stays wrong and the flaw is documented, exactly like the public scorecard.
tests/test_score_snapshots.py enforces this both functionally (re-running a
capture is a no-op) and statically (no update()/delete() against this model
anywhere under app/).

Columns mirror the live per-factor score storage on `tickers` (score, the six
sub_* factor scores, confidence_pct) — nothing more. No price/volume/key-stats:
prices are reconstructable from vendor bars at any time; the model's OPINION on
a given day is the thing that is not. No API surface yet either (licensing is
not validated); this is archival only.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ScoreSnapshot(Base):
    """One row per (snapshot_date, symbol): that day's composite + factor scores."""

    __tablename__ = "score_snapshots"
    __table_args__ = (
        # The idempotency anchor: the daily capture INSERTs with
        # ON CONFLICT DO NOTHING against this key, so re-running the capture on
        # the same day (worker restart, retry after a mid-day failure) can only
        # fill gaps, never rewrite what was already captured.
        UniqueConstraint(
            "snapshot_date", "symbol", name="uq_score_snapshots_date_symbol"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # NOT NULL: the capture only archives rows that HAVE a composite score —
    # an unscored ticker has no model opinion to preserve. Float (not Numeric)
    # to mirror `tickers.score` exactly: the archive must reproduce what the
    # live system said, not a re-rounded version of it.
    score: Mapped[float] = mapped_column(Float, nullable=False)

    # Factor scores — mirror of the live sub_* columns on `tickers` (the score
    # breakdown that weighted-sums to `score`). Nullable like the originals:
    # a factor with no data that day is honestly absent, not zero.
    sub_trend: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_rs: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_fundamentals: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_momentum: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_macro: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_smart_money: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Part of the per-ticker score record: how much data backed that day's
    # score (varies with feed coverage). Without it, a thin-data 80 and a
    # full-coverage 80 would be indistinguishable in the archive.
    confidence_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # When the row was captured — NOT when it was last touched. No onupdate,
    # by design: nothing updates these rows.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
