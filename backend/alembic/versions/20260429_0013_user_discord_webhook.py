"""user.discord_webhook_url + web_push_subscriptions

Revision ID: 0013_user_discord_webhook
Revises: 0012_ticker_confidence
Create Date: 2026-04-29 01:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_user_discord_webhook"
down_revision: Union[str, None] = "0012_ticker_confidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("discord_webhook_url", sa.String(300), nullable=True))

    # Web Push subscriptions — one row per (user, browser/device) combo.
    # When a user registers the Service Worker, the resulting PushSubscription
    # is POSTed here. The worker uses these endpoints + keys to deliver alerts.
    op.create_table(
        "web_push_subscriptions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(60), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("endpoint", sa.String(500), nullable=False),
        sa.Column("p256dh_key", sa.String(200), nullable=False),
        sa.Column("auth_key", sa.String(100), nullable=False),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "endpoint", name="uq_web_push_user_endpoint"),
    )


def downgrade() -> None:
    op.drop_table("web_push_subscriptions")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("discord_webhook_url")
