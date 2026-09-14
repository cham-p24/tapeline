"""A guard: a class share from the workbook lands on the row the vendor prices.

WHAT PRODUCTION LOOKS LIKE (read-only, 2026-09-14)
--------------------------------------------------
* The workbook has spelled class shares Yahoo-style in the past. The BRK-A and
  BRK-B rows exist, and the sheet last wrote them before 2026-08-24: their
  trend, RS and momentum are identical in every daily snapshot since. Their
  price is NULL, because the vendor does not answer for the hyphen spelling.
* As of 2026-09-14 the workbook writes BRK.A and BRK.B. ALL SIGNALS has no
  hyphenated tickers, and BRK.B and BRK.A are already sheet-governed.
* So on today's data this mapping changes nothing. It keeps a return to
  hyphens from recreating a second, never-priced row.

The two existing hyphen rows are left exactly as they are. Retiring them, and
redirecting /t/BRK-A and /t/BRK-B, is a production data change for the founder
to decide.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import session_scope
from app.models import Ticker
from app.services import symbols
from app.services.sheet_feed import (
    parse_all_signals_csv,
    parse_etf_benchmarks_csv,
    parse_smart_money_csv,
    parse_spike_intelligence_csv,
    upsert_etfs,
    upsert_tickers,
)

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

_ALL_SIGNALS_HEADER = (
    "Ticker,Type,Asset Class,Strategy,Conviction,Score,Raw Score,Signal,Verdict,Action,"
    "Hold Duration,Price,Above 200DMA,Market Regime,Beats SPY?,Momentum Quality,"
    "3M Return %,6M Return %,1Y Return %,RS vs SPY 3M %,RS vs SPY 6M %,RS vs SPY 1Y %,"
    "RS vs Sector 3M %,Near 52W High %"
)


def _all_signals_row(ticker: str, price: str = "514.83") -> str:
    return (
        f"{ticker},STOCK,Stock,QUALITY,A,72,90,ACCUMULATE,Buy,Accumulate,6-12 months,"
        f"{price},TRUE,BULL,Yes (+3.1%),All 3 positive,4.2,9.8,18.1,1.2,3.1,2.4,1.0,96.5\n"
    )


def _all_signals(*tickers: str) -> str:
    return _ALL_SIGNALS_HEADER + "\n" + "".join(_all_signals_row(t) for t in tickers)


@pytest.mark.parametrize(("sheet", "vendor"), [
    ("BRK-B", "BRK.B"),
    ("BRK-A", "BRK.A"),
    ("BF-B", "BF.B"),
    ("LEN-B", "LEN.B"),
])
def test_a_hyphenated_class_share_is_spelled_the_vendors_way(sheet: str, vendor: str) -> None:
    """Mutation: returning the symbol unchanged."""
    assert symbols.vendor_share_class_symbol(sheet) == vendor


@pytest.mark.parametrize("unchanged", [
    "BRK.B", "SPY", "BAC.PRL", "FFH.TO", "CL=F", "ZC=F", "ABCD-WS", "ABC-RT", "ABCDEF-B",
    "RCI-B.TO", "XYZ-WT", "BAC-PL",
])
def test_everything_else_is_left_alone(unchanged: str) -> None:
    """Only a one-letter class after one to five letters is a class share.
    Mutations: widening the suffix (XYZ-WT, a warrant, or BAC-PL, a preferred,
    would be rewritten into a symbol that does not exist); widening the root;
    dropping the end anchor (RCI-B.TO is a foreign listing, not a US class
    share)."""
    assert symbols.vendor_share_class_symbol(unchanged) == unchanged


def test_the_serving_path_still_resolves_the_existing_row() -> None:
    """/t/BRK-B keeps finding the row that exists until someone decides to
    retire it. Mutation: mapping inside clean_symbol, which every router uses."""
    assert symbols.clean_symbol("BRK-B") == "BRK-B"


def test_the_all_signals_tab_keys_berkshire_by_the_vendor_symbol() -> None:
    """Mutation: the parser calling _clean_symbol directly."""
    rows = parse_all_signals_csv(_all_signals("BRK-B"))
    assert [r["symbol"] for r in rows] == ["BRK.B"]


@pytest.mark.parametrize("typed", [" brk-b ", "brk-b"])
def test_a_hand_typed_cell_is_cleaned_before_it_is_mapped(typed: str) -> None:
    """The cell is stripped and uppercased first, then mapped. Mutation:
    mapping before cleaning, which misses the lowercase or padded form and
    ingests a new BRK-B twin."""
    rows = parse_all_signals_csv(_all_signals(typed))
    assert [r["symbol"] for r in rows] == ["BRK.B"]


def test_the_other_three_tabs_key_class_shares_the_same_way() -> None:
    """The spike, ETF-benchmark and smart-money tabs read the same Ticker cell.
    One tab spelling BRK-B and another BRK.B would split one company's inputs
    across two rows again. Mutation: any one parser left on _clean_symbol."""
    spike = parse_spike_intelligence_csv(
        "Spike Rank,Ticker,Buy By,Time Window,Stage,Entry Trigger,Stop / Risk,Price,Spike Score,"
        "Spike Direction,Type,Spike Urgency,Suggested Window,Buy Timing,Decision,Score,"
        "Source Confidence,Source Notes,Volume Expansion,RSI14,OBV Trend,Breakout Type,"
        "Spike Reasons,Why This May Move,Main Risk,Core Signal,Hold Duration\n"
        "1,BRK-B,Fri 29 May,Watch next 2 weeks,READY TO MOVE,close above 520,500 (-3%),514.83,90,"
        "UPSIDE,STOCK,HIGH,1-4 weeks,Possible entry,Entry timing,90,TECHNICAL-LED (54/100),"
        "price live,1.5,60.6,Rising,Breaking above upper BB,Tight squeeze,RSI in zone,Macro,"
        "STRONG SETUP,6-12 months\n"
    )
    etf = parse_etf_benchmarks_csv(
        "Ticker,Name,unused,Note,Score,Signal,3M Return %,6M Return %,1Y Return %,Above 200DMA,"
        "Beats SPY (6M),vs SPY 6M %,Action\n"
        "BRK-B,Berkshire Hathaway,,Holding company,75,BUY NOW,5.2,11.4,18.3,TRUE,Yes,0.0,"
        "Strong Buy & Hold\n"
    )
    smart = parse_smart_money_csv(
        "Watcher / Buyer,Category,Ticker,Recent Buy / Holding Signal,Filing / Period,Filed,"
        "Current Model Sign,Model Score,Model Action,Hold Window,Why It Matters\n"
        "Some Fund,Elite value investor,BRK-B,Added shares,Filed 2026-05-15,filed yesterday,"
        "BUY NOW,100,Strong Buy & Hold,6-12 months,Value\n"
    )
    for tab, rows in (("spike", spike), ("etf", etf), ("smart money", smart)):
        found = {r["symbol"] for r in rows}
        assert found == {"BRK.B"}, f"the {tab} tab keyed Berkshire as {found}"


async def test_the_sheet_upsert_lands_on_the_vendor_row_and_creates_no_twin() -> None:
    """End to end: the workbook row updates the priced vendor row, and no
    second Berkshire is inserted. Mutation: the parser left on _clean_symbol."""
    async with session_scope() as s:
        s.add(Ticker(
            symbol="BRK.B", name="Berkshire Hathaway", sector="Financials",
            asset_class="equity", score=64.0, price=514.83, volume=2_479_063,
        ))

    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_all_signals("BRK-B")))

    async with session_scope() as s:
        found = {
            row.symbol: row
            for row in (await s.execute(
                select(Ticker).where(Ticker.symbol.in_(["BRK.B", "BRK-B"]))
            )).scalars().all()
        }
    assert set(found) == {"BRK.B"}, f"the sheet created a second Berkshire: {sorted(found)}"


async def test_a_workbook_carrying_both_spellings_updates_one_row() -> None:
    """If the workbook ever carries BRK-B and BRK.B together, both parse to
    BRK.B and one row is written, the later sheet row winning. Mutation: the
    parser left on _clean_symbol, which writes a BRK-B twin."""
    csv_text = (
        _ALL_SIGNALS_HEADER + "\n"
        + _all_signals_row("BRK-B", price="500.00")
        + _all_signals_row("BRK.B", price="514.83")
    )
    rows = parse_all_signals_csv(csv_text)
    assert [r["symbol"] for r in rows] == ["BRK.B", "BRK.B"]

    async with session_scope() as s:
        await upsert_tickers(s, rows)

    async with session_scope() as s:
        found = (await s.execute(
            select(Ticker.symbol, Ticker.price).where(Ticker.symbol.in_(["BRK.B", "BRK-B"]))
        )).all()
    assert [(sym, price) for sym, price in found] == [("BRK.B", 514.83)]


async def test_the_etf_tab_carrying_both_spellings_updates_one_row() -> None:
    """The ETF BENCHMARKS upsert is the other path that inserts rows. Mutation:
    dropping its per-call symbol map, which adds the same new key twice."""
    rows = parse_etf_benchmarks_csv(
        "Ticker,Name,unused,Note,Score,Signal,3M Return %,6M Return %,1Y Return %,Above 200DMA,"
        "Beats SPY (6M),vs SPY 6M %,Action\n"
        "BRK-B,Berkshire (hyphen),,Holding company,75,BUY NOW,5.2,11.4,18.3,TRUE,Yes,0.0,Hold\n"
        "BRK.B,Berkshire (dot),,Holding company,75,BUY NOW,5.2,11.4,18.3,TRUE,Yes,0.0,Hold\n"
    )
    assert [r["symbol"] for r in rows] == ["BRK.B", "BRK.B"]

    async with session_scope() as s:
        await upsert_etfs(s, rows)

    async with session_scope() as s:
        found = (await s.execute(
            select(Ticker.symbol, Ticker.name).where(Ticker.symbol.in_(["BRK.B", "BRK-B"]))
        )).all()
    assert [(sym, name) for sym, name in found] == [("BRK.B", "Berkshire (dot)")]
