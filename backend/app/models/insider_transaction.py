"""Insider Form 4 transactions — DB-backed, cross-process.

Replaces the prior in-process `_INSIDER_FEED` list. The worker process
runs the daily Finnhub backfill on Fly machine A and writes rows here;
the API process on Fly machine B reads them. Without DB persistence, the
two machines have isolated in-memory caches and `/api/holdings` returns
empty regardless of how often the worker refreshes (real bug observed
2026-05-16: `feed_size=0` on a freshly-deployed app despite the worker
logging successful Finnhub fetches).

One row per Form 4 line. The natural key is (symbol, transaction_date,
insider_name, share_change, line_seq): `line_seq` numbers the lines that share
the first four values, so two different transactions that happen to match
there (a conversion and a sale of the same share count, equal vesting tranches)
are both kept. We bulk-replace per-symbol on each refresh (delete this symbol's
rows, insert the latest pull) so retraction-of-old-data edge cases also work
cleanly.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
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


class InsiderTransaction(Base):
    """One row per SEC Form 4 line item from Finnhub.

    Powers `/app/holdings` ("Recent Insider Buys") and the per-ticker
    insider tab on `/app/ticker/[symbol]`. Refreshed daily by the
    worker via `_refresh_insider_cache` → `upsert_insider_transactions`.
    """
    __tablename__ = "insider_transactions"
    __table_args__ = (
        # One row per line. `line_seq` separates lines that share the other
        # four values; see `line_seq` below and migration 0071.
        UniqueConstraint(
            "symbol", "transaction_date", "insider_name", "share_change", "line_seq",
            name="uq_insider_natural",
        ),
        # Index for the dominant query: "newest N rows across all symbols".
        Index("ix_insider_date_desc", "transaction_date"),
        # Index for the per-symbol filter (per-ticker InsiderTab).
        Index("ix_insider_symbol_date", "symbol", "transaction_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    insider_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # ISO date string — Finnhub returns YYYY-MM-DD strings; we keep that
    # shape so the existing API JSON contract doesn't change.
    transaction_date: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    share_change: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transaction_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Pre-computed transaction value (abs(share_change) * price) so the
    # API doesn't recompute per row. Helps when sorting by value later.
    transaction_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # SEC Form 4 transaction code: P=purchase (open market or private),
    # S=sale (open market or private),
    # A=grant/award, M=option exercise, G=gift, F=tax via shares, D=disposition,
    # C=conversion of derivative.
    code: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    #: 0 for the first line with a given (transaction_date, insider_name,
    #: share_change), 1 for the next, and so on, in the order the source listed
    #: them. The old four-value key collapsed such lines into one, which dropped
    #: real transactions from EDGAR (migration 0071).
    line_seq: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0",
    )
    #: Where the row came from. "edgar" for every row written since the insider
    #: pass switched to SEC EDGAR (migration 0069); NULL for rows the Finnhub
    #: pass wrote before it, which the switchover re-reads and replaces. The
    #: empty-answer guard in `signal_publisher._clear_smart_money_reading` only
    #: trusts "edgar" rows: a Finnhub row contradicting an EDGAR answer is the
    #: old vendor's attribution, not evidence the answer is wrong.
    source: Mapped[str | None] = mapped_column(String(12), nullable=True, default="edgar")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
