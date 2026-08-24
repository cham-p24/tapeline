"""Add users-facing official close to tickers, for the scorecard freeze.

`Ticker.price` is `session["price"]` — the last trade INCLUDING extended hours.
The scorecard freeze runs at 21:15 UTC = 17:15 ET, inside after-hours, so
`price_at_flag` was routinely an after-hours print rather than a close.

Measured 2026-08-24 over 11 dates: 37 of ~110 frozen rows (34%) sat 2-18% off
the vendor's official close, in both directions. That matters because
`spy_change_pct_1d` comes from SPY's daily bars — official closes — so
`alpha_vs_spy` compared an after-hours price against a close.

`day_close` carries `session["close"]` so the freeze can record a real close.

Revision ID: 0059_ticker_day_close
Revises: 0058_mcp_tool_calls
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0059_ticker_day_close"
down_revision: str | None = "0058_mcp_tool_calls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tickers", sa.Column("day_close", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("tickers", "day_close")
