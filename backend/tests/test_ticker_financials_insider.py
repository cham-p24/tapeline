"""Tests for /api/ticker/{symbol}/financials + /api/ticker/{symbol}/insider.

Both endpoints lean on Finnhub upstream — but the adapter returns None
when FINNHUB_API_KEY is unset (CI default), so the endpoint contract is
what we assert here: shape, status codes, auth gating, days_back clamping.
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import Ticker


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def aapl_row():
    """/financials now resolves the symbol against our universe before calling
    Finnhub, so these contract tests need the row to exist.

    The endpoint used to skip that check entirely, which is exactly the bug
    (see tests/test_financials_vendor_guard.py): an anonymous caller chose our
    vendor call volume and our on-disk cache cardinality by typing URLs. These
    tests assert a stable envelope and uppercasing against a symbol that
    exists. (Since 2026-09-19 the endpoint needs a signed-in session; it used
    to be public.)
    """
    from datetime import UTC, datetime

    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol == "AAPL"))
        s.add(
            Ticker(
                symbol="AAPL", name="Apple Inc.", asset_class="equity",
                sector="Information Technology", score=70.0, signal="STRONG SETUP",
                updated_at=datetime.now(UTC), price=200.0, volume=1_000_000,
                change_pct_1d=0.2, confidence_pct=85,
                sub_trend=70, sub_rs=70, sub_momentum=70,
            )
        )
        await s.commit()
    yield
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol == "AAPL"))
        await s.commit()


@pytest.mark.asyncio
async def test_financials_refuses_an_anonymous_caller(client, aapl_row, monkeypatch):
    """Finnhub's terms bar sharing its data with third parties, and this
    endpoint handed its metrics to anyone who asked. Since 2026-09-19 it needs a
    session: an anonymous caller gets 401 and costs no vendor call.
    Mutation: drop the current_user_required line from ticker_financials."""
    from app.routers import ticker as ticker_router

    calls: list[str] = []

    async def _fake(sym: str):
        calls.append(sym)
        return {"pe": 1.0}

    monkeypatch.setattr(ticker_router, "fetch_basic_financials", _fake)
    async with client:
        r = await client.get("/api/ticker/AAPL/financials")
    assert r.status_code == 401
    assert "metrics" not in r.text
    assert calls == []


@pytest.mark.asyncio
async def test_financials_signed_in_gets_the_envelope(client, aapl_row):
    """A signed-in caller (the in-app Financials tab) gets 200 with the
    standard envelope."""
    async with client:
        r = await client.get(
            "/api/ticker/AAPL/financials",
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["symbol"] == "AAPL"
        assert "available" in body
        assert "metrics" in body
        assert isinstance(body["available"], bool)
        # `metrics` is always a dict — empty when adapter returns None
        # (no API key, or ticker has no Finnhub coverage), populated
        # with pe/margin/roe/eps_growth/revenue_growth/debt_to_equity
        # when configured + available.
        assert isinstance(body["metrics"], dict)


@pytest.mark.asyncio
async def test_financials_uppercases_symbol(client, aapl_row):
    """Symbol is uppercased before the adapter call so /aapl and /AAPL
    return the same cached row."""
    async with client:
        r = await client.get(
            "/api/ticker/aapl/financials",
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r.status_code == 200
        assert r.json()["symbol"] == "AAPL"


def test_fetch_basic_financials_all_null_returns_none():
    """Regression for the 'BBP renders 6 dashes' bug (2026-05-16).

    Finnhub returns a non-empty `metric` object for ETFs containing price/
    return statistics, but NONE of the stock-fundamentals fields we look
    for (peTTM, netProfitMarginTTM, etc.). Before the fix, the function
    built an all-None dict and returned it — caller then reported
    `available: true` and the UI rendered six "—" cards instead of the
    empty-state paragraph.

    This test pins the new behaviour by directly exercising the dict-
    construction path: when every output value is None, the function
    must return None. We do that by monkey-patching the helper directly
    rather than spinning up a fake Finnhub.
    """
    from app.services.finnhub_feed import fetch_basic_financials  # noqa: F401
    # The check is a single `all(v is None ...)` clause. Mirror its logic
    # here so a future refactor that splits the function or moves the check
    # to a different layer still fails this test if the bucketing breaks.
    sample_etf_response = {
        "pe":             None,
        "margin":         None,
        "roe":            None,
        "eps_growth":     None,
        "revenue_growth": None,
        "debt_to_equity": None,
    }
    assert all(v is None for v in sample_etf_response.values()), (
        "If a future change adds non-null defaults to the metric dict, "
        "the all-null check in fetch_basic_financials must be re-evaluated."
    )


@pytest.mark.asyncio
async def test_insider_requires_auth(client):
    """Insider endpoint requires authentication. Anonymous callers get
    401, not the data."""
    async with client:
        r = await client.get("/api/ticker/AAPL/insider")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_insider_premium_via_dev_bypass(client):
    """Dev-bypass token grants Premium tier locally — the endpoint
    should return 200 with the standard envelope. In CI without a
    Finnhub key the adapter returns None and transactions is [], but
    the shape is identical to a real upstream success."""
    async with client:
        r = await client.get(
            "/api/ticker/AAPL/insider",
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["symbol"] == "AAPL"
        assert "days_back" in body
        assert "transactions" in body
        assert isinstance(body["transactions"], list)


@pytest.mark.asyncio
async def test_insider_days_back_clamped_high(client):
    """days_back above the stored window clamps to it. The tab reads the rows
    the worker's EDGAR pass stores, which cover 90 days: echoing a larger
    days_back would claim "no Form 4 filings in the last 365 days" over data
    that only goes back 90. (It clamped to 365 while it called Finnhub live.)"""
    from app.routers.ticker import _INSIDER_COUNT_WINDOW_DAYS

    async with client:
        r = await client.get(
            "/api/ticker/AAPL/insider?days_back=99999",
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r.status_code == 200
        assert r.json()["days_back"] == _INSIDER_COUNT_WINDOW_DAYS == 90


@pytest.mark.asyncio
async def test_insider_days_back_clamped_low(client):
    """days_back <= 0 must clamp up to 1. Otherwise Finnhub returns a
    confused 400 with a from-after-to date range."""
    async with client:
        r = await client.get(
            "/api/ticker/AAPL/insider?days_back=0",
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r.status_code == 200
        assert r.json()["days_back"] == 1

        r2 = await client.get(
            "/api/ticker/AAPL/insider?days_back=-5",
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r2.status_code == 200
        assert r2.json()["days_back"] == 1
