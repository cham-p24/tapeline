"""users.meta_* — the latest browser match keys for Meta Conversions API events.

Blueprint P1-P3 (docs/META_CONVERSION_BLUEPRINT_2026-09-13.md §2.3). StartTrial,
Purchase and Subscribe fire from Stripe webhooks, where no browser is present
and the request's IP address and user agent are Stripe's. Meta asks for the
browser's IP address and user agent on every website event, plus `_fbp` and
the most recent `fbc`. So those are stored from the requests the visitor's own
browser sends to the API (email signup, OAuth callback, checkout) and read back
when the webhook fires.

Adds four nullable columns to users, holding only the LATEST values:
  - meta_client_ip          varchar(45)   IPv4 or IPv6, unhashed
  - meta_client_user_agent  varchar(1024)
  - meta_fbp                varchar(200)  the `_fbp` cookie value
  - meta_fbc                varchar(500)  `fb.1.<ms>.<fbclid>`

No backfill: existing rows stay NULL until the account's next signup-path or
checkout request. Additive only; `signup_fbclid` (first-touch) is untouched.

Revision ID: 0073_user_meta_browser
Revises: 0072_alert_crossing_state
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0073_user_meta_browser"
down_revision = "0072_alert_crossing_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("meta_client_ip", sa.String(length=45), nullable=True))
    op.add_column(
        "users", sa.Column("meta_client_user_agent", sa.String(length=1024), nullable=True),
    )
    op.add_column("users", sa.Column("meta_fbp", sa.String(length=200), nullable=True))
    op.add_column("users", sa.Column("meta_fbc", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "meta_fbc")
    op.drop_column("users", "meta_fbp")
    op.drop_column("users", "meta_client_user_agent")
    op.drop_column("users", "meta_client_ip")
