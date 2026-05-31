"""mfa: users.totp_secret + users.mfa_enabled + mfa_recovery_codes

Adds TOTP (authenticator-app) two-factor auth for native email+password
accounts. Three schema changes, one PR:

  1. users.totp_secret  — base32 TOTP shared secret. Written during setup,
     before the user confirms; mfa_enabled stays false until they verify a
     live code, so a half-finished enrolment never blocks signin.
  2. users.mfa_enabled  — bool, default false. Flipped true on first
     successful verify; the signin path only challenges when this is set.
  3. mfa_recovery_codes — one row per single-use recovery code (sha256 hash
     only; plaintext is shown once at enable time and never stored).

server_default=false on mfa_enabled backfills the column for existing rows
without a separate UPDATE.

Revision ID: 0028_mfa_totp
Revises: 0028_inbox_classification_log
Create Date: 2026-05-30 09:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028_mfa_totp"
down_revision: Union[str, None] = "0028_inbox_classification_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("totp_secret", sa.String(64), nullable=True))
        batch.add_column(
            sa.Column(
                "mfa_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    op.create_table(
        "mfa_recovery_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(60),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("code_hash", sa.String(64), nullable=False, index=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("mfa_recovery_codes")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("mfa_enabled")
        batch.drop_column("totp_secret")
