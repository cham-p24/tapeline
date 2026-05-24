"""inbox bot — classification log + daily spend rollup

Phase A.5 of the inbox-bot ship list. Adds the audit + cost-tracking layer
on top of the Phase A `inbound_messages` table (migration 0026).

One row per LLM classification call. Existing rule-based fast-path matches
don't write here — the table is exclusively for LLM-backed decisions where
we want:

  - **Audit:** which model produced which tier, with the exact input + reason
    so future misclassifications can be tuned (system prompt, fixture set).
  - **Cost ceiling:** services/inbox_kill_switch.py SUMs `cost_usd` for the
    UTC day; when it exceeds `INBOX_CLAUDE_DAILY_CAP_USD`, the classifier
    skips the LLM and defaults every ambiguous message to Tier 1 manual
    review. Prevents a runaway feedback loop from incinerating the API bill.
  - **Latency monitoring:** if `latency_ms` p95 creeps up, we know to either
    bump the model down a tier or fix a prompt-cache miss before it hurts UX.

`inbound_message_id` is nullable so we can log dry-run / shadow classifications
that aren't tied to a stored InboundMessage row.

`input_hash` is the SHA-256 of the normalised body — used for dedup checks
and for spot-checking "did we get a consistent verdict on the same input
across model versions" without exposing the full body in dashboards.

Revision ID: 0027_inbox_classification_log
Revises: 0026_inbox_auto_handler
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0027_inbox_classification_log"
down_revision = "0026_inbox_auto_handler"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inbox_classification_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Nullable — dry-run / shadow classifications during model evals
        # have no InboundMessage row.
        sa.Column("inbound_message_id", sa.Integer(), nullable=True),
        # SHA-256 of normalised body (lowercased, whitespace-collapsed).
        # 64 hex chars.
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        # 'claude-haiku-4-5', 'claude-sonnet-4-5', or 'rule-based-fallback'
        # when the LLM was skipped (cap exceeded, key missing).
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        # Cached tokens reported separately so we can verify prompt caching
        # is actually firing (should be ~95% of input on warm cache).
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
        # USD with 6dp precision — typical Haiku call is fractions of a cent.
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=6), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        # 1/2/3 — what the classifier returned. Nullable for error rows.
        sa.Column("tier", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        # Truncated to 240 chars to keep the audit table queryable; full
        # error stack goes to logs / Sentry.
        sa.Column("error", sa.String(length=240), nullable=True),
    )
    op.create_index(
        "ix_inbox_classification_log_created_at",
        "inbox_classification_log",
        ["created_at"],
    )
    op.create_index(
        "ix_inbox_classification_log_input_hash",
        "inbox_classification_log",
        ["input_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inbox_classification_log_input_hash",
        table_name="inbox_classification_log",
    )
    op.drop_index(
        "ix_inbox_classification_log_created_at",
        table_name="inbox_classification_log",
    )
    op.drop_table("inbox_classification_log")
