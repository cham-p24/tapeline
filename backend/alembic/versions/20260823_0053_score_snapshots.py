"""score_snapshots — point-in-time daily archive of every scored ticker

`tickers` is a live snapshot overwritten on every scoring tick; every trading
day without a point-in-time capture is universe history that can never be
regenerated. `daily_scorecard` freezes only the filtered top-10. This table
freezes the FULL scored universe once per trading day — the hard prerequisite
for any future data-licensing record. Archival only: no API reads it yet.

APPEND-ONLY table: the capture job INSERTs with ON CONFLICT DO NOTHING against
UNIQUE(snapshot_date, symbol); no code path updates or deletes rows (enforced
by tests/test_score_snapshots.py). Column set mirrors the live per-factor score
storage on `tickers`: score (NOT NULL — only scored rows are archived), the six
nullable sub_* factor scores, and confidence_pct.

New table only; no existing data touched. The UNIQUE constraint is declared
inline in create_table so it works identically on Postgres and SQLite (CI).
Single-column indexes on snapshot_date and symbol serve the two obvious future
reads (one day's universe; one symbol's history) — the unique constraint's
composite index already covers (snapshot_date, symbol) lookups.

Revision id kept short (well under the version_num VARCHAR(32) limit — see
memory: tapeline_alembic_version_limit).

Revision ID: 0053_score_snapshots
Revises: 0052_signin_codes
Create Date: 2026-08-23 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0053_score_snapshots"
down_revision: str | None = "0052_signin_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "score_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("sub_trend", sa.Float(), nullable=True),
        sa.Column("sub_rs", sa.Float(), nullable=True),
        sa.Column("sub_fundamentals", sa.Float(), nullable=True),
        sa.Column("sub_momentum", sa.Float(), nullable=True),
        sa.Column("sub_macro", sa.Float(), nullable=True),
        sa.Column("sub_smart_money", sa.Float(), nullable=True),
        sa.Column("confidence_pct", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "snapshot_date", "symbol", name="uq_score_snapshots_date_symbol"
        ),
    )
    op.create_index(
        "ix_score_snapshots_snapshot_date", "score_snapshots", ["snapshot_date"]
    )
    op.create_index("ix_score_snapshots_symbol", "score_snapshots", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_score_snapshots_symbol", table_name="score_snapshots")
    op.drop_index("ix_score_snapshots_snapshot_date", table_name="score_snapshots")
    op.drop_table("score_snapshots")
