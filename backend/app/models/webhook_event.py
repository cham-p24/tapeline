"""Stripe webhook idempotency log — prevents replay-attack double-processing."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StripeWebhookEvent(Base):
    """One row per processed Stripe event. PK is Stripe's `evt_…` id.

    The webhook handler checks this before doing any work — if the event id
    is already here, return {ok: true, replay: true} and skip processing.
    Defends against:
      - Stripe redelivering the same event (network blip, our 5xx response)
      - Replay attacks if signing secret ever leaks
    """
    __tablename__ = "stripe_webhook_events"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)  # Stripe event id (evt_xxx)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
