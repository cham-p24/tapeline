"""tickers.is_non_common: flag notes, preferreds, warrants, rights and units.

Measured read-only on production 2026-09-18: 120 of the 6,012 rows stored as
stocks are not a company's common shares, and 118 of them were scored and
labelled like one. GREEL, a Greenidge 8.50% senior note due 2026, read STRONG
SETUP at 70.4, and a Brighthouse preferred (BHFAO) entered the public record on
2026-06-23. The new column is what the scorecard freeze, the default scanner,
the CSV export and the MCP `daily_picks` tool read to hold them out. See
services/non_common.py.

The backfill is Python, not SQL, for the reason 0065_ticker_is_leveraged gives:
the predicate needs regex features SQLite lacks entirely, so any SQL here would
be a different, weaker rule than the one the application ships. Importing the
helper makes the stored column and the live predicate provably the same rule.
It passes the whole universe, which four of the rules need.

Chained on 0073. Open PR #859 also chains a 0074 on 0073, and a peer's 0075
does too; whichever merges second re-chains its `down_revision`.

Revision id kept short: version_num is VARCHAR(32).

Revision ID: 0076_ticker_is_non_common
Revises: 0073_edgar_issuer_symbol
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0076_ticker_is_non_common"
down_revision = "0073_edgar_issuer_symbol"
branch_labels = None
depends_on = None

_BATCH = 500


def upgrade() -> None:
    op.add_column(
        "tickers",
        sa.Column(
            "is_non_common",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Inside upgrade(), so `alembic heads` (the CI single-head check) never
    # loads application services.
    from app.services.non_common import is_non_common_equity

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT symbol, name, asset_class FROM tickers")
    ).fetchall()
    universe = frozenset(r[0] for r in rows)

    flagged = [
        {"sym": r[0]}
        for r in rows
        if is_non_common_equity(r[0], r[1], r[2], universe)
    ]

    stmt = sa.text("UPDATE tickers SET is_non_common = true WHERE symbol = :sym")
    for i in range(0, len(flagged), _BATCH):
        bind.execute(stmt, flagged[i : i + _BATCH])


def downgrade() -> None:
    op.drop_column("tickers", "is_non_common")
