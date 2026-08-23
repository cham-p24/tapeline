"""
IPO + earnings calendar data.

Production path: Finnhub `/calendar/ipo` and `/calendar/earnings` endpoints
(free tier covers Tapeline). Dev path: synthesized data so UI works without
a Finnhub key.

Use `upcoming_ipos()` / `upcoming_earnings()` as the canonical entry points —
they try Finnhub first and fall back to the mock generators when no key is set.
"""
from __future__ import annotations

import contextlib
import logging
import random
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def _is_production() -> bool:
    """Mirrors signal_publisher._mock_writes_enabled(), inverted."""
    from app.config import get_settings

    return get_settings().app_env == "production"


# Handful of real upcoming-IPO style names for dev mode (fake dates)
_IPO_SAMPLE = [
    ("STRP", "Stripe Inc.", "Financials", "NYSE", 82, 95, "Goldman Sachs"),
    ("DBRK", "Databricks Inc.", "Technology", "NASDAQ", 48, 56, "Morgan Stanley"),
    ("CNVA", "Canva Pty Ltd.", "Technology", "NYSE", 28, 34, "J.P. Morgan"),
    ("REDT", "Reddit Inc.", "Communication Services", "NYSE", 31, 38, "Goldman Sachs"),
    ("KLNA", "Klarna Group", "Financials", "NYSE", 40, 50, "Goldman Sachs"),
    ("PRPS", "Perplexity AI Inc.", "Technology", "NASDAQ", 60, 72, "Citi"),
    ("CRSV", "Cursor Software", "Technology", "NASDAQ", 25, 30, "Morgan Stanley"),
    ("GROQ", "Groq Systems", "Technology", "NYSE", 45, 55, "BofA"),
    ("ANRP", "Anthropic PBC", "Technology", "NASDAQ", 85, 100, "Morgan Stanley"),
    ("MSTR2", "MongoDB Spinoff", "Technology", "NASDAQ", 50, 60, "Goldman Sachs"),
    ("FRMS", "Figma Inc.", "Technology", "NASDAQ", 35, 42, "J.P. Morgan"),
    ("LNRW", "Linear Inc.", "Technology", "NYSE", 18, 22, "Goldman Sachs"),
]


def mock_upcoming_ipos(days_ahead: int = 90) -> list[dict[str, Any]]:
    rows = []
    today = date.today()
    for _i, (sym, name, sector, exch, lo, hi, uw) in enumerate(_IPO_SAMPLE):
        expected = today + timedelta(days=random.randint(3, days_ahead))
        status = "upcoming" if expected > today + timedelta(days=2) else "priced"
        rows.append({
            "symbol": sym,
            "company_name": name,
            "sector": sector,
            "exchange": exch,
            "expected_date": expected,
            "price_low": float(lo),
            "price_high": float(hi),
            "shares_offered": random.randint(5, 40) * 1_000_000,
            "status": status,
            "lead_underwriter": uw,
            "description": f"{name} is targeting a {exch} listing.",
        })
    return sorted(rows, key=lambda r: r["expected_date"])


def mock_upcoming_earnings(days_ahead: int = 90) -> list[dict[str, Any]]:
    """Generate plausible earnings calendar for the scanner universe."""
    from app.services.mock_feed import TICKER_UNIVERSE
    today = date.today()
    rows = []
    # 80% of names will have an earnings date somewhere in the window. The
    # dates now honour `days_ahead` — it was previously accepted and ignored
    # (hardcoded 90), so dev mode silently spanned a different window than the
    # caller asked for.
    sample = random.sample([t[0] for t in TICKER_UNIVERSE], k=int(len(TICKER_UNIVERSE) * 0.8))
    for sym in sample:
        report = today + timedelta(days=random.randint(0, days_ahead))
        quarter = f"Q{((report.month - 1) // 3) + 1} {report.year}"
        rows.append({
            "symbol": sym,
            "report_date": report,
            "report_time": random.choice(["BMO", "AMC", "DMH"]),  # Before/After/During
            "fiscal_quarter": quarter,
            "eps_estimate": round(random.uniform(-0.5, 5.5), 2),
            "eps_actual": None,
            "revenue_estimate_m": round(random.uniform(50, 50_000), 0),
            "revenue_actual_m": None,
            "surprise_pct": None,
        })
    return sorted(rows, key=lambda r: r["report_date"])


# ---- Canonical entry points (Finnhub-aware, mock fallback) ----------------

async def upcoming_ipos(days_ahead: int = 90) -> list[dict[str, Any]]:
    """
    Returns the IPO calendar, preferring real Finnhub data when configured.
    Falls back to mock if Finnhub is unavailable so the /app/ipos page is
    never empty.
    """
    from app.services.finnhub_feed import fetch_ipo_calendar
    real = await fetch_ipo_calendar(days_ahead=days_ahead)
    if real:
        # Convert ISO date strings (from cache) back to date objects for DB write
        for r in real:
            if isinstance(r.get("expected_date"), str):
                with contextlib.suppress(ValueError):
                    r["expected_date"] = date.fromisoformat(r["expected_date"])
        logger.info("calendar.ipos source=finnhub count=%d", len(real))
        return real
    # NEVER in production. _IPO_SAMPLE invents offerings for REAL, NAMED
    # private companies — Stripe, Databricks, Canva, Reddit, Klarna, Figma,
    # Anthropic — with specific price ranges, share counts, expected dates and
    # named lead underwriters ("Goldman Sachs", "Morgan Stanley"). Writing
    # those to ipo_events publishes an invented securities offering, attributed
    # to real firms, on a public page. That is not a wrong number; it is a
    # fabricated claim about companies and banks that did not make it.
    #
    # The docstring said the fallback existed "so the /app/ipos page is never
    # empty". An empty calendar is a true statement about a quiet week. This
    # is the same defect as the /insider-buying showcase rows removed in #622.
    if _is_production():
        logger.warning("calendar.ipos unavailable — publishing no rows")
        return []
    logger.info("calendar.ipos source=mock")
    return mock_upcoming_ipos(days_ahead=days_ahead)


async def upcoming_earnings(days_ahead: int = 90) -> list[dict[str, Any]]:
    """
    Returns the earnings calendar, preferring real Finnhub data when configured.
    Falls back to mock if Finnhub is unavailable.

    Window widened 14 → 90 days (2026-08-22) so the per-ticker "next earnings"
    stat is usually populated. US companies report roughly quarterly, so a
    14-day window left most of the universe with no upcoming row at all and the
    ticker page had nothing to show for the vast majority of symbols. 90 days is
    one full reporting quarter — the same default upcoming_ipos() already uses,
    and the ceiling /api/calendar/earnings already allows (days=Query(le=90)).

    This costs nothing upstream: /calendar/earnings is a single ranged request
    either way (cached CACHE_TTL_CALENDAR_HOURS, keyed per window), so it is
    more rows in the same call, not more calls. Nor does it accumulate stale
    rows — the worker's _seed_calendar replaces earnings_events wholesale on
    each daily refresh. A name that reported in the last day or two can still
    fall just outside the quarter; that reads as a null, which is the honest
    answer, not a guessed date.
    """
    from app.services.finnhub_feed import fetch_earnings_calendar
    real = await fetch_earnings_calendar(days_ahead=days_ahead)
    if real:
        for r in real:
            if isinstance(r.get("report_date"), str):
                with contextlib.suppress(ValueError):
                    r["report_date"] = date.fromisoformat(r["report_date"])
        logger.info("calendar.earnings source=finnhub count=%d", len(real))
        return real
    # Same rule. The mock invents an EPS estimate and a revenue estimate for
    # 80% of the universe — numbers users are invited to trade around, that no
    # analyst produced. An empty earnings calendar is honest; an invented one
    # is not.
    if _is_production():
        logger.warning("calendar.earnings unavailable — publishing no rows")
        return []
    logger.info("calendar.earnings source=mock")
    return mock_upcoming_earnings(days_ahead=days_ahead)
