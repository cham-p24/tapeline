"""Single-use tokens for password reset.

Minted at POST /api/auth/forgot-password, consumed at POST
/api/auth/reset-password. 1-hour TTL (shorter than email-verification's
24h because the threat model is higher — anyone who reads the user's
inbox briefly can take over the account if the window is too wide).

Same shape as EmailVerificationToken — kept as a separate model so the
two concerns stay distinct and a future change to one doesn't
accidentally affect the other.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

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
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
