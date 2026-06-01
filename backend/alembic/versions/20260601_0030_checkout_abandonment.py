"""checkout-abandonment recovery columns

Backs the conversion lever that detects a started-but-incomplete Stripe
Checkout and emails a one-shot resume nudge (services/email.run_checkout_
abandonment_recovery, driven hourly by the worker).

New users.* columns (all nullable, so existing rows are fine):

  checkout_started_at      DateTime. Stamped when POST /api/billing/checkout
                           mints a Stripe Checkout Session; cleared the moment
                           checkout.session.completed lands. A non-null value
                           aged 1-24h is therefore an abandoned checkout.
  checkout_tier            String(20). "pro" | "premium" — the plan being
                           bought, for the recovery email copy + resume link.
  checkout_billing_period  String(20). "monthly" | "annual".

Revision ID: 0030_checkout_abandonment
Revises: 0029_retention_lifecycle
Create Date: 2026-06-01 12:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030_checkout_abandonment"
down_revision: Union[str, None] = "0029_retention_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("checkout_started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("checkout_tier", sa.String(20), nullable=True)
        )
        batch.add_column(
            sa.Column("checkout_billing_period", sa.String(20), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("checkout_billing_period")
        batch.drop_column("checkout_tier")
        batch.drop_column("checkout_started_at")
