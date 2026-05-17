"""watchlist_items.last_alert_at

Adds a per-watchlist-item timestamp used to debounce smart score-move
alerts. Each WatchlistItem already carries `baseline_score` (snapshot at
add time) and `alert_threshold_delta` (default 10 points). The new
evaluator fires when |current_score - baseline_score| crosses the
threshold; `last_alert_at` then floors the next fire to 24h later so a
ticker that stays elevated above the threshold doesn't spam the user —
the daily EOD digest already covers that drumbeat case.

Revision ID: 0021_watchlist_last_alert_at
Revises: 0020_user_onboarding_fields
Create Date: 2026-05-18 13:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_watchlist_last_alert_at"
down_revision: Union[str, None] = "0020_user_onboarding_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("watchlist_items") as batch:
        batch.add_column(
            sa.Column("last_alert_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("watchlist_items") as batch:
        batch.drop_column("last_alert_at")
