"""Add nullable market_cap (Float) to tickers

Adds an absolute-dollars market-cap column to the `tickers` snapshot table so
the scanner can surface a "Mkt Cap" column alongside Volume. Nullable because
many rows never get a read (ETFs, freshly discovered names, feeds without a
Finnhub profile) — a null renders as an em-dash in the UI. Population threads
the value out of the Finnhub company profile (reported in MILLIONS, multiplied
by 1e6 at the write site) via the per-tick snapshot path.

Nullable add → safe online change on Postgres (no table rewrite, no default
backfill). SQLite adds the column directly too. Downgrade drops it.

Revision id kept short (well under version_num VARCHAR(32) — see memory:
tapeline_alembic_version_limit).

Revision ID: 0049_ticker_market_cap
Revises: 0048_backfill_activated_at
Create Date: 2026-08-20 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0049_ticker_market_cap"
down_revision: Union[str, None] = "0048_backfill_activated_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickers",
        sa.Column("market_cap", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tickers", "market_cap")
