"""watchlists + scanner_presets + watchlist_id backfill

Phase A foundation (per docs/PHASE_1_EXECUTION_PLAN.md §A1). Adds:

- New `watchlists` parent table — id, user_id, name, sort_order, created_at
- New `scanner_presets` table — id, user_id, name, filters_json, created_at
- `watchlist_items.watchlist_id` nullable FK → watchlists(id) ON DELETE CASCADE

Data backfill: for every user with existing watchlist items, creates a
default "My Watchlist" and points all their items at it. After this
migration, no production row has a NULL watchlist_id. The column stays
nullable as an escape hatch for the legacy POST /api/watchlist endpoint
(which now auto-resolves to the default list on first add).

Tier caps for the new `watchlists` key are in services/tier.py:
  Free=1, Pro=5, Premium=20. Migration doesn't touch tier — that's a
  code change shipped in the same PR.

Revision ID: 0022_watchlists_and_presets
Revises: 0021_watchlist_last_alert_at
Create Date: 2026-05-18 14:30:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_watchlists_and_presets"
down_revision: Union[str, None] = "0021_watchlist_last_alert_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- watchlists parent table -------------------------------------------
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),
    )
    op.create_index("ix_watchlists_user_id", "watchlists", ["user_id"])

    # ---- scanner_presets table ---------------------------------------------
    op.create_table(
        "scanner_presets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_scanner_presets_user_name"),
    )
    op.create_index("ix_scanner_presets_user_id", "scanner_presets", ["user_id"])

    # ---- watchlist_items.watchlist_id column + FK + index ------------------
    # SQLite needs batch_alter_table to add a column with an FK; on Postgres
    # the batch is a no-op wrapper.
    with op.batch_alter_table("watchlist_items") as batch:
        batch.add_column(sa.Column("watchlist_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_watchlist_items_watchlist_id",
            "watchlists",
            ["watchlist_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index("ix_watchlist_items_watchlist_id", ["watchlist_id"])

    # ---- Data backfill -----------------------------------------------------
    # 1) For every distinct user_id in watchlist_items, ensure a default
    #    "My Watchlist" row exists in watchlists. Idempotent via NOT EXISTS.
    op.execute(
        """
        INSERT INTO watchlists (user_id, name, sort_order, created_at)
        SELECT DISTINCT wi.user_id, 'My Watchlist', 0, CURRENT_TIMESTAMP
        FROM watchlist_items wi
        WHERE NOT EXISTS (
            SELECT 1 FROM watchlists w
            WHERE w.user_id = wi.user_id AND w.name = 'My Watchlist'
        )
        """
    )

    # 2) Point every NULL-watchlist_id item at the user's default list.
    op.execute(
        """
        UPDATE watchlist_items
        SET watchlist_id = (
            SELECT id FROM watchlists
            WHERE watchlists.user_id = watchlist_items.user_id
              AND watchlists.name = 'My Watchlist'
            LIMIT 1
        )
        WHERE watchlist_id IS NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("watchlist_items") as batch:
        batch.drop_index("ix_watchlist_items_watchlist_id")
        batch.drop_constraint("fk_watchlist_items_watchlist_id", type_="foreignkey")
        batch.drop_column("watchlist_id")
    op.drop_index("ix_scanner_presets_user_id", table_name="scanner_presets")
    op.drop_table("scanner_presets")
    op.drop_index("ix_watchlists_user_id", table_name="watchlists")
    op.drop_table("watchlists")
