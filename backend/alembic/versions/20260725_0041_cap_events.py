"""cap_events — append-only free-tier cap-hit log

Backs the free→paid micro-funnel instrumentation. One row per moment a FREE
user is refused MORE of a metered resource at a server-side enforcement point
(scanner row cap, daily look-up cap, watchlist cap, web-push allowance, squeeze
preview). Written fire-and-forget by services/cap_events.record_cap_hit; read
only by low-N aggregate roll-ups that make the future free-tier-tightening
decision data-driven.

NO cap VALUES change here — this is pure instrumentation (a new table only).

`user_id` carries no FK on purpose: this is an audit/analytics trail that must
survive a user-row deletion, matching the no-FK posture of
inbox_classification_log. Indexes on created_at / user_id / cap cover the three
roll-up axes (time series, per-user funnel, per-cap totals).

Revision id kept short (well under the version_num VARCHAR(32) limit — see
memory: tapeline_alembic_version_limit).

Revision ID: 0041_cap_events
Revises: 0040_session_revocation
Create Date: 2026-07-25 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0041_cap_events"
down_revision: str | None = "0040_session_revocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cap_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # No FK to users — append-only trail must outlive a deleted user.
        sa.Column("user_id", sa.String(length=60), nullable=False),
        # One of {scanner_rows, daily_lookups, watchlist_tickers,
        # web_push_alerts, squeeze_preview}.
        sa.Column("cap", sa.String(length=32), nullable=False),
        # Denormalised tier at hit-time. Always "free" today.
        sa.Column("tier", sa.String(length=20), nullable=False),
    )
    op.create_index("ix_cap_events_created_at", "cap_events", ["created_at"])
    op.create_index("ix_cap_events_user_id", "cap_events", ["user_id"])
    op.create_index("ix_cap_events_cap", "cap_events", ["cap"])


def downgrade() -> None:
    op.drop_index("ix_cap_events_cap", table_name="cap_events")
    op.drop_index("ix_cap_events_user_id", table_name="cap_events")
    op.drop_index("ix_cap_events_created_at", table_name="cap_events")
    op.drop_table("cap_events")
