"""add is_admin flag to users

Revision ID: 0005_admin_flag
Revises: 0004_native_auth
Create Date: 2026-04-22 02:30:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_admin_flag"
down_revision: Union[str, None] = "0004_native_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_admin")
