"""edgar_form4_filings.issuer_symbol: the ticker a Form 4 names.

SEC lists several tickers under one CIK for many issuers (preferred depositary
shares, notes, warrants, ETNs, sibling share classes). Until this change every
one of them received the issuer's whole Form 4 set, so Strategy's STRK
preferred carried MSTR's insider sales. A filing's lines now go to the ticker
the filing names in issuerTradingSymbol (services/edgar_form4.py,
`attributed_ticker`), which the parsed-filing cache has to remember.

Additive: one nullable column on a cache table.

Revision ID: 0072_edgar_issuer_symbol
Revises: 0071_insider_line_seq
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0072_edgar_issuer_symbol"
down_revision = "0071_insider_line_seq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "edgar_form4_filings",
        sa.Column("issuer_symbol", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("edgar_form4_filings", "issuer_symbol")
