"""ticker.confidence_pct — per-ticker data-quality score

Revision ID: 0012_ticker_confidence
Revises: 0011_user_phone_number
Create Date: 2026-04-29 00:30:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_ticker_confidence"
down_revision: Union[str, None] = "0011_user_phone_number"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tickers") as batch:
        batch.add_column(sa.Column("confidence_pct", sa.Float, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tickers") as batch:
        batch.drop_column("confidence_pct")
