"""
IPO + earnings calendar data.

Production path: Finnhub `/calendar/ipo` and `/calendar/earnings` endpoints
(free tier covers Tapeline). Dev path: synthesized data so UI works without
a Finnhub key.

Use `upcoming_ipos()` / `upcoming_earnings()` as the canonical entry points —
they try Finnhub first and fall back to the mock generators when no key is set.
"""
from __future__ import annotations

import logging
import random
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)


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
    for i, (sym, name, sector, exch, lo, hi, uw) in enumerate(_IPO_SAMPLE):
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


def mock_upcoming_earnings(days_ahead: int = 14) -> list[dict[str, Any]]:
    """Generate plausible earnings calendar for the scanner universe."""
    from app.services.mock_feed import TICKER_UNIVERSE
    today = date.today()
    rows = []
    # 80% of names will have an earnings date sometime in 90 days
    sample = random.sample([t[0] for t in TICKER_UNIVERSE], k=int(len(TICKER_UNIVERSE) * 0.8))
    for sym in sample:
        report = today + timedelta(days=random.randint(0, 90))
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
                try:
                    r["expected_date"] = date.fromisoformat(r["expected_date"])
                except ValueError:
                    pass
        logger.info("calendar.ipos source=finnhub count=%d", len(real))
        return real
    logger.info("calendar.ipos source=mock")
    return mock_upcoming_ipos(days_ahead=days_ahead)


async def upcoming_earnings(days_ahead: int = 14) -> list[dict[str, Any]]:
    """
    Returns the earnings calendar, preferring real Finnhub data when configured.
    Falls back to mock if Finnhub is unavailable.
    """
    from app.services.finnhub_feed import fetch_earnings_calendar
    real = await fetch_earnings_calendar(days_ahead=days_ahead)
    if real:
        for r in real:
            if isinstance(r.get("report_date"), str):
                try:
                    r["report_date"] = date.fromisoformat(r["report_date"])
                except ValueError:
                    pass
        logger.info("calendar.earnings source=finnhub count=%d", len(real))
        return real
    logger.info("calendar.earnings source=mock")
    return mock_upcoming_earnings(days_ahead=days_ahead)
