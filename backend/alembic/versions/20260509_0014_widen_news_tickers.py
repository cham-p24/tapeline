"""Widen news_items.tickers from VARCHAR(200) to VARCHAR(2000)

Production incident 2026-05-09: Benzinga occasionally tags a single
article with 50+ ticker symbols (market round-up pieces, "Stocks That
Moved Today" articles). The concatenated tickers string exceeds
VARCHAR(200), every batch INSERT containing such an article fails,
and the entire batch rolls back — meaning zero new articles land
even though most were within the column width.

This migration widens the column to VARCHAR(2000), which fits even
the heaviest cashtag-bombed articles (~80 tickers × 5 chars + commas
≈ 480 chars). The 4× safety margin handles future tagging-density
increases without another migration.

A code-level truncate at 200 chars was also added in the news
adapters as belt-and-suspenders — if a future Benzinga update produces
even longer strings, articles still land (just with a truncated
ticker set rather than failing the batch).

Revision ID: 0014_widen_news_tickers
Revises: 0013_user_discord_webhook
Create Date: 2026-05-09 14:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_widen_news_tickers"
down_revision: Union[str, None] = "0013_user_discord_webhook"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER COLUMN type — Postgres handles this without a table rewrite
    # for VARCHAR widening. SQLite has no real length enforcement so the
    # batch_alter_table is a no-op there but stays correct.
    with op.batch_alter_table("news_items") as batch:
        batch.alter_column(
            "tickers",
            existing_type=sa.String(200),
            type_=sa.String(2000),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Truncating data on downgrade isn't ideal, but at downgrade time the
    # operator has accepted that tickers > 200 will be cut off. We pre-
    # truncate explicitly so the type narrowing doesn't fail mid-table.
    op.execute(
        "UPDATE news_items SET tickers = SUBSTRING(tickers FROM 1 FOR 200) "
        "WHERE LENGTH(tickers) > 200"
    )
    with op.batch_alter_table("news_items") as batch:
        batch.alter_column(
            "tickers",
            existing_type=sa.String(2000),
            type_=sa.String(200),
            existing_nullable=False,
        )
