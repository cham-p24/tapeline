"""api_keys table — Premium public-API keys

Backs the /api/api-keys management CRUD + the /api/v1 key-authenticated read
surface (PR8). Stores only a sha256 hash of each key plus a 16-char clear
prefix for identification; the plaintext key is shown to the user once at
creation and never persisted. `requests_today` / `requests_day` carry the
rolling per-UTC-day quota counter enforced in services/api_keys.

Revision ID: 0032_api_keys
Revises: 0031_sub_billing_period
Create Date: 2026-06-01 18:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032_api_keys"
down_revision: Union[str, None] = "0031_sub_billing_period"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requests_today", sa.Integer(), server_default="0", nullable=False),
        sa.Column("requests_day", sa.String(length=10), nullable=True),
        sa.Column("request_count_total", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index("ix_api_keys_prefix", "api_keys", ["prefix"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_index("ix_api_keys_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")
