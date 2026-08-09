"""signup_landing_path — capture WHICH page earned the signup, not just
which channel.

Attribution already stores the channel: signup_utm_* (tagged links),
signup_gclid/gbraid/wbraid (paid Google clicks) and signup_referrer_host
(AI-assistant / other external referrers). None of them say which of our
~4,750 published SEO URLs the visitor first landed on, so "organic search
brought 6 signups" can't be acted on — /compare/finviz, /glossary/rsi and a
ticker page are indistinguishable, and you can't double down on the format
that actually converts.

The frontend captures the first-touch PATHNAME with the same localStorage
first-touch/30-day-TTL mechanism as the other captures and forwards it on the
signup POST.

Adds one column to users:
  - signup_landing_path (varchar(200), nullable) — first-touch path on our
    own site, e.g. "/glossary/rsi". Normalised: lowercase, trailing slash
    dropped, query string and hash stripped (privacy: they can carry search
    terms or identifiers; they also destroy aggregation cardinality).
    Written once at signup, never updated. Null for existing rows and any
    client that doesn't forward it.

New column only, no backfill, no behaviour change for existing rows.

Revision id kept short (well under version_num VARCHAR(32) — see memory:
tapeline_alembic_version_limit).

Revision ID: 0046_signup_landing_path
Revises: 0045_signup_referrer
Create Date: 2026-08-09 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0046_signup_landing_path"
down_revision: str | None = "0045_signup_referrer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("signup_landing_path", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "signup_landing_path")
