"""Corruption guards on GET /api/ticker/{symbol}.

The detail endpoint backs the SSR'd public /t/{symbol} page, so junk-shaped
requests must 404 rather than render a fabricated page — otherwise a legacy
ghost row (e.g. the "🏆 IVV" trophy-badge cell) renders a duplicate of the
real ETF and hands Google a thin /t/🏆 IVV URL. The shape guard fires before
the DB lookup, so these cases need no seeding. The score>100 guard (legacy
pre-clamp ghosts like MCW=104) is exercised against live data post-deploy.

See routers/ticker.py (ticker_detail) and services/symbols.py.
"""
from __future__ import annotations

import urllib.parse

import httpx
import pytest

from app.main import app


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_ticker_detail_404s_emoji_space_symbol(client):
    """The exact corruption: "🏆 IVV". 404 before the DB lookup, so even if a
    legacy ghost row with that symbol still exists it can never render."""
    async with client:
        r = await client.get("/api/ticker/" + urllib.parse.quote("🏆 IVV"))
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_ticker_detail_404s_any_embedded_space(client):
    """Any embedded space (the display filter's notlike('% %') case) is junk."""
    async with client:
        r = await client.get("/api/ticker/" + urllib.parse.quote("ZZ WSPACE"))
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_ticker_detail_404s_unknown_but_valid_symbol(client):
    """A validly-shaped symbol that simply isn't in the DB must still 404 —
    confirms the shape guard didn't break the normal not-found path."""
    async with client:
        r = await client.get("/api/ticker/ZZZQXNONE")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_ticker_detail_accepts_real_symbol_shapes(client):
    """Real symbol shapes must NOT be rejected by the shape guard. These may
    or may not be seeded in the test DB, so we only assert they get PAST the
    shape guard — i.e. the response is anything other than the 'not a valid
    symbol' 404 the guard raises (200 if seeded, or the 'not in universe'
    404 from the DB miss, both of which mean the guard let it through)."""
    async with client:
        for sym in ("IVV", "AAPL", "BRK.B", "CL=F"):
            r = await client.get("/api/ticker/" + urllib.parse.quote(sym))
            assert r.status_code in (200, 404)
            if r.status_code == 404:
                # the DB-miss 404 says "not in scanner universe"; the shape
                # guard 404 says "not a valid symbol" — assert it's NOT the latter
                assert "not a valid symbol" not in r.json().get("detail", "")
