"""Asset-class data-quality floor for ranked surfaces (ticker_freshness).

The public freshness filter rejected symbols with spaces but NOT a dirty
``asset_class``. A row like "OPAL" carrying asset_class "📈 stock" (the raw,
emoji-decorated sheet cell, written before normalize_asset_class existed or
slipped past it) leaked to /api/public/signals with a garbled class label.

asset_class_clean_clauses() now drops any decorated / multi-word asset_class
while keeping clean bare tokens. This is a *shape* test, not a whitelist, so
``stock`` / ``equity`` / ``etf`` / ``crypto`` / ``commodity`` / ``future`` and
any future addition all survive.

Verified through the real /api/public/signals surface (which applies
live_clauses → valid_composite_clauses → asset_class_clean_clauses) plus a unit
test of the clause helper.
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import Ticker
from app.services.ticker_freshness import asset_class_clean_clauses


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# All seeds are FRESH with full display fields + >=2 factors, so the ONLY thing
# that can drop them is the asset_class clause — isolating this fix.
_DIRTY = "TEST_OPAL"       # asset_class "📈 stock" — the leak
_DIRTY_MULTIWORD = "TEST_CMDTY"  # asset_class "commodity etf" — multi-word raw
_CLEAN_STOCK = "TEST_AC_STOCK"   # asset_class "stock" — must survive
_CLEAN_FUTURE = "TEST_AC_FUT"    # asset_class "future" — non-enum but clean
_SEEDS = (_DIRTY, _DIRTY_MULTIWORD, _CLEAN_STOCK, _CLEAN_FUTURE)


async def _clear() -> None:
    async with session_scope() as s:
        existing = await s.execute(select(Ticker).where(Ticker.symbol.in_(_SEEDS)))
        for t in existing.scalars().all():
            await s.delete(t)
        await s.commit()


@pytest.mark.asyncio
async def test_public_signals_drops_emoji_asset_class(client):
    now = datetime.now(UTC)
    await _clear()
    async with session_scope() as s:
        s.add_all([
            # The leak: emoji-prefixed asset_class. Everything else pristine.
            Ticker(symbol=_DIRTY, name="Opal Inc", asset_class="📈 stock",
                   score=88.0, signal="STRONG SETUP", updated_at=now,
                   change_pct_1d=1.0, confidence_pct=80,
                   sub_trend=85, sub_rs=86, sub_momentum=87),
            # Multi-word raw asset_class (space) — also dropped.
            Ticker(symbol=_DIRTY_MULTIWORD, name="Cmdty Inc",
                   asset_class="commodity etf",
                   score=82.0, signal="STRONG SETUP", updated_at=now,
                   change_pct_1d=0.4, confidence_pct=70,
                   sub_trend=80, sub_rs=81, sub_momentum=82),
            # Clean single tokens — must survive.
            Ticker(symbol=_CLEAN_STOCK, name="Clean Stock", asset_class="stock",
                   score=75.0, signal="STRONG SETUP", updated_at=now,
                   change_pct_1d=0.6, confidence_pct=72,
                   sub_trend=72, sub_rs=76, sub_momentum=75),
            Ticker(symbol=_CLEAN_FUTURE, name="Clean Future", asset_class="future",
                   score=70.0, signal="STRONG SETUP", updated_at=now,
                   change_pct_1d=-0.2, confidence_pct=60,
                   sub_trend=68, sub_rs=71, sub_momentum=70),
        ])
        await s.commit()

    try:
        async with client:
            r = await client.get("/api/public/signals?limit=2000")
            assert r.status_code == 200, r.text
            symbols = {row["symbol"] for row in r.json()["items"]}
        # Dirty asset_class rows dropped despite being fresh + full composites.
        assert _DIRTY not in symbols, "emoji asset_class row leaked (the OPAL bug)"
        assert _DIRTY_MULTIWORD not in symbols, "multi-word asset_class leaked"
        # Clean bare tokens survive — the filter is shape-based, not a whitelist.
        assert _CLEAN_STOCK in symbols
        assert _CLEAN_FUTURE in symbols
    finally:
        await _clear()


def test_asset_class_clean_clauses_render():
    """Two clauses: no-space + first-char-is-an-ascii-letter. Render them and
    sanity-check the shape so a future edit can't silently no-op the guard."""
    clauses = asset_class_clean_clauses()
    assert len(clauses) == 2
    rendered = [
        str(c.compile(compile_kwargs={"literal_binds": True})).upper()
        for c in clauses
    ]
    # The whitespace-rejecting clause.
    assert any("NOT LIKE" in r and "% %" in r for r in rendered)
    # The leading-ascii-letter OR — at least one single-char LIKE pattern.
    assert any(" OR " in r and "LIKE" in r for r in rendered)
