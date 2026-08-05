"""signup_referrer — capture the signup referrer host so AI-assistant
signups stop landing as "direct".

A Microsoft Copilot referral (copilot.com) produced a real Premium-trial
signup, but AI-assistant referrals carry NO utm_* params — the only trace is
`document.referrer`. The frontend now captures the referrer HOSTNAME ONLY
(privacy: never path/query — an AI-chat referrer path can carry the user's
prompt text) with the same localStorage first-touch/30-day-TTL mechanism as
the signup_utm_* capture, and forwards it on the signup POST.

Adds one column to users:
  - signup_referrer_host (varchar(100), nullable) — external referrer
    hostname at first touch. Null for direct traffic and internal
    navigation. Written once at signup, never updated.

New column only, no backfill, no behaviour change for existing rows.

Revision id kept short (well under version_num VARCHAR(32) — see memory:
tapeline_alembic_version_limit).

Revision ID: 0045_signup_referrer
Revises: 0044_api_req_per_user
Create Date: 2026-08-06 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0045_signup_referrer"
down_revision: str | None = "0044_api_req_per_user"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("signup_referrer_host", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "signup_referrer_host")
