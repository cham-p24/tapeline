"""user.email_prefs

Per-user bitmask controlling which non-transactional email categories the
user wants to receive. Bits:

    1  trial_drip      day-3 / 7 / 11 / 13 / expired / post3
    2  re_engagement   re14 (14-day dormant nudge)
    4  daily_digest    EOD watchlist digest
    8  alert_emails    per-rule score / squeeze / regime / news alerts

Default 15 = all four bits set = opted into everything. Transactional
emails (welcome, payment-failed, referral confirmations) are NEVER
suppressed — they're account-state notifications, not marketing.

Revision ID: 0018_user_email_prefs
Revises: 0017_user_last_seen_at
Create Date: 2026-05-16 10:30:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_user_email_prefs"
down_revision: Union[str, None] = "0017_user_last_seen_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "email_prefs",
                sa.Integer(),
                nullable=False,
                server_default="15",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_prefs")
