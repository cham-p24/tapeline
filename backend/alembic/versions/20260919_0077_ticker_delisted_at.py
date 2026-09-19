"""tickers.delisted_at: when a symbol stopped appearing among the vendor's active listings.

Until this change nothing retired a ticker. The universe refresh reconciled
discovery into the table but never looked at what discovery had stopped
returning, so a symbol that stopped trading kept its row, its last price
(day_close = previous_close), a daily score, a daily score_snapshots row and a
place on every ranked surface. Measured read-only on 2026-09-19: GREE
(Greenidge, renamed VIP on 24 Jul 2026) read 75.8 STRONG SETUP; HLX (merged
into HOS, last traded 1 Sep) 65.3; CYCN (now KRSA since 9 Sep) 60.8 with a
-85.5% daily move; TOI (now STLN since 4 Aug) 66.0; BBBY (now NXH since
17 Aug) 28.1.

`delisted_at` is stamped by signal_publisher._refresh_universe when a COMPLETE
discovery walk no longer lists the symbol, and cleared if it reappears. NULL
means listed (or never checked). services/ticker_freshness.listed_clause is
the one predicate every reader uses.

Additive: one nullable column, no backfill. Which rows are retired is only
known after the first complete walk in production, so there is nothing honest
to backfill with here.

Revision ID: 0077_ticker_delisted_at
Revises: 0075_ticker_quote_at
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0077_ticker_delisted_at"
down_revision = "0075_ticker_quote_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tickers",
        sa.Column("delisted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tickers", "delisted_at")
