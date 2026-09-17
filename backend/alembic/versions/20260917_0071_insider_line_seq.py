"""Keep every Form 4 line: add `line_seq` to the insider natural key.

`uq_insider_natural` was (symbol, transaction_date, insider_name, share_change),
so the write collapsed any two lines sharing those four values. That was built
for Finnhub's duplicated payloads. SEC EDGAR lines that share them are
different transactions, and the collapse dropped them. Measured read-only
2026-09-17:

* GSHD: an insider's conversion (C -5,000 at $0) and her sale of the same
  5,000 shares (S at $65.20) collided. The sale was dropped, so the Insider tab
  showed a $0 conversion instead of a $326k sale.
* HFWA: vesting tranches of identical share counts on one day were stored once.

The score was always computed from every line, so about 1.4% of equities held a
sub_smart_money their own stored Form 4 rows could not reproduce, at the same
rate on sheet-owned and tick-owned rows.

`line_seq` numbers the lines that share the old four values, in the order the
source listed them. Every existing row already satisfies the old constraint, so
0 keeps them unique. No row is rewritten: each symbol's rows are replaced, with
every line, the next time the insider pass reads it.

Revision ID: 0071_insider_line_seq
Revises: 0070_job_period_claims
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0071_insider_line_seq"
down_revision = "0070_job_period_claims"
branch_labels = None
depends_on = None

_OLD = ["symbol", "transaction_date", "insider_name", "share_change"]


def upgrade() -> None:
    with op.batch_alter_table("insider_transactions") as batch:
        batch.add_column(
            sa.Column("line_seq", sa.Integer(), nullable=False, server_default="0"),
        )
        batch.drop_constraint("uq_insider_natural", type_="unique")
        batch.create_unique_constraint("uq_insider_natural", [*_OLD, "line_seq"])


def downgrade() -> None:
    # The old key cannot hold a second line with the same four values.
    op.execute("DELETE FROM insider_transactions WHERE line_seq > 0")
    with op.batch_alter_table("insider_transactions") as batch:
        batch.drop_constraint("uq_insider_natural", type_="unique")
        batch.create_unique_constraint("uq_insider_natural", _OLD)
        batch.drop_column("line_seq")
