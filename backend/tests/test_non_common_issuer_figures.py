"""A note, preferred or warrant does not show its issuer's company figures.

WHAT THIS FIXES. The vendor answers such a symbol with its ISSUER's figures,
and the ticker page printed them as the listing's own. Measured read-only on
production 2026-09-19: of 120 flagged listings, 28 showed at least one of P/E,
EPS or dividend yield and 96 a market cap. AGNCO, an AGNC preferred, showed
AGNC's $12.9B cap and AGNC common's 16.5% yield against its own 6.50% coupon.
The Financials tab fetched the issuer's financials live.

Pinned here: the page payload blanks them (whatever the row holds), the
Financials endpoint answers "non_common" without calling the vendor, the
key-statistics pass stops asking for them, and the settle clears what it wrote.
Every test was watched failing against the mutation its docstring names.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.main import app
from app.models import Ticker
from app.routers import ticker as ticker_router
from app.routers.ticker import _key_stats_payload
from app.workers import signal_publisher as sp

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

NOTE, STOCK = "ZIFN", "ZIFS"
OLD = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
ISSUER = dict(market_cap=12_909_893_029.0, beta=1.4, pe_ttm=5.57, eps_ttm=2.07,
              dividend_yield=16.53, ex_dividend_date=date(2026, 8, 28))
OWN = dict(price=24.5, previous_close=24.4, week52_low=22.0, week52_high=25.1,
           volume=40_000, avg_volume_30d=38_000)
_AUTH = {"Authorization": "Bearer dev-bypass"}


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
async def _cleanup() -> Any:
    yield
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_([NOTE, STOCK])))


async def _seed(symbol: str, *, non_common: bool, name: str | None = None) -> None:
    async with session_scope() as s:
        s.add(Ticker(
            symbol=symbol,
            name=name or ("Zebra Corp. 6.50% Series E Cumulative Preferred Stock"
                          if non_common else "Zebra Corp"),
            asset_class="equity", sector="Financials", is_non_common=non_common,
            score=55.0, signal="CONSTRUCTIVE", updated_at=OLD, **OWN, **ISSUER,
        ))


def _row(**kw: Any) -> Ticker:
    return Ticker(symbol="X", name="X", asset_class="equity", **OWN, **ISSUER, **kw)


# ═════════════════════════════════════════════════════════════════════════════
# The page payload
# ═════════════════════════════════════════════════════════════════════════════

def test_the_page_payload_blanks_the_issuer_figures_on_a_flagged_listing() -> None:
    """Mutation: returning the row's values whatever the flag says."""
    p = _key_stats_payload(_row(is_non_common=True), None)
    for field in ("market_cap", "beta", "pe_ttm", "eps_ttm", "dividend_yield",
                  "ex_dividend_date"):
        assert p[field] is None, f"{field} shows the issuer's figure: {p[field]!r}"
    assert p["is_non_common"] is True, "the page cannot say why the fields are empty"
    # The listing's own trading figures stay.
    for field, value in OWN.items():
        assert p[field] == value, f"{field} was blanked but is the listing's own"


def test_a_common_stock_keeps_every_figure() -> None:
    p = _key_stats_payload(_row(is_non_common=False), None)
    assert p["market_cap"] == ISSUER["market_cap"]
    assert p["pe_ttm"] == ISSUER["pe_ttm"]
    assert p["dividend_yield"] == ISSUER["dividend_yield"]
    assert p["ex_dividend_date"] == ISSUER["ex_dividend_date"].isoformat()
    assert p["is_non_common"] is False


# ═════════════════════════════════════════════════════════════════════════════
# The Financials tab
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def vendor(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def _fake(sym: str):
        calls.append(sym)
        return {"pe": 5.57}

    monkeypatch.setattr(ticker_router, "fetch_basic_financials", _fake)
    return calls


async def test_the_financials_tab_says_why_and_never_asks_the_vendor(client, vendor) -> None:
    """Mutation: fetching the issuer's financials for a flagged listing."""
    await _seed(NOTE, non_common=True)
    async with client:
        r = await client.get(f"/api/ticker/{NOTE}/financials", headers=_AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"symbol": NOTE, "available": False, "metrics": {}, "reason": "non_common"}
    assert vendor == [], "the vendor was asked for a note's financials"


async def test_a_common_stock_still_gets_its_financials(client, vendor) -> None:
    await _seed(STOCK, non_common=False)
    async with client:
        r = await client.get(f"/api/ticker/{STOCK}/financials", headers=_AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["available"] is True
    assert "reason" not in r.json()
    assert vendor == [STOCK]


# ═════════════════════════════════════════════════════════════════════════════
# The worker
# ═════════════════════════════════════════════════════════════════════════════

async def test_the_settle_clears_what_the_key_statistics_pass_wrote() -> None:
    """Mutation: _settle_non_common not running the issuer clear. The row is
    flagged by its name here, so the settle's reconcile flags it first."""
    await _seed(NOTE, non_common=False,
                name="Zebra Corp. 6.50% Series E Cumulative Preferred Stock")
    await _seed(STOCK, non_common=False)
    await sp._settle_non_common()
    async with session_scope() as s:
        n = await s.get(Ticker, NOTE)
        st = await s.get(Ticker, STOCK)
        assert n.is_non_common is True
        for field in ("beta", "pe_ttm", "eps_ttm", "dividend_yield", "ex_dividend_date"):
            assert getattr(n, field) is None, f"{field} still holds the issuer's figure"
        assert n.updated_at.replace(tzinfo=UTC) == OLD, "no live data changed"
        # Market cap is the profile path's to refuse, not this clear's.
        assert n.market_cap == ISSUER["market_cap"]
        assert (st.pe_ttm, st.dividend_yield) == (ISSUER["pe_ttm"], ISSUER["dividend_yield"])


async def test_the_key_statistics_pass_never_asks_for_a_flagged_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: the selection without its is_non_common clause."""
    await _seed(NOTE, non_common=True)
    await _seed(STOCK, non_common=False)
    asked: list[str] = []

    async def _fetch(sym: str) -> dict[str, Any] | None:
        asked.append(sym)
        return None

    async def _no_sleep(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr("app.services.finnhub_feed.fetch_key_statistics", _fetch)
    monkeypatch.setattr(sp.asyncio, "sleep", _no_sleep)
    await sp._backfill_key_statistics()
    assert STOCK in asked, "the pass did not run for the common stock"
    assert NOTE not in asked, "the pass asked the vendor for a note's statistics"
