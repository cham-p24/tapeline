"""email verification: tokens table + users.email_verified_at

Closes the account-takeover vector where someone signs up with another
person's email address. The verification email contains both a "verify"
link (consumes the token, stamps email_verified_at) and a "this wasn't
me" link (cancels the account before any damage is done).

OAuth signups (Google/Microsoft/Apple) are auto-verified — the OAuth
provider already proved the user owns the address — so this only matters
for native email/password signup.

The table is intentionally tiny and short-lived (24h TTL via expires_at);
the worker prunes expired rows daily. Token is 48 url-safe chars =
~285 bits of entropy, well above what's needed for a single-use code.

Revision ID: 0024_email_verification
Revises: 0023_weekly_newsletter_pref
Create Date: 2026-05-19 06:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_email_verification"
down_revision: Union[str, None] = "0023_weekly_newsletter_pref"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_verification_tokens",
        sa.Column("token", sa.String(80), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(60),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "email_verified_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified_at")
    op.drop_table("email_verification_tokens")
