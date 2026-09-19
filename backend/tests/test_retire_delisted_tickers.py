"""Tickers that stop trading are RETIRED, not left ranked with a frozen price.

Measured read-only against production on 2026-09-19: nothing retired a ticker.
The universe refresh reconciled the vendor's active-listings walk into the
table but never looked at what the walk had stopped returning, so GREE
(Greenidge, renamed VIP on 24 Jul 2026) still read 75.8 STRONG SETUP, HLX
(merged into HOS, last traded 1 Sep) 65.3, and CYCN (now KRSA) 60.8 beside a
-85.5% "daily move", each with a daily score and a score_snapshots row.

What is pinned here:

* discovery reports whether its walk COMPLETED and every active symbol of ANY
  type (a PFD-typed row is still trading even though it is not scoreable);
* `_refresh_universe` retires only on a complete, plausibly whole walk, never
  crypto, never past the per-run safety cap, and un-retires a symbol that comes
  back;
* a retired row leaves the snapshot universe, every ranked surface (scanner,
  search, /api/public/signals, the sitemap list), the insider/fundamentals
  pass selection and the daily score archive, while /api/ticker answers 404
  with the reason;
* the sheet ingest does not un-retire a row by rewriting it.

Every test here was watched failing against the pre-change code.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import delete, select

import app.services.delisting as delisting
import app.services.universe as universe_mod
from app.db import session_scope
from app.main import app
from app.models import ScoreSnapshot, Ticker
from app.services.polygon_feed import DiscoveredUniverse, discover_active_us_tickers
from app.workers import signal_publisher as sp

# Enough synthetic active symbols to clear MIN_PLAUSIBLE_ACTIVE.
_PAD = frozenset(f"PAD{i:05d}" for i in range(delisting.MIN_PLAUSIBLE_ACTIVE))
_STAMP = datetime(2026, 9, 19, 6, 0, tzinfo=UTC)


def _row(symbol: str, asset_class: str = "equity", **kw) -> Ticker:
    return Ticker(symbol=symbol, name=f"{symbol} Corp", sector="Unknown",
                  asset_class=asset_class, **kw)


def _scored(symbol: str, score: float = 70.0, **kw) -> Ticker:
    """A row that passes every ranked-surface floor while it is listed."""
    return _row(
        symbol,
        score=score, signal="STRONG SETUP", price=10.0, volume=1_000_000,
        change_pct_1d=1.0, confidence_pct=80.0,
        sub_trend=70.0, sub_rs=70.0, sub_fundamentals=70.0,
        sub_momentum=70.0, sub_macro=70.0, sub_smart_money=70.0,
        updated_at=datetime.now(UTC),
        **kw,
    )


async def _seed(*rows: Ticker) -> None:
    async with session_scope() as s:
        for r in rows:
            s.add(r)


async def _delisted_at(symbol: str) -> datetime | None:
    async with session_scope() as s:
        return (await s.execute(
            select(Ticker.delisted_at).where(Ticker.symbol == symbol)
        )).scalar_one()


def _walk(listed: list[str], *, complete: bool = True, extra_active=frozenset(),
          pad: frozenset[str] = _PAD) -> DiscoveredUniverse:
    """A discovery result listing `listed` as scoreable rows."""
    rows = [{"symbol": s, "name": f"{s} Corp", "sector": "Unknown",
             "asset_class": "equity"} for s in listed]
    return DiscoveredUniverse(
        rows,
        active_symbols=frozenset(listed) | frozenset(extra_active) | pad,
        complete=complete,
    )


def _patch_discovery(monkeypatch, result) -> None:
    async def fake_discover(*_a, **_k):
        return result

    monkeypatch.setattr(
        "app.services.polygon_feed.discover_active_us_tickers", fake_discover
    )


@pytest.fixture(autouse=True)
def _no_settle(monkeypatch):
    """The non-common settle pass is unrelated; keep each test to one concern."""
    async def _noop():
        return None

    monkeypatch.setattr(sp, "_settle_non_common", _noop)


# ---------------------------------------------------------------------------
# Discovery reports completeness and the full active set
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        if self._payload is None:
            raise httpx.HTTPError("page failed")

    def json(self):
        return self._payload


def _install_fake_vendor(monkeypatch, pages):
    from app.services import polygon_feed

    monkeypatch.setattr(polygon_feed, "_api_key", lambda: "test-key")
    calls = {"n": 0}

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, headers=None):
            i = calls["n"]
            calls["n"] += 1
            return _FakeResponse(pages[i])

    monkeypatch.setattr(polygon_feed.httpx, "AsyncClient", lambda *a, **k: _FakeClient())


_PAGE_1 = {
    "results": [
        {"ticker": "AAPL", "name": "Apple Inc.", "type": "CS"},
        {"ticker": "ZZPF", "name": "Zebra 6% Preferred", "type": "PFD"},
    ],
    "next_url": "https://vendor/page2",
}
_PAGE_2 = {"results": [{"ticker": "ZZZ", "name": "Zzz Corp", "type": "CS"}], "next_url": None}


async def test_a_full_walk_is_complete_and_lists_every_type(monkeypatch):
    _install_fake_vendor(monkeypatch, [_PAGE_1, _PAGE_2])
    found = await discover_active_us_tickers()
    assert [r["symbol"] for r in found] == ["AAPL", "ZZZ"]
    assert found.complete is True
    assert found.active_symbols == {"AAPL", "ZZPF", "ZZZ"}, (
        "a PFD-typed listing is still trading; the active set must hold it"
    )


async def test_a_failed_page_makes_the_walk_incomplete(monkeypatch):
    _install_fake_vendor(monkeypatch, [_PAGE_1, None])
    found = await discover_active_us_tickers()
    assert [r["symbol"] for r in found] == ["AAPL"]
    assert found.complete is False, (
        "a walk that broke off on a failed page reported itself complete, so "
        "every symbol after the failure would read as delisted"
    )


async def test_a_binding_cap_makes_the_walk_incomplete(monkeypatch):
    _install_fake_vendor(monkeypatch, [_PAGE_1, _PAGE_2])
    found = await discover_active_us_tickers(max_tickers=1)
    assert found.complete is False


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


async def test_complete_walk_retires_a_missing_equity(monkeypatch, caplog):
    await _seed(_row("ZZLIVE"), _row("ZZDEAD"), _row("ZZFUND", "etf"))
    _patch_discovery(monkeypatch, _walk(["ZZLIVE", "ZZFUND"]))
    with caplog.at_level(logging.INFO):
        await sp._refresh_universe()

    assert await _delisted_at("ZZDEAD") is not None, (
        "a complete walk that no longer lists the symbol left it unretired"
    )
    assert await _delisted_at("ZZLIVE") is None
    assert await _delisted_at("ZZFUND") is None
    line = next(r.getMessage() for r in caplog.records
                if r.getMessage().startswith("universe.delisting "))
    assert "retired=1" in line and "ZZDEAD" in line


async def test_incomplete_walk_retires_nothing(monkeypatch):
    await _seed(_row("ZZLIVE"), _row("ZZDEAD"))
    _patch_discovery(monkeypatch, _walk(["ZZLIVE"], complete=False))
    await sp._refresh_universe()
    assert await _delisted_at("ZZDEAD") is None


async def test_a_plain_list_counts_as_incomplete(monkeypatch):
    """Every older test double returns a plain list; none may retire."""
    await _seed(_row("ZZLIVE"), _row("ZZDEAD"))
    _patch_discovery(monkeypatch, [{"symbol": "ZZLIVE", "name": "ZZLIVE Corp",
                                    "sector": "Unknown", "asset_class": "equity"}])
    await sp._refresh_universe()
    assert await _delisted_at("ZZDEAD") is None


async def test_below_plausible_size_retires_nothing(monkeypatch):
    await _seed(_row("ZZLIVE"), _row("ZZDEAD"))
    short_pad = frozenset(list(_PAD)[: delisting.MIN_PLAUSIBLE_ACTIVE - 10])
    _patch_discovery(monkeypatch, _walk(["ZZLIVE"], pad=short_pad))
    await sp._refresh_universe()
    assert await _delisted_at("ZZDEAD") is None, (
        "a walk far smaller than the market was trusted as complete"
    )


async def test_safety_cap_trips_and_retires_nothing(monkeypatch, caplog):
    monkeypatch.setattr(delisting, "MAX_NEW_RETIREMENTS_FLOOR", 2)
    monkeypatch.setattr(delisting, "MAX_NEW_RETIREMENT_FRACTION", 0.0)
    await _seed(_row("ZZLIVE"), _row("ZZDA"), _row("ZZDB"), _row("ZZDC"))
    _patch_discovery(monkeypatch, _walk(["ZZLIVE"]))
    with caplog.at_level(logging.ERROR):
        await sp._refresh_universe()

    for sym in ("ZZDA", "ZZDB", "ZZDC"):
        assert await _delisted_at(sym) is None, (
            "a run over the safety cap still retired rows"
        )
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("universe.delisting_capped would_retire=3 cap=2" in m for m in errors)


def test_cap_size_today():
    """11,828 stored equity+etf rows on 2026-09-19: the cap is 5%, ~592."""
    assert delisting.max_new_retirements(11_828) == 592
    assert delisting.max_new_retirements(100) == delisting.MAX_NEW_RETIREMENTS_FLOOR


async def test_reappearing_symbol_is_unretired_even_on_a_partial_walk(monkeypatch, caplog):
    await _seed(_row("ZZBACK", delisted_at=_STAMP))
    _patch_discovery(monkeypatch, _walk(["ZZBACK"], complete=False))
    with caplog.at_level(logging.WARNING):
        await sp._refresh_universe()
    assert await _delisted_at("ZZBACK") is None
    assert any("universe.delisting_restored restored=1 symbols=ZZBACK" in r.getMessage()
               for r in caplog.records)


async def test_crypto_and_futures_are_never_retired(monkeypatch):
    await _seed(
        _row("ZZLIVE"),
        _row("X:ZZCOINUSD", "crypto"),
        _row("ZZ=F", "future_commodity"),
    )
    _patch_discovery(monkeypatch, _walk(["ZZLIVE"]))
    await sp._refresh_universe()
    assert await _delisted_at("X:ZZCOINUSD") is None
    assert await _delisted_at("ZZ=F") is None


async def test_a_symbol_active_under_a_filtered_type_is_not_retired(monkeypatch):
    """ZZPF is stored as an equity but the vendor types it PFD, so discovery
    drops it from the scoreable rows. It is still trading."""
    await _seed(_row("ZZLIVE"), _row("ZZPF"))
    _patch_discovery(monkeypatch, _walk(["ZZLIVE"], extra_active={"ZZPF"}))
    await sp._refresh_universe()
    assert await _delisted_at("ZZPF") is None, (
        "a listing the type filter dropped was retired as if it had stopped trading"
    )


async def test_sheet_ingest_does_not_unretire(monkeypatch):
    from app.services.sheet_feed import parse_all_signals_csv, upsert_tickers

    await _seed(_scored("OXY", delisted_at=_STAMP))
    csv = (
        "Ticker,Type,Asset Class,Strategy,Conviction,Score,Raw Score,Signal,"
        "Verdict,Action,Hold Duration,Price,Above 200DMA,Market Regime,Beats SPY?,"
        "Momentum Quality,3M Return %,6M Return %,1Y Return %,RS vs SPY 3M %,"
        "RS vs SPY 6M %,RS vs SPY 1Y %,RS vs Sector 3M %,Near 52W High %\n"
        "OXY,STOCK,Stock,MOMENTUM A+,A+,100,142,BUY NOW,Strong Buy,"
        "Strong Buy & Hold,6-12 months,59.62,TRUE,STRONG BULL,Yes (+32.8%),"
        "All 3 positive,30.4,43.4,40.4,21.9,32.8,13.8,19.1,99.5\n"
    )
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(csv))
    assert await _delisted_at("OXY") is not None


# ---------------------------------------------------------------------------
# A retired row leaves every live surface
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded_pair():
    """One listed and one retired row, identical otherwise."""
    await _seed(_scored("ZZLIVE", 70.0), _scored("ZZDEAD", 75.8, delisted_at=_STAMP))
    yield
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(("ZZLIVE", "ZZDEAD"))))


@pytest.fixture
def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_retired_row_leaves_the_snapshot_universe(seeded_pair):
    await _seed(_row("ZZNEWDEAD", delisted_at=_STAMP), _row("ZZNEW"))
    await universe_mod.refresh_active_universe()
    listed = {row[0] for row in universe_mod.active_universe()}
    assert "ZZLIVE" in listed and "ZZNEW" in listed
    assert "ZZDEAD" not in listed, "a retired scored row is still snapshotted"
    assert "ZZNEWDEAD" not in listed, "a retired unscored row is still bootstrapped"


async def test_retired_row_leaves_the_ranked_surfaces(seeded_pair, client):
    async with client:
        scanner = (await client.get("/api/scanner")).json()
        search = (await client.get("/api/search?q=ZZ")).json()
        public = (await client.get("/api/public/signals?limit=100")).json()
        sitemap = (await client.get("/api/public/top-tickers?limit=100")).json()

    scanner_syms = {r["symbol"] for r in scanner["items"]}
    search_syms = {r["symbol"] for r in search["results"]}
    public_syms = {r["symbol"] for r in public["items"]}
    for name, syms in (("scanner", scanner_syms), ("search", search_syms),
                       ("public signals", public_syms),
                       ("sitemap", set(sitemap["symbols"]))):
        assert "ZZLIVE" in syms, f"{name}: the control row is missing, test is void"
        assert "ZZDEAD" not in syms, f"{name} still lists a retired row"


async def test_retired_row_leaves_the_factor_passes(seeded_pair):
    at = datetime.now(UTC)
    for col in (Ticker.last_smart_money_at, Ticker.last_fundamentals_at):
        picked = await sp._select_factor_symbols(col, 10, now=at)
        assert "ZZLIVE" in picked
        assert "ZZDEAD" not in picked, (
            f"the {col.key} pass still spends a vendor request on a retired row"
        )


async def test_retired_row_is_not_archived(seeded_pair):
    from app.services.score_snapshots import capture_score_snapshots

    day = date(2026, 9, 18)  # a Friday, a trading day
    async with session_scope() as s:
        await capture_score_snapshots(s, day)
    async with session_scope() as s:
        archived = set((await s.execute(
            select(ScoreSnapshot.symbol).where(ScoreSnapshot.snapshot_date == day)
        )).scalars().all())
    assert "ZZLIVE" in archived
    assert "ZZDEAD" not in archived


async def test_ticker_endpoint_answers_404_with_the_reason(seeded_pair, client):
    async with client:
        r = await client.get("/api/ticker/ZZDEAD")
        live = await client.get("/api/ticker/ZZLIVE")
    assert live.status_code == 200
    assert r.status_code == 404
    assert r.json()["detail"] == (
        "No longer trading: ZZDEAD was not in our data vendor's list of active "
        "US listings on 19 September 2026. Its last score is no longer updated."
    )
    assert r.json()["detail"].startswith(delisting.RETIRED_PREFIX)


async def test_record_rows_for_a_retired_symbol_still_render(client):
    """Retiring a row must not touch the record: TOI was listed 1-5 June 2026
    and, if retired, those entries stay on /scorecard as they are."""
    from app.models import DailyScorecardEntry

    await _seed(_scored("ZZTOI", 66.0, delisted_at=_STAMP))
    async with session_scope() as s:
        s.add(DailyScorecardEntry(as_of=date(2026, 6, 1), symbol="ZZTOI", rank=7,
                                  score_at_flag=100.0, price_at_flag=5.0))
    async with client:
        r = await client.get("/api/scorecard/symbol/ZZTOI")
        whole = await client.get("/api/scorecard")
    assert r.status_code == 200
    assert [row["as_of"] for row in r.json()["rows"]] == ["2026-06-01"]
    assert whole.status_code == 200
