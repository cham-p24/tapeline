"""Tests for the signal-system sheet feed.

Covers the parser, upsert, label-derivation, and the dormant-when-unset
guard. Doesn't make real HTTP calls — Google Sheets CSV format is well
defined and we test against representative fixtures.

The HYLN regression case is asserted directly: a sheet row with HYLN +
score 100 + Strong Bull regime must result in a Ticker row with score=100
and signal="HIGH CONVICTION" — proving the user's flagship "HYLN should
have been scored" complaint is closed.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import session_scope
from app.models import Ticker
from app.services.sheet_feed import (
    _parse_float,
    configured,
    parse_all_signals_csv,
    refresh_from_workbook,
    score_to_signal,
    upsert_tickers,
)


# ---- score_to_signal --------------------------------------------------------

def test_score_to_signal_bands_match_brand_voice():
    """The mapping must hit Tapeline's descriptive labels at the exact
    band boundaries from /how-it-works. NEVER reproduce sheet's
    prescriptive labels (BUY NOW / ACCUMULATE / HOLD / WATCH / AVOID)."""
    assert score_to_signal(100) == "HIGH CONVICTION"
    assert score_to_signal(85)  == "HIGH CONVICTION"
    assert score_to_signal(84.9) == "STRONG SETUP"
    assert score_to_signal(70)  == "STRONG SETUP"
    assert score_to_signal(69.9) == "CONSTRUCTIVE"
    assert score_to_signal(55)  == "CONSTRUCTIVE"
    assert score_to_signal(54.9) == "NEUTRAL"
    assert score_to_signal(40)  == "NEUTRAL"
    assert score_to_signal(39.9) == "CAUTION"
    assert score_to_signal(25)  == "CAUTION"
    assert score_to_signal(24.9) == "WEAK"
    assert score_to_signal(0)   == "WEAK"


def test_score_to_signal_none_returns_none():
    """None score → None signal (downstream renders this as 'no coverage'
    rather than a default WEAK label)."""
    assert score_to_signal(None) is None


def test_score_to_signal_never_produces_buy_now():
    """Regression guard: the sheet's prescriptive labels must not leak
    into Tapeline through this mapping. Sweep the full 0-100 range and
    assert no banned label."""
    banned = {"BUY NOW", "ACCUMULATE", "HOLD", "WATCH", "AVOID", "BUY", "SELL"}
    for i in range(0, 101):
        label = score_to_signal(float(i))
        assert label not in banned, f"score={i} produced banned label {label}"


# ---- _parse_float -----------------------------------------------------------

def test_parse_float_handles_sheet_quirks():
    """Sheets exports are display strings: commas, percent signs, dashes
    for blanks, leading + signs. parse_float must normalise all of them."""
    assert _parse_float("1,234.5") == 1234.5
    assert _parse_float("+12.5%") == 12.5
    assert _parse_float("-7.5%") == -7.5
    assert _parse_float("100") == 100.0
    assert _parse_float("") is None
    assert _parse_float("—") is None
    assert _parse_float("-") is None
    assert _parse_float("N/A") is None
    assert _parse_float(None) is None
    # Genuinely garbage strings: don't crash, just return None
    assert _parse_float("not a number") is None


# ---- parse_all_signals_csv --------------------------------------------------

_FIXTURE_CSV = """Ticker,Type,Asset Class,Strategy,Conviction,Score,Raw Score,Signal,Verdict,Action,Hold Duration,Price,Above 200DMA,Market Regime,Beats SPY?,Momentum Quality,3M Return %,6M Return %,1Y Return %,RS vs SPY 3M %,RS vs SPY 6M %,RS vs SPY 1Y %,RS vs Sector 3M %,Near 52W High %
HYLN,STOCK,Stock,MOMENTUM,A,100,119,BUY NOW,Strong Buy,Strong Buy & Hold,6-12 months,4.67,TRUE,STRONG BULL,Yes (+187.4%),All 3 positive,127.8,178,222.1,119.3,187.4,195.4,,
OXY,STOCK,Stock,MOMENTUM A+,A+,100,142,BUY NOW,Strong Buy,Strong Buy & Hold,6-12 months,59.62,TRUE,STRONG BULL,Yes (+32.8%),All 3 positive,30.4,43.4,40.4,21.9,32.8,13.8,19.1,99.5
,,,,,,,,,,,,,,,,,,,,,,,
TICKER,,,,,,,,,,,,,,,,,,,,,,,
GS,STOCK,Stock,MOMENTUM,A+,100,121,BUY NOW,Strong Buy,Strong Buy & Hold,6-12 months,948.47,TRUE,STRONG BULL,Yes (+8.3%),All 3 positive,,,,,,,,
LOWBALL,STOCK,Stock,MOMENTUM,B,30,42,WATCH,Weak,Watch,12+ months,12.5,FALSE,NEUTRAL,No (-5%),Mixed,-10,5,2,-15,-3,-1,,
"""


def test_parser_extracts_hyln_row():
    """The HYLN regression: the test that asserts the user's flagship
    complaint is closed. Sheet row with HYLN + score 100 must parse
    cleanly into a dict whose derived signal is HIGH CONVICTION (NOT the
    sheet's prescriptive BUY NOW)."""
    rows = parse_all_signals_csv(_FIXTURE_CSV)
    hyln = next((r for r in rows if r["symbol"] == "HYLN"), None)
    assert hyln is not None, "parser dropped HYLN"
    assert hyln["score"] == 100.0
    assert hyln["signal"] == "HIGH CONVICTION"
    assert hyln["signal"] != "BUY NOW"   # explicitly NOT the sheet's label
    assert hyln["price"] == 4.67
    assert hyln["conviction"] == "A"
    assert hyln["confidence_pct"] == 85.0   # A → 85
    assert hyln["market_regime"] == "STRONG BULL"
    assert hyln["change_pct_3m"] == 127.8
    assert hyln["rs_vs_spy_1y"] == 195.4


def test_parser_skips_blank_and_repeated_header_rows():
    """Two filter cases: blank Ticker cell (the empty row in the fixture)
    and a re-declared header somewhere in the middle (the 'TICKER' row).
    Neither should appear in the output. Counting: HYLN + OXY + GS +
    LOWBALL = 4 keepers."""
    rows = parse_all_signals_csv(_FIXTURE_CSV)
    assert len(rows) == 4
    symbols = {r["symbol"] for r in rows}
    assert symbols == {"HYLN", "OXY", "GS", "LOWBALL"}


def test_parser_handles_low_score_rows():
    """Lower-conviction rows still parse (and get the WEAK label) so the
    full universe is upserted, not just the top picks. Bad bets get
    audited too — that's the public-scorecard ethos."""
    rows = parse_all_signals_csv(_FIXTURE_CSV)
    low = next((r for r in rows if r["symbol"] == "LOWBALL"), None)
    assert low is not None
    assert low["score"] == 30.0
    assert low["signal"] == "CAUTION"
    assert low["change_pct_3m"] == -10.0


# ---- configured() -----------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_is_dormant_without_env(monkeypatch):
    """If SIGNAL_SHEET_CSV_URL is unset, refresh_from_workbook returns a
    skipped result without making any HTTP call or DB write. This is the
    fall-back-to-mock-feed path that protects environments where the
    sheet hasn't been published yet."""
    from app.services import sheet_feed

    fake_settings_url = ""
    # Patch the config lookup to simulate "url not set"
    from app.config import get_settings as _real_settings
    settings = _real_settings()
    monkeypatch.setattr(settings, "signal_sheet_csv_url", fake_settings_url)

    assert sheet_feed.configured() is False

    async with session_scope() as s:
        result = await sheet_feed.refresh_from_workbook(s)
    assert result == {"inserted": 0, "updated": 0, "total": 0, "skipped": 1}


# ---- upsert -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_inserts_new_and_updates_existing():
    """Fresh symbol → new Ticker row. Re-running the upsert with the
    same symbol but a changed score → no duplicate, just an update."""
    rows = parse_all_signals_csv(_FIXTURE_CSV)
    async with session_scope() as s:
        # Pre-clean: remove HYLN if it exists from prior tests
        existing = await s.execute(select(Ticker).where(Ticker.symbol == "HYLN"))
        for t in existing.scalars().all():
            await s.delete(t)
        await s.commit()

        # First run: HYLN doesn't exist → inserted
        counts1 = await upsert_tickers(s, rows)
        assert counts1["total"] == 4

        # Verify HYLN is in DB with the right score and derived signal
        hyln_q = await s.execute(select(Ticker).where(Ticker.symbol == "HYLN"))
        hyln = hyln_q.scalar_one()
        assert hyln.score == 100.0
        assert hyln.signal == "HIGH CONVICTION"
        assert hyln.price == 4.67
        assert hyln.confidence_pct == 85.0   # A grade

        # Second run with mutated score: should update, not insert
        rows[0]["score"] = 75.0
        rows[0]["signal"] = score_to_signal(75.0)
        counts2 = await upsert_tickers(s, rows)
        assert counts2["inserted"] == 0
        assert counts2["updated"] == 4

        hyln_q2 = await s.execute(select(Ticker).where(Ticker.symbol == "HYLN"))
        hyln2 = hyln_q2.scalar_one()
        assert hyln2.score == 75.0
        assert hyln2.signal == "STRONG SETUP"  # band changed: 75 → STRONG SETUP

        # Cleanup
        for sym in ("HYLN", "OXY", "GS", "LOWBALL"):
            row = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
        await s.commit()
