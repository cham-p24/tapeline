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
