"""embed_impressions — measure the badge / iframe distribution loop.

`/badge/{SYMBOL}` (README SVG) and `/embed/score/{SYMBOL}` (iframe widget) exist
to be rendered on other people's sites, and both were completely uninstrumented:
every render was an invisible brand impression. This table makes the loop
measurable — which sites carry us, which tickers get embedded, and whether the
trend is up.

One AGGREGATED row per (day, host, symbol, surface), INCREMENTED — not one row
per request. Badges are hotlinked images; a row-per-render log would be unbounded
in traffic while this is bounded by the number of distinct embedding sites.

Privacy: `host` is the embedding site's HOSTNAME ONLY, never the referring URL
(a path/query can carry a search phrase, a title, or a session token from a
third-party site). Same posture as users.signup_referrer_host, same String(100)
cap. Normalisation lives in services/embed_impressions.normalize_embed_host.

Revision id kept short (well under version_num VARCHAR(32) — see memory:
tapeline_alembic_version_limit).

Revision ID: 0047_embed_impressions
Revises: 0046_signup_landing_path
Create Date: 2026-08-09 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0047_embed_impressions"
down_revision: str | None = "0046_signup_landing_path"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "embed_impressions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("host", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("surface", sa.String(length=8), nullable=False),
        sa.Column(
            "impressions", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        # Load-bearing: the recorder does UPDATE-then-INSERT-on-miss and relies
        # on this constraint to catch a concurrent first-write for the same
        # bucket, at which point it retries the increment instead of
        # duplicating the row.
        sa.UniqueConstraint(
            "day", "host", "symbol", "surface", name="uq_embed_impression_bucket"
        ),
    )
    op.create_index("ix_embed_impressions_day", "embed_impressions", ["day"])
    op.create_index(
        "ix_embed_impressions_day_host", "embed_impressions", ["day", "host"]
    )
    op.create_index(
        "ix_embed_impressions_day_symbol", "embed_impressions", ["day", "symbol"]
    )


def downgrade() -> None:
    op.drop_index("ix_embed_impressions_day_symbol", table_name="embed_impressions")
    op.drop_index("ix_embed_impressions_day_host", table_name="embed_impressions")
    op.drop_index("ix_embed_impressions_day", table_name="embed_impressions")
    op.drop_table("embed_impressions")
