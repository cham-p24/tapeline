"""tickers.quote_at + tickers.quote_timeframe: the vendor's own time for a price.

Until this change the only timestamp on a ticker row was `updated_at`, which is
our database write time. The 60-second tick re-stamps it on every row it
writes, including rows the vendor returned nothing for, and every in-app "As of"
read it. On a 15-minute-delayed plan that presented a quarter-hour-old price as
seconds old.

`quote_at` holds the time the VENDOR attached to the price (trade, then quote,
then minute-bar end; never our clock), and `quote_timeframe` the vendor's own
DELAYED / REAL-TIME flag when it sends one. Both NULL means "no vendor time",
which the UI states as the plan's delay (for a crypto pair, its daily-close
cadence) rather than as a time.

Additive: two nullable columns, no backfill (there is no honest value to
backfill with).

Numbered 0075 but chained after 0076_ticker_is_non_common (#875), which merged
first from the same parent (0073); the id is only a label, and CI asserts a
single head. A parallel change numbered 0074 must likewise chain after
whichever of these is head when it merges.

Revision ID: 0075_ticker_quote_at
Revises: 0076_ticker_is_non_common
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0075_ticker_quote_at"
down_revision = "0076_ticker_is_non_common"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tickers",
        sa.Column("quote_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tickers",
        sa.Column("quote_timeframe", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tickers", "quote_timeframe")
    op.drop_column("tickers", "quote_at")
