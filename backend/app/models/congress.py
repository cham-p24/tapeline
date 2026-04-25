"""Congressional trade disclosures."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CongressTrade(Base):
    __tablename__ = "congress_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    politician: Mapped[str] = mapped_column(String(100), nullable=False)
    chamber: Mapped[str] = mapped_column(String(20), nullable=False)  # House|Senate
    party: Mapped[str] = mapped_column(String(5), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY|SELL
    amount_min: Mapped[float] = mapped_column(Float, nullable=False)
    amount_max: Mapped[float] = mapped_column(Float, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    disclosed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
