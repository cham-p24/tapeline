"""User watchlists.

Two-level model:

  Watchlist (parent) — id, user_id, name, sort_order, created_at
    └── WatchlistItem (child) — id, watchlist_id, user_id, symbol, ...

The `watchlist_id` FK on `WatchlistItem` is nullable for backwards
compatibility with rows that pre-date the multi-list migration
(0022). The migration creates a default "My Watchlist" for every user
with existing items and back-fills watchlist_id, so production should
never see a NULL after the migration runs — the nullability is just an
escape hatch in case a future code path adds an item without specifying
a list (e.g. the legacy POST /api/watchlist endpoint, which now
auto-resolves to the user's default list).

Tier caps (see services/tier.py):
  Free    → 1 list  (matches the current single-list UX exactly)
  Pro     → 5 lists
  Premium → 20 lists

The `watchlist_tickers` cap (5/50/200) still applies to total items
across all lists, not per-list — keeps the model simple.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Watchlist(Base):
    """A named bucket of watchlist items belonging to one user.

    Free users get one (auto-created "My Watchlist"). Pro+ can rename,
    create more, delete. Deleting a list cascades to its items via the
    FK ON DELETE CASCADE in migration 0022 — there's no orphan state.
    """

    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # sort_order lets the UI render tabs in user-defined order without a
    # separate ordering table. The first list created gets 0, each new one
    # gets MAX+1. Renumbering is a frontend concern (drag-to-reorder).
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    # Nullable for migration safety. After 0022 backfills, every prod row
    # has a non-NULL watchlist_id pointing at the user's default list.
    # ondelete="CASCADE" mirrors the parent's delete semantics: removing
    # a list removes its items.
    watchlist_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("watchlists.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Baseline score when added — "smart alert" fires when current score drifts meaningfully
    baseline_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    alert_threshold_delta: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)

    # Last time the smart-alert evaluator fired an email/Telegram/push for
    # this item. Used to debounce: while a ticker stays above the threshold,
    # we re-fire at most once every 24h (the EOD digest carries the steady-
    # state cadence; this column ensures we don't spam mid-day).
    last_alert_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
