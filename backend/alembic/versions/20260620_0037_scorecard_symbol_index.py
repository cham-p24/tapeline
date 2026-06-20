"""daily_scorecard composite index for the symbol-filtered scorecard read

GET /api/scorecard/symbol/{symbol} (routers/scorecard.py) filters
`daily_scorecard` on `symbol` and sorts `ORDER BY as_of DESC`. The table had an
index on `as_of` alone but NONE on `symbol`, so the per-ticker history query did
a full table scan to find a symbol's rows — and the table grows ~10 rows per
trading day forever, so the scan cost climbs without bound.

This adds a composite B-tree on `(symbol, as_of)`. `symbol` leads as the
equality predicate; `as_of` follows so the same structure also serves the
`ORDER BY as_of DESC`, making the query fully index-served.

A plain composite B-tree is portable, so the index is created on Postgres AND
SQLite (dev matches prod). No pg-specific clause needed.

Revision ID: 0037_scorecard_symbol_index
Revises: 0036_merge_heads
Create Date: 2026-06-20 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0037_scorecard_symbol_index"
down_revision: str | None = "0036_merge_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_daily_scorecard_symbol_as_of"


def upgrade() -> None:
    op.create_index(_INDEX, "daily_scorecard", ["symbol", "as_of"])


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="daily_scorecard")
