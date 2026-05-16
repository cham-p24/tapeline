"""Tests for the SEC EDGAR 8-K direct adapter.

These tests exercise the parsing logic in isolation — no network calls
to sec.gov (CI doesn't have outbound internet to .gov). We feed a
hand-crafted Atom XML payload that mirrors the real EDGAR output and
verify each invariant we depend on downstream:

  - title / url / published_at extracted from <entry>
  - CIK extracted from the <id> URL (zero-padded to 10 digits)
  - CIK → ticker resolved via the in-memory map we pass in
  - Filings without a parseable timestamp are dropped, not returned
    with `published_at = None` (which would crash the NewsItem insert)
  - Accession number used as the stable ID

If any of these break, the news bar starts missing 8-K filings or
inserting malformed rows. Easier to catch the regression in CI than
in production logs.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from app.services.edgar_feed import _ATOM_NS, _parse_entry


def _make_entry(
    title: str = "8-K - Current report",
    url: str = "https://www.sec.gov/Archives/edgar/data/320193/000032019326000045/0000320193-26-000045-index.htm",
    raw_id: str = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193&accession_number=0000320193-26-000045",
    updated: str = "2026-05-16T14:32:11-04:00",
    summary: str | None = "8-K filed by Apple Inc.",
) -> ET.Element:
    """Build an <entry> element matching EDGAR's Atom feed shape."""
    ns_url = _ATOM_NS["a"]
    entry = ET.Element(f"{{{ns_url}}}entry")
    ET.SubElement(entry, f"{{{ns_url}}}title").text = title
    link = ET.SubElement(entry, f"{{{ns_url}}}link")
    link.set("href", url)
    ET.SubElement(entry, f"{{{ns_url}}}id").text = raw_id
    ET.SubElement(entry, f"{{{ns_url}}}updated").text = updated
    if summary is not None:
        ET.SubElement(entry, f"{{{ns_url}}}summary").text = summary
    return entry


_CIK_MAP = {
    "0000320193": "AAPL",
    "0001318605": "TSLA",
}


def test_parse_entry_happy_path():
    entry = _make_entry()
    row = _parse_entry(entry, _CIK_MAP)
    assert row is not None
    assert row["title"] == "8-K - Current report"
    assert row["publisher"] == "SEC EDGAR"
    assert row["url"].startswith("https://www.sec.gov/Archives/edgar/data/320193/")
    assert row["tickers"] == ["AAPL"]
    assert row["description"] == "8-K filed by Apple Inc."
    # Published timestamp converted to UTC
    assert isinstance(row["published_at"], datetime)
    assert row["published_at"].tzinfo is not None
    # 14:32 ET (-04:00) → 18:32 UTC
    assert row["published_at"].astimezone(UTC).hour == 18


def test_parse_entry_extracts_accession_number_as_id():
    """Accession numbers are stable per-filing — the ideal NewsItem.id.

    The raw_id URL contains the accession in the format `\\d{10}-\\d{2}-\\d{6}`.
    Without this extraction we'd fall back to slicing the URL, which is
    unstable across EDGAR's URL format changes.
    """
    entry = _make_entry(
        raw_id="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193&accession_number=0000320193-26-000045",
    )
    row = _parse_entry(entry, _CIK_MAP)
    assert row is not None
    assert row["id"] == "0000320193-26-000045"


def test_parse_entry_drops_entry_with_unparseable_timestamp():
    """If the timestamp doesn't parse, we drop the row entirely rather
    than inserting NULL into news_items.published_at (which has
    nullable=False)."""
    entry = _make_entry(updated="not-a-date")
    assert _parse_entry(entry, _CIK_MAP) is None


def test_parse_entry_drops_entry_missing_title():
    entry = _make_entry(title="")
    assert _parse_entry(entry, _CIK_MAP) is None


def test_parse_entry_unmapped_cik_returns_empty_ticker_list():
    """If we can't resolve the CIK to a ticker (small filer, ADR
    that's not in the company_tickers.json), the row still surfaces
    in the news bar — just without a ticker pill. Better than dropping
    the filing entirely."""
    entry = _make_entry(
        raw_id="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=9999999999",
    )
    row = _parse_entry(entry, _CIK_MAP)
    assert row is not None
    assert row["tickers"] == []


def test_parse_entry_handles_z_suffix_timestamp():
    """EDGAR sometimes returns Z-suffix UTC timestamps instead of -04:00.
    Both should round-trip through fromisoformat after our normalisation."""
    entry = _make_entry(updated="2026-05-16T18:32:11Z")
    row = _parse_entry(entry, _CIK_MAP)
    assert row is not None
    assert row["published_at"].astimezone(UTC).hour == 18


def test_parse_entry_caps_field_lengths_for_db():
    """NewsItem.title is String(300), url is String(500). EDGAR is well-
    behaved but a future change to longer titles shouldn't crash the
    insert."""
    long_title = "8-K - " + ("A" * 500)
    long_url = "https://www.sec.gov/" + ("a" * 600)
    entry = _make_entry(title=long_title, url=long_url)
    row = _parse_entry(entry, _CIK_MAP)
    assert row is not None
    assert len(row["title"]) <= 300
    assert len(row["url"]) <= 500


def test_parse_entry_zero_pads_short_cik():
    """The lookup dict is keyed by 10-digit zero-padded CIKs. The Atom
    feed sometimes contains unpadded ones — we must zero-pad before lookup."""
    entry = _make_entry(
        raw_id="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=320193",
    )
    row = _parse_entry(entry, _CIK_MAP)
    assert row is not None
    assert row["tickers"] == ["AAPL"]  # resolved via zero-padded "0000320193"
