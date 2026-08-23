"""Emailed sign-in codes (second factor for unrecognised devices).

One row per code issued at POST /api/auth/signin when the browser has no valid
trusted-device cookie. Consumed at POST /api/auth/2fa, which mints the session
and marks the browser trusted for 30 days.

Same shape as PasswordResetToken/EmailVerificationToken — deliberately a
separate table so a change to one auth concern can't affect another.

`code_hash` is a KEYED hash (HMAC-SHA256 with SESSION_SECRET, bound to the
user id) rather than the raw code — see services/signin_codes for why a fast
keyed hash is the right choice for a short-lived 6-digit credential.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SigninCode(Base):
    __tablename__ = "signin_codes"

    # Lookup is always "newest unused code for this user", so index the pair.
    __table_args__ = (
        Index("ix_signin_codes_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(60),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
