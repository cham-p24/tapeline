"""The calendar must not invent offerings for real, named companies.

`calendar_feed.upcoming_ipos` fell back to `mock_upcoming_ipos` whenever
Finnhub returned nothing, with the stated reason "so the /app/ipos page is
never empty". What that fallback contains is not placeholder data:

    ("STRP", "Stripe Inc.",      ..., 82, 95,  "Goldman Sachs"),
    ("ANRP", "Anthropic PBC",    ..., 85, 100, "Morgan Stanley"),
    ("FRMS", "Figma Inc.",       ..., 35, 42,  "J.P. Morgan"),

Written to `ipo_events` in production, those become a published claim that
named private companies are doing offerings at specific prices on specific
dates, led by named investment banks. None of it happened. It is the same
defect as the `/insider-buying` showcase rows removed in #622, with the
aggravating factor that the subjects are real firms.

`upcoming_earnings` is the same shape: an invented EPS estimate and revenue
estimate for 80% of the universe, numbers a user is invited to trade around
that no analyst produced.

An empty calendar is a true statement about a quiet week. These tests assert
that production gets the empty one, that dev keeps its fixtures, and — because
the refresh replaces the whole table — that an unavailable feed does not wipe
the real rows it cannot replace.
"""
from __future__ import annotations

import pytest

from app.services import calendar_feed

INVENTED = {
    "STRP", "DBRK", "CNVA", "REDT", "KLNA", "PRPS",
    "CRSV", "GROQ", "ANRP", "MSTR2", "FRMS", "LNRW",
}


@pytest.fixture
def finnhub_returns_nothing(monkeypatch):
    async def _no_ipos(days_ahead=90):
        return []

    async def _no_earnings(*a, **k):
        return []

    monkeypatch.setattr(
        "app.services.finnhub_feed.fetch_ipo_calendar", _no_ipos, raising=True
    )
    monkeypatch.setattr(
        "app.services.finnhub_feed.fetch_earnings_calendar", _no_earnings,
        raising=False,
    )


def _env(monkeypatch, value: str) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "app_env", value, raising=False)


@pytest.mark.asyncio
async def test_production_publishes_no_ipos_rather_than_invented_ones(
    monkeypatch, finnhub_returns_nothing
):
    _env(monkeypatch, "production")
    rows = await calendar_feed.upcoming_ipos()

    assert rows == [], (
        f"production returned {len(rows)} IPO rows with no feed data. "
        f"Symbols: {sorted(r['symbol'] for r in rows)}"
    )


@pytest.mark.asyncio
async def test_no_real_company_is_ever_given_an_invented_offering(
    monkeypatch, finnhub_returns_nothing
):
    """Named explicitly, because these are real firms and real banks."""
    _env(monkeypatch, "production")
    rows = await calendar_feed.upcoming_ipos()
    published = {r["symbol"] for r in rows}

    assert not (published & INVENTED), (
        f"published invented offerings for {sorted(published & INVENTED)}"
    )
    names = " ".join(r.get("company_name", "") for r in rows)
    for company in ("Stripe", "Anthropic", "Figma", "Databricks", "Canva", "Klarna"):
        assert company not in names, f"{company} given an invented IPO"


@pytest.mark.asyncio
async def test_production_publishes_no_earnings_estimates_it_did_not_receive(
    monkeypatch, finnhub_returns_nothing
):
    _env(monkeypatch, "production")
    assert await calendar_feed.upcoming_earnings() == []


@pytest.mark.asyncio
async def test_dev_keeps_its_fixtures(monkeypatch, finnhub_returns_nothing):
    """A local instance still renders a populated calendar."""
    _env(monkeypatch, "development")
    assert await calendar_feed.upcoming_ipos(), "dev lost its IPO fixtures"


@pytest.mark.asyncio
async def test_an_unavailable_feed_does_not_wipe_the_real_calendar(monkeypatch):
    """The refresh replaces the whole table, so empty must mean 'keep'.

    earnings_events holds ~2,700 real rows in production. A transient Finnhub
    failure is not a statement that no company reports this quarter, and now
    that the feeds return [] instead of inventing rows, delete-then-insert
    would erase the calendar on any outage.
    """
    from sqlalchemy import delete, select

    from app.db import session_scope
    from app.models import EarningsEvent
    from app.workers import signal_publisher

    from datetime import date

    async with session_scope() as s:
        await s.execute(delete(EarningsEvent))
        s.add(EarningsEvent(
            symbol="REALCO", report_date=date(2026, 12, 1),
            report_time="AMC", fiscal_quarter="Q4 2026",
        ))

    async def _empty(*a, **k):
        return []

    monkeypatch.setattr(signal_publisher, "_sync_next_earnings_dates", _empty)
    monkeypatch.setattr(
        "app.services.calendar_feed.upcoming_ipos", _empty, raising=True
    )
    monkeypatch.setattr(
        "app.services.calendar_feed.upcoming_earnings", _empty, raising=True
    )

    await signal_publisher._seed_calendar()

    async with session_scope() as s:
        rows = (await s.execute(select(EarningsEvent))).scalars().all()
        assert len(rows) == 1 and rows[0].symbol == "REALCO", (
            "an unavailable feed erased the real earnings calendar"
        )
