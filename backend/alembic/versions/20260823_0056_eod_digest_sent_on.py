"""Durable per-user dedupe for the EOD watchlist digest.

`run_eod_watchlist_digest` was the only email orchestrator with zero durable
per-recipient dedupe. Its only guard was a process-global date latch
(`_last_eod_digest_date`) set in the worker AFTER the entire batch returned
cleanly — so any partial run left the latch unset and the gate re-armed on the
very next tick, re-mailing the whole already-sent prefix. The window is ~180
ticks wide (the gate re-arms every tick while `started.hour >= 21`).

Nothing else stops it: EOD is SendClass.SCHEDULED, and FrequencyGovernor.allows
early-returns True for SCHEDULED before any ledger check, so a replay is never
blocked; and the governor's ledger is in-memory anyway.

A partial run is not hypothetical — the batch runs inline under the worker's
`asyncio.wait_for(tick(), timeout=60)` watchdog, and CancelledError is a
BaseException that slips past the `except Exception` around the call.

Revision ID: 0056_eod_digest_sent_on
Revises: 0055_alert_event_rule_null
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0056_eod_digest_sent_on"
down_revision: str | None = "0055_alert_event_rule_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("eod_digest_sent_on", sa.Date(), nullable=True))
    op.create_index(
        "ix_users_eod_digest_sent_on", "users", ["eod_digest_sent_on"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_users_eod_digest_sent_on", table_name="users")
    op.drop_column("users", "eod_digest_sent_on")
