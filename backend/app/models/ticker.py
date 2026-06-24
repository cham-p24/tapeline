"""Master ticker table + latest-score snapshot for the scanner."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Ticker(Base):
    __tablename__ = "tickers"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(80), nullable=True)
    asset_class: Mapped[str] = mapped_column(String(20), default="equity", nullable=False)

    # Latest score snapshot (denormalized for fast scanner reads)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct_5d: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct_1m: Mapped[float | None] = mapped_column(Float, nullable=True)
    # BigInteger: 32-bit INTEGER overflowed on high-turnover names (e.g. ADTX
    # ~5.28B shares > 2.147B int max), failing the whole scan-tick bulk write.
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Score breakdown — the synthesis moat. Always sums (weighted) to `score`.
    sub_trend: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_rs: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_fundamentals: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_momentum: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_macro: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_smart_money: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Per-ticker confidence (0-100) — varies with which underlying data feeds
    # returned data. Mega-caps with full Finnhub/FINRA coverage hit ~90+;
    # less-followed names where fundamentals or smart-money data is sparse
    # land in the 40-60 band. Surfaced in the scanner so users can deprioritise
    # signals built on thin data. Pattern ported from the personal signal-system.
    confidence_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # Discord webhook deliveries also need sector_leaders/rate_direction,
    # both still coming from the regime row — left here because it's the
    # ticker-level data that drives them.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
