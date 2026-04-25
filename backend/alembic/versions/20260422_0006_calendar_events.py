"""ipo_events, earnings_events

Revision ID: 0006_calendar_events
Revises: 0005_admin_flag
Create Date: 2026-04-22 02:45:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_calendar_events"
down_revision: Union[str, None] = "0005_admin_flag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ipo_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("sector", sa.String(80), nullable=True),
        sa.Column("exchange", sa.String(20), nullable=False),
        sa.Column("expected_date", sa.Date, nullable=False),
        sa.Column("price_low", sa.Float, nullable=True),
        sa.Column("price_high", sa.Float, nullable=True),
        sa.Column("shares_offered", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="upcoming"),
        sa.Column("lead_underwriter", sa.String(120), nullable=True),
        sa.Column("description", sa.String(400), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ipo_events_symbol", "ipo_events", ["symbol"])
    op.create_index("ix_ipo_events_expected_date", "ipo_events", ["expected_date"])

    op.create_table(
        "earnings_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column("report_time", sa.String(20), nullable=False),
        sa.Column("fiscal_quarter", sa.String(10), nullable=False),
        sa.Column("eps_estimate", sa.Float, nullable=True),
        sa.Column("eps_actual", sa.Float, nullable=True),
        sa.Column("revenue_estimate_m", sa.Float, nullable=True),
        sa.Column("revenue_actual_m", sa.Float, nullable=True),
        sa.Column("surprise_pct", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_earnings_events_symbol", "earnings_events", ["symbol"])
    op.create_index("ix_earnings_events_report_date", "earnings_events", ["report_date"])


def downgrade() -> None:
    op.drop_table("earnings_events")
    op.drop_table("ipo_events")
