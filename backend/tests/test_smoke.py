"""Smoke tests — verify every critical path returns something sane."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.main import app


@pytest.fixture
def client():
    """HTTPX ASGI client — no real server needed."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _get(client: httpx.AsyncClient, path: str, **kwargs) -> httpx.Response:
    return await client.get(path, **kwargs)


@pytest.mark.asyncio
async def test_health(client):
    async with client:
        r = await _get(client, "/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["app"] == "Tapeline"


@pytest.mark.asyncio
async def test_unauthenticated_me(client):
    async with client:
        r = await _get(client, "/api/me")
        assert r.status_code == 200
        body = r.json()
        assert body["authenticated"] is False
        assert body["tier"] == "free"


@pytest.mark.asyncio
async def test_dev_bypass_auth(client):
    async with client:
        r = await _get(client, "/api/me", headers={"Authorization": "Bearer dev-bypass"})
        assert r.status_code == 200
        body = r.json()
        assert body["authenticated"] is True
        assert body["tier"] == "premium"


@pytest.mark.asyncio
async def test_scanner_responds(client):
    async with client:
        r = await _get(client, "/api/scanner?limit=5")
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "count" in body


@pytest.mark.asyncio
async def test_rate_limit_kicks_in(client):
    """Hammer the API and confirm we get a 429 eventually."""
    async with client:
        responses = await asyncio.gather(*[_get(client, "/api/scanner?limit=1") for _ in range(150)])
        codes = [r.status_code for r in responses]
        assert 429 in codes, "rate limit should block at least one request"


@pytest.mark.asyncio
async def test_watchlist_requires_auth(client):
    async with client:
        r = await _get(client, "/api/watchlist")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_legal_404_graceful(client):
    async with client:
        r = await _get(client, "/api/nonexistent")
        assert r.status_code == 404
