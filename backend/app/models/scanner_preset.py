"""Saved scanner filter presets.

A `ScannerPreset` is a JSON-encoded blob of filter state (sector, score
range, signal, etc.) the user has saved on /app/scanner so they can
re-apply it with one click. Pro/Premium feature gated by the existing
`saved_scans` tier cap (Free=0 blocks creation; Pro=10; Premium=100).

Schema is minimal — `filters_json` carries the entire serialised filter
state the frontend passes. Keeping it opaque means we can add new
filter dimensions on the scanner page (e.g. confidence-pct cutoff)
without backend changes — old presets just lack the new keys, the
frontend tolerates `undefined`.

Per-user uniqueness on `name` so the dropdown doesn't show duplicates.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ScannerPreset(Base):
    __tablename__ = "scanner_presets"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_scanner_presets_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(60), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Text rather than JSON column so SQLite + Postgres handle the same
    # column type. Frontend serialises with JSON.stringify; we don't
    # validate the shape server-side — any non-empty string is accepted.
    # Max 8KB is generous for ~30 filter fields; trim earlier in the
    # router if abuse becomes a concern.
    filters_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
