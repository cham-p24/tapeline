"""user.drip_state — dedupe column for drip emails

Revision ID: 0009_user_drip_state
Revises: 0008_institutional_holdings
Create Date: 2026-04-27 02:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_user_drip_state"
down_revision: Union[str, None] = "0008_institutional_holdings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column(
            "drip_state", sa.String(40), nullable=False, server_default="",
        ))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("drip_state")
