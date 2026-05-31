"""inbox auto-handler — inbound_messages table

Phase A of the inbox-bot ship list (docs/launch/TAPELINE_BOT_PROMPT.md).
Creates the persistent store + idempotency layer for inbound messages
across Reddit, email, and Telegram. Subsequent phases add the channel
pollers, the LLM classifier, and the reply adapters.

Schema rationale (one row per inbound message):

  channel + channel_msg_id  unique pair — idempotency. PRAW or the
                            Resend webhook can deliver the same
                            message twice (rate-limit retries, dual
                            polling windows); a second insert no-ops on
                            the unique constraint.
  author                    @handle / email / chat_id, free-form. No
                            FK to users because most inbound senders
                            aren't Tapeline customers.
  body                      Full message text. Tier 1 LLM
                            classification needs the whole thing.
  tier (1|2|3, nullable)    Set by the classifier worker on next tick.
                            Indexed so the worker can fetch pending
                            messages efficiently.
  status                    State machine: 'new' → 'classified' →
                            ['approved' | 'auto_replied' | 'ignored']
                            → 'sent'. Indexed for the same reason.
  telegram_alert_message_id Reply card we sent the founder so we can
                            edit it ("Approved ✓") when they tap.

Revision ID: 0026_inbox_auto_handler
Revises: 0025_newsletter_and_signup_utm
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0026_inbox_auto_handler"
down_revision = "0025_newsletter_and_signup_utm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inbound_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("channel_msg_id", sa.String(length=200), nullable=False),
        sa.Column("author", sa.String(length=200), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=True),
        sa.Column("tier_reason", sa.String(length=500), nullable=True),
        sa.Column("suggested_reply", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="new",
        ),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_alert_message_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "channel", "channel_msg_id", name="uq_inbox_channel_msgid",
        ),
    )
    op.create_index(
        "ix_inbound_messages_channel", "inbound_messages", ["channel"],
    )
    op.create_index(
        "ix_inbound_messages_author", "inbound_messages", ["author"],
    )
    op.create_index(
        "ix_inbound_messages_tier", "inbound_messages", ["tier"],
    )
    op.create_index(
        "ix_inbound_messages_status", "inbound_messages", ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_inbound_messages_status", table_name="inbound_messages")
    op.drop_index("ix_inbound_messages_tier", table_name="inbound_messages")
    op.drop_index("ix_inbound_messages_author", table_name="inbound_messages")
    op.drop_index("ix_inbound_messages_channel", table_name="inbound_messages")
    op.drop_table("inbound_messages")
