"""freemium daily ticker-lookup meter columns

Backs the freemium model's per-user daily cap on detailed single-ticker score
views (GET /api/ticker/{symbol}). FREE users get a tunable daily cap
(services/tier.FREE_DAILY_LOOKUPS); Pro/Premium/active-trial users are never
metered. Enforcement lives in services/usage.consume_ticker_lookup.

New users.* columns:

  lookups_today     Integer, NOT NULL, default 0. Running count of detailed
                    ticker lookups for the current UTC day.
  lookups_reset_on  Date, nullable. The UTC date `lookups_today` belongs to.
                    When it != today, the counter rolls to 0 before the next
                    increment. NULL on existing rows = "never looked up" → the
                    first lookup initialises it to today.

Chains off 0036_merge_heads, which is the single current alembic head (it
merged the two 0034 branches — bigint_volume_shares + scanner_composite_index).
Do NOT branch this off anything else or we re-introduce a multi-head.

Revision ID: 0037_freemium_lookup_meter
Revises: 0036_merge_heads
Create Date: 2026-06-20 09:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037_freemium_lookup_meter"
down_revision: Union[str, None] = "0036_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "lookups_today",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.add_column(
            sa.Column("lookups_reset_on", sa.Date(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("lookups_reset_on")
        batch.drop_column("lookups_today")
