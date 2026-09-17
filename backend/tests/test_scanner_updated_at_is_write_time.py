"""/api/scanner `updated_at` is the write time; the vendor delay is a separate field.

Review round 2 of #842: when `data_delayed_minutes` started carrying the
vendor's ~15-minute delay, the same number was also subtracted from every
row's `updated_at`, for every tier. That silently changed what the public
field means (the MCP server's `as_of` note says it is when Tapeline last wrote
the row). Only a TIER-imposed delay (0 for every tier today, see
services/tier.py) may shift the timestamp; the vendor delay is reported in
`data_delayed_minutes`.
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.main import app
from app.models import Ticker
from app.services.freshness import PRICE_DELAY_MINUTES

_SECTOR = "UpdatedAtWriteTimeSector"
_SYMBOL = "UAWT01"


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _parse(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@pytest.mark.asyncio
async def test_updated_at_is_not_shifted_by_the_vendor_delay(client):
    written = datetime.now(UTC).replace(microsecond=0)
    async with SessionLocal() as s:
        await s.merge(
            Ticker(
                symbol=_SYMBOL,
                name="Updated At Write Time Co",
                sector=_SECTOR,
                asset_class="stock",
                score=90.0,
                signal="HIGH CONVICTION",
                change_pct_1d=1.0,
                confidence_pct=80.0,
                sub_trend=70.0,
                sub_momentum=65.0,
                reason="Trend and momentum confirm the composite.",
                updated_at=written,
                price=50.0,
                volume=1_000_000,
            )
        )
        await s.commit()
    try:
        async with client:
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&limit=50")
        assert r.status_code == 200, r.text
        body = r.json()
        # The vendor delay is disclosed in its own field...
        assert body["data_delayed_minutes"] == PRICE_DELAY_MINUTES
        rows = [row for row in body["items"] if row["symbol"] == _SYMBOL]
        assert rows, body
        # ...and is NOT folded into the row's write time.
        assert _parse(rows[0]["updated_at"]) == written
    finally:
        async with SessionLocal() as s:
            await s.execute(delete(Ticker).where(Ticker.symbol == _SYMBOL))
            await s.commit()
