"""Record WHEN and HOW marketing consent was given, not just that it was.

`users.marketing_opt_in` is a bare boolean written from three different
surfaces (signup form, onboarding submit, settings). A boolean records the
answer but not the evidence.

Under the Australian Spam Act 2003 — the governing regime, since Tapeline
sends from Melbourne, rather than the laxer US CAN-SPAM opt-out regime most
email advice assumes — the ONUS OF PROVING CONSENT sits with the sender. If
ACMA asks when a given recipient consented and what they were shown, `True`
is not an answer. This adds the two columns that make it one:

  marketing_opt_in_at      — the instant consent was recorded (UTC)
  marketing_opt_in_source  — which surface recorded it

BACKFILL POLICY, deliberately conservative. Existing opted-in rows get
`marketing_opt_in_at = created_at` and the source `backfill_unverified`. That
is NOT a claim that consent was given at signup — it is a truthful marker that
the timestamp was reconstructed and the surface is unknown. Inventing a
specific source ("signup_form") for rows we cannot verify would manufacture
exactly the evidence this migration exists to make trustworthy. Rows that
never opted in are left NULL.

Revision ID: 0060_consent_provenance
Revises: 0059_ticker_day_close
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0060_consent_provenance"
down_revision: str | None = "0059_ticker_day_close"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("marketing_opt_in_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("marketing_opt_in_source", sa.String(40), nullable=True),
    )

    # Reconstruct what can be reconstructed, and label it as reconstructed.
    op.execute(
        """
        UPDATE users
           SET marketing_opt_in_at = created_at,
               marketing_opt_in_source = 'backfill_unverified'
         WHERE marketing_opt_in = true
           AND marketing_opt_in_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("users", "marketing_opt_in_source")
    op.drop_column("users", "marketing_opt_in_at")
