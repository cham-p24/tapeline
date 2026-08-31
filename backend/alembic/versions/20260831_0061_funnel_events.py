"""funnel_events — activation events plus the counterfactual card-wall verdict.

The card wall was removed on 2026-08-30 (#683). Whether that was right cannot
be settled by an A/B test at two to three signups a month — detecting a 5% vs
10% difference needs roughly 430 per arm, so a split would take decades and
would halve the only signal there is meanwhile.

This table supports the question that IS answerable without splitting traffic:
how much product use was sitting on the other side of that wall. Every row
carries `would_have_been_walled`, computed from the same
`services.tier.must_add_card` predicate the wall itself used.

It also closes a plain gap. Nothing recorded that a user ran a scan.
`users.lookups_today` counts ticker pages; `cap_events` only fires when someone
is REFUSED. A free user who ran five scans and hit no limit left no trace, and
running a scan is the primary activation event under the current design.

One row per (user, event, UTC day), enforced by a unique index rather than by
SELECT-then-INSERT so concurrent requests race into the constraint instead of
into duplicate rows.

Revision ID: 0061_funnel_events
Revises: 0060_consent_provenance
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0061_funnel_events"
down_revision = "0060_consent_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "funnel_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("user_id", sa.String(length=60), nullable=False),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column(
            "would_have_been_walled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_funnel_events_user_id", "funnel_events", ["user_id"])
    op.create_index("ix_funnel_events_event", "funnel_events", ["event"])
    op.create_index(
        "ix_funnel_events_event_day", "funnel_events", ["event", "day"]
    )
    # The dedup guarantee. The writer depends on this existing.
    op.create_index(
        "ux_funnel_events_user_event_day",
        "funnel_events",
        ["user_id", "event", "day"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_funnel_events_user_event_day", table_name="funnel_events")
    op.drop_index("ix_funnel_events_event_day", table_name="funnel_events")
    op.drop_index("ix_funnel_events_event", table_name="funnel_events")
    op.drop_index("ix_funnel_events_user_id", table_name="funnel_events")
    op.drop_table("funnel_events")
