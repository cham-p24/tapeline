"""subscription billing_period column

Adds subscriptions.billing_period ("monthly" | "annual"), nullable so existing
rows are unaffected. Backs exact MRR/ARR in the founder revenue dashboard
(services/tier.mrr_contribution + routers/admin.revenue_dashboard) — without it
an annual Pro ($24.99/mo recognized) was counted at the $29.99 monthly rate.

Populated going forward by billing.subscription_payload off the Stripe price's
recurring.interval ("year" -> annual, else monthly), persisted in the
customer.subscription.created/updated webhook upsert. Legacy NULL rows are
treated as monthly by mrr_contribution and self-heal on their next renewal
webhook.

Revision ID: 0031_sub_billing_period
Revises: 0030_checkout_abandonment
Create Date: 2026-06-01 14:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_sub_billing_period"
down_revision: Union[str, None] = "0030_checkout_abandonment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch:
        batch.add_column(
            sa.Column("billing_period", sa.String(20), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch:
        batch.drop_column("billing_period")
