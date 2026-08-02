"""api_req_per_user — move the public-API daily quota from per-key to per-account.

The daily `api_requests_per_day` quota was enforced against each ApiKey row's
own counter, so a user could mint up to MAX_KEYS_PER_USER keys and multiply the
cap (a trial user: 10 keys x 100/day = 1,000/day, defeating the anti-abuse
throttle). The quota is a per-ACCOUNT entitlement (the marketed "1,000/day"), so
enforcement moves to a single per-user counter.

Adds two columns to users:
  - api_requests_today   (int, NOT NULL, server_default 0) — the running count
  - api_requests_reset_on (varchar(10), nullable) — the "YYYY-MM-DD" UTC day it
    belongs to (matches ApiKey.requests_day's string form)

New columns only, backfilled to 0 / NULL, no behaviour change until the
authenticator's per-account gate reads them. Per-key ApiKey counters are kept
for the usage display.

Revision id kept short (well under version_num VARCHAR(32) — see memory:
tapeline_alembic_version_limit).

Revision ID: 0044_api_req_per_user
Revises: 0043_ads_conversion_upload
Create Date: 2026-08-02 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0044_api_req_per_user"
down_revision: str | None = "0043_ads_conversion_upload"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "api_requests_today",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "api_requests_reset_on",
            sa.String(length=10),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "api_requests_reset_on")
    op.drop_column("users", "api_requests_today")
