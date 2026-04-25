"""score_breakdown, watchlist, scorecard, news

Revision ID: 0003_differentiation
Revises: 0002_users_billing_alerts
Create Date: 2026-04-22 01:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_differentiation"
down_revision: Union[str, None] = "0002_users_billing_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add score-breakdown columns to tickers
    with op.batch_alter_table("tickers") as batch:
        batch.add_column(sa.Column("sub_trend", sa.Float, nullable=True))
        batch.add_column(sa.Column("sub_rs", sa.Float, nullable=True))
        batch.add_column(sa.Column("sub_fundamentals", sa.Float, nullable=True))
        batch.add_column(sa.Column("sub_momentum", sa.Float, nullable=True))
        batch.add_column(sa.Column("sub_macro", sa.Float, nullable=True))
        batch.add_column(sa.Column("sub_smart_money", sa.Float, nullable=True))
        batch.add_column(sa.Column("reason", sa.String(400), nullable=True))

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(60), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("baseline_score", sa.Float, nullable=True),
        sa.Column("alert_threshold_delta", sa.Float, nullable=False, server_default="10.0"),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),
    )
    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"])

    op.create_table(
        "daily_scorecard",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("as_of", sa.Date, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("score_at_flag", sa.Float, nullable=False),
        sa.Column("price_at_flag", sa.Float, nullable=False),
        sa.Column("price_next_day", sa.Float, nullable=True),
        sa.Column("change_pct_1d_after", sa.Float, nullable=True),
        sa.Column("spy_change_pct_1d", sa.Float, nullable=True),
        sa.Column("alpha_vs_spy", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_daily_scorecard_as_of", "daily_scorecard", ["as_of"])

    op.create_table(
        "news_items",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("publisher", sa.String(100), nullable=False),
        sa.Column("author", sa.String(120), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tickers", sa.String(200), nullable=False, server_default=""),
        sa.Column("sentiment", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_news_items_published_at", "news_items", ["published_at"])
    op.create_index("ix_news_items_tickers", "news_items", ["tickers"])


def downgrade() -> None:
    op.drop_table("news_items")
    op.drop_table("daily_scorecard")
    op.drop_table("watchlist_items")
    with op.batch_alter_table("tickers") as batch:
        for col in ["sub_trend", "sub_rs", "sub_fundamentals", "sub_momentum",
                    "sub_macro", "sub_smart_money", "reason"]:
            batch.drop_column(col)
