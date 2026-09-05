"""scan_logs — what each scan asked for and what it returned.

On 2026-09-05 "why did this trial user cancel five minutes after a scan?" was
found to be permanently unanswerable: two of three cancellations in the first
paying cohort followed a `scan_run` within five minutes, and nothing recorded
what the scan was for or what came back.

`funnel_events` cannot carry this. It is deliberately one row per
(user, event, UTC day), so ten scans in a day produce one row — filter
parameters hung off it would describe the first scan and silently drop the
rest. This is a separate per-execution table.

Both blobs are Text holding JSON rather than a JSON column, matching
`scanner_presets.filters_json`, so SQLite (tests) and Postgres (prod) use the
identical column type. No FK on user_id: instrumentation must never block a
user row from being deleted (same posture as cap_events). Erasure is handled
explicitly in services/account_purge.py instead, because this table stores the
user's own typed search text.

Revision ID: 0064_scan_logs
Revises: 0063_drop_crypto
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0064_scan_logs"
down_revision = "0063_drop_crypto"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=60), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        # Separates a human scan from the scanner page's automatic SSE refetch.
        # Without it most rows are machine traffic and "their last scan" is a
        # background tick. See models/scan_log.py.
        sa.Column(
            "src", sa.String(length=16), server_default="unknown", nullable=False,
        ),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        # Nullable: the paginating tiers are never capped, so the endpoint does
        # not run the COUNT and there is no true value to store.
        sa.Column("total_matched", sa.Integer(), nullable=True),
        sa.Column("row_cap", sa.Integer(), nullable=False),
        sa.Column("top_symbols_json", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Composite, not a bare user_id index: every read of this table is
    # "this user's scans, newest first", and the composite removes the sort.
    op.create_index(
        "ix_scan_logs_user_created", "scan_logs", ["user_id", "created_at"]
    )
    # Indexed so a delete-older-than prune stays cheap if this table ever grows
    # enough to need one, and so "this user's scans, newest first" is a range
    # scan rather than a sort.
    op.create_index("ix_scan_logs_created_at", "scan_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_scan_logs_created_at", table_name="scan_logs")
    op.drop_index("ix_scan_logs_user_created", table_name="scan_logs")
    op.drop_table("scan_logs")
