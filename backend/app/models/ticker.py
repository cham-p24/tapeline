"""Master ticker table + latest-score snapshot for the scanner."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, String, func
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
    # Absolute market cap in dollars (nullable — many rows have no read yet).
    # Sourced from the Finnhub company profile, which reports it in MILLIONS,
    # so the populator multiplies by 1e6 before storing. Displayed compactly in
    # the scanner ("Mkt Cap" column); an em-dash renders when null.
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Key statistics — the summary block a reader expects on a ticker page.
    # Storage only; each value is written by the feed that already pays for it,
    # so this comment records which feed owns which column:
    #
    #   SNAPSHOT  — Massive v3 snapshot, polygon_feed._to_scanner_row. Both
    #               `session.previous_close` and `session.open` are already in
    #               the payload today and dropped on the floor.
    #   BARS      — the 365d daily OHLCV bars already pulled per symbol in
    #               signal_publisher._refresh_aggregates_cache (each bar has
    #               o/h/l/c/v/t) and currently reduced to 3 scalars.
    #   METRIC    — Finnhub /stock/metric?metric=all, already requested and
    #               cached for 7 days in finnhub_feed.fetch_fundamentals while
    #               only 6 keys are kept. Widening the keep-list costs ZERO
    #               extra API calls.
    #   EARNINGS  — calendar_events.earnings_events (report_date), populated in
    #               prod and not currently joined to this table.
    #
    # Every column is nullable with NO default: ~72% of the universe has no
    # price/volume read at all, so most bar-derived values are legitimately
    # absent. Null means "we do not have it" and renders as an em-dash — a zero
    # would be a fabricated statistic, which this product must never publish.
    # Bid/ask and the 1-year analyst target are deliberately NOT here: we have
    # no level-1 quote feed and no analyst-target entitlement, so there is no
    # honest value to store.
    previous_close: Mapped[float | None] = mapped_column(Float, nullable=True)   # SNAPSHOT
    day_open: Mapped[float | None] = mapped_column(Float, nullable=True)         # SNAPSHOT
    # Day range, from the SNAPSHOT's `session` object (which does carry high and
    # low). Deliberately not from the daily bars: the bar cache refreshes once
    # per 24h, so a bar-derived "day range" would usually be the PREVIOUS
    # session's range sitting beside a live price — a quote outside its own
    # stated range. Same tick as the price it brackets, or nothing.
    day_high: Mapped[float | None] = mapped_column(Float, nullable=True)         # SNAPSHOT
    day_low: Mapped[float | None] = mapped_column(Float, nullable=True)          # SNAPSHOT
    week52_high: Mapped[float | None] = mapped_column(Float, nullable=True)      # BARS
    week52_low: Mapped[float | None] = mapped_column(Float, nullable=True)       # BARS
    # BigInteger for the same reason as `volume` above — a 30-day average of a
    # multi-billion-share tape still overflows 32-bit INTEGER.
    avg_volume_30d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # BARS
    beta: Mapped[float | None] = mapped_column(Float, nullable=True)             # METRIC
    eps_ttm: Mapped[float | None] = mapped_column(Float, nullable=True)          # METRIC
    # Trailing-twelve-month P/E specifically. Distinct from the `pe` already in
    # the fundamentals keep-list, which prefers peNormalizedAnnual.
    pe_ttm: Mapped[float | None] = mapped_column(Float, nullable=True)           # METRIC
    dividend_yield: Mapped[float | None] = mapped_column(Float, nullable=True)   # METRIC
    # Date, not DateTime — these are calendar dates with no meaningful time of
    # day, and storing a midnight timestamp would invent a precision we lack.
    ex_dividend_date: Mapped[date | None] = mapped_column(Date, nullable=True)   # METRIC
    next_earnings_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # EARNINGS

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
    # sector_leaders/rate_direction live on the regime row, not here — the
    # alert payloads that quote them are built from that row plus this
    # ticker-level data. (The Discord channel that also read them was retired
    # 2026-05-04.)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
