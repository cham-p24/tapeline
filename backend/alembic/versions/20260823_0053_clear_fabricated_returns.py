"""Clear the fabricated 5-day and 1-month returns.

`Ticker.change_pct_5d` and `Ticker.change_pct_1m` were never measured. They came
from mock_feed's `random.gauss(0, 3.0)` and `random.gauss(2, 6.0)`: polygon_feed
builds each row on the mock base and overrides only some fields, so both draws
survived into production and were rewritten every 60 seconds.

Confirmed on the live database before this migration: change_pct_5d had mean
-0.023 and standard deviation 3.011 across 2,500 rows — the signature of the
generator, not of a market.

The code fix derives both from the daily OHLCV bars we already fetch. But the
snapshot writer COALESCEs cache-derived columns (so a cold cache cannot erase good
data), which means a stale fabricated value would be PRESERVED for any symbol
whose bars cannot support a real one. Hence this one-time clear: delete the
invented numbers so the columns hold either a measurement or an honest NULL, and
never a leftover.

Not reversible in any meaningful sense, and deliberately so — downgrade is a
no-op. Restoring random numbers is not a state worth returning to; the next
worker pass repopulates the real values.

Revision ID: 0053_clear_fabricated_returns
Revises: 0052_signin_codes
"""
from __future__ import annotations

from alembic import op

revision: str = "0053_clear_fabricated_returns"
down_revision: str | None = "0052_signin_codes"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Dialect-agnostic: plain UPDATE, no server-specific syntax.
    op.execute(
        "UPDATE tickers SET change_pct_5d = NULL, change_pct_1m = NULL "
        "WHERE change_pct_5d IS NOT NULL OR change_pct_1m IS NOT NULL"
    )


def downgrade() -> None:
    # Intentionally a no-op. The previous state was fabricated data; there is
    # nothing to restore and restoring it would be the bug.
    pass
