"""A Form 4's lines go to EVERY common-stock ticker of its issuer, and to
nothing else (`services/edgar_form4.py`, point 5, 2026-09-19).

What was wrong with the rule before (#862, 2026-09-17), measured read-only in
production on 2026-09-19:

* A filing went to ONE ticker: the one it names in issuerTradingSymbol. So the
  other common class got nothing - Alphabet's insiders file under GOOGL, and
  GOOG held none of the 183 lines GOOGL held; NWSA none of the 64 NWS held.
* When the named ticker was not one SEC lists for the CIK, the filing went to
  the CIK's FIRST-listed ticker - a guess. Production logged a filing naming
  TOI under a CIK listing STLN, DFPH and STLNW.

And what must NOT come back from before #862: preferreds, notes, ETNs,
warrants, units and rights carrying their issuer's insider trades (STRK
carrying MSTR's sales). Those still get nothing, and a symbol whose CIK we
carry only as a note never falls back to it.

The lines a cross-ticker list shows once are pinned in section 4.
"""
# ruff: noqa: F811  - test parameters named `sec` / `worker` are imported fixtures.
from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy import select, update

from app.db import session_scope
from app.main import app
from app.models import EdgarForm4Filing, InsiderTransaction, Ticker
from app.services import edgar_form4
from app.services.edgar_form4 import Listing, fetch_insider_transactions
from app.services.finnhub_feed import get_recent_insider_transactions_db, insider_feed_size_db
from app.workers import signal_publisher as sp
from tests.test_edgar_form4 import (
    FakeSec,
    _d,
    _form4_rows,
    _seed_ticker,
    form4_xml,
    sec,  # noqa: F401  (pytest fixture, used by name)
    worker,  # noqa: F401  (pytest fixture, used by name)
)
from tests.test_edgar_form4_attribution import _archive_hits, _seed_v1_cache

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

#: The real `load_listing`, before the `sec` fixture replaces it.
_REAL_LOAD_LISTING = edgar_form4.load_listing

ALPHABET = "0001652044"
BERKSHIRE = "0001067983"
NEWS_CORP = "0001564708"
STRATEGY = "0001050446"
TMOBILE = "0001283699"
JPMORGAN = "0000019617"
GREENIDGE = "0001844971"
BRIGHTHOUSE = "0001685040"
PREFERRED_BANK = "0001492165"
CROSSAMERICA = "0001538849"
STARLING = "0001855457"

#: Names and classes as production stores them (read-only, 2026-09-19).
LISTINGS: dict[str, tuple[str | None, str | None]] = {
    "GOOG": ("Alphabet Inc. Class C Capital Stock", "equity"),
    "GOOGL": ("Alphabet Inc.", "equity"),
    "GOOGN": ("Alphabet Inc. Depositary Shares representing a 1/20th Interest in a Share of "
              "Series B Mandatory Convertible Preferred Stock", "equity"),
    "BRK.A": ("Berkshire Hathaway Inc.", "equity"),
    "BRK.B": ("Berkshire Hathaway", "equity"),
    "BRK-A": ("Berkshire Hathaway Inc", "equity"),
    "BRK-B": ("Berkshire Hathaway Inc", "equity"),
    "NWS": ("News Corp", "equity"),
    "NWSA": ("News Corp", "equity"),
    "MSTR": ("Strategy Inc", "equity"),
    "STRK": ("Strategy Inc", "equity"),
    "TMUS": ("T-Mobile US", "equity"),
    "TMUSZ": ("T-Mobile US, Inc. 5.500% Senior Notes due March 2070", "equity"),
    "JPM": ("JPMorgan Chase", "equity"),
    "VYLD": ("Inverse VIX Short-Term Futures ETNs due March 22, 2045", "etf"),
    "GREEL": ("Greenidge Generation Holdings Inc. 8.50% Senior Notes due 2026", "equity"),
    "BHF": ("Brighthouse Financial, Inc.", "equity"),
    "BHFAO": ("Brighthouse Financial, Inc. Depositary Shares 6.75% Non-Cum Pfd Series B", "equity"),
    "PFBC": ("Preferred Bank", "equity"),
    "CAPL": ("CrossAmerica Partners LP Common units representing limited partner interests", "equity"),
    "STLN": ("Starling Oncology, Inc. Common Stock", "equity"),
    "STLNW": ("STLNW", "equity"),
    # No tickers row in production.
    "DFPH": (None, None),
}


def _sec_lists(fake: FakeSec, cik: str, tickers: list[str]) -> None:
    """SEC's company_tickers.json rows for one CIK, in the order given."""
    start = 100 + len(fake.tickers)
    for i, ticker in enumerate(tickers):
        fake.tickers[str(start + i)] = {"cik_str": int(cik), "ticker": ticker, "title": "x"}


@pytest.fixture
def listed(sec: FakeSec, monkeypatch: pytest.MonkeyPatch) -> FakeSec:
    """`sec`, with production's names for every symbol these tests ask about,
    the universe the fifth-letter rules read, and the not-listed log reset."""
    universe = frozenset(LISTINGS)

    async def _listing(symbol: str) -> Listing:
        name, asset_class = LISTINGS.get(symbol, (f"{symbol} Inc", "equity"))
        return Listing(name=name, asset_class=asset_class, universe=universe)

    monkeypatch.setattr(edgar_form4, "load_listing", _listing)
    monkeypatch.setattr(edgar_form4, "_NAMED_NOT_LISTED_LOGGED", set())
    return sec


def _xml(cik: str, symbol: str, day: int, shares: str, ad: str, price: str, code: str,
         owner: str = "Insider One", owner_cik: str = "0000000101") -> str:
    return form4_xml(issuer_cik=cik, symbol=symbol, owner=owner, owner_cik=owner_cik,
                     lines=[(_d(day), shares, ad, price, code)])


async def _shares(symbol: str) -> list[int]:
    rows = await fetch_insider_transactions(symbol, raise_failures=True)
    assert rows is not None
    return sorted(r["share_change"] for r in rows)


def _submissions_for(fake: FakeSec, cik: str) -> int:
    return sum(p.endswith(f"/CIK{cik}.json") for p in fake.paths())


# ===========================================================================
# 1. Every common class keeps the issuer's lines
# ===========================================================================


async def test_goog_and_googl_both_keep_alphabets_lines(listed: FakeSec) -> None:
    """Alphabet's insiders name GOOGL. Mutation (#862's rule: only the named
    ticker) - GOOG gets nothing."""
    _sec_lists(listed, ALPHABET, ["GOOGL", "GOOG", "GOOGN"])
    listed.add(ALPHABET, "0001652044-26-000001", _d(2), _xml(ALPHABET, "GOOGL", 3, "2000", "D", "250", "S"))
    assert await _shares("GOOGL") == [-2000]
    assert await _shares("GOOG") == [-2000]
    # The mandatory convertible preferred's depositary shares: nothing.
    assert await _shares("GOOGN") == []


async def test_all_four_berkshire_rows_keep_berkshires_lines(listed: FakeSec) -> None:
    """Buffett files as BRK.A, O'Sullivan as BRK.B (both measured 2026-09-19).
    Every Class A and Class B row the universe carries - dotted and hyphenated
    - holds both. Mutation (#862's rule): each class holds only the lines that
    name it."""
    _sec_lists(listed, BERKSHIRE, ["BRK-A"])  # BRK-B is FakeSec's default row
    listed.add(BERKSHIRE, "0001067983-26-000001", _d(3),
               _xml(BERKSHIRE, "BRK.A", 4, "9000", "D", "0", "G", owner="BUFFETT WARREN E"))
    listed.add(BERKSHIRE, "0001067983-26-000002", _d(2),
               _xml(BERKSHIRE, "BRK.B", 3, "400", "A", "512.52", "P", owner="O'Sullivan Michael J."))
    for symbol in ("BRK.A", "BRK.B", "BRK-A", "BRK-B"):
        assert await _shares(symbol) == [-9000, 400], symbol


async def test_nws_and_nwsa_both_keep_news_corps_lines(listed: FakeSec) -> None:
    _sec_lists(listed, NEWS_CORP, ["NWSA", "NWS"])
    listed.add(NEWS_CORP, "0001564708-26-000001", _d(2), _xml(NEWS_CORP, "NWS", 3, "500", "D", "30", "S"))
    assert await _shares("NWS") == [-500]
    assert await _shares("NWSA") == [-500]


async def test_mlp_common_units_keep_their_issuers_lines(listed: FakeSec) -> None:
    """"Common units representing limited partner interests" is an MLP's
    equity, not a unit of a SPAC."""
    _sec_lists(listed, CROSSAMERICA, ["CAPL"])
    listed.add(CROSSAMERICA, "0001538849-26-000001", _d(2), _xml(CROSSAMERICA, "CAPL", 3, "75", "A", "21", "P"))
    assert await _shares("CAPL") == [75]


# ===========================================================================
# 2. Everything that is not common stock keeps nothing
# ===========================================================================


async def test_preferreds_notes_and_etns_keep_nothing_and_cost_no_request(listed: FakeSec) -> None:
    """STRK (named "Strategy Inc", caught by symbol), TMUSZ (a note) and VYLD
    (an ETN stored as an ETF) - each a ticker SEC lists under its issuer's CIK.
    Mutation: fan out to every ticker of the CIK - all three get the issuer's
    sale. And they are answered without asking SEC at all."""
    _sec_lists(listed, STRATEGY, ["MSTR", "STRK"])
    _sec_lists(listed, TMOBILE, ["TMUS", "TMUSZ"])
    _sec_lists(listed, JPMORGAN, ["JPM", "VYLD"])
    listed.add(STRATEGY, "0001050446-26-000009", _d(2), _xml(STRATEGY, "MSTR", 3, "925", "D", "300", "S"))
    listed.add(TMOBILE, "0001283699-26-000009", _d(2), _xml(TMOBILE, "TMUS", 3, "80", "D", "240", "S"))
    listed.add(JPMORGAN, "0000019617-26-000009", _d(2), _xml(JPMORGAN, "JPM", 3, "60", "D", "300", "S"))
    before = len(listed.requests)
    for symbol in ("STRK", "TMUSZ", "VYLD"):
        assert await _shares(symbol) == [], symbol
    assert len(listed.requests) == before, "a non-common listing asked SEC"
    assert await _shares("MSTR") == [-925]
    assert await _shares("TMUS") == [-80]
    assert await _shares("JPM") == [-60]


async def test_a_cik_carried_only_as_a_note_keeps_nothing(listed: FakeSec) -> None:
    """We carry Greenidge only as its note GREEL, which SEC lists FIRST under
    the CIK, and the filing names a ticker SEC does not list. #862's fallback
    handed such a filing to the first-listed ticker - the note. Mutation:
    restore that fallback - GREEL carries the issuer's purchase."""
    _sec_lists(listed, GREENIDGE, ["GREEL", "GREE"])
    listed.add(GREENIDGE, "0001844971-26-000001", _d(2), _xml(GREENIDGE, "GREEX", 3, "1000", "A", "2", "P"))
    assert await _shares("GREEL") == []


@pytest.mark.parametrize("named", ["BHFAO", "BHF"])
async def test_bhfao_is_not_common_whichever_ticker_the_filing_names(listed: FakeSec, named: str) -> None:
    """BHFAO is a depositary share of a non-cumulative preferred; BHF is the
    common. A filing naming either is Brighthouse's, and only BHF carries it.
    Mutation (#862's rule): a filing naming BHFAO lands on BHFAO, not BHF."""
    _sec_lists(listed, BRIGHTHOUSE, ["BHF", "BHFAO"])
    listed.add(BRIGHTHOUSE, "0001685040-26-000001", _d(2), _xml(BRIGHTHOUSE, named, 3, "300", "D", "55", "S"))
    assert await _shares("BHF") == [-300]
    assert await _shares("BHFAO") == []


async def test_preferred_bank_is_a_common_stock(listed: FakeSec) -> None:
    """"Preferred" is the bank's name, not its security type. Mutation: flag
    any name with "Preferred" - PFBC loses its insiders' lines."""
    _sec_lists(listed, PREFERRED_BANK, ["PFBC"])
    listed.add(PREFERRED_BANK, "0001492165-26-000001", _d(2),
               _xml(PREFERRED_BANK, "PFBC", 3, "100", "A", "90", "P"))
    assert await _shares("PFBC") == [100]


# ===========================================================================
# 3. A filing naming a ticker SEC does not list for its CIK
# ===========================================================================


async def test_a_filing_naming_an_unlisted_ticker_is_kept_and_measured_once(
    listed: FakeSec, caplog: pytest.LogCaptureFixture,
) -> None:
    """Production, 2026-09-18: a filing named TOI under a CIK SEC lists as
    STLN, DFPH and STLNW. It is still the company's filing - the issuer CIK
    matches - so the common stock keeps it; the warrant and the row-less DFPH
    do not. It is logged at INFO once per filing, however many symbols read
    it. Mutations: drop the log - no trace; log per read - counted twice."""
    _sec_lists(listed, STARLING, ["STLN", "DFPH", "STLNW"])
    listed.add(STARLING, "0001855457-26-000001", _d(2), _xml(STARLING, "TOI", 3, "5000", "A", "4", "P"))
    with caplog.at_level("INFO", logger="app.services.edgar_form4"):
        assert await _shares("STLN") == [5000]
        assert await _shares("STLN") == [5000]
        assert await _shares("STLNW") == []
        assert await _shares("DFPH") == []
    logged = [r for r in caplog.records if "edgar_form4.named_ticker_not_listed" in r.getMessage()]
    assert len(logged) == 1
    assert logged[0].levelname == "INFO"
    assert "'TOI'" in logged[0].getMessage()
    # Naming a listed ticker is not a measurement.
    caplog.clear()
    listed.add(STARLING, "0001855457-26-000002", _d(1), _xml(STARLING, "STLN", 2, "7", "A", "4", "P"))
    with caplog.at_level("INFO", logger="app.services.edgar_form4"):
        assert await _shares("STLN") == [7, 5000]
    assert "named_ticker_not_listed" not in caplog.text


async def test_version_1_cache_rows_serve_a_multi_ticker_cik(listed: FakeSec) -> None:
    """A version-1 row records no issuer symbol. The named symbol no longer
    decides attribution, so such rows serve every CIK and nothing is
    downloaded again. Mutation: keep #862's issuer-symbol version floor for
    multi-ticker CIKs - the filing is fetched again."""
    _sec_lists(listed, STRATEGY, ["MSTR", "STRK"])
    listed.add(STRATEGY, "0001050446-26-000003", _d(2), _xml(STRATEGY, "STRK", 3, "40", "A", "1", "P"))
    await _seed_v1_cache("0001050446-26-000003", STRATEGY, _d(2), _d(3))
    assert [r["filer_name"] for r in await fetch_insider_transactions("MSTR", raise_failures=True) or []] \
        == ["Cached Owner"]
    assert _archive_hits(listed) == 0
    assert await _shares("STRK") == []


def test_the_parser_records_each_lines_security_title() -> None:
    """Recorded for a later per-line check; nothing reads it yet. Cached rows
    parsed before 2026-09-19 carry no such key (see the v1 test above, whose
    lines have none and still serve)."""
    xml = form4_xml().replace("<value>Common Stock</value>", "<value>Class C Capital Stock</value>")
    assert edgar_form4.parse_form4_xml(xml)["lines"][0]["security_title"] == "Class C Capital Stock"
    missing = form4_xml().replace("<value>Common Stock</value>", "<value></value>")
    assert edgar_form4.parse_form4_xml(missing)["lines"][0]["security_title"] is None
    assert edgar_form4.PARSE_VERSION == 2, "security_title was added without a version bump on purpose"


# ===========================================================================
# 3a. A caller that holds no Listing
# ===========================================================================


async def test_a_caller_without_a_listing_gets_the_one_tickers_holds(
    sec: FakeSec, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`fetch_insider_transactions(sym)` with no listing reads the symbol's
    row. Mutation: treat a missing listing as common - STRK (a preferred by
    its symbol) would still be caught, so this uses a NOTE by name, and a
    symbol with no row at all."""
    monkeypatch.setattr(edgar_form4, "load_listing", _REAL_LOAD_LISTING)
    monkeypatch.setattr(edgar_form4, "_NAMED_NOT_LISTED_LOGGED", set())
    _sec_lists(sec, TMOBILE, ["TMUS", "TMUSZ", "TMUSX"])
    sec.add(TMOBILE, "0001283699-26-000001", _d(2), _xml(TMOBILE, "TMUS", 3, "80", "D", "240", "S"))
    await _seed_ticker("TMUS", name="T-Mobile US")
    await _seed_ticker("TMUSZ", name="T-Mobile US, Inc. 5.500% Senior Notes due March 2070")
    assert await _shares("TMUS") == [-80]
    assert await _shares("TMUSZ") == []
    # No tickers row: not KNOWN to be common stock, and SEC is not asked.
    before = len(sec.requests)
    assert await _shares("TMUSX") == []
    assert len(sec.requests) == before


async def test_load_listing_reads_the_row_and_its_four_letter_root() -> None:
    await _seed_ticker("OIMA", name="OneIM Acquisition Corp. Class A")
    await _seed_ticker("OIMAU", name="OneIM Acquisition Corp.")
    listing = await _REAL_LOAD_LISTING("OIMAU")
    assert (listing.name, listing.asset_class) == ("OneIM Acquisition Corp.", "equity")
    assert listing.universe == frozenset({"OIMA", "OIMAU"})
    # The unit is caught by its listed root, not its name.
    assert not listing.is_common_stock("OIMAU")
    assert (await _REAL_LOAD_LISTING("OIMA")).is_common_stock("OIMA")
    assert await _REAL_LOAD_LISTING("NONE") == Listing(name=None, asset_class=None)


# ===========================================================================
# 3b. The worker pass
# ===========================================================================


async def _held_rows(symbol: str, day: str, shares: int) -> None:
    async with session_scope() as s:
        s.add(InsiderTransaction(
            symbol=symbol, insider_name="Held Filer", transaction_date=day,
            share_change=shares, transaction_price=10.0, transaction_value=abs(shares) * 10.0,
            code="S", source="edgar",
        ))


async def test_the_pass_fans_out_to_common_classes_and_retires_the_rest(
    listed: FakeSec, worker: None,
) -> None:
    """One pass over GOOG, GOOGL, STRK and USO, with the listings read from
    `tickers` once. GOOG and GOOGL both store Alphabet's line; STRK stores
    nothing; USO (an ETF, so not common stock) had rows under the old rule
    and loses them. Its empty answer is the RULE's, not SEC's, so the stored
    rows cannot "contradict" it. Mutation: drop by_rule - USO's clear is
    refused as contradicted, counts as a failure, and its rows stay forever
    (USO held 21 such rows in production on 2026-09-19)."""
    _sec_lists(listed, ALPHABET, ["GOOGL", "GOOG"])
    listed.add(ALPHABET, "0001652044-26-000001", _d(2), _xml(ALPHABET, "GOOGL", 3, "2000", "D", "250", "S"))
    await _seed_ticker("GOOG", name="Alphabet Inc. Class C Capital Stock")
    await _seed_ticker("GOOGL", name="Alphabet Inc.")
    await _seed_ticker("STRK", name="Strategy Inc", sub_smart_money=40.0)
    await _seed_ticker("USO", name="United States Oil", asset_class="etf", sub_smart_money=30.0)
    await _held_rows("USO", _d(3), -500)
    await _held_rows("STRK", _d(3), -925)

    await sp._refresh_insider_cache(limit=10)

    assert [r.share_change for r in await _form4_rows("GOOG")] == [-2000]
    assert [r.share_change for r in await _form4_rows("GOOGL")] == [-2000]
    assert await _form4_rows("STRK") == []
    assert await _form4_rows("USO") == []
    async with session_scope() as s:
        readings = dict((await s.execute(
            select(Ticker.symbol, Ticker.sub_smart_money).where(Ticker.symbol.in_(["STRK", "USO"]))
        )).all())
        stamps = dict((await s.execute(select(Ticker.symbol, Ticker.last_smart_money_at))).all())
    assert readings == {"STRK": None, "USO": None}
    assert all(stamps[s] is not None for s in ("GOOG", "GOOGL", "STRK", "USO"))
    # Neither non-common symbol cost an SEC request: only Alphabet was asked.
    assert _submissions_for(listed, ALPHABET) == 2
    assert sum("/submissions/" in p for p in listed.paths()) == 2


async def test_a_common_stocks_empty_answer_is_still_checked(listed: FakeSec, worker: None) -> None:
    """The guard is skipped only for a rule-decided answer. SEC answering []
    for a common stock whose recent EDGAR rows we hold is still refused."""
    _sec_lists(listed, JPMORGAN, ["JPM"])
    await _seed_ticker("JPM", name="JPMorgan Chase", sub_smart_money=40.0)
    await _held_rows("JPM", _d(3), -60)
    await sp._refresh_insider_cache(limit=5)
    assert len(await _form4_rows("JPM")) == 1


# ===========================================================================
# 4. A line several classes carry is listed once
# ===========================================================================


async def _filing(accession: str, cik: str, owner: str, lines: list[tuple[str, int, float, str]]) -> None:
    """The parsed-filing cache row an EDGAR insider row was written from."""
    async with session_scope() as s:
        s.add(EdgarForm4Filing(
            accession=accession, form="4", filing_date=_d(1), issuer_cik=cik, issuer_symbol=None,
            owner_cik="0000000101", owner_name=owner, original_filing_date=None,
            rows_json=json.dumps([
                {"transaction_date": day, "share_change": shares, "transaction_price": price, "code": code}
                for day, shares, price, code in lines
            ]),
            parse_version=2,
        ))


async def _rows(symbol: str, owner: str, lines: list[tuple[str, int, float, str]],
                source: str | None = "edgar") -> None:
    async with session_scope() as s:
        for day, shares, price, code in lines:
            s.add(InsiderTransaction(
                symbol=symbol, insider_name=owner, transaction_date=day, share_change=shares,
                transaction_price=price, transaction_value=abs(shares * price), code=code,
                source=source,
            ))
    if source is None:
        # The ORM fills in the model's "edgar" default for None; migration
        # 0069 left pre-switch rows NULL, so write that with an UPDATE.
        async with session_scope() as s:
            await s.execute(
                update(InsiderTransaction).where(InsiderTransaction.symbol == symbol).values(source=None)
            )


ALPHABET_SALE = (_d(3), -2000, 250.0, "S")
ALPHABET_OLDER = (_d(6), -10, 250.0, "S")


async def _alphabet_on_both_classes() -> None:
    await _filing("0001652044-26-000001", ALPHABET, "Pichai Sundar", [ALPHABET_SALE, ALPHABET_OLDER])
    for symbol in ("GOOG", "GOOGL"):
        await _rows(symbol, "Pichai Sundar", [ALPHABET_SALE, ALPHABET_OLDER])


async def test_the_feed_lists_a_line_both_classes_carry_once() -> None:
    """Mutation: no collapse - Pichai's one sale is listed under GOOG and
    again under GOOGL."""
    await _alphabet_on_both_classes()
    items = await get_recent_insider_transactions_db(days=30)
    assert [(i["symbol"], i["symbols"], i["share_change"]) for i in items] == [
        ("GOOG", ["GOOG", "GOOGL"], -2000), ("GOOG", ["GOOG", "GOOGL"], -10),
    ]
    # Filtered to one ticker, nothing is collapsed and nothing is lost.
    only = await get_recent_insider_transactions_db(days=30, symbol="GOOGL")
    assert [(i["symbol"], i["symbols"]) for i in only] == [("GOOGL", ["GOOGL"])] * 2


async def test_two_companies_identical_lines_are_never_merged() -> None:
    """Production, 2026-09-19: MetLife Investment Management redeemed 36,000
    shares at $25.00 on 2026-08-24 in CCD AND in CHI - two Calamos funds, two
    CIKs, identical lines. Mutation: key on the line's content alone - they
    merge into one company's line."""
    line = (_d(4), -36000, 25.0, "J")
    await _filing("0000000001-26-000001", "0001396277", "MetLife Investment Management, LLC", [line])
    await _filing("0000000002-26-000001", "0001227073", "MetLife Investment Management, LLC", [line])
    await _rows("CCD", "MetLife Investment Management, LLC", [line])
    await _rows("CHI", "MetLife Investment Management, LLC", [line])
    items = await get_recent_insider_transactions_db(days=30)
    assert sorted((i["symbol"], i["symbols"]) for i in items) == [("CCD", ["CCD"]), ("CHI", ["CHI"])]
    assert await insider_feed_size_db() == 2


async def test_rows_with_no_filing_to_check_are_never_merged() -> None:
    """A row whose filing is not in the cache, or a pre-EDGAR Finnhub row,
    cannot be shown to be one issuer's, so it is listed as stored."""
    line = (_d(4), -5, 10.0, "S")
    await _rows("AAA", "Same Person", [line])
    await _rows("AAB", "Same Person", [line])
    await _rows("FNA", "Old Vendor", [line], source=None)
    await _rows("FNB", "Old Vendor", [line], source=None)
    await _filing("0000000009-26-000001", "0000000009", "Old Vendor", [line])
    items = await get_recent_insider_transactions_db(days=30)
    assert sorted(i["symbol"] for i in items) == ["AAA", "AAB", "FNA", "FNB"]


async def test_a_page_still_fills_its_limit_with_distinct_lines() -> None:
    """Mutation: read only `limit` rows - the two copies of the newest line
    fill a page of two, and the older line never appears."""
    await _alphabet_on_both_classes()
    items = await get_recent_insider_transactions_db(days=30, limit=2)
    assert [i["share_change"] for i in items] == [-2000, -10]
    one = await get_recent_insider_transactions_db(days=30, limit=1)
    assert [i["share_change"] for i in one] == [-2000]


async def test_the_tracked_count_counts_a_shared_line_once() -> None:
    """The Holdings page's "N tracked transactions". Mutation: COUNT(*) - 4."""
    await _alphabet_on_both_classes()
    assert await insider_feed_size_db() == 2


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_the_public_list_shows_a_shared_purchase_once(client: httpx.AsyncClient) -> None:
    """/api/public/insider-buys. Berkshire's four rows each hold O'Sullivan's
    purchase. Mutation: no collapse on this endpoint - it is listed four
    times."""
    buy = (_d(3), 400, 512.52, "P")
    await _filing("0001067983-26-000002", BERKSHIRE, "O'Sullivan Michael J.", [buy])
    for symbol in ("BRK-A", "BRK-B", "BRK.A", "BRK.B"):
        await _rows(symbol, "O'Sullivan Michael J.", [buy])
    async with client:
        body = (await client.get("/api/public/insider-buys?limit=10")).json()
    assert body["count"] == 1
    # The hyphen twins are not covered since #889 (services/coverage.py), so
    # the line is listed, and linked, under the covered spellings only.
    # Mutation: plain sorted() puts BRK-A first and lists all four.
    assert body["items"][0]["symbols"] == ["BRK.A", "BRK.B"]
    assert body["items"][0]["symbol"] == "BRK.A"
    assert "line_seq" not in body["items"][0] and "source" not in body["items"][0]


async def test_the_premium_feed_and_preview_show_a_shared_line_once(client: httpx.AsyncClient) -> None:
    await _alphabet_on_both_classes()
    headers = {"Authorization": "Bearer dev-bypass"}
    async with client:
        feed = (await client.get("/api/holdings?days=30", headers=headers)).json()
        preview = (await client.get("/api/holdings/preview", headers=headers)).json()
    assert feed["count"] == 2 and feed["feed_size"] == 2
    assert [i["symbols"] for i in feed["items"]] == [["GOOG", "GOOGL"]] * 2
    assert preview["count"] == 2 and preview["feed_size"] == 2


async def test_a_tickers_own_count_is_its_own_lines(client: httpx.AsyncClient) -> None:
    """gated_counts is per ticker, so a sibling class never doubles it: GOOG's
    count is GOOG's two lines, the same two its Insider tab lists."""
    await _alphabet_on_both_classes()
    async with session_scope() as s:
        s.add(Ticker(symbol="GOOG", name="Alphabet Inc. Class C Capital Stock", score=55.0))
    async with client:
        count = (await client.get("/api/ticker/GOOG")).json()["gated_counts"]["insider_form4"]
        tab = (await client.get("/api/ticker/GOOG/insider", headers={"Authorization": "Bearer dev-bypass"})).json()
    assert count == len(tab["transactions"]) == 2

