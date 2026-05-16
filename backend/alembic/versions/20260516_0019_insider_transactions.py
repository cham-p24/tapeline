"""insider_transactions table

Persistence for Finnhub Form 4 insider transactions. Replaces the
in-process `_INSIDER_FEED` global in services/finnhub_feed.py because
Fly runs `api` and `worker` on separate machines — the worker's
in-memory cache wasn't visible to the API process, so /api/holdings
returned empty regardless of how successfully the worker refreshed.

Bulk-replace pattern per symbol on each daily refresh:
  DELETE FROM insider_transactions WHERE symbol = :sym
  INSERT INTO insider_transactions (...) VALUES (...) -- N rows

UniqueConstraint absorbs collisions if the refresh task overlaps with
itself (shouldn't, but defensive).

Revision ID: 0019_insider_transactions
Revises: 0018_user_email_prefs
Create Date: 2026-05-16 13:55:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_insider_transactions"
down_revision: Union[str, None] = "0018_user_email_prefs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "insider_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("insider_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("transaction_date", sa.String(10), nullable=False, server_default=""),
        sa.Column("share_change", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transaction_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("transaction_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("code", sa.String(4), nullable=False, server_default=""),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "symbol", "transaction_date", "insider_name", "share_change",
            name="uq_insider_natural",
        ),
    )
    op.create_index("ix_insider_date_desc", "insider_transactions", ["transaction_date"])
    op.create_index(
        "ix_insider_symbol_date",
        "insider_transactions",
        ["symbol", "transaction_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_insider_symbol_date", table_name="insider_transactions")
    op.drop_index("ix_insider_date_desc", table_name="insider_transactions")
    op.drop_table("insider_transactions")
