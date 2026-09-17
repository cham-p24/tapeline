"""Insider Form 4 read straight from SEC EDGAR (`services/edgar_form4.py`).

Why the source moved, measured 2026-09-14: after the insider pass had re-read
every equity, Finnhub's newest Form 4 filing for AAPL, NVDA and META was 14, 67
and 30 days older than the newest on SEC EDGAR, and for JPM it returned 12
filings in 90 days where EDGAR lists 134 in a year.

These tests drive the real client through an httpx MockTransport shaped like
SEC's own responses (company_tickers.json, the submissions JSON, Form 4 XML as
AAPL's 2026-09-10 filing is laid out), so nothing touches the network. They pin:

1. Parsing: non-derivative lines only, signed by acquired/disposed, a missing
   price is 0, not a guess.
2. Selection: the 90-day window on filing AND trade date; only filings whose XML
   names this issuer (a company's list includes Form 4s it filed as an owner of
   someone else); a 4/A replaces the same owner's Form 4 of its original date.
3. The cache: an accession is downloaded once; an unreadable document is
   remembered, not retried forever; a parse-version bump re-reads.
4. The failure contract the worker pass depends on: [] only for a real answer,
   403/429 throttle, everything else unavailable, raised only when asked.
5. The worker: EDGAR rows are written with source "edgar"; a pre-switch Finnhub
   row cannot veto an EDGAR empty answer, an EDGAR row still can; Finnhub
   stamps are due at the switchover.
"""
from __future__ import annotations

import asyncio
import itertools
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select, update

from app.db import session_scope
from app.models import EdgarForm4Filing, InsiderTransaction, Ticker
from app.services import edgar_form4, finnhub_feed
from app.services.edgar_form4 import (
    EdgarThrottledError,
    EdgarUnavailableError,
    fetch_insider_transactions,
    parse_form4_xml,
)
from app.services.finnhub_feed import FinnhubThrottledError, FinnhubUnavailableError
from app.services.vendor_errors import VendorThrottledError, VendorUnavailableError
from app.workers import signal_publisher as sp

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

TODAY = date.today()


def _d(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat()


AAPL_CIK = "0000320193"
OTHER_CIK = "0000999999"


def form4_xml(
    *,
    issuer_cik: str = AAPL_CIK,
    owner_cik: str = "0001780525",
    owner: str = "Newstead Jennifer",
    doc_type: str = "4",
    original: str | None = None,
    lines: list[tuple[str, str, str, str | None, str]] | None = None,
    derivative: bool = False,
    xmlns: bool = False,
) -> str:
    """lines: (trade date, shares, acquired/disposed, price or None, code)."""
    lines = lines if lines is not None else [(_d(3), "1438", "D", "317.23", "S")]
    txs = "".join(
        f"""
        <nonDerivativeTransaction>
            <securityTitle><value>Common Stock</value><footnoteId id="F1"/></securityTitle>
            <transactionDate><value>{when}</value></transactionDate>
            <transactionCoding>
                <transactionFormType>4</transactionFormType>
                <transactionCode>{code}</transactionCode>
                <equitySwapInvolved>0</equitySwapInvolved>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares><value>{shares}</value></transactionShares>
                <transactionPricePerShare>{
                    f"<value>{price}</value>" if price is not None else '<footnoteId id="F2"/>'
                }</transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>{ad}</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
            <postTransactionAmounts>
                <sharesOwnedFollowingTransaction><value>34352</value></sharesOwnedFollowingTransaction>
            </postTransactionAmounts>
        </nonDerivativeTransaction>"""
        for when, shares, ad, price, code in lines
    )
    deriv = f"""
    <derivativeTable>
        <derivativeTransaction>
            <securityTitle><value>Stock Option</value></securityTitle>
            <transactionDate><value>{_d(3)}</value></transactionDate>
            <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
            <transactionAmounts>
                <transactionShares><value>50000</value></transactionShares>
                <transactionPricePerShare><value>1.00</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
        </derivativeTransaction>
    </derivativeTable>""" if derivative else ""
    ns = ' xmlns="http://www.sec.gov/edgar/ownership"' if xmlns else ""
    orig = f"<dateOfOriginalSubmission>{original}</dateOfOriginalSubmission>" if original else ""
    return f"""<?xml version="1.0"?>
<ownershipDocument{ns}>
    <schemaVersion>X0609</schemaVersion>
    <documentType>{doc_type}</documentType>
    <periodOfReport>{_d(3)}</periodOfReport>
    {orig}
    <issuer>
        <issuerCik>{issuer_cik}</issuerCik>
        <issuerName>Apple Inc.</issuerName>
        <issuerTradingSymbol>AAPL</issuerTradingSymbol>
    </issuer>
    <reportingOwner>
        <reportingOwnerId>
            <rptOwnerCik>{owner_cik}</rptOwnerCik>
            <rptOwnerName>{owner}</rptOwnerName>
        </reportingOwnerId>
        <reportingOwnerRelationship><isOfficer>true</isOfficer></reportingOwnerRelationship>
    </reportingOwner>
    <nonDerivativeTable>{txs}
    </nonDerivativeTable>{deriv}
    <ownerSignature><signatureName>/s/ x</signatureName><signatureDate>{_d(1)}</signatureDate></ownerSignature>
</ownershipDocument>"""


class FakeSec:
    """SEC's three endpoints, recording every request."""

    def __init__(self) -> None:
        self.tickers: dict[str, Any] = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            "1": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE HATHAWAY INC"},
            "2": {"cik_str": 999999, "ticker": "OTHR", "title": "Other Co"},
        }
        #: cik -> list of (accession, filing date, form, primary document)
        self.filings: dict[str, list[tuple[str, str, str, str]]] = {}
        #: accession (no dashes) -> XML body, or an int status
        self.documents: dict[str, str | int] = {}
        self.status: dict[str, int] = {}
        self.requests: list[httpx.Request] = []

    def add(self, cik: str, accession: str, filed: str, xml: str | int, form: str = "4") -> None:
        self.filings.setdefault(cik, []).append((accession, filed, form, "xslF345X06/form4.xml"))
        self.documents[accession.replace("-", "")] = xml

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        for fragment, status in self.status.items():
            if fragment in url:
                return httpx.Response(status, text="refused")
        if url.endswith("/files/company_tickers.json"):
            return httpx.Response(200, json=self.tickers)
        if "/submissions/CIK" in url:
            cik = url.rsplit("CIK", 1)[1].removesuffix(".json")
            rows = sorted(self.filings.get(cik, []), key=lambda r: r[1], reverse=True)
            recent = {
                "accessionNumber": [r[0] for r in rows],
                "filingDate": [r[1] for r in rows],
                "form": [r[2] for r in rows],
                "primaryDocument": [r[3] for r in rows],
                "reportDate": ["" for _ in rows],
            }
            return httpx.Response(200, json={"cik": cik, "filings": {"recent": recent, "files": []}})
        if "/Archives/edgar/data/" in url:
            accession = url.split("/")[-2]
            body = self.documents.get(accession, 404)
            if isinstance(body, int):
                return httpx.Response(body, text="")
            return httpx.Response(200, content=body.encode())
        return httpx.Response(599, text=f"unexpected {url}")

    def paths(self) -> list[str]:
        return [r.url.path for r in self.requests]


@pytest.fixture
def sec(monkeypatch: pytest.MonkeyPatch) -> FakeSec:
    fake = FakeSec()
    monkeypatch.setattr(edgar_form4, "_TICKER_CIK", {})
    monkeypatch.setattr(edgar_form4, "_TICKER_CIK_LOADED_AT", 0.0)
    monkeypatch.setattr(edgar_form4, "REQUEST_INTERVAL_SECONDS", 0.0)
    real_client = edgar_form4._client

    def _client() -> httpx.AsyncClient:
        client = real_client()
        client._transport = httpx.MockTransport(fake.handler)  # headers/timeouts stay real
        return client

    monkeypatch.setattr(edgar_form4, "_client", _client)
    return fake


# ===========================================================================
# 1. Parsing
# ===========================================================================


def test_parse_reads_aapls_layout() -> None:
    parsed = parse_form4_xml(form4_xml())
    assert parsed["issuer_cik"] == AAPL_CIK
    assert parsed["owner_name"] == "Newstead Jennifer"
    assert parsed["owner_cik"] == "0001780525"
    assert parsed["lines"] == [{
        "transaction_date": _d(3), "share_change": -1438,
        "transaction_price": 317.23, "code": "S",
    }]


def test_parse_signs_by_acquired_disposed_and_never_guesses_a_price() -> None:
    parsed = parse_form4_xml(form4_xml(lines=[
        (_d(2), "2,000", "A", "25.5", "P"),
        (_d(2), "300", "A", None, "A"),       # a grant: no price on the form
        (_d(2), "0.4", "A", "10", "A"),       # rounds to 0 shares: dropped
        (_d(2), "", "D", "10", "S"),          # no share count: dropped
    ]))
    assert parsed["lines"] == [
        {"transaction_date": _d(2), "share_change": 2000, "transaction_price": 25.5, "code": "P"},
        {"transaction_date": _d(2), "share_change": 300, "transaction_price": 0.0, "code": "A"},
    ]


def test_parse_ignores_the_derivative_table() -> None:
    """Mutation: read derivativeTransaction too - a 50,000-option exercise at a
    $1 strike is netted as if it were stock."""
    parsed = parse_form4_xml(form4_xml(derivative=True))
    assert [line["code"] for line in parsed["lines"]] == ["S"]


def test_parse_tolerates_a_namespace_and_reads_an_amendment() -> None:
    parsed = parse_form4_xml(form4_xml(xmlns=True, doc_type="4/A", original=_d(9)))
    assert parsed["original_filing_date"] == _d(9)
    assert len(parsed["lines"]) == 1


@pytest.mark.parametrize("body", ["not xml at all", "<html><body>Error</body></html>"])
def test_parse_refuses_anything_but_an_ownership_document(body: str) -> None:
    with pytest.raises(ValueError):
        parse_form4_xml(body)


# ===========================================================================
# 2. Selection
# ===========================================================================


async def test_reads_a_symbols_form4_lines(sec: FakeSec) -> None:
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(1), form4_xml())
    txns = await fetch_insider_transactions("AAPL", raise_failures=True)
    assert txns == [{
        "filer_name": "Newstead Jennifer", "transaction_date": _d(3),
        "share_change": -1438, "transaction_price": 317.23, "code": "S",
    }]
    # SEC fair access: every request declares who is asking.
    assert all("tapeline" in r.headers["user-agent"].lower() for r in sec.requests)


async def test_share_classes_use_secs_hyphen(sec: FakeSec) -> None:
    await fetch_insider_transactions("BRK.B", raise_failures=True)
    assert any(p.endswith("/submissions/CIK0001067983.json") for p in sec.paths())


async def test_a_ticker_sec_does_not_list_is_an_empty_answer_without_a_lookup(
    sec: FakeSec,
) -> None:
    assert await fetch_insider_transactions("SPYX", raise_failures=True) == []
    assert sec.paths() == ["/files/company_tickers.json"]


async def test_the_window_applies_to_filing_date_and_trade_date(sec: FakeSec) -> None:
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(120), form4_xml(lines=[(_d(121), "5", "A", "1", "P")]))
    sec.add(AAPL_CIK, "0001140361-26-000002", _d(2), form4_xml(lines=[
        (_d(95), "7", "A", "1", "P"),   # filed late, traded outside the window
        (_d(4), "9", "A", "1", "P"),
    ]))
    txns = await fetch_insider_transactions("AAPL", raise_failures=True)
    assert [t["share_change"] for t in txns] == [9]
    assert not any("000114036126000001" in p for p in sec.paths()), "an out-of-window filing was downloaded"


async def test_a_share_count_the_column_cannot_hold_is_dropped_not_fatal(sec: FakeSec) -> None:
    """SVRE, production 2026-09-14: a filing reported one line of 16,608,240,000
    shares. `insider_transactions.share_change` is a 32-bit INTEGER on Postgres,
    so the write raised on every re-read and the symbol failed forever. SQLite
    does not enforce the width, so this pins the filter, not the database error.
    Mutation: drop the filter - the unstorable line is handed to the writer."""
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(1), form4_xml(lines=[
        (_d(2), "16608240000", "A", "6.93", "J"),
        (_d(2), "2147483647", "A", "6.93", "J"),   # the largest that fits
        (_d(2), "500", "A", "6.93", "P"),
    ]))
    txns = await fetch_insider_transactions("AAPL", raise_failures=True)
    assert sorted(t["share_change"] for t in txns) == [500, 2_147_483_647]
    assert edgar_form4.MAX_STORABLE_SHARES == 2**31 - 1
    # The cache keeps what the document says; only the write-bound output is filtered.
    async with session_scope() as s:
        cached = json.loads((await s.execute(select(EdgarForm4Filing.rows_json))).scalar_one() or "[]")
    assert 16_608_240_000 in [line["share_change"] for line in cached]


async def test_filings_about_another_issuer_are_not_this_symbols(sec: FakeSec) -> None:
    """Apple's submission list can carry a Form 4 Apple filed as a 10% OWNER of
    another company. Mutation: drop the issuer check - that company's trade is
    scored as Apple's insiders."""
    sec.add(AAPL_CIK, "0000320193-26-000009", _d(1), form4_xml(issuer_cik=OTHER_CIK, owner="Apple Inc."))
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(1), form4_xml())
    txns = await fetch_insider_transactions("AAPL", raise_failures=True)
    assert [t["filer_name"] for t in txns] == ["Newstead Jennifer"]


async def test_an_amendment_replaces_the_owners_original_filing(sec: FakeSec) -> None:
    """Mutation: skip the supersede - the corrected and the original lines both
    count. Another owner's filing on the same day is untouched."""
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(10), form4_xml(lines=[(_d(11), "1000", "D", "300", "S")]))
    sec.add(AAPL_CIK, "0001140361-26-000002", _d(10), form4_xml(
        owner_cik="0000000042", owner="Other Officer", lines=[(_d(11), "50", "A", "300", "P")],
    ))
    sec.add(
        AAPL_CIK, "0001140361-26-000003", _d(5),
        form4_xml(doc_type="4/A", original=_d(10), lines=[(_d(11), "1200", "D", "300", "S")]),
        form="4/A",
    )
    txns = await fetch_insider_transactions("AAPL", raise_failures=True)
    assert sorted(t["share_change"] for t in txns) == [-1200, 50]


# ===========================================================================
# 3. The cache
# ===========================================================================


async def _archive_hits(sec: FakeSec) -> int:
    return sum("/Archives/" in p for p in sec.paths())


async def test_an_accession_is_downloaded_once(sec: FakeSec) -> None:
    """Mutation: skip the cache lookup - every re-read downloads every filing."""
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(1), form4_xml())
    first = await fetch_insider_transactions("AAPL", raise_failures=True)
    assert await _archive_hits(sec) == 1
    second = await fetch_insider_transactions("AAPL", raise_failures=True)
    assert second == first
    assert await _archive_hits(sec) == 1


async def test_an_unreadable_document_is_remembered_not_retried(sec: FakeSec) -> None:
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(1), 404)
    sec.add(AAPL_CIK, "0001140361-26-000002", _d(1), "<html>not a form</html>")
    sec.add(AAPL_CIK, "0001140361-26-000003", _d(1), form4_xml())
    assert len(await fetch_insider_transactions("AAPL", raise_failures=True)) == 1
    assert await _archive_hits(sec) == 3
    await fetch_insider_transactions("AAPL", raise_failures=True)
    assert await _archive_hits(sec) == 3


async def test_a_parse_version_bump_reads_the_filing_again(
    sec: FakeSec, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(1), form4_xml())
    await fetch_insider_transactions("AAPL", raise_failures=True)
    monkeypatch.setattr(edgar_form4, "PARSE_VERSION", edgar_form4.PARSE_VERSION + 1)
    await fetch_insider_transactions("AAPL", raise_failures=True)
    assert await _archive_hits(sec) == 2


async def test_documents_read_before_a_failure_are_kept(sec: FakeSec) -> None:
    sec.add(AAPL_CIK, "0001140361-26-000002", _d(1), form4_xml())
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(2), 503)
    with pytest.raises(EdgarUnavailableError):
        await fetch_insider_transactions("AAPL", raise_failures=True)
    async with session_scope() as s:
        kept = (await s.execute(select(EdgarForm4Filing.accession))).scalars().all()
    assert kept == ["0001140361-26-000002"]


# ===========================================================================
# 4. The failure contract
# ===========================================================================


def test_error_types_share_the_vendor_bases_and_stay_distinct() -> None:
    assert issubclass(EdgarThrottledError, VendorThrottledError)
    assert issubclass(FinnhubThrottledError, VendorThrottledError)
    assert issubclass(EdgarUnavailableError, VendorUnavailableError)
    assert issubclass(FinnhubUnavailableError, VendorUnavailableError)
    assert not issubclass(VendorUnavailableError, VendorThrottledError)


@pytest.mark.parametrize("status", [403, 429])
async def test_secs_rate_refusal_is_a_throttle(sec: FakeSec, status: int) -> None:
    sec.status["/submissions/"] = status
    with pytest.raises(EdgarThrottledError) as exc:
        await fetch_insider_transactions("AAPL", raise_failures=True)
    assert exc.value.status == status
    assert await fetch_insider_transactions("AAPL") is None


@pytest.mark.parametrize("where,status", [("/submissions/", 500), ("/submissions/", 404), ("/Archives/", 502)])
async def test_other_non_answers_are_unavailable_never_empty(
    sec: FakeSec, where: str, status: int,
) -> None:
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(1), form4_xml())
    sec.status[where] = status
    with pytest.raises(EdgarUnavailableError):
        await fetch_insider_transactions("AAPL", raise_failures=True)
    assert await fetch_insider_transactions("AAPL") is None


async def test_a_transport_failure_is_unavailable(
    sec: FakeSec, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    monkeypatch.setattr(sec, "handler", _down)
    with pytest.raises(EdgarUnavailableError):
        await fetch_insider_transactions("AAPL", raise_failures=True)


async def test_no_ticker_map_is_a_failure_not_an_empty_answer(sec: FakeSec) -> None:
    """Mutation: treat a failed map download as an empty map - every symbol
    answers [] and the pass retires every reading in the universe."""
    sec.status["company_tickers"] = 500
    with pytest.raises(EdgarUnavailableError):
        await fetch_insider_transactions("AAPL", raise_failures=True)


async def test_a_failed_map_refresh_keeps_the_map_it_has(
    sec: FakeSec, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(1), form4_xml())
    assert await fetch_insider_transactions("AAPL", raise_failures=True)
    monkeypatch.setattr(edgar_form4, "_TICKER_CIK_LOADED_AT", 0.0)  # expired
    sec.status["company_tickers"] = 500
    assert await fetch_insider_transactions("AAPL", raise_failures=True)


async def test_concurrent_downloads_still_start_an_interval_apart(
    sec: FakeSec, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Documents download DOWNLOAD_CONCURRENCY at a time. Mutation: pace them
    without the shared lock - every download in a batch reads the same last
    start, and four requests leave in the same instant."""
    now = [1_000.0]
    real_sleep = asyncio.sleep

    async def _sleep(seconds: float, *a: Any, **k: Any) -> None:
        now[0] += seconds
        await real_sleep(0)

    monkeypatch.setattr(edgar_form4, "REQUEST_INTERVAL_SECONDS", 0.125)
    monkeypatch.setattr(edgar_form4, "_last_request_at", 0.0)
    monkeypatch.setattr(edgar_form4, "monotonic", lambda: now[0])
    monkeypatch.setattr(asyncio, "sleep", _sleep)
    starts: list[float] = []
    handler = sec.handler

    def _timed(request: httpx.Request) -> httpx.Response:
        starts.append(now[0])
        return handler(request)

    monkeypatch.setattr(sec, "handler", _timed)
    for i in range(6):
        sec.add(AAPL_CIK, f"0001140361-26-00000{i}", _d(1), form4_xml())
    await fetch_insider_transactions("AAPL", raise_failures=True)

    assert len(starts) == 2 + 6  # ticker map, submissions, six documents
    gaps = [round(b - a, 6) for a, b in itertools.pairwise(starts)]
    assert min(gaps) >= 0.125, gaps


async def test_a_throttle_outranks_other_failures_in_a_batch(sec: FakeSec) -> None:
    """The pass never stamps a throttle, and stamps every other failure. A batch
    holding both must surface the throttle."""
    # Newest accession first in the batch, so the 503 is met before the 403.
    sec.add(AAPL_CIK, "0001140361-26-000002", _d(1), 503)
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(1), 403)
    with pytest.raises(EdgarThrottledError):
        await fetch_insider_transactions("AAPL", raise_failures=True)


async def test_requests_are_paced_under_secs_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [100.0]
    slept: list[float] = []

    async def _sleep(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(edgar_form4, "monotonic", lambda: now[0])
    monkeypatch.setattr(edgar_form4.asyncio, "sleep", _sleep)
    monkeypatch.setattr(edgar_form4, "_last_request_at", 0.0)
    for _ in range(3):
        await edgar_form4._pace()
    assert slept == [edgar_form4.REQUEST_INTERVAL_SECONDS] * 2
    assert 1 / edgar_form4.REQUEST_INTERVAL_SECONDS < 10


# ===========================================================================
# 5. The worker
# ===========================================================================


@pytest.fixture
def worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_CLEARED", set())
    monkeypatch.setattr(sp, "_sheet_is_scoring_source", lambda: False)


async def _seed_ticker(symbol: str, **extra: Any) -> None:
    async with session_scope() as s:
        s.add(Ticker(**{
            "symbol": symbol, "name": f"{symbol} Inc", "asset_class": "equity",
            "price": 100.0, "volume": 1_000, **extra,
        }))


async def _form4_rows(symbol: str) -> list[InsiderTransaction]:
    async with session_scope() as s:
        rows = (await s.execute(
            select(InsiderTransaction).where(InsiderTransaction.symbol == symbol)
        )).scalars().all()
        for r in rows:
            s.expunge(r)
    return list(rows)


async def test_the_pass_writes_edgar_rows_and_scores_them(sec: FakeSec, worker: None) -> None:
    await _seed_ticker("AAPL")
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(1), form4_xml(lines=[(_d(2), "1000", "A", "50", "P")]))
    assert await sp._refresh_insider_cache(limit=5) is False
    rows = await _form4_rows("AAPL")
    assert [(r.share_change, r.code, r.source) for r in rows] == [(1000, "P", "edgar")]
    assert finnhub_feed.get_cached_smart_money_score("AAPL") == 90.0


async def _seed_finnhub_era_row(symbol: str, *, source: str | None) -> None:
    """A stored Form 4 row. source=None is what migration 0069 leaves on every
    pre-switch row: the column is added with no default, so it is written with
    an UPDATE here - the ORM would fill in the model's "edgar" default."""
    async with session_scope() as s:
        s.add(InsiderTransaction(
            symbol=symbol, insider_name="Underlying CEO", transaction_date=_d(5),
            share_change=5_000, transaction_price=20.0, transaction_value=100_000.0,
            code="P",
        ))
    async with session_scope() as s:
        await s.execute(
            update(InsiderTransaction)
            .where(InsiderTransaction.symbol == symbol)
            .values(source=source)
        )


async def test_a_finnhub_row_cannot_veto_an_edgar_empty_answer(sec: FakeSec, worker: None) -> None:
    """A 2x single-stock ETF held its underlying's insider trades from Finnhub.
    EDGAR lists no filer for the ETF, and that answer must retire them.
    Mutation: drop the source filter in the guard - the stale row is read as a
    contradiction and the reading is never retired."""
    await _seed_ticker("NVDL", asset_class="etf", sub_smart_money=80.0)
    await _seed_finnhub_era_row("NVDL", source=None)
    await sp._refresh_insider_cache(limit=5)
    assert await _form4_rows("NVDL") == []
    async with session_scope() as s:
        held = await s.scalar(select(Ticker.sub_smart_money).where(Ticker.symbol == "NVDL"))
    assert held is None


async def test_an_edgar_row_still_contradicts_an_empty_answer(sec: FakeSec, worker: None) -> None:
    await _seed_ticker("OTHR", sub_smart_money=80.0)
    await _seed_finnhub_era_row("OTHR", source="edgar")
    await sp._refresh_insider_cache(limit=5)
    assert len(await _form4_rows("OTHR")) == 1, "a contradicted empty answer deleted rows"


async def test_an_edgar_throttle_is_not_stamped(
    sec: FakeSec, worker: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_sleep(seconds: float, *a: Any, **k: Any) -> None:
        return None

    monkeypatch.setattr(sp.asyncio, "sleep", _no_sleep)
    await _seed_ticker("AAPL")
    sec.status["/submissions/"] = 403
    assert await sp._refresh_insider_cache(limit=5) is True
    async with session_scope() as s:
        stamp = await s.scalar(select(Ticker.last_smart_money_at).where(Ticker.symbol == "AAPL"))
    assert stamp is None


@pytest.mark.parametrize("asset_class", ["equity", "etf"])
async def test_finnhub_era_stamps_are_due_at_the_switchover(
    monkeypatch: pytest.MonkeyPatch, asset_class: str,
) -> None:
    """Mutation: no switchover rule - a Finnhub reading from an hour before the
    switch waits out 36 hours (equities) or 30 days (everything else)."""
    since = datetime(2026, 9, 14, 14, 0, tzinfo=UTC)
    monkeypatch.setattr(sp, "_SMART_MONEY_EDGAR_SINCE", since)
    at = since + timedelta(hours=2)
    await _seed_ticker("PRE", asset_class=asset_class, last_smart_money_at=since - timedelta(hours=1),
                       last_fundamentals_at=at)
    await _seed_ticker("POST", asset_class=asset_class, last_smart_money_at=since + timedelta(minutes=1),
                       last_fundamentals_at=at)
    assert (await sp._factor_due_counts(now=at))[1] == 1
    assert await sp._select_factor_symbols(Ticker.last_smart_money_at, 10, now=at) == ["PRE"]


def test_the_switchover_instant_is_the_edgar_deploy_not_a_placeholder() -> None:
    """The instant is set to the expected boot of the deploy that ships the EDGAR
    pass (2026-09-14 14:10 UTC). Earlier, and Finnhub stamps the old worker
    writes during the deploy wait out a horizon; later, and EDGAR's own first
    stamps are re-read once - cheap, since their filings are cached. A date on
    any other day would be one of those mistakes by hours."""
    assert sp._SMART_MONEY_EDGAR_SINCE.tzinfo is not None
    assert sp._SMART_MONEY_EDGAR_SINCE.date() == date(2026, 9, 14)
    assert sp._INSIDER_PACE_SECONDS == 0.0


async def test_the_cache_table_round_trips_rows_json(sec: FakeSec) -> None:
    sec.add(AAPL_CIK, "0001140361-26-000001", _d(1), form4_xml())
    await fetch_insider_transactions("AAPL", raise_failures=True)
    async with session_scope() as s:
        row = (await s.execute(select(EdgarForm4Filing))).scalar_one()
        count = await s.scalar(select(func.count()).select_from(EdgarForm4Filing))
    assert count == 1
    assert row.issuer_cik == AAPL_CIK and row.form == "4" and row.parse_version == edgar_form4.PARSE_VERSION
    assert json.loads(row.rows_json or "[]")[0]["share_change"] == -1438
