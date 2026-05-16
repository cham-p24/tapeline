"""Phase 2B/2C/2D — ETF BENCHMARKS, MARKET INTELLIGENCE, SMART MONEY tests.

Mirrors test_sheet_feed.py's pattern: parser fixtures + upsert round-trips
+ dormant-when-unset guards. Kept in a separate file so the original
sheet_feed test suite stays focused on the universe + SPIKE tabs.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import session_scope
from app.models import RegimeState, Ticker


# ============================================================================
# ETF BENCHMARKS — parser + upsert
# ============================================================================

_ETF_FIXTURE_CSV = """Ticker,Name,unused,Note,Score,Signal,3M Return %,6M Return %,1Y Return %,Above 200DMA,Beats SPY (6M),vs SPY 6M %,Action
SPY,SPDR S&P 500,,Broad US large-cap,75,BUY NOW,5.2,11.4,18.3,TRUE,Yes,0.0,Strong Buy & Hold
VTI,Vanguard Total Stock,,Total US market,73,BUY NOW,5.5,11.9,19.1,TRUE,Yes (+0.5%),0.5,Strong Buy & Hold
TLT,iShares 20+Y Treasury,,Long-duration govt — rate play,8,WATCH,-5.9,-4.3,1.6,FALSE,No (-14.9%),-14.9,Avoid
EFA,iShares MSCI EAFE,,Developed ex-US (EAFE),0,Not in scan,,,,FALSE,—,—,—
,,,,,,,,,,,,
TICKER,,,,,,,,,,,,
"""


def test_parse_etfs_skips_not_in_scan_and_headers():
    """ETF parser must:
      - skip 'Not in scan' rows (no real data → no upsert)
      - skip header re-declaration + blank rows
      - mark valid ETFs with asset_class='etf'"""
    from app.services.sheet_feed import parse_etf_benchmarks_csv

    rows = parse_etf_benchmarks_csv(_ETF_FIXTURE_CSV)
    symbols = {r["symbol"] for r in rows}
    assert symbols == {"SPY", "VTI", "TLT"}
    for r in rows:
        assert r["asset_class"] == "etf"


def test_parse_etfs_derives_descriptive_signal():
    """Sheet's 'BUY NOW' / 'WATCH' / 'AVOID' columns must NEVER appear in
    the parsed row's `signal` field — only descriptive labels per the
    score band. Same publisher-exemption stance as the equity parser."""
    from app.services.sheet_feed import parse_etf_benchmarks_csv

    rows = parse_etf_benchmarks_csv(_ETF_FIXTURE_CSV)
    spy = next(r for r in rows if r["symbol"] == "SPY")
    assert spy["score"] == 75.0
    assert spy["signal"] == "STRONG SETUP"   # 75 → STRONG SETUP per bands
    assert spy["signal"] != "BUY NOW"

    tlt = next(r for r in rows if r["symbol"] == "TLT")
    assert tlt["signal"] == "WEAK"           # 8 → WEAK
    assert tlt["signal"] != "WATCH"


@pytest.mark.asyncio
async def test_upsert_etfs_marks_asset_class_etf():
    """The ETF upsert path writes asset_class='etf' on every row, even if
    a Ticker with the same symbol exists from the equity feed (the sheet
    is authoritative on asset class)."""
    from app.services.sheet_feed import parse_etf_benchmarks_csv, upsert_etfs

    rows = parse_etf_benchmarks_csv(_ETF_FIXTURE_CSV)
    async with session_scope() as s:
        # Pre-clean
        for sym in ("SPY", "VTI", "TLT"):
            existing = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one_or_none()
            if existing is not None:
                await s.delete(existing)
        await s.commit()

        counts = await upsert_etfs(s, rows)
        assert counts["total"] == 3

        for sym in ("SPY", "VTI", "TLT"):
            t = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one()
            assert t.asset_class == "etf"

        # Cleanup
        for sym in ("SPY", "VTI", "TLT"):
            t = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one_or_none()
            if t is not None:
                await s.delete(t)
        await s.commit()


# ============================================================================
# MARKET INTELLIGENCE — kv parser + RegimeState upsert
# ============================================================================

_MARKET_FIXTURE_CSV = """Indicator / Field,Value / Details,Note
--- HOW TO READ THE WORKBOOK ---,,
Market mode,"STRONG BULL. VIX is 18.4, which means the market is not currently pricing panic.",controls aggression
Oil + geopolitical risk,Oil is about $105 and GPR is CAUTIOUS,
Rates + inflation,Fed funds is 3.64%; CPI YoY is 3.95%. Rates moderate,
--- MACRO & GEOPOLITICAL ---,,
Fed Funds Rate,Fed Funds Rate,3.64
10Y Treasury Yield,10Y Treasury Yield,4.47
VIX Fear Index,VIX Fear Index,18.4
US Dollar Index (DXY),US Dollar Index (DXY),99.27
"""


def test_parse_market_extracts_regime_and_macro():
    """Parser collapses the vertical KV layout into a single dict that
    matches RegimeState columns. 'STRONG BULL' → regime=BULL; numeric
    macro values pulled from the free-text 'Value / Details' cells."""
    from app.services.sheet_feed import parse_market_intelligence_csv

    parsed = parse_market_intelligence_csv(_MARKET_FIXTURE_CSV)
    assert parsed["regime"] == "BULL"
    assert parsed["vix"] == 18.4
    assert parsed["yield_10y"] == 4.47
    assert parsed["dxy"] == 99.27
    # rate_direction is derived from text — "moderate" → SIDEWAYS (default)
    assert parsed["rate_direction"] in ("SIDEWAYS", "RISING", "FALLING")


@pytest.mark.asyncio
async def test_upsert_market_regime_single_row():
    """RegimeState is a single-row table (id=1). Running the upsert
    twice with different parsed values must update the same row, not
    create a second one."""
    from app.services.sheet_feed import (
        parse_market_intelligence_csv,
        upsert_market_regime,
    )

    parsed = parse_market_intelligence_csv(_MARKET_FIXTURE_CSV)

    async with session_scope() as s:
        # Clear any prior state so the test is deterministic
        existing = (await s.execute(select(RegimeState))).scalar_one_or_none()
        if existing is not None:
            await s.delete(existing)
            await s.commit()

        counts1 = await upsert_market_regime(s, parsed)
        assert counts1["total"] == 1

        rs = (await s.execute(select(RegimeState))).scalar_one()
        assert rs.regime == "BULL"
        assert rs.vix == 18.4

        # Mutate parsed values, re-upsert; expect update not insert
        parsed["regime"] = "BEAR"
        parsed["vix"] = 28.5
        counts2 = await upsert_market_regime(s, parsed)
        assert counts2["updated"] == 1
        assert counts2["inserted"] == 0

        rs2 = (await s.execute(select(RegimeState))).scalar_one()
        assert rs2.regime == "BEAR"
        assert rs2.vix == 28.5

        # Cleanup
        await s.delete(rs2)
        await s.commit()


# ============================================================================
# SMART MONEY & CONGRESS — appearance-count → sub_smart_money boost
# ============================================================================

_SMART_FIXTURE_CSV = """Watcher / Buyer,Category,Ticker,Recent Buy / Holding Signal,Filing / Period,Filed,Current Model Sign,Model Score,Model Action,Hold Window,Why It Matters
DATA SOURCES THIS RUN,Data freshness explainer,—,"Quiver live...",,,,,,
=== SECTION ===,Section header,—,"Headers...",,,,,,
Conflict: Nancy Pelosi,Committee × industry overlap,GOOGL,500001.0 on 2026-01-16,Commerce Committee,,BUY NOW,100,Strong Buy & Hold,6-12 months,Political trade
Congress / Josh Gottheimer,Congress STOCK Act,GEV,Buy 1001.0,,2026-02-04 filed 100d ago,BUY NOW,100,Strong Buy & Hold,6-12 months,Political trade
Coatue / Philippe Laffont,Elite tech/growth investor,TSM,Top new position about $2.62B,Filed 2026-05-15,filed yesterday,BUY NOW,100,Strong Buy & Hold,6-12 months,AI supply-chain
Coatue / Philippe Laffont,Elite tech/growth investor,GOOGL,Added shares,Filed 2026-05-15,filed yesterday,BUY NOW,100,Strong Buy & Hold,6-12 months,Tech rotation
Tiger Global / Chase Coleman,Elite tech/growth investor,TSM,Large new stake,Filed 2026-05-15,filed yesterday,BUY NOW,100,Strong Buy & Hold,6-12 months,Semiconductor
"""


def test_parse_smart_money_counts_appearances():
    """Each ticker should appear once per category. TSM has 2 signals
    (Coatue + Tiger Global) → score = 70 (base 60 + 10). GOOGL has 2
    signals (Pelosi committee + Coatue) → score = 70. GEV has 1
    → score = 60. Section headers + data-source explainers filtered out."""
    from app.services.sheet_feed import parse_smart_money_csv

    rows = parse_smart_money_csv(_SMART_FIXTURE_CSV)
    by_symbol = {r["symbol"]: r for r in rows}
    assert set(by_symbol.keys()) == {"GOOGL", "GEV", "TSM"}

    assert by_symbol["TSM"]["signal_count"] == 2
    assert by_symbol["TSM"]["sub_smart_money"] == 70.0

    assert by_symbol["GOOGL"]["signal_count"] == 2
    assert by_symbol["GOOGL"]["sub_smart_money"] == 70.0

    assert by_symbol["GEV"]["signal_count"] == 1
    assert by_symbol["GEV"]["sub_smart_money"] == 60.0


def test_parse_smart_money_caps_score_at_100():
    """Five signals → 60 + 4*10 = 100. Six signals also = 100 (capped)."""
    csv = "Ticker,Category\n" + "\n".join([f"AAPL,Elite hedge fund investor"] * 7)
    csv = "Watcher / Buyer,Category,Ticker,Recent Buy / Holding Signal,Filing / Period,Filed,Current Model Sign,Model Score,Model Action,Hold Window,Why It Matters\n" + "\n".join([
        ",Elite hedge fund investor,AAPL,Buy,,,BUY NOW,100,Strong Buy,6-12,test"
    ] * 7)
    from app.services.sheet_feed import parse_smart_money_csv
    rows = parse_smart_money_csv(csv)
    aapl = next(r for r in rows if r["symbol"] == "AAPL")
    assert aapl["signal_count"] == 7
    assert aapl["sub_smart_money"] == 100.0


@pytest.mark.asyncio
async def test_upsert_smart_money_skips_unknown_tickers():
    """Smart-money upsert only writes to Ticker rows that ALREADY exist
    (universe membership is owned by the ALL SIGNALS feed). Missing
    symbols are counted as skipped, not inserted as stubs."""
    from app.services.sheet_feed import (
        parse_smart_money_csv,
        upsert_smart_money,
    )

    async with session_scope() as s:
        # Seed one known ticker, leave GEV/GOOGL absent so the test
        # exercises the skip path
        existing = (await s.execute(select(Ticker).where(Ticker.symbol == "TSM"))).scalar_one_or_none()
        if existing is not None:
            await s.delete(existing)
        await s.commit()

        s.add(Ticker(symbol="TSM", name="Taiwan Semi", asset_class="equity", score=92.0, signal="HIGH CONVICTION"))
        await s.commit()

        rows = parse_smart_money_csv(_SMART_FIXTURE_CSV)
        counts = await upsert_smart_money(s, rows)
        # TSM is in DB → updated. GOOGL + GEV aren't → skipped.
        assert counts["updated"] == 1
        assert counts["skipped"] == 2

        tsm = (await s.execute(select(Ticker).where(Ticker.symbol == "TSM"))).scalar_one()
        assert tsm.sub_smart_money == 70.0

        # Cleanup
        await s.delete(tsm)
        await s.commit()
