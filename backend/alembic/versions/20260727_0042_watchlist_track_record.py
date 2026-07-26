"""watchlist_track_record — per-user daily snapshot + next-day-vs-SPY

Premium, per-user analogue of the public daily_scorecard: freezes (score, price,
signal) for every Premium user's watchlist ticker each session and back-checks
the next-day return vs SPY. Backs the "personal track record" surface on the
watchlist. New table only — no existing data touched, no cap values change.

Revision id kept short (well under the version_num VARCHAR(32) limit — see
memory: tapeline_alembic_version_limit).

Revision ID: 0042_watchlist_track_record
Revises: 0041_cap_events
Create Date: 2026-07-27 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0042_watchlist_track_record"
down_revision: str | None = "0041_cap_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watchlist_track_record",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.String(length=60),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("score_at_flag", sa.Float(), nullable=False),
        sa.Column("price_at_flag", sa.Float(), nullable=False),
        sa.Column("signal_at_flag", sa.String(length=30), nullable=True),
        sa.Column("price_next_day", sa.Float(), nullable=True),
        sa.Column("change_pct_1d_after", sa.Float(), nullable=True),
        sa.Column("spy_change_pct_1d", sa.Float(), nullable=True),
        sa.Column("alpha_vs_spy", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "symbol", "as_of", name="uq_wl_trackrecord_user_symbol_asof"
        ),
    )
    op.create_index(
        "ix_watchlist_track_record_user_id", "watchlist_track_record", ["user_id"]
    )
    op.create_index(
        "ix_watchlist_track_record_as_of", "watchlist_track_record", ["as_of"]
    )
    op.create_index(
        "ix_wl_trackrecord_user_asof",
        "watchlist_track_record",
        ["user_id", "as_of"],
    )


def downgrade() -> None:
    op.drop_index("ix_wl_trackrecord_user_asof", table_name="watchlist_track_record")
    op.drop_index("ix_watchlist_track_record_as_of", table_name="watchlist_track_record")
    op.drop_index("ix_watchlist_track_record_user_id", table_name="watchlist_track_record")
    op.drop_table("watchlist_track_record")
