"""Insider Form 4 from SEC EDGAR: the parsed-filing cache and a row source.

The insider pass read Form 4 transactions from Finnhub. Measured 2026-09-14,
Finnhub's newest Form 4 filing for AAPL, NVDA and META was 14, 67 and 30 days
older than the newest on SEC EDGAR, and for JPM it returned 12 filings in 90
days where EDGAR lists 134 in a year. The pass now reads EDGAR directly.

* `edgar_form4_filings` caches each parsed filing by accession number, so an
  issuer re-read only downloads filings it has not seen. Pure cache: public
  data, safe to empty.
* `insider_transactions.source` is NULL on every existing (Finnhub) row and
  "edgar" on rows the new pass writes. Nothing is deleted here - the pass
  replaces each symbol's rows as it re-reads it.

Additive only: one new table, one nullable column.

Revision ID: 0069_edgar_form4
Revises: 0068_scorecard_single_writer
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0069_edgar_form4"
down_revision = "0068_scorecard_single_writer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "edgar_form4_filings",
        sa.Column("accession", sa.String(length=25), primary_key=True),
        sa.Column("form", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("filing_date", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("issuer_cik", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("owner_cik", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("owner_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("original_filing_date", sa.String(length=10), nullable=True),
        sa.Column("rows_json", sa.Text(), nullable=True),
        sa.Column("parse_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index(
        "ix_edgar_form4_issuer_filed", "edgar_form4_filings", ["issuer_cik", "filing_date"],
    )
    op.add_column(
        "insider_transactions", sa.Column("source", sa.String(length=12), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("insider_transactions", "source")
    op.drop_index("ix_edgar_form4_issuer_filed", table_name="edgar_form4_filings")
    op.drop_table("edgar_form4_filings")
