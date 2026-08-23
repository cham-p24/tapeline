"""signup_fbclid — capture the Meta click id, the missing half of paid-click
attribution.

Gap G4 in docs/PAID_ADS_METRICS_BIBLE.md §2.8. Attribution already stores the
Google side of a paid click (signup_gclid / signup_gbraid / signup_wbraid,
migration 0039) and the un-tagged side (signup_referrer_host,
signup_landing_path). Nothing captured Meta's `fbclid`, which has two
consequences the doc spells out in §7.1:

  - Event Match Quality plateaus around 5-6, because the only identifiers the
    Conversions API receives are a hashed email and a hashed user id. `fbc`
    (derived from fbclid) is the cheapest available upgrade and needs no new
    PII.
  - The fbclid -> User -> Stripe join cannot exist. Tapeline's trial is 14
    days, so the first charge lands outside Meta's 7-day click window by
    construction and the in-platform Purchase column reads ~0 regardless of
    truth. Joining our own rows is the only honest Meta payer count.

Adds one column to users:
  - signup_fbclid (varchar(200), nullable) — the RAW fbclid query param as it
    arrived, not the `fb.1.<ts>.<fbclid>` wire format. The wire value is built
    at send time by services/meta_capi.fbc_value(); see that function for why
    the format is not stored. Written once at signup, never updated. Null for
    existing rows, for organic traffic, and for any client that doesn't
    forward it.

Same shape as 0039 (String(200) — click ids are long opaque tokens), same
write-once contract, no backfill, no behaviour change for existing rows.

Revision id kept short (well under version_num VARCHAR(32) — see memory:
tapeline_alembic_version_limit).

Revision ID: 0053_signup_fbclid
Revises: 0052_signin_codes
Create Date: 2026-08-23 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0053_signup_fbclid"
down_revision: str | None = "0052_signin_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("signup_fbclid", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "signup_fbclid")
