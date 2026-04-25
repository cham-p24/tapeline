"""
IPO + earnings calendar data.

Production path: Polygon.io IPO + earnings endpoints. Dev path: synthesized
data so UI works without a Polygon key.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any


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
