"""Ticker identity fields must be RECONCILED, not just written once.

`Ticker.name` and `Ticker.asset_class` had no repair path. Universe discovery
was insert-only, so the weekly pull of Polygon's reference data — the
authoritative source for both — was fetched and discarded for every symbol that
already existed. `_backfill_sectors` selected on `sector` and wrote only
`sector`. The snapshot tick creates new rows as `name=snap["symbol"]`, because a
snapshot payload carries no company name.

So whatever the FIRST writer guessed became permanent. Measured against
production on 2026-08-27, across all 2,463 live tickers:

  * 168 (6.8%) displayed a bare ticker symbol instead of a company name —
    ASML, PAYC, QLYS, ONTO, MT, OVV and 162 others.
  * SPY, QQQ, IWM, DIA, VTI, GLD, SMH, XLK and ARKG were all typed
    `asset_class="equity"`. That is not cosmetic: `frontend/lib/filters.ts`
    buckets the scanner's asset-class filter off this column, so those ETFs
    were missing when a user filtered to ETFs, and `/t/{symbol}` renders the
    value directly, so SPY's own page read "Equity".

These tests pin the repair paths, and the NARROWNESS of the placeholder test —
a rule that overwrote real names would be a worse bug than the one it fixes.
"""

import pytest
from sqlalchemy import select  # noqa: F401  (kept for parity with sibling suites)

from app.db import session_scope
from app.models import Ticker
from app.workers.signal_publisher import _is_placeholder_name, _refresh_universe

# ---------------------------------------------------------------------------
# The placeholder predicate — the "safe to overwrite" test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", [None, "", "   ", "AAPL", "aapl", " AAPL "])
def test_placeholder_names_are_detected(name):
    assert _is_placeholder_name(name, "AAPL") is True


@pytest.mark.parametrize(
    "name",
    [
        "Apple Inc.",
        "ASML Holding N.V.",
        "AAPL Corp",  # starts with the symbol but carries more
        "Alphabet Inc.",
    ],
)
def test_real_names_are_never_treated_as_placeholders(name):
    """The predicate gates an OVERWRITE, so a false positive destroys a real
    company name. It must be an exact match on the symbol — never a prefix,
    never a substring test."""
    assert _is_placeholder_name(name, "AAPL") is False


# ---------------------------------------------------------------------------
# Universe refresh reconciles existing rows
# ---------------------------------------------------------------------------

_TEST_SYMBOLS = ["ZZRECON", "ZZETF", "ZZREAL", "ZZSECT"]


@pytest.fixture
async def cleanup_tickers():
    yield
    async with session_scope() as s:
        for sym in _TEST_SYMBOLS:
            t = await s.get(Ticker, sym)
            if t is not None:
                await s.delete(t)
        await s.commit()


def _row(symbol, name, sector="Unknown", asset_class="equity"):
    return Ticker(symbol=symbol, name=name, sector=sector, asset_class=asset_class)


def _patch_discovery(monkeypatch, rows):
    async def fake_discover(*_a, **_k):
        return rows

    monkeypatch.setattr(
        "app.services.polygon_feed.discover_active_us_tickers", fake_discover
    )


@pytest.mark.asyncio
async def test_refresh_repairs_placeholder_name_and_wrong_asset_class(
    monkeypatch, cleanup_tickers
):
    async with session_scope() as s:
        s.add(_row("ZZRECON", "ZZRECON"))
        s.add(_row("ZZETF", "ZZETF"))
        await s.commit()

    _patch_discovery(
        monkeypatch,
        [
            {
                "symbol": "ZZRECON",
                "name": "Zebra Recon Corp.",
                "sector": "Unknown",
                "asset_class": "equity",
            },
            {
                "symbol": "ZZETF",
                "name": "Zebra Index ETF",
                "sector": "Unknown",
                "asset_class": "etf",
            },
        ],
    )
    await _refresh_universe()

    async with session_scope() as s:
        a = await s.get(Ticker, "ZZRECON")
        b = await s.get(Ticker, "ZZETF")
        assert a.name == "Zebra Recon Corp.", (
            "an existing row's placeholder name was not repaired — the weekly "
            "reference pull is still being fetched and discarded"
        )
        assert b.asset_class == "etf", (
            "an existing row's wrong asset_class was not corrected, so this ETF "
            "stays invisible to the scanner's ETF filter"
        )


@pytest.mark.asyncio
async def test_refresh_never_overwrites_a_real_name(monkeypatch, cleanup_tickers):
    """The sheet and Finnhub also write this column and may hold a better name
    than Polygon does. Repair the blank case only."""
    async with session_scope() as s:
        s.add(_row("ZZREAL", "Zebra Real Holdings Inc."))
        await s.commit()

    _patch_discovery(
        monkeypatch,
        [
            {
                "symbol": "ZZREAL",
                "name": "ZEBRA REAL HLDGS",
                "sector": "Unknown",
                "asset_class": "equity",
            }
        ],
    )
    await _refresh_universe()

    async with session_scope() as s:
        t = await s.get(Ticker, "ZZREAL")
        assert t.name == "Zebra Real Holdings Inc."


@pytest.mark.asyncio
async def test_refresh_never_writes_sector(monkeypatch, cleanup_tickers):
    """Discovery always reports sector="Unknown" — a real per-ticker sector
    costs its own rate-limited call — so reconciling sector here would erase
    whatever _backfill_sectors worked out."""
    async with session_scope() as s:
        s.add(_row("ZZSECT", "Zebra Sector Co.", sector="Health Care"))
        await s.commit()

    _patch_discovery(
        monkeypatch,
        [
            {
                "symbol": "ZZSECT",
                "name": "Zebra Sector Co.",
                "sector": "Unknown",
                "asset_class": "equity",
            }
        ],
    )
    await _refresh_universe()

    async with session_scope() as s:
        t = await s.get(Ticker, "ZZSECT")
        assert t.sector == "Health Care", "the refresh clobbered a real sector"


# ---------------------------------------------------------------------------
# Source-level guards for the two paths that are awkward to drive end-to-end
# ---------------------------------------------------------------------------


def _code(fn) -> str:
    """Source with comments and docstrings stripped.

    This repo has repeatedly shipped assertions that passed against the
    explanatory comment sitting above the line they were meant to pin.
    """
    import ast
    import inspect
    import textwrap

    return ast.unparse(ast.parse(textwrap.dedent(inspect.getsource(fn))))


def test_sector_backfill_also_selects_and_repairs_placeholder_names():
    """A row whose sector was already good but whose name was still the
    placeholder was invisible to this pass, because the selection only ever
    asked about sector. That is precisely how 168 rows got stuck. The profile
    call it already makes returns the company name, so the repair is free."""
    from app.workers.signal_publisher import _backfill_sectors

    code = _code(_backfill_sectors)
    assert "Ticker.name == Ticker.symbol" in code, (
        "the backfill still cannot see a row that has a sector but no name"
    )
    assert "Ticker.name.is_(None)" in code
    assert "_is_placeholder_name" in code, (
        "the backfill does not gate the name write on the placeholder test, so "
        "it could overwrite a real name"
    )


def test_spy_key_stats_are_cached_from_the_benchmark_bars():
    """SPY is skipped in the per-symbol loop because its bars were already
    fetched as the RS benchmark. But that loop is also where the 52-week range
    and 30-day average volume are derived, so SPY silently had neither while
    every other major ETF did."""
    from app.workers.signal_publisher import _refresh_aggregates_cache

    code = _code(_refresh_aggregates_cache)
    assert "set_cached_bar_stats('SPY', compute_bar_stats(spy_bars))" in code, (
        "SPY still gets no key statistics, so the most-viewed symbol on the "
        "site renders em-dashes for its 52-week range and average volume"
    )
