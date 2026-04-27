"""stripe_webhook_events + roadmap_votes

Revision ID: 0010_idempotency_and_voting
Revises: 0009_user_drip_state
Create Date: 2026-04-27 03:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_idempotency_and_voting"
down_revision: Union[str, None] = "0009_user_drip_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "roadmap_votes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(60), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("item_slug", sa.String(80), nullable=False),
        sa.Column("voted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "item_slug", name="uq_roadmap_votes_user_item"),
    )
    op.create_index("ix_roadmap_votes_user_id", "roadmap_votes", ["user_id"])
    op.create_index("ix_roadmap_votes_item_slug", "roadmap_votes", ["item_slug"])


def downgrade() -> None:
    op.drop_index("ix_roadmap_votes_item_slug", "roadmap_votes")
    op.drop_index("ix_roadmap_votes_user_id", "roadmap_votes")
    op.drop_table("roadmap_votes")
    op.drop_table("stripe_webhook_events")
