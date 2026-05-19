"""users.email_prefs default += WEEKLY_NEWSLETTER

Migration 0018 created users.email_prefs with server_default="15" (all
four original bits on). We're adding a fifth bit — bit 16 = weekly
newsletter — so the new default is 31. Existing rows are NOT touched:
users who pre-date this migration never gave explicit marketing consent
(marketing_opt_in is False on every existing row), so leaving their
prefs at 15 just means "no newsletter for you". They can opt in via the
toggle on /app/settings/email — which sets both the bit and
marketing_opt_in in one go (see routers/me.py:set_email_prefs).

New signups starting from this migration get email_prefs=31. They still
need to tick marketing-opt-in at onboarding for the newsletter to
actually deliver — `email_prefs` is the day-to-day toggle, but
marketing_opt_in is the GDPR consent record.

Revision ID: 0023_email_prefs_weekly_newsletter
Revises: 0022_watchlists_and_presets
Create Date: 2026-05-19 09:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_email_prefs_weekly_newsletter"
down_revision: Union[str, None] = "0022_watchlists_and_presets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Server-default change only — existing rows stay at whatever they
    # were (15 for the typical case). New rows get 31.
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "email_prefs",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="31",
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "email_prefs",
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="15",
        )
