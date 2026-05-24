"""password_reset_tokens + users.email_undeliverable_at

Two related additions that close the last UX + deliverability gaps:

  1. password_reset_tokens — single-use 1h-TTL tokens for the
     /forgot-password → /reset-password flow. Mirrors the
     email_verification_tokens shape (token PK, user_id FK CASCADE,
     expires_at, used_at, created_at).

  2. users.email_undeliverable_at — stamped when Resend reports
     email.bounced (hard bounce) or email.complained (user marked us
     as spam). send_email short-circuits on this column so we stop
     burning sender reputation on dead addresses.

Why one migration: both ship in the same "launch polish" PR and are
trivial enough that splitting them adds more friction than value.

Revision ID: 0027_password_reset_and_undeliverable
Revises: 0026_inbox_auto_handler
Create Date: 2026-05-24 09:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_password_reset_undeliverable"
down_revision: Union[str, None] = "0026_inbox_auto_handler"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("token", sa.String(80), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(60),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "email_undeliverable_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_undeliverable_at")
    op.drop_table("password_reset_tokens")
