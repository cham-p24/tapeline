"""user.last_seen_at

Tracks the last time an authenticated user's session was active. Bumped on
every resolved authenticated request (throttled to once per hour to avoid
write amplification) so the re-engagement drip can target users who haven't
opened the app in ~14 days.

Indexed because the daily drip filter is range-scan on this column across
the entire users table; without the index the worker would full-table scan
each tick.

Revision ID: 0017_user_last_seen_at
Revises: 0016_user_referral_credit_months
Create Date: 2026-05-16 09:30:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_user_last_seen_at"
down_revision: Union[str, None] = "0016_user_referral_credit_months"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "last_seen_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
    op.create_index(
        "ix_users_last_seen_at",
        "users",
        ["last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_last_seen_at", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("last_seen_at")
