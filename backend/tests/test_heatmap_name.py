"""Heatmap response must carry the company `name` per tile.

The frontend heatmap previously had no name field to show — tiles rendered
the symbol only and any name-aware UI (the tile tooltip) had nothing to
populate. This pins the contract that /api/heatmap returns a `name` on each
ticker so the UI can show the company name instead of leaving it blank.

Seeds a single liquid, freshly-snapshotted Ticker and asserts it surfaces
in the heatmap with its name intact. Auth uses the dev-bypass token (Premium
in CI's development env) so the Pro-gated endpoint lets us through.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest

from app.main import app


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_heatmap_tile_includes_company_name(client):
    from app.db import session_scope
    from app.models import Ticker

    # Unique symbol so reruns / parallel seeds don't collide.
    symbol = f"HM{uuid.uuid4().hex[:4].upper()}"
    company = "Heatmap Name Test Co"

    async with session_scope() as s:
        s.add(Ticker(
            symbol=symbol,
            name=company,
            sector="Information Technology",
            asset_class="stock",
            price=42.0,
            score=77.0,
            signal="STRONG SETUP",
            reason="seed",
            change_pct_1d=1.5,
            # Above the 100k liquidity floor the heatmap requires.
            volume=5_000_000,
            # Fresh — within HEATMAP_MAX_STALE_MIN so it isn't filtered out.
            updated_at=datetime.now(UTC),
        ))
        await s.commit()

    headers = {"Authorization": "Bearer dev-bypass"}
    async with client:
        r = await client.get("/api/heatmap", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()

    # Find our seeded tile across all sector buckets.
    tile = None
    for sector in body["sectors"]:
        for t in sector["tickers"]:
            if t["symbol"] == symbol:
                tile = t
                break
        if tile:
            break

    assert tile is not None, f"seeded {symbol} should appear in the heatmap"
    assert "name" in tile, "each heatmap tile must carry a `name` field"
    assert tile["name"] == company
