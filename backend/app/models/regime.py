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
    # Advancers today as a % of the names that MOVED today:
    # 100 * advancers / (advancers + decliners), from each row's change_pct_1d.
    # Names with no price read, and names that closed unchanged, are excluded
    # from the denominator. This is a same-day advance/decline ratio — it is
    # NOT the share of the universe above its 200-day moving average, which we
    # do not compute here. Column name kept for compatibility.
    breadth_pct: Mapped[float] = mapped_column(Float, nullable=False)
    # Top 3 sectors by the MEAN of our own composite score across the symbols
    # in that sector, not relative strength vs SPY. Writers pass None when they
    # could not rank them (no sector data, or no scored symbols carrying a known
    # sector this tick); the default coerces that to an em-dash so an unknown
    # renders as "—" instead of a stale or invented list of sector names.
    sector_leaders: Mapped[str] = mapped_column(
        String(300), nullable=False, default="—"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
