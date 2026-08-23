"""signin_codes — emailed sign-in codes for unrecognised devices

Backs the new-device second factor: a 6-digit code is emailed at sign-in when
the browser has no valid trusted-device cookie, and consumed at /api/auth/2fa.
New table only; no existing data touched and no change to any tier/cap value.

Revision id kept short (well under the version_num VARCHAR(32) limit — see
memory: tapeline_alembic_version_limit).

Revision ID: 0052_signin_codes
Revises: 0051_ticker_key_stats
Create Date: 2026-08-23 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0052_signin_codes"
down_revision: str | None = "0051_ticker_key_stats"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signin_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(length=60),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # HMAC-SHA256 hex digest (64 chars), keyed with SESSION_SECRET and
        # bound to user_id — never the raw code.
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_signin_codes_user_id", "signin_codes", ["user_id"])
    op.create_index("ix_signin_codes_expires_at", "signin_codes", ["expires_at"])
    op.create_index(
        "ix_signin_codes_user_created", "signin_codes", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_signin_codes_user_created", table_name="signin_codes")
    op.drop_index("ix_signin_codes_expires_at", table_name="signin_codes")
    op.drop_index("ix_signin_codes_user_id", table_name="signin_codes")
    op.drop_table("signin_codes")
