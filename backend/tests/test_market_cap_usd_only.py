"""Ticker.market_cap holds US dollars, or nothing.

Finnhub's /stock/profile2 reports `marketCapitalization` in MILLIONS of the
company's FILING currency, which it names in the same payload's `currency`
field. The profile adapter stored the figure without that field and the
populator multiplied it by 1e6 as if it were dollars, so a foreign filer's cap
was published in its home currency with a "$" in front: a Korean filer read
over $1,000T (won), a Taiwanese one $61.6T (new Taiwan dollars), a Japanese one
$36.3T (yen). Smaller currencies were wrong by less and looked plausible
(rupees, reais, Canadian dollars), so no size ceiling can catch them.

The rule this file pins:

  * the profile carries its currency, upper-cased;
  * a cap is seeded only when that currency is USD; a non-USD or missing
    currency seeds nothing, and the row keeps its NULL (an em-dash);
  * a cap of zero is not a reading, and a listing that is not a company's
    common shares (a note, a preferred) takes no cap, because the vendor's
    figure for it is its issuer's;
  * the backfill reaches equities before funds, and skips non-common rows, so
    the refill after migration 0078 converges;
  * migration 0078 clears every stored cap once, and only that column.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa

from app.db import session_scope
from app.models import Ticker
from app.services import finnhub_feed
from app.workers import signal_publisher as sp

# ---------------------------------------------------------------------------
# A stand-in for Finnhub /stock/profile2
# ---------------------------------------------------------------------------


class _FakeResp:
    status_code = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


def _profile_client(payloads: dict[str, dict[str, Any]], calls: list[str]):
    """An httpx.AsyncClient stand-in answering profile2 per symbol."""

    class _Client:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_a: Any) -> bool:
            return False

        async def get(self, url: str, params: dict[str, Any] | None = None, **_k: Any):
            assert url.endswith("/stock/profile2"), url
            sym = (params or {})["symbol"]
            calls.append(sym)
            return _FakeResp(payloads.get(sym, {}))

    return _Client


def _payload(currency: str | None, cap_millions: float, name: str = "Zz Co") -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": name,
        "finnhubIndustry": "Semiconductors",
        "marketCapitalization": cap_millions,
        "country": "ZZ",
        "exchange": "NEW YORK STOCK EXCHANGE, INC.",
        "ipo": "1997-10-09",
    }
    if currency is not None:
        body["currency"] = currency
    return body


@pytest.fixture
def feed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """finnhub_feed with a key, a private disk cache and fresh in-process caches.

    Returns a function that installs the profile2 answers and hands back the
    list of symbols actually requested from the vendor.
    """
    monkeypatch.setattr(finnhub_feed.settings, "finnhub_api_key", "test_key", raising=False)
    monkeypatch.setattr(finnhub_feed, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(finnhub_feed, "_MARKET_CAP_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_FUND_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_NO_FUNDAMENTALS", set())

    def install(payloads: dict[str, dict[str, Any]]) -> list[str]:
        calls: list[str] = []
        monkeypatch.setattr(finnhub_feed.httpx, "AsyncClient", _profile_client(payloads, calls))
        return calls

    return install


# ---------------------------------------------------------------------------
# 1. The profile adapter and the seed
# ---------------------------------------------------------------------------


async def test_a_krw_profile_seeds_no_cap(feed) -> None:
    feed({"ZZKRW": _payload("KRW", 1_230_324_927.73)})

    profile = await finnhub_feed.fetch_company_profile("ZZKRW")

    assert profile is not None
    assert profile["currency"] == "KRW"
    assert finnhub_feed.get_cached_market_cap("ZZKRW") is None, (
        "a cap stated in won was seeded as dollars"
    )


async def test_a_usd_profile_seeds_the_value_times_one_million(feed) -> None:
    feed({"ZZUSD": _payload("USD", 3_512_345.5)})

    profile = await finnhub_feed.fetch_company_profile("ZZUSD")

    assert profile is not None
    assert profile["currency"] == "USD"
    assert finnhub_feed.get_cached_market_cap("ZZUSD") == pytest.approx(3_512_345.5e6)


async def test_a_profile_with_no_currency_seeds_no_cap(feed) -> None:
    """No currency means we cannot say what unit the figure is in."""
    feed({"ZZNONE": _payload(None, 25_000.0)})

    profile = await finnhub_feed.fetch_company_profile("ZZNONE")

    assert profile is not None
    assert profile["currency"] == ""
    assert finnhub_feed.get_cached_market_cap("ZZNONE") is None


async def test_the_currency_is_stored_upper_cased(feed) -> None:
    feed({"ZZLOW": _payload(" usd ", 12_000.0)})

    profile = await finnhub_feed.fetch_company_profile("ZZLOW")

    assert profile is not None
    assert profile["currency"] == "USD"
    assert finnhub_feed.get_cached_market_cap("ZZLOW") == pytest.approx(12_000.0e6)


async def test_a_zero_cap_is_not_seeded(feed) -> None:
    """Some funds answer 0. A "$0" cap is a number nobody gave us."""
    feed({"ZZZERO": _payload("USD", 0.0)})

    await finnhub_feed.fetch_company_profile("ZZZERO")

    assert finnhub_feed.get_cached_market_cap("ZZZERO") is None


async def test_the_cached_profile_path_applies_the_same_rule(feed) -> None:
    """The cache-hit path seeds too (it has to: the in-process cap cache is
    empty after every restart). It must not seed a non-USD figure either."""
    calls = feed({})
    finnhub_feed._save_cache(
        "profile_ZZTWD",
        {"sector": "Semiconductors", "name": "Zz Twd", "market_cap": 61_589_376.7,
         "currency": "TWD", "country": "TW", "exchange": "", "ipo": ""},
    )
    finnhub_feed._save_cache(
        "profile_ZZUSDC",
        {"sector": "Semiconductors", "name": "Zz Usd", "market_cap": 4_514_709.3,
         "currency": "USD", "country": "US", "exchange": "", "ipo": ""},
    )

    await finnhub_feed.fetch_company_profile("ZZTWD")
    await finnhub_feed.fetch_company_profile("ZZUSDC")

    assert calls == [], "a cached profile that states its currency was re-fetched"
    assert finnhub_feed.get_cached_market_cap("ZZTWD") is None
    assert finnhub_feed.get_cached_market_cap("ZZUSDC") == pytest.approx(4_514_709.3e6)


async def test_a_cached_profile_written_before_the_currency_field_is_fetched_again(
    feed,
) -> None:
    """A profile cached by the old adapter has no `currency` key. Trusting it
    would mean either seeding an unchecked figure or holding no cap for up to
    seven days; asking again answers the question."""
    calls = feed({"ZZOLD": _payload("TWD", 61_589_376.7)})
    finnhub_feed._save_cache(
        "profile_ZZOLD",
        {"sector": "Semiconductors", "name": "Zz Old", "market_cap": 61_589_376.7,
         "country": "TW", "exchange": "", "ipo": ""},
    )

    profile = await finnhub_feed.fetch_company_profile("ZZOLD")

    assert calls == ["ZZOLD"]
    assert profile is not None and profile["currency"] == "TWD"
    assert finnhub_feed.get_cached_market_cap("ZZOLD") is None


async def test_the_empty_negative_cache_is_still_honoured(feed) -> None:
    """`{}` is the adapter's "no such ticker" sentinel and has no currency by
    definition; it must not be mistaken for an old-shape profile."""
    calls = feed({})
    finnhub_feed._save_cache("profile_ZZGONE", {})

    assert await finnhub_feed.fetch_company_profile("ZZGONE") is None
    assert calls == []


async def test_a_listing_that_is_not_common_stock_takes_no_cap(feed) -> None:
    """A note or preferred answers with its issuer's cap (a class-M/N note
    showed its parent's $4.2T). Flagged before the fetch: nothing is seeded.
    Flagged after: the cached figure is dropped."""
    feed({
        "ZZNOTE": _payload("USD", 4_217_148.6),
        "ZZLATE": _payload("USD", 4_217_148.6),
    })
    finnhub_feed.set_no_fundamentals_symbols({"ZZNOTE"})

    await finnhub_feed.fetch_company_profile("ZZNOTE")
    await finnhub_feed.fetch_company_profile("ZZLATE")
    assert finnhub_feed.get_cached_market_cap("ZZNOTE") is None
    assert finnhub_feed.get_cached_market_cap("ZZLATE") == pytest.approx(4_217_148.6e6)

    finnhub_feed.set_no_fundamentals_symbols({"ZZNOTE", "ZZLATE"})
    assert finnhub_feed.get_cached_market_cap("ZZLATE") is None


# ---------------------------------------------------------------------------
# 2. The backfill, through the real profile adapter
# ---------------------------------------------------------------------------


async def _no_sleep(*_a: Any, **_k: Any) -> None:
    return None


async def _seed_rows(*rows: dict[str, Any]) -> None:
    async with session_scope() as s:
        for row in rows:
            s.add(Ticker(**{"sector": "Information Technology", **row}))


async def _caps(*symbols: str) -> dict[str, float | None]:
    async with session_scope() as s:
        result = await s.execute(
            sa.select(Ticker.symbol, Ticker.market_cap).where(Ticker.symbol.in_(symbols))
        )
        return dict(result.all())


async def test_the_backfill_writes_a_usd_cap_and_leaves_a_foreign_one_null(
    feed, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sp.asyncio, "sleep", _no_sleep)
    feed({
        "ZZUSD": _payload("USD", 2_500.0),
        "ZZKRW": _payload("KRW", 1_230_324_927.73),
        "ZZNONE": _payload(None, 900.0),
    })
    await _seed_rows(
        {"symbol": "ZZUSD", "name": "Zz Usd", "asset_class": "equity", "price": 10.0, "volume": 1_000},
        {"symbol": "ZZKRW", "name": "Zz Krw", "asset_class": "equity", "price": 10.0, "volume": 2_000},
        {"symbol": "ZZNONE", "name": "Zz None", "asset_class": "equity", "price": 10.0, "volume": 3_000},
    )

    await sp._backfill_market_cap(cap=10)

    assert await _caps("ZZUSD", "ZZKRW", "ZZNONE") == {
        "ZZUSD": pytest.approx(2_500.0e6),
        "ZZKRW": None,
        "ZZNONE": None,
    }


async def test_the_backfill_reaches_equities_before_funds_and_skips_non_common(
    feed, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measured on production 2026-09-19: of the 2,500 rows the backfill took
    by dollar volume alone, 2,318 were funds and 123 crypto pairs that never
    receive a cap, so they sat at the head of every run. With every equity
    cap cleared, a dollar-volume-only order would never reach about 1,700 of
    the 6,012 equities. Equities first reaches them all in three to four."""
    monkeypatch.setattr(sp.asyncio, "sleep", _no_sleep)
    calls = feed({
        "ZZFUND": _payload("USD", 1_000.0),
        "ZZPREF": _payload("USD", 4_217_148.6),
        "ZZEQ": _payload("USD", 2_000.0),
    })
    await _seed_rows(
        # Most liquid, but a fund.
        {"symbol": "ZZFUND", "name": "Zz Fund", "asset_class": "etf",
         "price": 500.0, "volume": 90_000_000},
        # Liquid, but a preferred share: its issuer's cap is not its own.
        {"symbol": "ZZPREF", "name": "Zz Co 6.00% Series A Preferred", "asset_class": "equity",
         "price": 25.0, "volume": 80_000_000, "is_non_common": True},
        {"symbol": "ZZEQ", "name": "Zz Equity", "asset_class": "equity",
         "price": 10.0, "volume": 1_000},
    )

    await sp._backfill_market_cap(cap=1)

    assert calls == ["ZZEQ"]
    assert (await _caps("ZZEQ"))["ZZEQ"] == pytest.approx(2_000.0e6)

    # With budget to spare, the fund is still reached; the preferred never is.
    calls.clear()
    await sp._backfill_market_cap(cap=10)
    assert calls == ["ZZFUND"]
    assert await _caps("ZZFUND", "ZZPREF") == {
        "ZZFUND": pytest.approx(1_000.0e6),
        "ZZPREF": None,
    }


# ---------------------------------------------------------------------------
# 3. Migration 0078: clear every stored cap once
# ---------------------------------------------------------------------------

_MIGRATION = (
    Path(__file__).resolve().parent.parent
    / "alembic" / "versions" / "20260919_0078_market_cap_usd_only.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("mig_0078", _MIGRATION)
    assert spec and spec.loader, f"migration not found at {_MIGRATION}"
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    return mig


def test_the_migration_chains_onto_the_current_head() -> None:
    mig = _load_migration()
    assert mig.revision == "0078_market_cap_usd_only"
    assert len(mig.revision) <= 32, "alembic_version.version_num is VARCHAR(32)"
    assert mig.down_revision == "0075_ticker_quote_at"


def test_the_migration_clears_every_cap_and_nothing_else_and_downgrades_cleanly() -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    mig = _load_migration()
    stamp = "2026-09-18 21:00:00"
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE tickers (symbol VARCHAR(20) PRIMARY KEY, asset_class VARCHAR(20), "
            "market_cap FLOAT, price FLOAT, updated_at VARCHAR(32))"
        ))
        conn.execute(
            sa.text(
                "INSERT INTO tickers VALUES (:s, :a, :m, :p, :u)"
            ),
            [
                {"s": "ZZKRW", "a": "equity", "m": 1.23e15, "p": 110.0, "u": stamp},
                {"s": "ZZUSD", "a": "equity", "m": 4.5e12, "p": 230.0, "u": stamp},
                {"s": "ZZETN", "a": "etf", "m": 6.6e10, "p": 40.0, "u": stamp},
                {"s": "ZZNULL", "a": "equity", "m": None, "p": 5.0, "u": stamp},
                {"s": "X:ZZUSD", "a": "crypto", "m": None, "p": 1.0, "u": stamp},
            ],
        )
        mig.op = Operations(MigrationContext.configure(conn))

        def _rows() -> dict[str, tuple[Any, ...]]:
            return {
                r[0]: tuple(r[1:])
                for r in conn.execute(sa.text(
                    "SELECT symbol, market_cap, price, updated_at FROM tickers"
                ))
            }

        mig.upgrade()
        after = _rows()
        assert {s: r[0] for s, r in after.items()} == dict.fromkeys(after), (
            "every stored cap came through the unchecked path and must be cleared"
        )
        # Only market_cap moved: prices and the freshness stamp are untouched.
        assert {s: r[1:] for s, r in after.items()} == {
            "ZZKRW": (110.0, stamp), "ZZUSD": (230.0, stamp), "ZZETN": (40.0, stamp),
            "ZZNULL": (5.0, stamp), "X:ZZUSD": (1.0, stamp),
        }

        # Forward-only data repair: the downgrade runs and restores nothing.
        mig.downgrade()
        assert _rows() == after
    engine.dispose()

