"""Add nullable users.trial_started_at — "has this account ever trialled?"

The 14-day Premium trial is now card-required: signup creates a FREE account
and the trial only begins when a Stripe Checkout with a card comes back
`trialing` (routers/webhooks.py). That makes the one-trial-per-account gate a
real question we could not previously answer — `trial_ends_at` stays set after
a trial finishes, so it cannot distinguish "never trialled" from "trial over",
and both cohorts read as tier=free.

Adds one column to users:
  - trial_started_at (timestamptz, nullable) — stamped ONCE when a trial
    actually starts, never cleared. Null = never trialled.

No backfill. Legacy rows from the old no-card auto-trial keep trial_started_at
NULL while carrying a non-null trial_ends_at; the eligibility gate in
routers/billing.py checks BOTH columns, so those users are still correctly
treated as having already used their trial. Backfilling trial_started_at from
`created_at` would have been a guess (it would also stamp accounts whose trial
was never actually granted), so the gate reads the two columns instead.

Nullable add → safe online change on Postgres (no table rewrite, no default
backfill) and a plain ALTER on SQLite. Dialect-agnostic: sa.DateTime with
timezone=True maps to timestamptz on Postgres and DATETIME on SQLite, matching
every other timestamp column on this table. Downgrade drops it.

Idempotent in the only sense that matters for Alembic: a single add_column
guarded by the alembic_version stamp, exactly like 0045/0049.

Revision id kept short (well under version_num VARCHAR(32) — see memory:
tapeline_alembic_version_limit).

Revision ID: 0050_user_trial_started_at
Revises: 0049_ticker_market_cap
Create Date: 2026-08-21 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0050_user_trial_started_at"
down_revision: Union[str, None] = "0049_ticker_market_cap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "trial_started_at")
