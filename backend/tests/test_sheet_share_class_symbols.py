"""A class share from the workbook must land on the row the vendor prices.

MEASURED IN PRODUCTION, 2026-09-14 (read-only SQL and page fetches)
------------------------------------------------------------------
* BRK.A and BRK.B - the vendor's spelling, created by discovery - were scored
  and priced live (BRK.B $514.83).
* BRK-A and BRK-B - the workbook's Yahoo-style spelling - were SEPARATE rows:
  scored (61.4 / 61.3), no price, no daily move. The vendor never answers for
  the hyphen form, so each minute's snapshot wrote price NULL. The sheet
  upsert writes the sheet's price on every sheet change, so the two writers
  flipped the price back and forth.
* /t/BRK-B rendered "BRK-B Stock Score" with a dash for a price. The sitemap
  lists only BRK.A and BRK.B.
* Non-crypto symbol shapes: 11,774 plain, 26 dotted, 10 dot-PR, and exactly
  two hyphenated - both Berkshire.

The workbook's class shares are now spelled the vendor's way at the parse, on
all four tabs that read a Ticker cell. The two existing hyphen rows are left
exactly as they are; retiring or merging them is a production data change for
the founder to decide.
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
    upsert_tickers,
)

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

_ALL_SIGNALS_HEADER = (
    "Ticker,Type,Asset Class,Strategy,Conviction,Score,Raw Score,Signal,Verdict,Action,"
    "Hold Duration,Price,Above 200DMA,Market Regime,Beats SPY?,Momentum Quality,"
    "3M Return %,6M Return %,1Y Return %,RS vs SPY 3M %,RS vs SPY 6M %,RS vs SPY 1Y %,"
    "RS vs Sector 3M %,Near 52W High %"
)


def _all_signals(ticker: str) -> str:
    return (
        _ALL_SIGNALS_HEADER + "\n"
        f"{ticker},STOCK,Stock,QUALITY,A,72,90,ACCUMULATE,Buy,Accumulate,6-12 months,"
        "514.83,TRUE,BULL,Yes (+3.1%),All 3 positive,4.2,9.8,18.1,1.2,3.1,2.4,1.0,96.5\n"
    )


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
])
def test_everything_else_is_left_alone(unchanged: str) -> None:
    """Only a one-letter class after one to five letters is a class share.
    Mutations: widening the suffix (ABCD-WS, a warrant-style suffix, would be
    rewritten into a symbol that does not exist); widening the root."""
    assert symbols.vendor_share_class_symbol(unchanged) == unchanged


def test_the_serving_path_still_resolves_the_existing_row() -> None:
    """/t/BRK-B keeps finding the row that exists until someone decides to
    retire it. Mutation: mapping inside clean_symbol, which every router uses."""
    assert symbols.clean_symbol("BRK-B") == "BRK-B"


def test_the_all_signals_tab_keys_berkshire_by_the_vendor_symbol() -> None:
    """The regression. Mutation: the parser calling _clean_symbol directly."""
    rows = parse_all_signals_csv(_all_signals("BRK-B"))
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
