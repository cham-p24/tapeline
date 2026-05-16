"""Sheet-driven ticker universe + composite scores.

The signal-system (separate project at C:\\signal-system\\) computes the
6-factor composite for a ~200-500 ticker universe and publishes the
result to a Google Sheet ("Live Dashboard - Stocks"). This module pulls
the **ALL SIGNALS** tab as Tapeline's canonical source of truth for:

  1. Which tickers exist in the universe (was hardcoded to 112 in
     mock_feed.TICKER_UNIVERSE; that miss is why HYLN went unscored
     despite being a +187% vs-SPY winner the signal-system flagged).
  2. The composite 0-100 score per ticker.
  3. The per-factor decomposition where the sheet exposes it (3M/6M/1Y
     returns, RS vs SPY, market regime).

Tapeline's own 6-factor formula in services/score.py becomes a
verification tool — same math as the sheet, useful for sanity-checking
that the sheet hasn't drifted. Live scoring is the sheet's job.

Configuration is via SIGNAL_SHEET_CSV_URL (a published-CSV URL for the
ALL SIGNALS tab). Without that env var, configured() returns False and
the worker falls back to mock_feed. The whole module is dormant until
the user publishes the sheet + sets the env var.

Why CSV-publish and not the Sheets API? It matches Tapeline's "public
formula, public scorecard" brand stance — the data IS public, so the
URL being public is consistent. For service-account auth instead, swap
fetch_csv() for a google-api-python-client call; the rest of the
pipeline doesn't change.

Refresh cadence is throttled by SIGNAL_SHEET_REFRESH_SECONDS (default
300s = 5 min). Below Google's public-CSV quota (~100 req/100s) and
fresh enough for a sheet the signal-system updates every few hours.
"""
from __future__ import annotations

import csv
import io
import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Ticker

logger = logging.getLogger(__name__)


# Tapeline's descriptive signal labels, mapped from the composite 0-100
# score using fixed bands. NEVER reuse the sheet's prescriptive column
# ("BUY NOW" / "ACCUMULATE" / "HOLD" / "WATCH" / "AVOID") — Tapeline's
# publisher-exemption posture requires descriptive language only. Even
# when the sheet says BUY NOW at score 100, Tapeline surfaces
# HIGH CONVICTION at the same score. Bands match /how-it-works copy
# and the existing services/score.score_to_signal() mapping.
_SIGNAL_BANDS: list[tuple[float, str]] = [
    (85.0, "HIGH CONVICTION"),
    (70.0, "STRONG SETUP"),
    (55.0, "CONSTRUCTIVE"),
    (40.0, "NEUTRAL"),
    (25.0, "CAUTION"),
    (0.0,  "WEAK"),
]


# Conviction grade from sheet → Tapeline confidence_pct mapping. The
# signal-system's letter grade collapses a basket of confidence signals
# (factor coverage, freshness, agreement across sub-scores) into a
# letter; Tapeline expresses the same idea as a percentile 0-100.
_CONVICTION_TO_CONFIDENCE: dict[str, float] = {
    "A+": 95.0,
    "A":  85.0,
    "B":  65.0,
    "C":  45.0,
    "D":  30.0,
    "F":  15.0,
}


def score_to_signal(score: float | None) -> str | None:
    """Map composite 0-100 to Tapeline's descriptive label.

    Public for use by other modules that need the same mapping (e.g. the
    /api/scanner endpoint when surfacing sheet-sourced rows alongside
    mock-feed rows). Returns None for None — caller decides whether
    that's a data-coverage gap or a freshly-onboarded ticker.
    """
    if score is None:
        return None
    for floor, label in _SIGNAL_BANDS:
        if score >= floor:
            return label
    return "WEAK"


def _parse_float(v: Any) -> float | None:
    """Coerce a sheet cell value to float or None.

    Sheets export numbers as their display string — so we strip commas,
    percent signs, leading + signs, and a handful of empty-cell tokens
    that show up in the BUY NOW EXECUTION LIST ("—", "-", ""). Returns
    None on any failure so the upsert path treats it as "no data" rather
    than crashing.
    """
    if v is None:
        return None
    s = str(v).strip()
    if not s or s in ("—", "-", "—%", "N/A", "n/a"):
        return None
    s = s.replace(",", "").replace("%", "")
    if s.startswith("+"):
        s = s[1:]
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def configured() -> bool:
    """True if SIGNAL_SHEET_CSV_URL is set. Callers short-circuit when False."""
    return bool(get_settings().signal_sheet_csv_url)


async def fetch_csv(url: str) -> str:
    """Pull the published-CSV content. Raises httpx.HTTPError on non-200.

    A 15s timeout covers a few-thousand-row sheet over reasonable
    bandwidth. The worker's tick runs in a try/except so a transient
    network blip drops one refresh cycle without taking down scoring.
    """
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        return r.text


def parse_all_signals_csv(text: str) -> list[dict[str, Any]]:
    """Parse the ALL SIGNALS tab CSV into normalized ticker dicts.

    Column order in the sheet (as of 2026-05-16):
      A Ticker, B Type, C Asset Class, D Strategy, E Conviction,
      F Score, G Raw Score, H Signal (sheet's prescriptive — discarded),
      I Verdict, J Action, K Hold Duration, L Price, M Above 200DMA,
      N Market Regime, O Beats SPY?, P Momentum Quality,
      Q 3M Return %, R 6M Return %, S 1Y Return %,
      T RS vs SPY 3M %, U RS vs SPY 6M %, V RS vs SPY 1Y %,
      W RS vs Sector 3M %, X Near 52W High %, ...

    Returns one dict per data row. Header row + any row missing a
    Ticker cell is filtered out so accidental blank rows or summary
    rows at the bottom of the sheet don't break the upsert.
    """
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for raw in reader:
        symbol = (raw.get("Ticker") or "").strip().upper()
        # Skip the header (if csv module didn't), blank rows, summary
        # rows like "TOTAL", and any row that doesn't look like a stock
        # ticker (a 1-5 letter all-caps string with optional .X suffix).
        if not symbol or symbol == "TICKER":
            continue
        if len(symbol) > 12:    # tickers are short; longer = junk
            continue

        score = _parse_float(raw.get("Score"))
        conviction = (raw.get("Conviction") or "").strip().upper()

        rows.append({
            "symbol":          symbol,
            "asset_class":     (raw.get("Asset Class") or "equity").strip().lower(),
            "score":           score,
            "signal":          score_to_signal(score),   # derived, descriptive
            "price":           _parse_float(raw.get("Price")),
            "conviction":      conviction,
            "confidence_pct":  _CONVICTION_TO_CONFIDENCE.get(conviction),
            "change_pct_3m":   _parse_float(raw.get("3M Return %")),
            "change_pct_6m":   _parse_float(raw.get("6M Return %")),
            "change_pct_1y":   _parse_float(raw.get("1Y Return %")),
            "rs_vs_spy_3m":    _parse_float(raw.get("RS vs SPY 3M %")),
            "rs_vs_spy_6m":    _parse_float(raw.get("RS vs SPY 6M %")),
            "rs_vs_spy_1y":    _parse_float(raw.get("RS vs SPY 1Y %")),
            "market_regime":   (raw.get("Market Regime") or "").strip(),
            "strategy":        (raw.get("Strategy") or "").strip(),
            "raw_score":       _parse_float(raw.get("Raw Score")),
        })
    return rows


def _approx_change_pct_1m(row: dict[str, Any]) -> float | None:
    """Tapeline's Ticker.change_pct_1m is a real 1-month price change.
    The sheet only publishes 3M/6M/1Y. As a usable proxy until per-tick
    snapshots fill the gap, return 3M / 3. Marked approximate in the
    code so a future precise feed can override.
    """
    m3 = row.get("change_pct_3m")
    if m3 is None:
        return None
    return m3 / 3.0


def _approx_sub_rs(row: dict[str, Any]) -> float | None:
    """Composite of RS-vs-SPY across timeframes into a 0-100 sub-score.

    Sheet exposes raw % outperformance vs SPY at 3M / 6M / 1Y. Tapeline's
    sub_rs is a 0-100 percentile-ish score. Quick proxy:
      - +50% outperformance at any window → 100
      -   0% outperformance              →  50
      - −50% underperformance            →   0
    Clamped to [0, 100]. Bias toward longer windows (1Y weighted 2x).
    """
    weights = [("rs_vs_spy_3m", 1.0), ("rs_vs_spy_6m", 1.5), ("rs_vs_spy_1y", 2.0)]
    total = 0.0
    weight = 0.0
    for key, w in weights:
        v = row.get(key)
        if v is None:
            continue
        # Map ±50% → ±50 score points around midpoint 50
        component = 50.0 + v
        total += w * component
        weight += w
    if weight == 0:
        return None
    avg = total / weight
    return max(0.0, min(100.0, avg))


async def upsert_tickers(
    session: AsyncSession, rows: list[dict[str, Any]]
) -> dict[str, int]:
    """Insert-or-update Ticker rows from sheet data.

    Maps the sheet's columns to the existing Ticker model:
      symbol           → symbol (key)
      score            → score
      derived signal   → signal (NOT the sheet's prescriptive column)
      price            → price
      ~3M return / 3   → change_pct_1m (approximation noted in code)
      RS-vs-SPY blend  → sub_rs
      conviction grade → confidence_pct (via _CONVICTION_TO_CONFIDENCE)

    Other Ticker columns (sub_trend, sub_fundamentals, sub_momentum,
    sub_macro, sub_smart_money, sector, name) are left alone for the
    existing flow to fill — _backfill_sectors handles sector, the
    Finnhub-driven fundamentals pre-fetch fills sub_fundamentals, etc.
    Phase 2 will wire SMART MONEY & CONGRESS into sub_smart_money and
    MARKET INTELLIGENCE into sub_macro from the same workbook.
    """
    inserted = updated = 0
    for r in rows:
        existing_q = await session.execute(
            select(Ticker).where(Ticker.symbol == r["symbol"])
        )
        t = existing_q.scalar_one_or_none()
        is_new = t is None
        if is_new:
            t = Ticker(
                symbol=r["symbol"],
                name=r["symbol"],          # placeholder; sector backfill names later
                asset_class=r["asset_class"] or "equity",
            )
            session.add(t)
            inserted += 1
        else:
            updated += 1

        t.score = r["score"]
        t.signal = r["signal"]
        t.price = r["price"]
        if r.get("confidence_pct") is not None:
            t.confidence_pct = r["confidence_pct"]
        # 1M approximated from 3M / 3 — leave existing change_pct_5d untouched
        m1_proxy = _approx_change_pct_1m(r)
        if m1_proxy is not None:
            t.change_pct_1m = m1_proxy
        rs = _approx_sub_rs(r)
        if rs is not None:
            t.sub_rs = rs

    await session.commit()
    return {"inserted": inserted, "updated": updated, "total": inserted + updated}


async def refresh_from_workbook(session: AsyncSession) -> dict[str, int]:
    """Top-level entrypoint for the worker tick: fetch + parse + upsert.

    Returns counts so the worker can log {inserted, updated, total} on
    successful refreshes and skip silently when the env var is unset.
    On any error (network, CSV parse, DB upsert) returns a result dict
    with `error=1` so the caller can log and proceed without crashing
    the tick.
    """
    if not configured():
        return {"inserted": 0, "updated": 0, "total": 0, "skipped": 1}
    url = get_settings().signal_sheet_csv_url
    try:
        text = await fetch_csv(url)
    except Exception:
        logger.exception("sheet_feed.fetch_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    try:
        rows = parse_all_signals_csv(text)
    except Exception:
        logger.exception("sheet_feed.parse_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    try:
        counts = await upsert_tickers(session, rows)
    except Exception:
        logger.exception("sheet_feed.upsert_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    logger.info(
        "sheet_feed.refreshed rows=%d ins=%d upd=%d",
        counts["total"], counts["inserted"], counts["updated"],
    )
    return counts


# =============================================================================
# Phase 2 — additional tabs (SPIKE / SMART MONEY & CONGRESS / MARKET / ETF)
# =============================================================================
# Each tab follows the same pattern as ALL SIGNALS: parse the CSV into
# normalized dicts, then upsert into the matching Tapeline table. Tab-level
# env vars (spike_intelligence_csv_url etc.) gate each independently so the
# user can light them up one at a time. RUN HEALTH is intentionally NOT
# pulled — user explicitly dropped it from Phase 2 scope.


# ---- SPIKE INTELLIGENCE -----------------------------------------------------

def parse_spike_intelligence_csv(text: str) -> list[dict[str, Any]]:
    """Parse the SPIKE INTELLIGENCE tab into normalized squeeze rows.

    Column order in the sheet (as of 2026-05-16):
      A ticker, B last, C move_bar_pc, D move_day_pc, E volume_multipl,
      F source, G (unused), H score, I signal, J last_timestamp,
      K snapshot_time, L yahoo_sym, M data_provid, N prev_bar,
      O day_open, P last_volume, Q data_age_minute, R data_status,
      S ref_price, T source_confidence, U decision_gate

    Maps to Tapeline's SqueezeSetup model:
      ticker            → symbol
      move_day_pc       → spike_score (clamped 0-100 from the absolute %)
      volume_multipl    → volume_multiple
      source_confidence → obv_trend (rough proxy; we strip the "(N/100)" suffix)
      decision_gate     → breakout_type
      source            → suggested_window (the tab classifies windows)
      decision_gate     → reason (verbatim)

    squeeze_days isn't in the sheet — the signal-system doesn't expose how
    many days a ticker has been in a tight range. We default to 0 and rely
    on Tapeline's own squeeze detection (services/squeeze.py) to fill that
    in for the tickers it independently flags.
    """
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for raw in reader:
        symbol = (raw.get("ticker") or "").strip().upper()
        if not symbol or symbol == "TICKER" or len(symbol) > 12:
            continue

        move_day = _parse_float(raw.get("move_day_pc"))
        # spike_score: absolute day move, clamped 0-100. A 5% move scores 50,
        # 10%+ scores 100. Direction is folded in via decision_gate text so
        # the spike_score itself measures intensity not direction.
        spike_score = None
        if move_day is not None:
            spike_score = max(0.0, min(100.0, abs(move_day) * 10.0))

        rows.append({
            "symbol":         symbol,
            "spike_score":    spike_score if spike_score is not None else 0.0,
            "squeeze_days":   0,           # not exposed by the sheet
            "volume_multiple": _parse_float(raw.get("volume_multipl")) or 1.0,
            "obv_trend":      _strip_confidence_suffix(raw.get("source_confidence")),
            "breakout_type":  _short(raw.get("decision_gate"), 40),
            "suggested_window": _short(raw.get("source"), 40) or "—",
            "reason":         _short(raw.get("decision_gate"), 300) or "Flagged by signal-system spike intelligence",
        })
    return rows


def _strip_confidence_suffix(v: Any) -> str:
    """The sheet's source_confidence is 'HIGH (88/100)' / 'TECHNICAL-LED (54/100)'.
    For SqueezeSetup.obv_trend (capped at String(20)) we strip the trailing
    score-in-parens and uppercase the prefix.
    """
    if not v:
        return "NEUTRAL"
    s = str(v).strip().upper()
    # Drop the "(N/100)" tail
    if "(" in s:
        s = s.split("(", 1)[0].strip()
    return s[:20] or "NEUTRAL"


def _short(v: Any, cap: int) -> str:
    """Truncate a sheet cell to fit a tight VARCHAR — same defensive pattern
    as news_feed.clip_news_row but inline because callers vary in cap."""
    if not v:
        return ""
    s = str(v).strip()
    return s[:cap]


async def upsert_spikes(
    session: AsyncSession, rows: list[dict[str, Any]]
) -> dict[str, int]:
    """Insert-or-update SqueezeSetup rows from sheet data.

    The sheet's SPIKE INTELLIGENCE is broader than Tapeline's previous
    squeeze detection — it catches movement-confirmed setups (volume +
    intraday range) in addition to compression-release squeezes. We let
    the sheet drive all of them; Tapeline's services/squeeze.py logic
    layers ON TOP via a separate symbol set, not overlapping.
    """
    from app.models import SqueezeSetup

    inserted = updated = 0
    for r in rows:
        existing = await session.execute(
            select(SqueezeSetup).where(SqueezeSetup.symbol == r["symbol"])
        )
        sq = existing.scalar_one_or_none()
        if sq is None:
            sq = SqueezeSetup(
                symbol=r["symbol"],
                spike_score=r["spike_score"],
                squeeze_days=r["squeeze_days"],
                volume_multiple=r["volume_multiple"],
                obv_trend=r["obv_trend"],
                breakout_type=r["breakout_type"],
                suggested_window=r["suggested_window"],
                reason=r["reason"],
            )
            session.add(sq)
            inserted += 1
        else:
            sq.spike_score = r["spike_score"]
            sq.volume_multiple = r["volume_multiple"]
            sq.obv_trend = r["obv_trend"]
            sq.breakout_type = r["breakout_type"]
            sq.suggested_window = r["suggested_window"]
            sq.reason = r["reason"]
            updated += 1

    await session.commit()
    return {"inserted": inserted, "updated": updated, "total": inserted + updated}


async def refresh_spikes_from_workbook(session: AsyncSession) -> dict[str, int]:
    """Entrypoint paralleling refresh_from_workbook for the SPIKE tab."""
    url = get_settings().spike_intelligence_csv_url
    if not url:
        return {"inserted": 0, "updated": 0, "total": 0, "skipped": 1}
    try:
        text = await fetch_csv(url)
    except Exception:
        logger.exception("sheet_feed.spike_fetch_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    try:
        rows = parse_spike_intelligence_csv(text)
    except Exception:
        logger.exception("sheet_feed.spike_parse_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    try:
        counts = await upsert_spikes(session, rows)
    except Exception:
        logger.exception("sheet_feed.spike_upsert_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    logger.info(
        "sheet_feed.spikes_refreshed rows=%d ins=%d upd=%d",
        counts["total"], counts["inserted"], counts["updated"],
    )
    return counts


# ---- ETF BENCHMARKS ---------------------------------------------------------

def parse_etf_benchmarks_csv(text: str) -> list[dict[str, Any]]:
    """Parse ETF BENCHMARKS tab.

    Column order (as of 2026-05-16):
      A Ticker, B Name, C (note continuation), D Note, E Score, F Signal,
      G 3M Return %, H 6M Return %, I 1Y Return %, J Above 200DMA,
      K Beats SPY (6M), L vs SPY 6M %, M Action

    Maps to the same Ticker schema as parse_all_signals_csv but with
    asset_class='etf'. Tapeline doesn't need a separate EtfBenchmark
    table — ETFs are tickers too, just with a different asset_class.
    The /signals public page already groups by signal tier so ETFs
    naturally surface alongside equities.

    Section-header rows (text in column A like "--- 3. INTERNATIONAL ---")
    + the "Not in scan" rows (score = 0, no real data) are filtered out
    so the upsert doesn't poison real ticker rows.
    """
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for raw in reader:
        symbol = (raw.get("Ticker") or "").strip().upper()
        if not symbol or symbol == "TICKER" or len(symbol) > 12:
            continue
        # Section headers have non-ticker-looking content
        if symbol.startswith("-") or symbol.startswith("="):
            continue

        signal_raw = (raw.get("Signal") or "").strip().upper()
        # Skip "Not in scan" — those are ETFs flagged by the sheet but
        # without real score data; upserting them would create junk rows.
        if signal_raw == "NOT IN SCAN" or not signal_raw:
            continue

        score = _parse_float(raw.get("Score"))
        rows.append({
            "symbol":         symbol,
            "name":           (raw.get("Name") or "").strip() or symbol,
            "asset_class":    "etf",
            "score":          score,
            "signal":         score_to_signal(score),   # descriptive labels
            "change_pct_3m":  _parse_float(raw.get("3M Return %")),
            "change_pct_6m":  _parse_float(raw.get("6M Return %")),
            "change_pct_1y":  _parse_float(raw.get("1Y Return %")),
            "vs_spy_6m":      _parse_float(raw.get("vs SPY 6M %")),
            "above_200dma":   (raw.get("Above 200DMA") or "").strip().upper() == "TRUE",
            "note":           _short(raw.get("Note"), 300),
            "sector":         _short(raw.get("Name"), 80),  # ETF "sector" = its theme name
        })
    return rows


async def upsert_etfs(
    session: AsyncSession, rows: list[dict[str, Any]]
) -> dict[str, int]:
    """Upsert ETF BENCHMARKS rows into Ticker table with asset_class='etf'.

    Reuses the same Ticker model as equities (no separate EtfBenchmark
    table). The /signals public page renders ETFs and equities in the
    same table; users can mentally filter by symbol shape (3-4 letter
    funds like SPY, VTI vs equity tickers) or via the future sector
    filter once asset_class is exposed to clients.
    """
    inserted = updated = 0
    for r in rows:
        existing_q = await session.execute(
            select(Ticker).where(Ticker.symbol == r["symbol"])
        )
        t = existing_q.scalar_one_or_none()
        if t is None:
            t = Ticker(
                symbol=r["symbol"],
                name=r["name"],
                asset_class="etf",
                sector=r["sector"],
            )
            session.add(t)
            inserted += 1
        else:
            # Don't downgrade asset_class — if a symbol exists as 'equity'
            # somehow (mock-feed seed) but the sheet flags it as ETF, the
            # sheet wins. The asset_class column was meant to distinguish.
            t.asset_class = "etf"
            t.name = r["name"]
            if r["sector"]:
                t.sector = r["sector"]
            updated += 1

        t.score = r["score"]
        t.signal = r["signal"]
        # 1M proxy from 3M / 3 (ETFs barely move intraday; coarser is fine)
        if r["change_pct_3m"] is not None:
            t.change_pct_1m = r["change_pct_3m"] / 3.0

    await session.commit()
    return {"inserted": inserted, "updated": updated, "total": inserted + updated}


async def refresh_etfs_from_workbook(session: AsyncSession) -> dict[str, int]:
    url = get_settings().etf_benchmarks_csv_url
    if not url:
        return {"inserted": 0, "updated": 0, "total": 0, "skipped": 1}
    try:
        text = await fetch_csv(url)
    except Exception:
        logger.exception("sheet_feed.etf_fetch_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    try:
        rows = parse_etf_benchmarks_csv(text)
    except Exception:
        logger.exception("sheet_feed.etf_parse_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    try:
        counts = await upsert_etfs(session, rows)
    except Exception:
        logger.exception("sheet_feed.etf_upsert_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    logger.info("sheet_feed.etfs_refreshed rows=%d ins=%d upd=%d",
                counts["total"], counts["inserted"], counts["updated"])
    return counts


# ---- MARKET INTELLIGENCE ----------------------------------------------------

def parse_market_intelligence_csv(text: str) -> dict[str, Any]:
    """Parse the MARKET INTELLIGENCE tab — key-value layout, not row-per-ticker.

    The sheet is a vertical dashboard of macro indicators. Column A is the
    indicator name; column B is the value (which may be a string with a
    number embedded, like 'STRONG BULL. VIX is 18.4...' or 'Fed funds is
    3.64%').

    We extract the values we know how to map to RegimeState columns:
      'Market mode'          → regime (extract BULL/NEUTRAL/CAUTIOUS/BEAR from value)
      'VIX Fear Index'       → vix
      'US Dollar Index (DXY)' → dxy
      '10Y Treasury Yield'   → yield_10y
      'Rates + inflation' or 'Fed Funds Rate' → rate_direction inference

    Returns a dict that upsert_market_regime can write to the single-row
    RegimeState table. Missing fields default to safe values so an
    incomplete sheet doesn't crash the upsert.
    """
    reader = csv.DictReader(io.StringIO(text))
    kv: dict[str, str] = {}
    for raw in reader:
        # The header is "Indicator / Field" + "Value / Details" + "Note"
        indicator = (raw.get("Indicator / Field") or "").strip()
        value = (raw.get("Value / Details") or "").strip()
        if not indicator or indicator.startswith("-"):
            continue
        kv[indicator] = value

    def _extract_number(s: str) -> float | None:
        """Pull the first float out of a free-form string."""
        import re
        m = re.search(r"-?\d+(?:\.\d+)?", s or "")
        if not m:
            return None
        try:
            return float(m.group(0))
        except ValueError:
            return None

    # Market mode — "STRONG BULL. VIX is 18.4..." → BULL
    mode = (kv.get("Market mode") or "").upper()
    if "BULL" in mode:
        regime = "BULL"
    elif "BEAR" in mode:
        regime = "BEAR"
    elif "CAUTIOUS" in mode or "CAUTION" in mode:
        regime = "CAUTIOUS"
    else:
        regime = "NEUTRAL"

    # Rate direction — derive from "Rates + inflation" or fall back to neutral
    rate_text = (kv.get("Rates + inflation") or "").lower()
    if "rising" in rate_text or "hik" in rate_text:
        rate_direction = "RISING"
    elif "fall" in rate_text or "cut" in rate_text:
        rate_direction = "FALLING"
    else:
        rate_direction = "SIDEWAYS"

    return {
        "regime":         regime,
        "vix":            _extract_number(kv.get("VIX Fear Index", "")) or 18.0,
        "dxy":            _extract_number(kv.get("US Dollar Index (DXY)", "")) or 100.0,
        "yield_10y":      _extract_number(kv.get("10Y Treasury Yield", "")) or 4.0,
        "rate_direction": rate_direction,
        # breadth_pct + sector_leaders aren't in the sheet — keep existing
        # values if a row exists, otherwise default.
        "breadth_pct_default":  50.0,
        "sector_leaders_default": "—",
    }


async def upsert_market_regime(session: AsyncSession, parsed: dict[str, Any]) -> dict[str, int]:
    """Update the single-row RegimeState table from the parsed sheet values."""
    from app.models import RegimeState

    existing = (await session.execute(select(RegimeState))).scalar_one_or_none()
    if existing is None:
        rs = RegimeState(
            id=1,
            regime=parsed["regime"],
            vix=parsed["vix"],
            dxy=parsed["dxy"],
            yield_10y=parsed["yield_10y"],
            rate_direction=parsed["rate_direction"],
            breadth_pct=parsed["breadth_pct_default"],
            sector_leaders=parsed["sector_leaders_default"],
        )
        session.add(rs)
        await session.commit()
        return {"inserted": 1, "updated": 0, "total": 1}

    existing.regime = parsed["regime"]
    existing.vix = parsed["vix"]
    existing.dxy = parsed["dxy"]
    existing.yield_10y = parsed["yield_10y"]
    existing.rate_direction = parsed["rate_direction"]
    await session.commit()
    return {"inserted": 0, "updated": 1, "total": 1}


async def refresh_market_from_workbook(session: AsyncSession) -> dict[str, int]:
    url = get_settings().market_intelligence_csv_url
    if not url:
        return {"inserted": 0, "updated": 0, "total": 0, "skipped": 1}
    try:
        text = await fetch_csv(url)
    except Exception:
        logger.exception("sheet_feed.market_fetch_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    try:
        parsed = parse_market_intelligence_csv(text)
    except Exception:
        logger.exception("sheet_feed.market_parse_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    try:
        counts = await upsert_market_regime(session, parsed)
    except Exception:
        logger.exception("sheet_feed.market_upsert_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    logger.info("sheet_feed.market_refreshed regime=%s vix=%.1f yield=%.2f rate=%s",
                parsed["regime"], parsed["vix"], parsed["yield_10y"], parsed["rate_direction"])
    return counts


# ---- SMART MONEY & CONGRESS -------------------------------------------------

def parse_smart_money_csv(text: str) -> list[dict[str, Any]]:
    """Parse SMART MONEY & CONGRESS rows into ticker boost signals.

    The tab has multiple categories of smart-money signal:
      - Congress STOCK Act trades (Nancy Pelosi, Josh Gottheimer, ...)
      - Committee × industry overlap conflicts
      - Elite hedge fund holdings (Coatue, Pershing Square, Appaloosa,
        Tiger Global, Duquesne, ...)
      - Elite 13F investor activity (Activist, macro, tech/growth)
      - SEC Form 4 insider buying (Corporate insiders / TICKER)

    Rather than try to parse each row's free-text "Recent Buy / Holding
    Signal" into a fully-typed CongressTrade or InsiderTransaction row
    (the sheet's data is descriptive, not structured), we **boost
    sub_smart_money** for tickers that appear in the tab. Multiple
    appearances mean stronger conviction across smart-money signals.

    Returns list of {symbol, signal_count, sub_smart_money_score} dicts.
    Score formula:
      base 60 + 10 per additional signal, capped at 100
      (1 signal = 60, 2 = 70, ..., 5+ = 100)
    """
    appearances: dict[str, int] = {}
    reader = csv.DictReader(io.StringIO(text))
    for raw in reader:
        symbol = (raw.get("Ticker") or "").strip().upper()
        category = (raw.get("Category") or "").strip()
        # Skip section headers, data-source explainers, blank rows
        if not symbol or symbol == "TICKER" or symbol == "—" or len(symbol) > 12:
            continue
        if "Section header" in category or "Data freshness" in category:
            continue
        appearances[symbol] = appearances.get(symbol, 0) + 1

    rows: list[dict[str, Any]] = []
    for symbol, n in appearances.items():
        score = min(100.0, 60.0 + (n - 1) * 10.0)
        rows.append({
            "symbol":   symbol,
            "signal_count":      n,
            "sub_smart_money":   score,
        })
    return rows


async def upsert_smart_money(
    session: AsyncSession, rows: list[dict[str, Any]]
) -> dict[str, int]:
    """Update Ticker.sub_smart_money for symbols flagged by the SMART MONEY tab.

    Only WRITES to sub_smart_money — leaves all other Ticker columns alone.
    If a symbol in the sheet doesn't exist in Ticker yet (rare — the
    universe is already broader after PR #52 lit up ALL SIGNALS), we skip
    it rather than insert a stub. The ALL SIGNALS feed is responsible
    for universe membership; SMART MONEY just enriches.
    """
    updated = skipped = 0
    for r in rows:
        existing_q = await session.execute(
            select(Ticker).where(Ticker.symbol == r["symbol"])
        )
        t = existing_q.scalar_one_or_none()
        if t is None:
            skipped += 1
            continue
        t.sub_smart_money = r["sub_smart_money"]
        updated += 1
    await session.commit()
    return {"inserted": 0, "updated": updated, "total": updated, "skipped": skipped}


async def refresh_smart_money_from_workbook(session: AsyncSession) -> dict[str, int]:
    url = get_settings().smart_money_congress_csv_url
    if not url:
        return {"inserted": 0, "updated": 0, "total": 0, "skipped": 1}
    try:
        text = await fetch_csv(url)
    except Exception:
        logger.exception("sheet_feed.smart_money_fetch_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    try:
        rows = parse_smart_money_csv(text)
    except Exception:
        logger.exception("sheet_feed.smart_money_parse_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    try:
        counts = await upsert_smart_money(session, rows)
    except Exception:
        logger.exception("sheet_feed.smart_money_upsert_failed")
        return {"inserted": 0, "updated": 0, "total": 0, "error": 1}
    logger.info("sheet_feed.smart_money_refreshed rows=%d", counts["total"])
    return counts
