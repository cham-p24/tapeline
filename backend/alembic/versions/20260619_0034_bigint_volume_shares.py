"""Widen count columns INTEGER -> BIGINT to stop 32-bit overflow

The scan-tick bulk write into `tickers` was failing every cycle with
`psycopg.errors.NumericValueOutOfRange: integer out of range` because
high-turnover names (e.g. ADTX ~5.28B shares) exceed the 32-bit INTEGER max
(2,147,483,647). One overflowing row aborted the entire batch, so scores
stopped persisting AND it flooded Sentry (5k+ identical DataErrors → quota
exhausted). Widen `tickers.volume` to BIGINT, plus the same latent-overflow
columns `institutional_holdings.shares` (a fund can hold >2.1B shares of one
name) and `ipo_events.shares_offered`.

Postgres-only: SQLite stores INTEGER as a dynamic 64-bit value, so no change
is needed there (and `ALTER COLUMN TYPE` would require batch mode).

Revision ID: 0034_bigint_volume_shares
Revises: 0033_news_tickers_trgm
Create Date: 2026-06-19 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034_bigint_volume_shares"
down_revision: Union[str, None] = "0033_news_tickers_trgm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column, nullable) tuples to widen.
_COLUMNS = (
    ("tickers", "volume", True),
    ("institutional_holdings", "shares", False),
    ("ipo_events", "shares_offered", True),
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return  # SQLite INTEGER is already 64-bit; nothing to do.
    for table, column, nullable in _COLUMNS:
        op.alter_column(
            table, column,
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=nullable,
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, column, nullable in _COLUMNS:
        op.alter_column(
            table, column,
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=nullable,
        )
