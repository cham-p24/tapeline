"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-22 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tickers",
        sa.Column("symbol", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sector", sa.String(80), nullable=True),
        sa.Column("asset_class", sa.String(20), nullable=False, server_default="equity"),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("signal", sa.String(30), nullable=True),
        sa.Column("price", sa.Float, nullable=True),
        sa.Column("change_pct_1d", sa.Float, nullable=True),
        sa.Column("change_pct_5d", sa.Float, nullable=True),
        sa.Column("change_pct_1m", sa.Float, nullable=True),
        sa.Column("volume", sa.Integer, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tickers_score", "tickers", ["score"])
    op.create_index("ix_tickers_sector", "tickers", ["sector"])

    op.create_table(
        "squeeze_setups",
        sa.Column("symbol", sa.String(20), primary_key=True),
        sa.Column("spike_score", sa.Float, nullable=False),
        sa.Column("squeeze_days", sa.Integer, nullable=False),
        sa.Column("volume_multiple", sa.Float, nullable=False),
        sa.Column("obv_trend", sa.String(20), nullable=False),
        sa.Column("breakout_type", sa.String(40), nullable=False),
        sa.Column("suggested_window", sa.String(40), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "regime_state",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("regime", sa.String(20), nullable=False),
        sa.Column("vix", sa.Float, nullable=False),
        sa.Column("dxy", sa.Float, nullable=False),
        sa.Column("yield_10y", sa.Float, nullable=False),
        sa.Column("rate_direction", sa.String(20), nullable=False),
        sa.Column("breadth_pct", sa.Float, nullable=False),
        sa.Column("sector_leaders", sa.String(300), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "congress_trades",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("politician", sa.String(100), nullable=False),
        sa.Column("chamber", sa.String(20), nullable=False),
        sa.Column("party", sa.String(5), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("amount_min", sa.Float, nullable=False),
        sa.Column("amount_max", sa.Float, nullable=False),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("disclosed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_congress_trades_symbol", "congress_trades", ["symbol"])
    op.create_index("ix_congress_trades_disclosed_at", "congress_trades", ["disclosed_at"])


def downgrade() -> None:
    op.drop_table("congress_trades")
    op.drop_table("regime_state")
    op.drop_table("squeeze_setups")
    op.drop_table("tickers")
