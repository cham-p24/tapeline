"""Institutional holdings — elite-fund 13F positions from Quiver."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class InstitutionalHolding(Base):
    """
    Latest 13F snapshot for one (fund, symbol) pair.

    Refreshed every 24 hours by the worker (`_refresh_elite_13f`). The whole
    table is bulk-replaced on each refresh — we don't keep history here.
    Per-fund history can be added later via a separate `_history` table.
    """
    __tablename__ = "institutional_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    manager: Mapped[str] = mapped_column(String(80), nullable=False)
    cik: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    value_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # BigInteger: large institutions can hold >2.147B shares of a single name.
    shares: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    percent_portfolio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
