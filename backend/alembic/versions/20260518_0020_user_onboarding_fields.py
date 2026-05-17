"""user onboarding fields

Captures the investor profile we ask for on the post-signup onboarding
step. All fields are nullable so existing users (created before this
migration) don't break — they keep onboarding_completed_at = NULL and
the frontend prompts them to fill it in the next time they sign in.

  experience_level       beginner | intermediate | advanced
  trading_style          day | swing | longterm | mixed
  portfolio_band         under_10k | 10_50k | 50_250k | 250k_plus | prefer_not_to_say
  referral_source        twitter_x | reddit | youtube | podcast | friend | search | hacker_news | other
  marketing_opt_in       Boolean. Explicit consent for the weekly newsletter
                         (GDPR posture). Default False — opt-in, not opt-out.
  sectors_of_interest    Comma-separated sector slugs (technology, healthcare,
                         financials, energy, etc.). Single column, not a join
                         table, because we never query by sector — only read
                         the user's selection back on /app/settings.
  onboarding_completed_at  Set when the user submits OR skips the onboarding
                           page. Drives the post-signup redirect: users with
                           NULL here get bounced through /app/onboarding once.

Revision ID: 0020_user_onboarding_fields
Revises: 0019_insider_transactions
Create Date: 2026-05-18 12:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_user_onboarding_fields"
down_revision: Union[str, None] = "0019_insider_transactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("experience_level", sa.String(20), nullable=True))
        batch.add_column(sa.Column("trading_style", sa.String(20), nullable=True))
        batch.add_column(sa.Column("portfolio_band", sa.String(20), nullable=True))
        batch.add_column(sa.Column("referral_source", sa.String(40), nullable=True))
        batch.add_column(
            sa.Column(
                "marketing_opt_in",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("sectors_of_interest", sa.String(400), nullable=True))
        batch.add_column(
            sa.Column(
                "onboarding_completed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("onboarding_completed_at")
        batch.drop_column("sectors_of_interest")
        batch.drop_column("marketing_opt_in")
        batch.drop_column("referral_source")
        batch.drop_column("portfolio_band")
        batch.drop_column("trading_style")
        batch.drop_column("experience_level")
