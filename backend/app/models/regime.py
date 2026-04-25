"""Market regime snapshot — single row, updated each tick."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RegimeState(Base):
    __tablename__ = "regime_state"

    # Fixed single-row table; id always = 1
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    regime: Mapped[str] = mapped_column(String(20), nullable=False)  # BULL|NEUTRAL|CAUTIOUS|BEAR
    vix: Mapped[float] = mapped_column(Float, nullable=False)
    dxy: Mapped[float] = mapped_column(Float, nullable=False)
    yield_10y: Mapped[float] = mapped_column(Float, nullable=False)
    rate_direction: Mapped[str] = mapped_column(String(20), nullable=False)
    breadth_pct: Mapped[float] = mapped_column(Float, nullable=False)  # % above 200DMA
    sector_leaders: Mapped[str] = mapped_column(String(300), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
