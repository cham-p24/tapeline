"""Tests for /api/ticker/{symbol}/financials + /api/ticker/{symbol}/insider.

Both endpoints lean on Finnhub upstream — but the adapter returns None
when FINNHUB_API_KEY is unset (CI default), so the endpoint contract is
what we assert here: shape, status codes, auth gating, days_back clamping.
"""
from __future__ import annotations

import httpx
import pytest

from app.main import app


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_financials_public_no_auth(client):
    """Financials endpoint is public — same access surface as /{symbol}
    and /{symbol}/history. Unauthenticated callers get 200 with the
    standard envelope."""
    async with client:
        r = await client.get("/api/ticker/AAPL/financials")
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
async def test_financials_uppercases_symbol(client):
    """Symbol is uppercased before the adapter call so /aapl and /AAPL
    return the same cached row."""
    async with client:
        r = await client.get("/api/ticker/aapl/financials")
        assert r.status_code == 200
        assert r.json()["symbol"] == "AAPL"


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
    """days_back > 365 must clamp down. Bounds upstream cost — without
    this a malicious caller could ask Finnhub for 10 years of data
    per request, blowing through the rate limit."""
    async with client:
        r = await client.get(
            "/api/ticker/AAPL/insider?days_back=99999",
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r.status_code == 200
        assert r.json()["days_back"] == 365


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
