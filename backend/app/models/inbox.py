"""Inbox auto-handler — inbound message store + idempotency.

Backs the Tier 1 / 2 / 3 inbox classifier worker (see
`services/inbox_classifier.py`). One row per inbound message across
Reddit, email, and Telegram. Idempotent: each message carries a stable
`channel_msg_id` and a unique constraint on (channel, channel_msg_id)
so the same Reddit comment / email message-id / Telegram update_id
can be polled twice without double-processing.

Tier definitions (match the classifier system prompt):
  - 1 = high-value, needs founder voice (FinTwit influencer, journalist,
    real retail trader with specific ticker question, newsletter pitch).
    Bot drafts a reply and routes it to founder's Telegram for one-tap
    approval — NEVER auto-sends.
  - 2 = templatable, auto-reply safe ("what's $TICKER score?", "how does
    the free tier work?", "thanks for building this"). Bot looks up the
    canonical template, fills in any live data via the public API, and
    auto-sends through the channel-appropriate adapter.
  - 3 = ignore (crypto shillers, bots, off-platform paid-signal-service
    offers, hostile trolls). Bot marks status='ignored' and doesn't
    send anything.

Status state machine:
  new → (classified, tier set) → [approved | auto_replied | ignored] → sent

The 'sent' status is terminal. If the channel adapter fails (Reddit
PRAW exception, Resend 5xx, Telegram timeout), status stays at
'approved' / 'auto_replied' and the next worker tick retries.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class InboundMessage(Base):
    __tablename__ = "inbound_messages"
    __table_args__ = (
        # Per-channel uniqueness on the upstream message id. Reddit comment
        # ids like "t1_xyz" are globally unique within Reddit; email
        # Message-ID headers are globally unique; Telegram update_id is
        # unique per bot. Composite uniqueness still works because
        # channel namespaces them.
        UniqueConstraint("channel", "channel_msg_id", name="uq_inbox_channel_msgid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 'reddit_comment' | 'reddit_dm' | 'email' | 'telegram'
    channel: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Upstream-stable id (Reddit comment 't1_xyz', email Message-ID,
    # Telegram update_id as string). Idempotency key.
    channel_msg_id: Mapped[str] = mapped_column(String(200), nullable=False)

    # @handle / email / chat_id — whoever sent it. Free-form, no FK
    # because the sender isn't a Tapeline user (most aren't).
    author: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    # Email subject, or first 80 chars of the body for channels without
    # subjects. Used in the Telegram alert preview.
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Full message text. Cap is generous because Reddit comments and emails
    # can both be long; Tier 1 classification reads the whole thing.
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # When the message arrived at the upstream platform (NOT when we polled
    # it). Reddit gives us created_utc; email has Date header; Telegram has
    # update.message.date.
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    # 1 / 2 / 3 — null until classified.
    tier: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # One-line LLM explanation of why this tier was chosen. Shown in the
    # Telegram alert + the /app/inbox admin UI for spot-checks.
    tier_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # The drafted reply (for Tier 1 — populated by classifier, surfaced
    # to the founder via Telegram). For Tier 2 this is filled by the
    # template lookup at auto-send time.
    suggested_reply: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 'new' (just inserted) → 'classified' (LLM ran, tier set) →
    # 'approved' (founder tapped /approve) | 'auto_replied' (Tier 2 went
    # out without approval) | 'ignored' (Tier 3) → 'sent' (channel
    # adapter confirmed delivery). 'error' is reserved for unrecoverable
    # failures.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="new", index=True,
    )

    # Set when the reply actually landed at the upstream platform.
    handled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Telegram message id of the approval card, so the bot can edit it
    # in place ("Approved ✓" / "Sent ✓") when the founder taps the
    # button.
    telegram_alert_message_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
