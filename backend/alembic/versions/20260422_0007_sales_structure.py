"""trial_ends_at + referral + lifetime flag

Revision ID: 0007_sales_structure
Revises: 0006_calendar_events
Create Date: 2026-04-22 03:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_sales_structure"
down_revision: Union[str, None] = "0006_calendar_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("referral_code", sa.String(20), nullable=True))
        batch.add_column(sa.Column("referred_by", sa.String(60), nullable=True))
        batch.add_column(sa.Column("is_lifetime", sa.Boolean, nullable=False, server_default=sa.text("false")))
        batch.create_unique_constraint("uq_users_referral_code", ["referral_code"])
        batch.create_index("ix_users_referred_by", ["referred_by"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_referred_by")
        batch.drop_constraint("uq_users_referral_code", type_="unique")
        batch.drop_column("is_lifetime")
        batch.drop_column("referred_by")
        batch.drop_column("referral_code")
        batch.drop_column("trial_ends_at")
