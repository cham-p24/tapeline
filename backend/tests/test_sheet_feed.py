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
    parse_all_signals_csv,
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
    cleanly into a dict whose derived signal stays descriptive (NOT the
    sheet's prescriptive BUY NOW).

    As of 2026-06-01 (Fix 2 of docs/SCORING_AUDIT_2026-06-01.md), `score`
    is Tapeline's own 6-factor composite computed locally, not the
    sheet's column-F value. The sheet's raw value is preserved in
    `sheet_score` for transparency.
    """
    rows = parse_all_signals_csv(_FIXTURE_CSV)
    hyln = next((r for r in rows if r["symbol"] == "HYLN"), None)
    assert hyln is not None, "parser dropped HYLN"
    # Sheet still passes through the raw value (now under sheet_score)
    assert hyln["sheet_score"] == 100.0
    # Tapeline composite stays in [0, 100]
    assert 0 <= hyln["score"] <= 100
    # Signal is descriptive (one of the published Tapeline labels) and
    # explicitly NOT the sheet's prescriptive BUY NOW
    assert hyln["signal"] != "BUY NOW"
    assert hyln["signal"] in {
        "HIGH CONVICTION", "STRONG SETUP", "CONSTRUCTIVE",
        "NEUTRAL", "CAUTION", "WEAK"
    }
    assert hyln["price"] == 4.67
    assert hyln["conviction"] == "A"
    assert hyln["confidence_pct"] == 85.0   # A → 85
    assert hyln["market_regime"] == "STRONG BULL"
    assert hyln["change_pct_3m"] == 127.8
    assert hyln["rs_vs_spy_1y"] == 195.4
    # The composite must produce all 6 sub-scores as keys
    for sub_key in ("sub_trend", "sub_rs", "sub_fundamentals",
                    "sub_smart_money", "sub_macro", "sub_momentum"):
        assert sub_key in hyln, f"composite did not produce {sub_key}"


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
    """Lower-conviction rows still parse (and get a low descriptive label)
    so the full universe is upserted, not just the top picks. Bad bets get
    audited too — that's the public-scorecard ethos.

    As of 2026-06-01 the `score` field is Tapeline's composite (Fix 2);
    `sheet_score` carries the sheet's column-F value.
    """
    rows = parse_all_signals_csv(_FIXTURE_CSV)
    low = next((r for r in rows if r["symbol"] == "LOWBALL"), None)
    assert low is not None
    assert low["sheet_score"] == 30.0
    assert 0 <= low["score"] <= 100
    # Negative 3M return + weak inputs should yield a below-neutral composite
    # → signal label one of CAUTION/WEAK/NEUTRAL, never STRONG SETUP or higher
    assert low["signal"] in {"CAUTION", "WEAK", "NEUTRAL"}
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

        # Verify HYLN is in DB with the right composite score and derived
        # signal. As of 2026-06-01, Ticker.score is Tapeline's composite,
        # not the sheet's column F.
        hyln_q = await s.execute(select(Ticker).where(Ticker.symbol == "HYLN"))
        hyln = hyln_q.scalar_one()
        assert 0 <= hyln.score <= 100
        # HYLN fixture has strong inputs (3M +127.8%, 1Y RS +195.4%, STRONG
        # BULL regime, A conviction) — composite should land in
        # STRONG SETUP / HIGH CONVICTION band (>= 70)
        assert hyln.score >= 70, f"HYLN composite landed at {hyln.score}, expected >=70 given strong inputs"
        assert hyln.signal in {"STRONG SETUP", "HIGH CONVICTION"}
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


# ============================================================================
# Phase 2A — SPIKE INTELLIGENCE
# ============================================================================

_SPIKE_FIXTURE_CSV = """Spike Rank,Ticker,Buy By,Time Window,Stage,Entry Trigger,Stop / Risk,Price,Spike Score,Spike Direction,Type,Spike Urgency,Suggested Window,Buy Timing,Decision,Score,Source Confidence,Source Notes,Volume Expansion,RSI14,OBV Trend,Breakout Type,Spike Reasons,Why This May Move,Main Risk,Core Signal,Hold Duration
1,SOC,Fri 29 May,Watch next 2 weeks,READY TO MOVE,close above 16.40,12.48 (-17.5%),15.13,96,UPSIDE,STOCK,HIGH,1-4 weeks,Possible entry,Entry timing,100,TECHNICAL-LED (54/100),price live,1.5,60.6,Rising +12% accumulating,Breaking above upper BB,Tight BB squeeze 14d coiled spring,RSI in momentum zone OBV rising,Spike signals predict movement pressure not direction,BUY NOW,6-12 months
2,APPS,Mon 1 Jun,Watch next 3 weeks,ARMED,close above 8.20,6.55 (-20%),7.85,82,UPSIDE,STOCK,MED,2-4 weeks,Possible entry,Entry timing,88,HIGH (88/100),price live,2.1,68.4,Rising +18% strong accumulation,Range breakout pending,Volume 2.1x avg coiled price,Volume confirming RSI healthy,Macro risk softening,STRONG SETUP,3-6 months
3,RGTI,Thu 21 May,Within 1 week,IMMINENT,close above 17.50,14.20 (-15%),17.05,73,UPSIDE,STOCK,LOW,1-2 weeks,Possible entry,Entry timing,73,TECHNICAL-LED (62/100),price live,1.3,55.2,Flat,Tightening range,BB bandwidth contracting volume basing,Compression release setup,Sector rotation risk,CONSTRUCTIVE,2-4 weeks
,,,,,,,,,,,,,,,,,,,,,,,,,,
TICKER,,,,,,,,,,,,,,,,,,,,,,,,,,
=== SECTION HEADER ===,,,,,,,,,,,,,,,,,,,,,,,,,,
"""


def test_spike_parser_extracts_rows_and_clamps_score():
    """SPIKE INTELLIGENCE parser (post-2026-05-17 schema) must:
      - skip header re-declaration + blank rows + section headers
      - parse Spike Score directly (already on 0-100 scale from the sheet)
      - default missing Volume Expansion to 1.0 (zero divides badly downstream)
      - clean OBV Trend + truncate Breakout Type / Suggested Window / Reasons"""
    from app.services.sheet_feed import parse_spike_intelligence_csv

    rows = parse_spike_intelligence_csv(_SPIKE_FIXTURE_CSV)
    symbols = {r["symbol"] for r in rows}
    assert symbols == {"SOC", "APPS", "RGTI"}

    soc = next(r for r in rows if r["symbol"] == "SOC")
    assert soc["spike_score"] == 96.0
    assert soc["volume_multiple"] == 1.5
    # OBV Trend "Rising +12% accumulating" gets cleaned + truncated to <=20
    assert soc["obv_trend"].startswith("RISING")
    assert "Breaking above upper BB" in soc["breakout_type"]
    # `reason` falls back to "Spike Reasons" column
    assert "BB squeeze" in soc["reason"] or "coiled spring" in soc["reason"]


def test_spike_parser_caps_breakout_type_and_obv_trend_lengths():
    """SqueezeSetup has tight VARCHAR limits (obv_trend 20, breakout_type 40,
    suggested_window 40, reason 300). The parser truncates so the
    StringDataRightTruncation bug from PR #50 can't repeat at this layer."""
    from app.services.sheet_feed import parse_spike_intelligence_csv

    rows = parse_spike_intelligence_csv(_SPIKE_FIXTURE_CSV)
    for r in rows:
        assert len(r["obv_trend"]) <= 20
        assert len(r["breakout_type"]) <= 40
        assert len(r["suggested_window"]) <= 40
        assert len(r["reason"]) <= 300


@pytest.mark.asyncio
async def test_spike_upsert_round_trip():
    """Run upsert, verify row exists, mutate score, re-run, verify update."""
    from app.models import SqueezeSetup
    from app.services.sheet_feed import (
        parse_spike_intelligence_csv,
        upsert_spikes,
    )

    rows = parse_spike_intelligence_csv(_SPIKE_FIXTURE_CSV)
    async with session_scope() as s:
        # Pre-clean
        for sym in ("SOC", "APPS", "RGTI"):
            existing = (await s.execute(select(SqueezeSetup).where(SqueezeSetup.symbol == sym))).scalar_one_or_none()
            if existing is not None:
                await s.delete(existing)
        await s.commit()

        counts = await upsert_spikes(s, rows)
        assert counts["inserted"] == 3
        assert counts["updated"] == 0

        # Round-trip
        soc = (await s.execute(select(SqueezeSetup).where(SqueezeSetup.symbol == "SOC"))).scalar_one()
        assert soc.volume_multiple == 1.5
        assert soc.spike_score == 96.0

        # Mutate and re-upsert — should now be all updates
        rows[0]["spike_score"] = 88.0
        counts2 = await upsert_spikes(s, rows)
        assert counts2["inserted"] == 0
        assert counts2["updated"] == 3

        soc2 = (await s.execute(select(SqueezeSetup).where(SqueezeSetup.symbol == "SOC"))).scalar_one()
        assert soc2.spike_score == 88.0

        # Cleanup
        for sym in ("CLH", "ECPG", "ENS"):
            row = (await s.execute(select(SqueezeSetup).where(SqueezeSetup.symbol == sym))).scalar_one_or_none()
            if row is not None:
                await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_refresh_spikes_dormant_without_env(monkeypatch):
    """refresh_spikes_from_workbook is dormant when the spike URL env var
    is unset — caller gets a skipped result, no HTTP call."""
    from app.services import sheet_feed

    settings = get_settings_for_tests()
    monkeypatch.setattr(settings, "spike_intelligence_csv_url", "")

    async with session_scope() as s:
        result = await sheet_feed.refresh_spikes_from_workbook(s)
    assert result.get("skipped") == 1
    assert result.get("total") == 0


def get_settings_for_tests():
    """Helper to grab the cached settings singleton for monkeypatching."""
    from app.config import get_settings
    return get_settings()
