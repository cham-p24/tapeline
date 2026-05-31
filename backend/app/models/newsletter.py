"""Newsletter subscribers — the lead-magnet capture path.

Distinct from `users` because most newsletter subscribers are not
trial signups (yet). The goal of this surface is to capture an email
from someone who isn't ready to commit to a trial but is curious about
the daily Top 10. Once they're in this table:

  - Welcome email fires immediately (Resend, transactional)
  - Daily Top 10 digest sends 6:00 ET Tue-Fri (worker task — added in
    a follow-up PR; this PR only ships the capture side)
  - When/if they later create a `users` row with the same email, the
    onboarding step can mark them as already-newsletter-converted

Schema lives in migration 0021. See that file's docstring for the full
column-by-column rationale.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True,
    )
    # confirmed | unsubscribed | pending. We auto-confirm on signup (no
    # double opt-in gate yet) but `pending` is reserved so we can flip it on
    # later without a migration.
    status: Mapped[str] = mapped_column(String(20), default="confirmed", nullable=False)

    # Free-form source string — 'homepage' / 'scorecard' / 'pricing' / 'api'.
    # Captured from the POST body so we know which surface converted them.
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Marketing-attribution UTMs from the user's landing query string. These
    # are forwarded from the frontend's lib/utm.ts (localStorage capture on
    # first visit, 30-day TTL). Distinct fields rather than one JSON blob so
    # we can index/group/segment by source or campaign in plain SQL.
    utm_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(80), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(120), nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String(120), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # 32-byte hex token (secrets.token_hex(32) → 64 chars). One-click
    # unsubscribe link is /api/newsletter/unsubscribe?token=...; we never
    # expose the row id, so URL leakage doesn't enable enumeration attacks.
    unsubscribe_token: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True,
    )

    # Filled when the user clicks the welcome email CTA. If we don't gate
    # delivery on it (current posture), this is just informational.
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    unsubscribed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Bumped by the daily digest worker so a worker restart mid-run doesn't
    # double-send to anyone we already hit today.
    last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
