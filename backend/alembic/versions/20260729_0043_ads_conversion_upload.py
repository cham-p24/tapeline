"""ads_conversion_upload — mark when a paid subscriber's Google Ads click
conversion has been reported to Google (offline conversion import).

Adds a single nullable timestamp to users. Null = the offline-conversion
upload job (app.scripts.upload_google_ads_conversions) has NOT yet reported
this converted (trial->paid) subscriber's gclid back to Google Ads. Set once,
on a successful upload, so the daily job is idempotent and never double-counts
a conversion. New column only, nullable, no default — no existing data touched,
no behaviour change until the (founder-gated) job runs live.

Revision id kept short (well under version_num VARCHAR(32) — see memory:
tapeline_alembic_version_limit).

Revision ID: 0043_ads_conversion_upload
Revises: 0042_watchlist_track_record
Create Date: 2026-07-29 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0043_ads_conversion_upload"
down_revision: str | None = "0042_watchlist_track_record"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "ads_conversion_uploaded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "ads_conversion_uploaded_at")
