"""Bollinger Band squeeze + volume expansion detections."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SqueezeSetup(Base):
    __tablename__ = "squeeze_setups"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    spike_score: Mapped[float] = mapped_column(Float, nullable=False)
    squeeze_days: Mapped[int] = mapped_column(Integer, nullable=False)
    volume_multiple: Mapped[float] = mapped_column(Float, nullable=False)
    obv_trend: Mapped[str] = mapped_column(String(20), nullable=False)
    breakout_type: Mapped[str] = mapped_column(String(40), nullable=False)
    suggested_window: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
