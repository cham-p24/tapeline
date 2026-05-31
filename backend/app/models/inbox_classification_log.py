"""Inbox bot — audit + cost-tracking row for every LLM classification.

One row per Anthropic API call made by `services/inbox_classifier.py`.
Rule-based fast-path matches don't write here — only the LLM path does.

Two consumers:

  - **`services/inbox_kill_switch.spend_today()`** sums `cost_usd` over the
    current UTC day to enforce `INBOX_CLAUDE_DAILY_CAP_USD`. Once tripped,
    the classifier downgrades every ambiguous message to Tier 1 manual
    review (the safe default) until midnight UTC.
  - **`GET /api/inbox/stats`** (admin-only) reads this table to surface
    tier-counts, cache-hit rates, p50/p95 latency, and today's spend vs cap.
    Rendered as the chip strip + cap/dry-run banners atop `/app/inbox`.

`input_hash` is a SHA-256 of the normalised body (lowercased,
whitespace-collapsed). Lets the operator spot-check "did we give a
consistent verdict on the same input across model upgrades" without
exposing the full body in dashboards.

`inbound_message_id` is nullable because dry-run / shadow classifications
during model evals don't have a stored InboundMessage row.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class InboxClassificationLog(Base):
    __tablename__ = "inbox_classification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )

    # Nullable: dry-run / shadow classifications run without a stored
    # InboundMessage. No FK constraint — we don't want a deleted message
    # to take its audit trail with it.
    inbound_message_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )

    # SHA-256 hex of the normalised body. 64 chars.
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # 'claude-haiku-4-5' / 'claude-sonnet-4-5' for real calls, or
    # 'rule-based-fallback' / 'cap-exceeded' / 'no-api-key' for the
    # short-circuit paths so we can audit how often the LLM was actually
    # invoked vs deflected.
    model: Mapped[str] = mapped_column(String(64), nullable=False)

    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Cached tokens reported separately so we can verify prompt caching is
    # actually firing (warm-cache should hit ~95% of input).
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 6dp precision because typical Haiku calls are fractions of a cent.
    # Use Decimal in Python for safe summing.
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False, default=Decimal("0"),
    )

    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # The classifier's verdict. Nullable for error rows.
    tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Truncated to 240 chars to keep the table queryable. Full stack
    # trace goes to logs + Sentry.
    error: Mapped[str | None] = mapped_column(String(240), nullable=True)
