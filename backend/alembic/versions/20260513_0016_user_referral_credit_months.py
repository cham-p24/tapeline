"""user.referral_credit_months

Tracks free months earned via the referral program. Both the referrer and
the referee get +1 on a successful referral signup; the credit is consumed
at next Stripe checkout (one-shot 100%-off coupon, duration_in_months=N)
and zeroed in the customer.subscription.created webhook.

Revision ID: 0016_user_referral_credit_months
Revises: 0015_telegram_link_tokens
Create Date: 2026-05-13 14:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_user_referral_credit_months"
down_revision: Union[str, None] = "0015_telegram_link_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "referral_credit_months",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("referral_credit_months")
