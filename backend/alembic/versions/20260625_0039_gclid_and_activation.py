"""measurement: signup gclid capture + activation milestone

Two Growth-Playbook measurement gaps, one migration:

1) `users.signup_gclid` / `signup_gbraid` / `signup_wbraid` (§3.7) — Google Ads
   click IDs captured at signup, same write-once mechanism as the existing
   signup_utm_* columns. `gclid` is the Search/Display click ID; `gbraid` /
   `wbraid` are the iOS-privacy app/web variants. Stored so the founder-gated
   offline-conversion upload to Google (value-based bidding) has the click ID
   available to tie a converted subscriber back to its paid click. Nullable —
   only paid Google traffic carries these; wider than the UTM cols because
   gclids are long opaque tokens.

2) `users.activated_at` (§4.2) — activation milestone timestamp, stamped the
   FIRST time a user adds a watchlist ticker (consistent with the existing
   act_wl activation drip, which already treats "first watchlist ticker added"
   as activation milestone #1). Set once, never overwritten. Surfaced as
   activation_rate in the admin revenue dashboard.

Revision ID: 0039_gclid_and_activation
Revises: 0038_merge_0037_heads
Create Date: 2026-06-25 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0039_gclid_and_activation"
down_revision: str | None = "0038_merge_0037_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("signup_gclid", sa.String(200), nullable=True))
        batch.add_column(sa.Column("signup_gbraid", sa.String(200), nullable=True))
        batch.add_column(sa.Column("signup_wbraid", sa.String(200), nullable=True))
        batch.add_column(
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("activated_at")
        batch.drop_column("signup_wbraid")
        batch.drop_column("signup_gbraid")
        batch.drop_column("signup_gclid")
