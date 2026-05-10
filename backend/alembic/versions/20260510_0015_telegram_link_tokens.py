"""Telegram link tokens — one-click signup flow

Replaces the manual chat_id paste UX with a deep-link round-trip:
1. User clicks "Connect Telegram" -> backend mints a token tied to user_id
2. Frontend opens https://t.me/Tapeline_Bot?start=<token>
3. User taps Start in Telegram -> bot receives /start <token>
4. Webhook handler matches token to user, persists chat_id, deletes token

Tokens expire after 10 minutes. Rows are deleted on successful link or
on expiry sweep. The table stays small (one row per pending link).

Revision ID: 0015_telegram_link_tokens
Revises: 0014_widen_news_tickers
Create Date: 2026-05-10 16:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_telegram_link_tokens"
down_revision: Union[str, None] = "0014_widen_news_tickers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_link_tokens",
        sa.Column("token", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(60), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("telegram_link_tokens")
