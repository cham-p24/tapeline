"""Insider Form 4 transactions — DB-backed, cross-process.

Replaces the prior in-process `_INSIDER_FEED` list. The worker process
runs the daily Finnhub backfill on Fly machine A and writes rows here;
the API process on Fly machine B reads them. Without DB persistence, the
two machines have isolated in-memory caches and `/api/holdings` returns
empty regardless of how often the worker refreshes (real bug observed
2026-05-16: `feed_size=0` on a freshly-deployed app despite the worker
logging successful Finnhub fetches).

One row per (symbol, transaction_date, insider_name, share_change)
quad — that's how Finnhub natively de-duplicates so we can safely
INSERT on every refresh and rely on the unique constraint to absorb
collisions. We bulk-replace per-symbol on each daily refresh (delete
this symbol's rows, insert the latest pull) so retraction-of-old-data
edge cases also work cleanly.
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
        # Natural composite uniqueness — Finnhub returns identical rows
        # across runs for the same filing, so we de-dupe on this 4-tuple.
        UniqueConstraint(
            "symbol", "transaction_date", "insider_name", "share_change",
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
    # SEC Form 4 transaction code: P=open-market buy, S=open-market sale,
    # A=grant/award, M=option exercise, G=gift, F=tax via shares, D=disposition,
    # C=conversion of derivative.
    code: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
