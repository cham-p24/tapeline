"""SEC EDGAR Form 4 - insider transactions read from the filings themselves.

WHY NOT FINNHUB ANY MORE
    The insider pass used Finnhub's /stock/insider-transactions. Measured on
    2026-09-14, after the pass had re-read every equity, Finnhub's newest Form 4
    filing for AAPL, NVDA and META was 27 Aug, 6 Jul and 12 Aug; SEC EDGAR's was
    10, 11 and 11 Sep (14, 67 and 30 days behind). For JPM Finnhub returned 12
    filings in 90 days; EDGAR lists 134 in the year. Re-reading a lagging vendor
    more often could not fix that, so the pass reads the source.

HOW ONE SYMBOL IS READ (`fetch_insider_transactions`, same contract as the
Finnhub function it replaces)
    1. Ticker -> CIK from SEC's company_tickers.json (share classes are written
       with a hyphen there: BRK.B is "BRK-B"). A ticker SEC does not list has
       no Section 16 filer behind it - ETFs, most funds, foreign private issuers
       - so the answer is an empty list, not a failure.
    2. data.sec.gov/submissions/CIK##########.json. Its `filings.recent` block
       holds at least a year of filings, so the 90-day window never needs the
       paged overflow files. Form 4 and 4/A inside the window are kept.
    3. Each filing's XML, from the primary document with its xsl rendering
       prefix removed (`xslF345X06/form4.xml` -> `form4.xml`). Parsed once and
       cached by accession number in `edgar_form4_filings`.
    4. Only filings whose XML names THIS issuer are used: a company's
       submission list also carries Form 4s it filed as a 10% owner of some
       other company.
    5. ATTRIBUTION. SEC lists several tickers under one CIK for many issuers:
       preferred depositary shares, notes, warrants, ETNs and sibling share
       classes. A filing's lines go to ONE of them - the ticker the filing
       itself names in issuerTradingSymbol, or the CIK's first-listed SEC
       ticker when the named symbol is not one SEC lists for the CIK. Until
       2026-09-18 every ticker of the CIK received the issuer's whole Form 4
       set: 70 CIKs, e.g. Strategy's STRC/STRF/STRK/STRD preferreds carried
       MSTR's insider sales, JPM's VYLD/AMJB ETNs carried JPM's, and notes like
       GREEL and TMUSZ carried their issuer's.
    6. A 4/A replaces only the same owner's original(s) it restates: originals
       filed on its dateOfOriginalSubmission (or up to 4 days later, since
       EDGAR's filing date can move past the filer's submission date) whose
       trade dates overlap the amendment's; failing any overlap, the single
       original filed on that exact date. An amendment with no non-derivative
       lines replaces nothing. Until 2026-09-18 a 4/A dropped EVERY Form 4 its
       owner filed that day: CRWV lost 51 sale lines Magnetar filed separately
       on 14 Aug, because one of three same-day filings was amended.
    7. A line whose trade date is later than the filing's own filing date is a
       typo (a 2026-09-03 GIC filing reported a trade on 2027-09-03) and is
       dropped: a future date sorted to the top of every "most recent" list.
    8. Non-derivative transactions only (the common-stock table). Derivative
       lines are option grants and exercises priced at strike, which would
       swamp the dollar netting in `compute_smart_money_score` and double-count
       every exercise. Share change is signed by the acquired/disposed code.

FAILURE CONTRACT (what the worker pass relies on)
    * An answer is a list, possibly empty.
    * 403/429 from SEC is a throttle -> EdgarThrottledError. SEC answers an
      over-rate client with 403 "Request Rate Threshold Exceeded".
    * Anything else that is not an answer -> EdgarUnavailableError: other
      non-200s, transport errors and timeouts, bodies that are not the JSON SEC
      sends, a ticker map that cannot be loaded at all, or a filing in the
      window whose XML could not be downloaded. Never an empty list: an empty
      list retires the symbol's reading.
    * A filing whose XML is missing (404) or malformed is cached as unreadable
      and skipped, so one bad document cannot fail the symbol forever.
    * Both raise only under `raise_failures=True`; otherwise None, like the
      Finnhub function.

SEC FAIR ACCESS
    Declared User-Agent with a contact address, and no more than 10 requests a
    second. Every request here goes through `_pace()`, which spaces request
    STARTS at least REQUEST_INTERVAL_SECONDS apart (8/s). A symbol's uncached
    documents download DOWNLOAD_CONCURRENCY at a time under one per-call lock
    around the pacing, so overlapping requests still start 0.125s apart: from
    Fly's Sydney region one request takes ~0.2-0.3s, and strictly one at a time
    the ~6,000-equity switchover ran at ~4 requests a second. The lock is created
    per call, so it never outlives the event loop that made it.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from time import monotonic
from typing import Any

import httpx

from app.services.edgar_feed import _USER_AGENT
from app.services.vendor_errors import VendorThrottledError, VendorUnavailableError

logger = logging.getLogger(__name__)

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

#: 8 requests a second, under SEC's published 10.
REQUEST_INTERVAL_SECONDS = 0.125

#: Documents one symbol downloads at once; see "SEC FAIR ACCESS" above.
DOWNLOAD_CONCURRENCY = 4

#: SEC refuses an over-rate or undeclared client with 403; 429 is kept for
#: completeness. Neither says anything about the company asked about.
THROTTLED_STATUSES = frozenset({403, 429})

FORM4_TYPES = frozenset({"4", "4/A"})

#: The version `parse_form4_xml`'s output is written at. Bump it when that
#: output changes.
PARSE_VERSION = 2

#: The oldest cached version still valid for ANY filing. Raise it to
#: PARSE_VERSION when a parse change makes every older row wrong; cached
#: filings below it are fetched and parsed again.
MIN_PARSE_VERSION = 1

#: The first version that records `issuer_symbol` (2026-09-18). Only a CIK with
#: more than one SEC ticker needs it for attribution, so a single-ticker CIK
#: keeps serving version-1 rows and only ~70 issuers' filings are downloaded
#: again (see `_fetch`).
ISSUER_SYMBOL_PARSE_VERSION = 2

#: How far past a 4/A's dateOfOriginalSubmission the original's EDGAR filing
#: date may fall and still be the filing it amends. EDGAR dates a submission
#: accepted after 17:30 ET to the next business day, which crosses a weekend.
AMENDMENT_FILING_DATE_SLACK_DAYS = 4

#: The largest share change `insider_transactions.share_change` can hold: it is
#: a 32-bit INTEGER on Postgres (SQLite, which the tests run on, does not
#: enforce it). A line beyond it is dropped, with a warning, when a symbol's
#: transactions are assembled - not at parse time, so the cached filing keeps
#: what the document says.
#:
#: Found on the first production run, 2026-09-14: SVRE's filing by VisionWave
#: Holdings reports one "J" line of 16,608,240,000 shares at $6.93 (a $115B
#: "transaction" for a small cap - evidently mis-scaled). The insert raised on
#: every re-read, so the symbol counted as a failed call forever. No real
#: single-line transaction comes near 2.1 billion shares.
MAX_STORABLE_SHARES = 2_147_483_647

_TICKER_MAP_TTL_SECONDS = 24 * 3600
_TIMEOUT = httpx.Timeout(20.0)


class EdgarThrottledError(VendorThrottledError):
    """SEC refused the client (403 rate threshold, or 429), not the company."""

    def __init__(self, endpoint: str, status: int) -> None:
        super().__init__(f"edgar {endpoint} throttled status={status}")
        self.endpoint = endpoint
        self.status = status


class EdgarUnavailableError(VendorUnavailableError):
    """SEC did not give an answer about the company; see the module docstring."""

    def __init__(self, endpoint: str, detail: str) -> None:
        super().__init__(f"edgar {endpoint} unavailable: {detail}")
        self.endpoint = endpoint


# ---- pacing and requests ---------------------------------------------------

_last_request_at = 0.0


async def _pace() -> None:
    global _last_request_at
    wait = _last_request_at + REQUEST_INTERVAL_SECONDS - monotonic()
    if wait > 0:
        await asyncio.sleep(wait)
    _last_request_at = monotonic()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=_TIMEOUT,
        headers={"User-Agent": _USER_AGENT, "Accept-Encoding": "gzip, deflate"},
        follow_redirects=True,
    )


async def _get(
    client: httpx.AsyncClient, url: str, endpoint: str, pacing: asyncio.Lock | None = None,
) -> httpx.Response:
    """One paced GET. Raises for a throttle or a transport failure; every other
    status is returned for the caller to judge (a 404 means different things
    for a submission list and for one filing's document).

    Concurrent callers pass one shared `pacing` lock so their starts are spaced."""
    if pacing is None:
        await _pace()
    else:
        async with pacing:
            await _pace()
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        raise EdgarUnavailableError(endpoint, type(exc).__name__) from exc
    if response.status_code in THROTTLED_STATUSES:
        raise EdgarThrottledError(endpoint, response.status_code)
    return response


# ---- ticker -> CIK ------------------------------------------------------------

_TICKER_CIK: dict[str, str] = {}
_TICKER_CIK_LOADED_AT = 0.0
#: CIK -> its tickers in company_tickers.json order. The first entry is the one
#: a filing is attributed to when it names no ticker SEC lists for the CIK.
_CIK_TICKERS: dict[str, list[str]] = {}


def sec_ticker(symbol: str) -> str:
    """Our symbol as company_tickers.json spells it: BRK.B -> BRK-B."""
    return symbol.strip().upper().replace(".", "-").replace("/", "-")


async def _ticker_cik_map(client: httpx.AsyncClient) -> dict[str, str]:
    """SEC's ticker -> zero-padded CIK map, refreshed daily.

    A refresh that fails falls back to the map already held. With no map at all
    the failure is raised: "SEC lists no such ticker" must never be concluded
    from a download that did not happen."""
    global _TICKER_CIK, _TICKER_CIK_LOADED_AT, _CIK_TICKERS
    if _TICKER_CIK and time.time() - _TICKER_CIK_LOADED_AT < _TICKER_MAP_TTL_SECONDS:
        return _TICKER_CIK
    try:
        response = await _get(client, COMPANY_TICKERS_URL, "company_tickers")
        if response.status_code != 200:
            raise EdgarUnavailableError("company_tickers", f"status={response.status_code}")
        data = response.json()
        if not isinstance(data, dict):
            raise EdgarUnavailableError("company_tickers", "not a JSON object")
        fresh: dict[str, str] = {}
        by_cik: dict[str, list[str]] = {}
        # Keys are row numbers; SEC's order is what "first-listed" means.
        for key in sorted(data, key=lambda k: int(k) if str(k).isdigit() else 0):
            row = data[key]
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").strip().upper()
            cik = str(row.get("cik_str") or "").strip()
            if ticker and cik.isdigit() and ticker not in fresh:
                padded = cik.zfill(10)
                fresh[ticker] = padded
                by_cik.setdefault(padded, []).append(ticker)
        if not fresh:
            raise EdgarUnavailableError("company_tickers", "empty map")
    except (EdgarUnavailableError, ValueError) as exc:
        if _TICKER_CIK:
            logger.warning("edgar_form4.ticker_map_stale %s", exc)
            return _TICKER_CIK
        if isinstance(exc, EdgarUnavailableError):
            raise
        raise EdgarUnavailableError("company_tickers", type(exc).__name__) from exc
    _TICKER_CIK = fresh
    _CIK_TICKERS = by_cik
    _TICKER_CIK_LOADED_AT = time.time()
    logger.info("edgar_form4.ticker_map_loaded tickers=%d", len(fresh))
    return _TICKER_CIK


# ---- parsing ------------------------------------------------------------------


def _text(node: ET.Element | None, path: str) -> str:
    if node is None:
        return ""
    found = node.find(path)
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def _number(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def _cik(raw: str) -> str:
    digits = raw.strip()
    return digits.zfill(10) if digits.isdigit() else ""


def parse_form4_xml(document: bytes | str) -> dict[str, Any]:
    """One ownershipDocument -> issuer, first reporting owner, and its
    non-derivative transaction lines. Raises ValueError on anything that is not
    a readable ownershipDocument."""
    try:
        root = ET.fromstring(document)
    except ET.ParseError as exc:
        raise ValueError(f"not XML: {exc}") from exc
    for element in root.iter():
        if isinstance(element.tag, str) and "}" in element.tag:
            element.tag = element.tag.split("}", 1)[1]
    if root.tag != "ownershipDocument":
        raise ValueError(f"root is <{root.tag}>, not <ownershipDocument>")

    owner = root.find("reportingOwner")
    lines: list[dict[str, Any]] = []
    for tx in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        traded = _text(tx, "transactionDate/value")[:10]
        shares = _number(_text(tx, "transactionAmounts/transactionShares/value"))
        direction = _text(tx, "transactionAmounts/transactionAcquiredDisposedCode/value").upper()
        if not traded or shares is None or direction not in ("A", "D"):
            continue
        change = round(shares) * (1 if direction == "A" else -1)
        if change == 0:
            continue
        price = _number(_text(tx, "transactionAmounts/transactionPricePerShare/value"))
        lines.append({
            "transaction_date": traded,
            "share_change": change,
            "transaction_price": price if price and price > 0 else 0.0,
            "code": _text(tx, "transactionCoding/transactionCode")[:4],
        })
    return {
        "issuer_cik": _cik(_text(root, "issuer/issuerCik")),
        "issuer_symbol": sec_ticker(_text(root, "issuer/issuerTradingSymbol"))[:20],
        "owner_cik": _cik(_text(owner, "reportingOwnerId/rptOwnerCik")),
        "owner_name": _text(owner, "reportingOwnerId/rptOwnerName")[:120],
        "original_filing_date": _text(root, "dateOfOriginalSubmission")[:10] or None,
        "lines": lines,
    }


def _form4_filings_in_window(submissions: Any, cutoff: str) -> list[dict[str, str]]:
    """Form 4 / 4/A entries filed on or after `cutoff`, newest first."""
    try:
        recent = submissions["filings"]["recent"]
        columns = zip(
            recent["accessionNumber"], recent["filingDate"],
            recent["form"], recent["primaryDocument"], strict=True,
        )
        found = [
            {"accession": acc, "filing_date": filed, "form": form, "document": doc}
            for acc, filed, form, doc in columns
            if form in FORM4_TYPES and isinstance(filed, str) and filed >= cutoff
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise EdgarUnavailableError("submissions", f"unexpected body: {type(exc).__name__}") from exc
    found.sort(key=lambda f: (f["filing_date"], f["accession"]), reverse=True)
    return found


# ---- the cache ------------------------------------------------------------------


async def _cached_filings(
    accessions: list[str], min_version: int = MIN_PARSE_VERSION,
) -> dict[str, dict[str, Any]]:
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import EdgarForm4Filing

    if not accessions:
        return {}
    async with session_scope() as session:
        rows = (await session.execute(
            select(EdgarForm4Filing).where(
                EdgarForm4Filing.accession.in_(accessions),
                EdgarForm4Filing.parse_version >= min_version,
                EdgarForm4Filing.parse_version <= PARSE_VERSION,
            )
        )).scalars().all()
    return {
        row.accession: {
            "issuer_cik": row.issuer_cik,
            "issuer_symbol": row.issuer_symbol or "",
            "owner_cik": row.owner_cik,
            "owner_name": row.owner_name,
            "original_filing_date": row.original_filing_date,
            "lines": None if row.rows_json is None else json.loads(row.rows_json),
        }
        for row in rows
    }


async def _store_filings(filings: list[tuple[dict[str, str], dict[str, Any]]]) -> None:
    from app.db import session_scope
    from app.models import EdgarForm4Filing

    if not filings:
        return
    async with session_scope() as session:
        for meta, parsed in filings:
            await session.merge(EdgarForm4Filing(
                accession=meta["accession"],
                form=meta["form"],
                filing_date=meta["filing_date"],
                issuer_cik=parsed["issuer_cik"],
                issuer_symbol=parsed.get("issuer_symbol") or None,
                owner_cik=parsed["owner_cik"],
                owner_name=parsed["owner_name"],
                original_filing_date=parsed["original_filing_date"],
                rows_json=None if parsed["lines"] is None else json.dumps(parsed["lines"]),
                parse_version=PARSE_VERSION,
            ))


_UNREADABLE: dict[str, Any] = {
    "issuer_cik": "", "issuer_symbol": "", "owner_cik": "", "owner_name": "",
    "original_filing_date": None, "lines": None,
}


async def _read_filing(
    client: httpx.AsyncClient, cik: str, meta: dict[str, str], pacing: asyncio.Lock,
) -> dict[str, Any]:
    document = meta["document"].rsplit("/", 1)[-1]
    if not document.lower().endswith(".xml"):
        logger.warning("edgar_form4.not_xml accession=%s document=%s", meta["accession"], document)
        return dict(_UNREADABLE)
    url = ARCHIVE_URL.format(
        cik=int(cik), accession=meta["accession"].replace("-", ""), document=document,
    )
    response = await _get(client, url, "archives", pacing)
    if response.status_code == 404:
        logger.warning("edgar_form4.document_missing accession=%s", meta["accession"])
        return dict(_UNREADABLE)
    if response.status_code != 200:
        raise EdgarUnavailableError("archives", f"status={response.status_code}")
    try:
        return parse_form4_xml(response.content)
    except ValueError as exc:
        logger.warning("edgar_form4.unparseable accession=%s %s", meta["accession"], exc)
        return dict(_UNREADABLE)


# ---- the public entry point --------------------------------------------------------


async def _fetch(symbol: str, days_back: int) -> list[dict[str, Any]]:
    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    async with _client() as client:
        cik = (await _ticker_cik_map(client)).get(sec_ticker(symbol))
        if cik is None:
            return []
        response = await _get(client, SUBMISSIONS_URL.format(cik=cik), "submissions")
        if response.status_code != 200:
            raise EdgarUnavailableError("submissions", f"status={response.status_code}")
        try:
            submissions = response.json()
        except ValueError as exc:
            raise EdgarUnavailableError("submissions", "body is not JSON") from exc
        filings = _form4_filings_in_window(submissions, cutoff)
        if not filings:
            return []

        cik_tickers = _CIK_TICKERS.get(cik) or [sec_ticker(symbol)]
        # A single-ticker CIK needs no issuer symbol, so older rows serve.
        parsed = await _cached_filings(
            [f["accession"] for f in filings],
            min_version=(
                max(MIN_PARSE_VERSION, ISSUER_SYMBOL_PARSE_VERSION)
                if len(cik_tickers) > 1 else MIN_PARSE_VERSION
            ),
        )
        missing = [f for f in filings if f["accession"] not in parsed]
        fresh: list[tuple[dict[str, str], dict[str, Any]]] = []
        pacing = asyncio.Lock()
        failure: BaseException | None = None
        for start in range(0, len(missing), DOWNLOAD_CONCURRENCY):
            batch = missing[start:start + DOWNLOAD_CONCURRENCY]
            results = await asyncio.gather(
                *(_read_filing(client, cik, meta, pacing) for meta in batch),
                return_exceptions=True,
            )
            for meta, result in zip(batch, results, strict=True):
                if isinstance(result, BaseException):
                    # A throttle outranks any other failure in the batch: it
                    # is the one the pass must not stamp.
                    if failure is None or isinstance(result, EdgarThrottledError):
                        failure = result
                    continue
                parsed[meta["accession"]] = result
                fresh.append((meta, result))
            if failure is not None:
                break
        # Whatever was read is kept even when another document failed, so the
        # retry does not download it again.
        await _store_filings(fresh)
        if failure is not None:
            raise failure

    wanted = sec_ticker(symbol)
    own = [
        f for f in filings
        if parsed[f["accession"]]["issuer_cik"] == cik
        and attributed_ticker(parsed[f["accession"]], cik_tickers) == wanted
    ]
    replaced = superseded_accessions(own, parsed)
    transactions: list[dict[str, Any]] = []
    for meta in own:
        if meta["accession"] in replaced:
            continue
        reading = parsed[meta["accession"]]
        for line in reading["lines"] or []:
            if line["transaction_date"] < cutoff:
                continue
            if line["transaction_date"] > meta["filing_date"]:
                logger.warning(
                    "edgar_form4.trade_after_filing symbol=%s accession=%s traded=%s filed=%s",
                    symbol, meta["accession"], line["transaction_date"], meta["filing_date"],
                )
                continue
            if abs(line["share_change"]) > MAX_STORABLE_SHARES:
                logger.warning(
                    "edgar_form4.share_count_unstorable symbol=%s accession=%s shares=%d",
                    symbol, meta["accession"], line["share_change"],
                )
                continue
            transactions.append({"filer_name": reading["owner_name"], **line})
    return transactions


def attributed_ticker(reading: dict[str, Any], cik_tickers: list[str]) -> str:
    """The one ticker a filing's lines belong to; see "ATTRIBUTION" above."""
    named = reading.get("issuer_symbol") or ""
    return named if named in cik_tickers else cik_tickers[0]


def superseded_accessions(
    own: list[dict[str, str]], parsed: dict[str, dict[str, Any]],
) -> set[str]:
    """Accessions of original Form 4s that a 4/A in `own` restates.

    See point 6 of the module docstring for the rule, and for why it is not
    "every Form 4 the owner filed that day"."""
    replaced: set[str] = set()
    originals = [f for f in own if f["form"] == "4"]
    for amendment in (f for f in own if f["form"] == "4/A"):
        reading = parsed[amendment["accession"]]
        original_date = reading.get("original_filing_date")
        amended_dates = {line["transaction_date"] for line in reading["lines"] or []}
        if not original_date or not amended_dates:
            continue
        try:
            earliest = date.fromisoformat(original_date)
        except ValueError:
            continue
        latest = (earliest + timedelta(days=AMENDMENT_FILING_DATE_SLACK_DAYS)).isoformat()
        candidates = [
            f for f in originals
            if parsed[f["accession"]]["owner_cik"] == reading["owner_cik"]
            and original_date <= f["filing_date"] <= latest
        ]
        overlapping = [
            f for f in candidates
            if amended_dates
            & {line["transaction_date"] for line in parsed[f["accession"]]["lines"] or []}
        ]
        if overlapping:
            replaced.update(f["accession"] for f in overlapping)
            continue
        same_day = [f for f in candidates if f["filing_date"] == original_date]
        if len(same_day) == 1:
            replaced.add(same_day[0]["accession"])
    return replaced


async def fetch_insider_transactions(
    symbol: str, days_back: int = 90, *, raise_failures: bool = False,
) -> list[dict[str, Any]] | None:
    """Form 4 non-derivative transactions for `symbol` in the last `days_back`
    days, newest filing first, as
    {filer_name, transaction_date, share_change, transaction_price, code}.

    See the module docstring for what counts as an answer."""
    try:
        return await _fetch(symbol, days_back)
    except (EdgarThrottledError, EdgarUnavailableError):
        if raise_failures:
            raise
        return None
