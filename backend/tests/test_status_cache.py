"""/api/status short-TTL cache (launch-load safety).

Every homepage visitor's LiveCounters strip polls /api/status every 60s, and
each call runs 5 DB queries. Under a launch traffic spike that multiplies onto
Neon. A 30s server cache collapses N concurrent polls into one DB hit per
window; the payload is a "~5min refresh" band so the staleness is invisible.

Pinned here: within the TTL a second call returns the byte-identical cached
payload (same `now` timestamp — proving no re-query); once expired it refreshes.
"""
from __future__ import annotations

import httpx
import pytest

import app.main as main_module


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=main_module.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def _reset_status_cache():
    """Start from a cold cache and leave it cold, so this test is independent
    of any other suite that touched /api/status."""
    main_module._STATUS_CACHE["payload"] = None
    main_module._STATUS_CACHE["ts"] = 0.0
    yield
    main_module._STATUS_CACHE["payload"] = None
    main_module._STATUS_CACHE["ts"] = 0.0


@pytest.mark.asyncio
async def test_status_is_cached_within_ttl_then_refreshes(client):
    async with client:
        r1 = await client.get("/api/status")
        assert r1.status_code in (200, 503)
        # A 503 means the DB genuinely errored (not cached by design) — skip the
        # caching assertions in that environment rather than assert on an error.
        if r1.status_code != 200:
            pytest.skip("status DB probe unavailable in this environment")
        first_now = r1.json()["now"]

        # Second call within the TTL → byte-identical cached payload (the
        # handler regenerates `now` on every real run, so an identical value
        # proves the DB path was skipped).
        r2 = await client.get("/api/status")
        assert r2.status_code == 200
        assert r2.json()["now"] == first_now

        # Expire the cache → next call recomputes with a fresh timestamp.
        main_module._STATUS_CACHE["ts"] = 0.0
        r3 = await client.get("/api/status")
        assert r3.status_code == 200
        assert r3.json()["now"] != first_now
