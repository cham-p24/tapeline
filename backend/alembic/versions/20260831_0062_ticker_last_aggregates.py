"""Add tickers.last_aggregates_at so the aggregates pass can round-robin.

The daily aggregates pass selected symbols with

    ORDER BY coalesce(volume * price, -1) DESC LIMIT 2500

which ranks on the very column the pass exists to populate. `volume` is NULL
until the pass has run for a symbol, so NULLs sorted last, the first run
tie-broke on physical (alphabetical) order, and those winners sorted FIRST on
every run after. The covered set could never grow past whatever won that first
tie-break.

Measured on production 2026-08-30: volume present for 94% of A-symbols, 95% B,
92% C, 65% D, 26% E, 4-12% F-R, 1% S, 1% T, and 0% of Y and Z — 72.2% of the
11,808-ticker universe with no volume read at all. Every name in the published
Top 10 began with A, B, C or D.

This column records when a symbol's bars were last fetched, so the pass can
spend part of its budget on never-refreshed (NULL) symbols, oldest first.
`updated_at` cannot be used: the 60s scoring tick writes every scored row.

Backfill note: deliberately left NULL for every existing row. NULL means
"never fetched by the new accounting", which is exactly what makes the first
runs prioritise the ~9,300 symbols that have been starved. Stamping now() would
reproduce the freeze this migration exists to end.

Revision ID kept short — `version_num` is VARCHAR(32).
"""
from alembic import op
import sqlalchemy as sa

revision = "0062_ticker_last_agg"
down_revision = "0061_funnel_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tickers",
        sa.Column("last_aggregates_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Partial-ish index for the explore slice: it orders by this column with
    # NULLS FIRST, so the planner benefits from having it ordered.
    op.create_index(
        "ix_tickers_last_aggregates_at",
        "tickers",
        ["last_aggregates_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tickers_last_aggregates_at", table_name="tickers")
    op.drop_column("tickers", "last_aggregates_at")
