"""Durable once-per-period claims for the worker's founder jobs.

The weekly SEO digest was latched in process memory and ran inline in the
tick. On a Monday every restart forgot the latch, ran the digest again inside
the tick, and the 240s watchdog killed it: measured 2026-09-14 18:45Z, four
minutes with no price pass after the deploy. `job_period_claims` holds the
claim in the database instead, so a restart neither re-runs nor re-sends it.

Additive only: one new table.

Revision ID: 0070_job_period_claims
Revises: 0069_edgar_form4
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0070_job_period_claims"
down_revision = "0069_edgar_form4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_period_claims",
        sa.Column("job", sa.String(length=64), primary_key=True),
        sa.Column("period", sa.String(length=32), primary_key=True),
        sa.Column(
            "claimed_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("job_period_claims")
