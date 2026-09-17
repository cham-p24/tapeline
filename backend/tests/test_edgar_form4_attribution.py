"""Which ticker a Form 4 belongs to, what a 4/A replaces, and dates in the future.

Found by an adversarial review of the insider feed on 2026-09-17, every one
verified read-only against production before it was fixed:

1. ATTRIBUTION. SEC lists several tickers under one CIK for many issuers, and
   every one of them received the issuer's whole Form 4 set: 70 CIKs spread
   2,609 rows over 173 symbols. Strategy's STRC/STRF/STRK/STRD preferreds
   carried MSTR's insider sales, JPM's VYLD/AMJB ETNs carried JPM's, and notes
   such as GREEL and TMUSZ carried their issuer's. A filing now goes to the
   ticker it names in issuerTradingSymbol, or to the CIK's first-listed SEC
   ticker when it names none SEC lists.
2. AMENDMENTS. A 4/A dropped EVERY Form 4 its owner filed that day. Magnetar
   filed three CRWV Form 4s on 2026-08-14 (trades of 12, 13 and 14 Aug); its
   4/A restated only the 14 Aug one, and the 12-13 Aug sales - 51 lines - were
   gone. It also missed originals EDGAR dated a day or more after the filer's
   submission date.
3. FUTURE DATES. A GIC filing made on 2026-09-03 reported a trade on
   2027-09-03. Nothing bounded a date from above, so it headed the Free
   preview's "most recent" list and the Premium feed, and - as the newest EDGAR
   row on file - would have "contradicted" GIC's empty answers for a year.
4. The read paths gained the same upper bound, "Buys only" now means a code-P
   purchase (it meant any positive share change: mostly option exercises and
   grants), and the Insider tab says when it truncates.
5. The stored rows predate all of this, so every row is re-read once
   (`_SMART_MONEY_REREAD_BEFORE`), and rows fetched before that instant do not
   count as evidence against an empty answer - otherwise a preferred's correct
   empty answer would be "contradicted" by the issuer rows it wrongly held.
"""
# ruff: noqa: F811  - test parameters named `sec` are the imported fixture.
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select

from app.db import session_scope
from app.main import app
from app.models import EdgarForm4Filing, InsiderTransaction, Ticker
from app.services import finnhub_feed
from app.services.edgar_form4 import (
    attributed_ticker,
    fetch_insider_transactions,
    parse_form4_xml,
    superseded_accessions,
)
from app.services.finnhub_feed import get_recent_insider_transactions_db
from app.workers import signal_publisher as sp
from tests.test_edgar_form4 import (
    AAPL_CIK,
    FakeSec,
    _d,
    form4_xml,
    sec,  # noqa: F401  (pytest fixture, used by name)
)

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

MSTR_CIK = "0001050446"


def _with_strategy(fake: FakeSec) -> FakeSec:
    """Strategy's common stock and two preferreds, in SEC's listing order."""
    fake.tickers.update({
        "10": {"cik_str": 1050446, "ticker": "MSTR", "title": "Strategy Inc"},
        "11": {"cik_str": 1050446, "ticker": "STRC", "title": "Strategy Inc"},
        "12": {"cik_str": 1050446, "ticker": "STRK", "title": "Strategy Inc"},
    })
    return fake


# ===========================================================================
# 1. Attribution
# ===========================================================================


def test_the_parser_records_the_named_symbol_in_secs_spelling() -> None:
    assert parse_form4_xml(form4_xml(symbol="brk.b"))["issuer_symbol"] == "BRK-B"


def test_attribution_rule() -> None:
    tickers = ["MSTR", "STRC", "STRK"]
    assert attributed_ticker({"issuer_symbol": "STRK"}, tickers) == "STRK"
    assert attributed_ticker({"issuer_symbol": "MSTR"}, tickers) == "MSTR"
    # Named symbol SEC does not list for the CIK (renamed, typo, blank):
    assert attributed_ticker({"issuer_symbol": "OLDNAME"}, tickers) == "MSTR"
    assert attributed_ticker({"issuer_symbol": ""}, tickers) == "MSTR"


async def test_a_preferred_does_not_carry_the_common_stocks_filings(sec: FakeSec) -> None:
    """Mutation: attribute every filing to every ticker of the CIK - STRK gets
    MSTR's insider sale."""
    _with_strategy(sec)
    sec.add(MSTR_CIK, "0001050446-26-000001", _d(2),
            form4_xml(issuer_cik=MSTR_CIK, symbol="MSTR", lines=[(_d(3), "925", "D", "300", "S")]))
    assert [t["share_change"] for t in await fetch_insider_transactions("MSTR", raise_failures=True)] == [-925]
    assert await fetch_insider_transactions("STRK", raise_failures=True) == []
    assert await fetch_insider_transactions("STRC", raise_failures=True) == []


async def test_a_filing_naming_no_listed_ticker_goes_to_the_first_listed(sec: FakeSec) -> None:
    _with_strategy(sec)
    sec.add(MSTR_CIK, "0001050446-26-000002", _d(2),
            form4_xml(issuer_cik=MSTR_CIK, symbol="MSTRX", lines=[(_d(3), "10", "A", "1", "P")]))
    assert len(await fetch_insider_transactions("MSTR", raise_failures=True)) == 1
    assert await fetch_insider_transactions("STRC", raise_failures=True) == []


async def _seed_v1_cache(accession: str, issuer_cik: str, filed: str, line_date: str) -> None:
    """A cache row as version 1 wrote it: no issuer symbol."""
    async with session_scope() as s:
        s.add(EdgarForm4Filing(
            accession=accession, form="4", filing_date=filed, issuer_cik=issuer_cik,
            owner_cik="0000000007", owner_name="Cached Owner", original_filing_date=None,
            rows_json=f'[{{"transaction_date": "{line_date}", "share_change": 5, '
                      f'"transaction_price": 1.0, "code": "P"}}]',
            parse_version=1,
        ))


def _archive_hits(fake: FakeSec) -> int:
    return sum("/Archives/" in r.url.path for r in fake.requests)


async def test_version_1_rows_still_serve_a_single_ticker_cik(sec: FakeSec) -> None:
    """Mutation: require the issuer-symbol version everywhere - every cached
    filing in the universe is downloaded again."""
    sec.add(AAPL_CIK, "0001140361-26-000077", _d(2), form4_xml())
    await _seed_v1_cache("0001140361-26-000077", AAPL_CIK, _d(2), _d(3))
    rows = await fetch_insider_transactions("AAPL", raise_failures=True)
    assert [r["filer_name"] for r in rows] == ["Cached Owner"]
    assert _archive_hits(sec) == 0


async def test_version_1_rows_are_read_again_for_a_multi_ticker_cik(sec: FakeSec) -> None:
    """Mutation: serve version-1 rows to a multi-ticker CIK - with no issuer
    symbol every filing falls back to the first-listed ticker, whatever it names."""
    _with_strategy(sec)
    sec.add(MSTR_CIK, "0001050446-26-000003", _d(2),
            form4_xml(issuer_cik=MSTR_CIK, symbol="STRK", lines=[(_d(3), "40", "A", "1", "P")]))
    await _seed_v1_cache("0001050446-26-000003", MSTR_CIK, _d(2), _d(3))
    assert await fetch_insider_transactions("MSTR", raise_failures=True) == []
    assert _archive_hits(sec) == 1
    assert len(await fetch_insider_transactions("STRK", raise_failures=True)) == 1


# ===========================================================================
# 2. Amendments
# ===========================================================================


def _f(acc: str, form: str, filed: str) -> dict[str, str]:
    return {"accession": acc, "form": form, "filing_date": filed, "document": "form4.xml"}


def _r(owner: str, dates: list[str], original: str | None = None) -> dict[str, Any]:
    return {
        "issuer_cik": MSTR_CIK, "issuer_symbol": "MSTR", "owner_cik": owner, "owner_name": owner,
        "original_filing_date": original,
        "lines": [{"transaction_date": d, "share_change": -1, "transaction_price": 1.0, "code": "S"}
                  for d in dates],
    }


def test_an_amendment_replaces_only_the_same_day_filing_it_restates() -> None:
    """The CRWV case. Mutation: drop every same-day original by the owner - the
    12 and 13 Aug filings vanish."""
    own = [_f("a12", "4", "2026-08-14"), _f("a13", "4", "2026-08-14"),
           _f("a14", "4", "2026-08-14"), _f("amd", "4/A", "2026-08-18")]
    parsed = {
        "a12": _r("MAG", ["2026-08-12"]), "a13": _r("MAG", ["2026-08-13"]),
        "a14": _r("MAG", ["2026-08-14"]), "amd": _r("MAG", ["2026-08-14"], original="2026-08-14"),
    }
    assert superseded_accessions(own, parsed) == {"a14"}


def test_a_filing_naming_nothing_falls_back_to_the_first_listed_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The fallback is a guess: SEC does not document common stock first, so a
    preferred can be [0]. Mutation: stay silent - the guess leaves no trace for
    a post-deploy grep."""
    with caplog.at_level("WARNING"):
        assert attributed_ticker({"issuer_symbol": ""}, ["STRK", "MSTR"]) == "STRK"
    assert "edgar_form4.attribution_fallback" in caplog.text
    # One ticker is not a guess, so it says nothing.
    caplog.clear()
    with caplog.at_level("WARNING"):
        assert attributed_ticker({"issuer_symbol": "ODD"}, ["MSTR"]) == "MSTR"
    assert "attribution_fallback" not in caplog.text


def test_an_amendment_replaces_the_original_it_matches_best_not_every_overlap() -> None:
    """Two same-day filings share a trade date; the 4/A restates one of them.
    Mutation: replace every overlapping candidate - the other filing's lines go
    with it."""
    own = [_f("keep", "4", "2026-08-14"), _f("amended", "4", "2026-08-14"),
           _f("amd", "4/A", "2026-08-18")]
    parsed = {
        # Both report a trade on 12 Aug; only `amended`'s whole lines match.
        "keep": _r("OWN", ["2026-08-12"]),
        "amended": _r("OWN", ["2026-08-12", "2026-08-13"]),
        "amd": _r("OWN", ["2026-08-12", "2026-08-13"], original="2026-08-14"),
    }
    assert superseded_accessions(own, parsed) == {"amended"}


def test_a_second_amendment_of_one_original_replaces_the_first() -> None:
    """A filer corrected the same Form 4 twice. Mutation: claim nothing - the
    original is dropped once but BOTH amendments are read, so the trade is
    counted twice."""
    own = [_f("orig", "4", "2026-08-14"), _f("amd1", "4/A", "2026-08-18"),
           _f("amd2", "4/A", "2026-08-21")]
    parsed = {
        "orig": _r("OWN", ["2026-08-12"]),
        "amd1": _r("OWN", ["2026-08-12"], original="2026-08-14"),
        "amd2": _r("OWN", ["2026-08-12"], original="2026-08-14"),
    }
    assert superseded_accessions(own, parsed) == {"orig", "amd1"}
    # Two amendments of DIFFERENT originals keep each other.
    two = [_f("o1", "4", "2026-08-14"), _f("o2", "4", "2026-08-14"),
           _f("a1", "4/A", "2026-08-18"), _f("a2", "4/A", "2026-08-19")]
    parsed_two = {
        "o1": _r("OWN", ["2026-08-11"]), "o2": _r("OWN", ["2026-08-12"]),
        "a1": _r("OWN", ["2026-08-11"], original="2026-08-14"),
        "a2": _r("OWN", ["2026-08-12"], original="2026-08-14"),
    }
    assert superseded_accessions(two, parsed_two) == {"o1", "o2"}


def test_an_amendment_finds_an_original_edgar_dated_later() -> None:
    """EDGAR dates an after-hours submission to the next business day.
    Mutation: exact-date match only - both filings count."""
    own = [_f("orig", "4", "2026-08-17"), _f("amd", "4/A", "2026-08-20")]
    parsed = {"orig": _r("OWN", ["2026-08-12"]),
              "amd": _r("OWN", ["2026-08-12"], original="2026-08-14")}
    assert superseded_accessions(own, parsed) == {"orig"}
    # ...but not beyond the slack.
    late = [_f("orig", "4", "2026-08-25"), _f("amd", "4/A", "2026-08-26")]
    assert superseded_accessions(late, parsed) == set()


def test_an_amendment_that_changed_the_dates_replaces_the_one_same_day_original() -> None:
    own = [_f("orig", "4", "2026-08-14"), _f("amd", "4/A", "2026-08-18")]
    parsed = {"orig": _r("OWN", ["2026-08-11"]), "amd": _r("OWN", ["2026-08-12"], original="2026-08-14")}
    assert superseded_accessions(own, parsed) == {"orig"}


def test_an_ambiguous_amendment_replaces_nothing() -> None:
    """No date overlap and two same-day originals: guessing would delete a real
    filing, so both stay."""
    own = [_f("o1", "4", "2026-08-14"), _f("o2", "4", "2026-08-14"), _f("amd", "4/A", "2026-08-18")]
    parsed = {"o1": _r("OWN", ["2026-08-11"]), "o2": _r("OWN", ["2026-08-10"]),
              "amd": _r("OWN", ["2026-08-12"], original="2026-08-14")}
    assert superseded_accessions(own, parsed) == set()


def test_an_amendment_with_no_share_lines_or_another_owner_replaces_nothing() -> None:
    own = [_f("orig", "4", "2026-08-14"), _f("amd", "4/A", "2026-08-18"),
           _f("other", "4", "2026-08-14")]
    parsed = {"orig": _r("OWN", ["2026-08-14"]), "other": _r("SOMEONE", ["2026-08-14"]),
              "amd": _r("OWN", [], original="2026-08-14")}
    assert superseded_accessions(own, parsed) == set()
    parsed["amd"] = _r("OWN", ["2026-08-14"], original="2026-08-14")
    assert superseded_accessions(own, parsed) == {"orig"}


# ===========================================================================
# 3. A trade dated after its own filing
# ===========================================================================


async def test_a_trade_dated_after_its_filing_is_dropped(sec: FakeSec) -> None:
    """The GIC case. Mutation: no upper bound - the 2027 line is returned."""
    future = (date.today() + timedelta(days=350)).isoformat()
    sec.add(AAPL_CIK, "0001437749-26-029639", _d(2), form4_xml(lines=[
        (future, "250", "A", "10", "J"),
        (_d(2), "7", "A", "10", "P"),     # same day as the filing: kept
    ]))
    rows = await fetch_insider_transactions("AAPL", raise_failures=True)
    assert [r["transaction_date"] for r in rows] == [_d(2)]


# ===========================================================================
# 4. Read paths
# ===========================================================================


async def _add_rows(symbol: str, rows: list[tuple[str, int, str]], *, fetched_at: datetime | None = None) -> None:
    async with session_scope() as s:
        for i, (day, change, code) in enumerate(rows):
            s.add(InsiderTransaction(
                symbol=symbol, insider_name=f"Filer {i}", transaction_date=day,
                share_change=change, transaction_price=10.0,
                transaction_value=abs(change) * 10.0, code=code, source="edgar",
                **({"fetched_at": fetched_at} if fetched_at else {}),
            ))


FUTURE = (date.today() + timedelta(days=351)).isoformat()


async def test_the_feed_never_returns_a_future_trade_and_buys_only_means_purchases() -> None:
    """Mutations: drop the upper bound (the future row leads); buys_only as
    share_change > 0 (the M and A rows come back)."""
    await _add_rows("RDB", [
        (FUTURE, 250, "J"), (_d(1), 500, "P"), (_d(1), 700, "M"), (_d(2), 90, "A"), (_d(3), -40, "S"),
    ])
    rows = await get_recent_insider_transactions_db(symbol="RDB", days=30)
    assert FUTURE not in [r["transaction_date"] for r in rows]
    assert len(rows) == 4
    buys = await get_recent_insider_transactions_db(symbol="RDB", days=30, buys_only=True)
    assert [(b["share_change"], b["code"]) for b in buys] == [(500, "P")]


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_the_public_list_never_leads_with_a_future_trade(client: httpx.AsyncClient) -> None:
    await _add_rows("RDP", [(FUTURE, 250, "P"), (_d(1), 500, "P")])
    async with client:
        items = (await client.get("/api/public/insider-buys?limit=20")).json()["items"]
    assert FUTURE not in [i["transaction_date"] for i in items]
    assert any(i["symbol"] == "RDP" for i in items)


async def test_the_gated_count_and_the_tab_agree_and_skip_future_trades(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: drop the upper bound from the count - it promises 3 lines and
    the tab opens on 2. Also: the tab flags truncation instead of cutting
    silently."""
    async with session_scope() as s:
        s.add(Ticker(symbol="RDT", name="Read Bound Co", score=55.0))
    await _add_rows("RDT", [(FUTURE, 9, "P"), (_d(1), 5, "P"), (_d(4), -3, "S")])
    async with client:
        count = (await client.get("/api/ticker/RDT")).json()["gated_counts"]["insider_form4"]
        tab = (await client.get("/api/ticker/RDT/insider",
                                headers={"Authorization": "Bearer dev-bypass"})).json()
        assert count == len(tab["transactions"]) == 2
        assert tab["truncated"] is False

        monkeypatch.setattr("app.routers.ticker._INSIDER_TAB_ROW_CAP", 1)
        capped = (await client.get("/api/ticker/RDT/insider",
                                   headers={"Authorization": "Bearer dev-bypass"})).json()
    assert capped["truncated"] is True
    assert len(capped["transactions"]) == 1


# ===========================================================================
# 5. The one-off re-read and the guard's trust window
# ===========================================================================


@pytest.fixture
def worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_CLEARED", set())
    monkeypatch.setattr(sp, "_sheet_is_scoring_source", lambda: False)


async def _held(symbol: str) -> int:
    async with session_scope() as s:
        return int(await s.scalar(
            select(func.count()).select_from(InsiderTransaction)
            .where(InsiderTransaction.symbol == symbol)
        ) or 0)


async def test_rows_fetched_before_the_reread_do_not_contradict_an_empty_answer(
    worker: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """STRK held MSTR's filings. Its correct empty answer must retire them.
    Mutation: drop the fetched_at condition - the clear raises, counts as a
    failure, and the rows stay forever."""
    cut = datetime(2026, 9, 17, 17, 30, tzinfo=UTC)
    monkeypatch.setattr(sp, "_SMART_MONEY_REREAD_BEFORE", cut)
    async with session_scope() as s:
        s.add(Ticker(symbol="STRK", name="Strategy Inc", sub_smart_money=20.0))
        s.add(Ticker(symbol="KEPT", name="Kept Co", sub_smart_money=20.0))
    await _add_rows("STRK", [(_d(2), -925, "S")], fetched_at=cut - timedelta(hours=2))
    await _add_rows("KEPT", [(_d(2), -925, "S")], fetched_at=cut + timedelta(hours=2))

    await sp._clear_smart_money_reading("STRK")
    assert await _held("STRK") == 0

    with pytest.raises(sp.EmptyAnswerContradictedError):
        await sp._clear_smart_money_reading("KEPT")
    assert await _held("KEPT") == 1


async def test_a_future_dated_row_does_not_contradict_an_empty_answer(
    worker: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: drop the date bound from the guard - GIC could never be
    cleared until 2027."""
    monkeypatch.setattr(sp, "_SMART_MONEY_REREAD_BEFORE", datetime(1970, 1, 1, tzinfo=UTC))
    async with session_scope() as s:
        s.add(Ticker(symbol="GIC", name="GIC Co", sub_smart_money=90.0))
    await _add_rows("GIC", [(FUTURE, 250, "J")])
    await sp._clear_smart_money_reading("GIC")
    assert await _held("GIC") == 0


@pytest.mark.parametrize("asset_class", ["equity", "etf"])
async def test_every_stamp_before_the_reread_is_due(
    monkeypatch: pytest.MonkeyPatch, asset_class: str,
) -> None:
    """Mutation: no re-read rule - the wrongly attributed rows wait out a 36h
    or 30-day horizon."""
    cut = datetime(2026, 9, 17, 17, 30, tzinfo=UTC)
    monkeypatch.setattr(sp, "_SMART_MONEY_EDGAR_SINCE", datetime(1970, 1, 1, tzinfo=UTC))
    monkeypatch.setattr(sp, "_SMART_MONEY_REREAD_BEFORE", cut)
    at = cut + timedelta(hours=2)
    async with session_scope() as s:
        for sym, stamp in (("PRE", cut - timedelta(hours=1)), ("POST", cut + timedelta(minutes=1))):
            s.add(Ticker(symbol=sym, name=f"{sym} Inc", asset_class=asset_class,
                         price=10.0, volume=1_000, last_smart_money_at=stamp, last_fundamentals_at=at))
    assert (await sp._factor_due_counts(now=at))[1] == 1
    assert await sp._select_factor_symbols(Ticker.last_smart_money_at, 10, now=at) == ["PRE"]


def test_the_reread_instant_follows_the_edgar_switch() -> None:
    assert sp._SMART_MONEY_REREAD_BEFORE.tzinfo is not None
    assert sp._SMART_MONEY_REREAD_BEFORE > sp._SMART_MONEY_EDGAR_SINCE
    assert sp._SMART_MONEY_REREAD_BEFORE.date() == date(2026, 9, 17)

