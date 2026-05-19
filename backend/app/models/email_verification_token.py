"""Single-use tokens for email-verification flow.

Minted at signup (or via POST /api/auth/resend-verification), consumed at
GET /api/auth/verify-email?token=... — stamps `User.email_verified_at`.
24h TTL via `expires_at`; a daily worker task prunes expired rows.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    token: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(60),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    # Set when the token is consumed via /api/auth/verify-email. We keep the
    # row around for ~24h post-consumption so repeat clicks on an old link
    # return a clean "already verified" response rather than a "token not
    # found" 404 that would scare the user.
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
