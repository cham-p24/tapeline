"""institutional_holdings (elite-fund 13F snapshots)

Revision ID: 0008_institutional_holdings
Revises: 0007_sales_structure
Create Date: 2026-04-27 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_institutional_holdings"
down_revision: Union[str, None] = "0007_sales_structure"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "institutional_holdings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fund_name", sa.String(80), nullable=False),
        sa.Column("manager", sa.String(80), nullable=False),
        sa.Column("cik", sa.String(20), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("value_usd", sa.Float, nullable=False, server_default=sa.text("0")),
        sa.Column("shares", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("percent_portfolio", sa.Float, nullable=False, server_default=sa.text("0")),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_institutional_holdings_symbol", "institutional_holdings", ["symbol"])
    op.create_index("ix_institutional_holdings_fund_name", "institutional_holdings", ["fund_name"])
    op.create_index("ix_institutional_holdings_cik", "institutional_holdings", ["cik"])


def downgrade() -> None:
    op.drop_index("ix_institutional_holdings_cik", "institutional_holdings")
    op.drop_index("ix_institutional_holdings_fund_name", "institutional_holdings")
    op.drop_index("ix_institutional_holdings_symbol", "institutional_holdings")
    op.drop_table("institutional_holdings")
