"""edgar_form4_filings.issuer_symbol: the ticker a Form 4 names.

SEC lists several tickers under one CIK for many issuers (preferred depositary
shares, notes, warrants, ETNs, sibling share classes). Until this change every
one of them received the issuer's whole Form 4 set, so Strategy's STRK
preferred carried MSTR's insider sales. A filing's lines now go to the ticker
the filing names in issuerTradingSymbol (services/edgar_form4.py,
`attributed_ticker`), which the parsed-filing cache has to remember.

Additive: one nullable column on a cache table.

Revision ID: 0073_edgar_issuer_symbol
Revises: 0072_alert_crossing_state
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0073_edgar_issuer_symbol"
down_revision = "0072_alert_crossing_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "edgar_form4_filings",
        sa.Column("issuer_symbol", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("edgar_form4_filings", "issuer_symbol")
