"""SEC EDGAR Form 4 filings, parsed once and kept by accession number.

A filing on EDGAR never changes after it is accepted - a correction arrives as a
new 4/A with its own accession number - so the XML behind an accession only ever
has to be fetched and parsed once. The insider pass re-reads each issuer's
submission list on its horizon, then fetches only the accessions this table does
not already hold at the current `parse_version`. Without it every re-read would
re-download every Form 4 in the 90-day window.

This is a cache of public filings, not a record of anything Tapeline decided:
dropping every row loses nothing but download time. What the product serves is
still `insider_transactions`, which the pass writes per symbol from these rows.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EdgarForm4Filing(Base):
    __tablename__ = "edgar_form4_filings"
    __table_args__ = (
        Index("ix_edgar_form4_issuer_filed", "issuer_cik", "filing_date"),
    )

    #: "0001140361-26-036226" - EDGAR's own id for the filing.
    accession: Mapped[str] = mapped_column(String(25), primary_key=True)
    #: "4" or "4/A", from the issuer's submission list.
    form: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    #: YYYY-MM-DD, the date EDGAR accepted the filing.
    filing_date: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    #: Zero-padded 10-digit issuer CIK as the XML states it. Empty when the
    #: filing could not be parsed. A company's submission list also carries Form
    #: 4s it filed as an OWNER of another issuer, so rows are only ever served
    #: for the issuer named here.
    issuer_cik: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    owner_cik: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    owner_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    #: A 4/A's dateOfOriginalSubmission; the amendment replaces the owner's
    #: Form 4 filed that day.
    original_filing_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    #: JSON list of non-derivative transaction lines. NULL = the document could
    #: not be read (missing or malformed XML); kept so it is not re-fetched on
    #: every pass.
    rows_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: `edgar_form4.PARSE_VERSION` at parse time. A row at an older version is
    #: fetched and parsed again.
    parse_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
