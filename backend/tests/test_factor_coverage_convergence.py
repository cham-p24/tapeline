"""The composite must stop being a four-factor score for most of the universe.

MEASURED ON PRODUCTION 2026-09-07 (read-only SQL): of 7,417 scored tickers,
5,697 (77%) had BOTH `sub_fundamentals` AND `sub_smart_money` NULL. Of the
1,035 scored rows with market_cap >= $10B, 1,001 (97%) had both null — NVDA,
AAPL, MSFT, AMZN, META, TSLA and SPY among them. Coverage by first letter:
A 462/948, B 427/749, C 429/870, then D 69/491, H 3/368, J 0/223, S 6/917,
Y 0/77, Z 0/92.

A missing factor scores as NEUTRAL 50 by design (services/score.py). Those two
factors carry 30% of the composite between them, so a both-null row's composite
cannot exceed 85. The best any both-null row had ever reached was 80.2 against
a top-ten cutoff of 81.1 — which is the entire reason the public record
contained no mega-caps.

THREE FAILURES STACKED:

1. `_FUND_SCORE_CACHE` and `_SMART_MONEY_SCORE_CACHE` are process-local dicts,
   so every deploy emptied them, and nothing read the persisted values back off
   the Ticker row. The first tick after each restart recomputed the composite
   from a cache miss for every symbol.
2. Both passes selected the top `ACTIVE_UNIVERSE_SIZE` rows by dollar-volume —
   a ranking over the whole table, with no reference to what was already known
   — so a restart re-fetched the same rows and the covered set could not grow.
3. Both passes sat at the BACK of a serial ~2h Finnhub chain whose completion
   latches are in-memory globals, so on a deploy-heavy day they were never
   reached at all.

These tests drive the real selection and the real passes against a seeded
table. The one source-level test here reads the AST, not the text, so no
comment or docstring explaining the fix can vouch for it.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import pathlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.db import session_scope
from app.models import Ticker
from app.workers import signal_publisher

# NO `pytestmark = pytest.mark.anyio` — pytest.ini sets `asyncio_mode = auto`.
# See the note in test_aggregates_coverage_rotation.py for what adding it did.


async def _seed(rows: list[dict[str, Any]]) -> None:
    async with session_scope() as s:
        for row in rows:
            s.add(Ticker(name=f"{row['symbol']} Inc", asset_class="equity", **row))


@pytest.fixture(autouse=True)
def _no_pacing_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """The passes sleep 1.1s per symbol to stay under Finnhub's 60/min.

    Patched out so these tests exercise the selection and stamping logic in
    milliseconds. monkeypatch restores the real sleep at teardown.
    """
    real_sleep = asyncio.sleep

    async def _fast(delay: float, *a: Any, **kw: Any) -> Any:
        return await real_sleep(0, *a, **kw)

    monkeypatch.setattr(asyncio, "sleep", _fast)


# ---------------------------------------------------------------------------
# Selection: gaps first, biggest missing names first, and it MOVES.
# ---------------------------------------------------------------------------


async def test_a_stamped_symbol_drops_out_of_the_next_runs_selection() -> None:
    """The load-bearing one — this is what "resumes" means.

    Under the old ranking the top rows by dollar-volume came back every run,
    forever, whatever had already been fetched. Here the first run's three
    symbols must be gone from the gap slice on the second run, and the second
    run must reach names the first never touched.
    """
    now = datetime.now(UTC)
    await _seed([
        {"symbol": f"S{i}", "price": 100.0, "volume": 1_000_000 - i}
        for i in range(6)
    ])

    first = await signal_publisher._select_factor_symbols(
        Ticker.last_fundamentals_at, 3,
    )
    assert first == ["S0", "S1", "S2"], "gaps must be attempted most-traded first"

    await signal_publisher._stamp_factor_attempts(
        "last_fundamentals_at", first, now,
    )

    second = await signal_publisher._select_factor_symbols(
        Ticker.last_fundamentals_at, 3,
    )
    assert {"S3", "S4"} <= set(second), (
        f"the second run must advance to symbols never attempted, not re-fetch "
        f"the same top-of-book slice; got {second}"
    )
    # Exactly one slot goes back to the staleness rotation (see
    # _FACTOR_ROTATION_RESERVE) — so the run is not required to be all-new, but it
    # IS required to be mostly new. Under the old dollar-volume ranking the
    # second run was ["S0", "S1", "S2"] again, forever.
    assert len(set(second) - set(first)) >= 2, (
        f"the frontier barely moved: first={first}, second={second}"
    )


async def test_the_gap_slice_leads_with_the_most_traded_missing_names() -> None:
    """Dollar-volume is the primary key; market cap is only a tie-break.

    Finnhub reports some foreign ADRs' market caps in local currency — a real
    production row carries a "cap" of $1.2 quadrillion — so a cap-first
    ordering would lead with arithmetic nonsense instead of with NVDA.
    """
    await _seed([
        {"symbol": "NVDA", "price": 229.0, "volume": 135_000_000,
         "market_cap": 5.19e12},
        {"symbol": "ADRX", "price": None, "volume": None,
         "market_cap": 1.23e15},   # cap reported in local currency
        {"symbol": "TINY", "price": 1.0, "volume": 100},
    ])
    picked = await signal_publisher._select_factor_symbols(
        Ticker.last_fundamentals_at, 3,
    )
    assert picked[0] == "NVDA"
    assert picked.index("TINY") < picked.index("ADRX"), (
        "a symbol with a real dollar-volume read must outrank one with none, "
        "however large the vendor claims its market cap is"
    )


async def test_part_of_every_run_is_reserved_for_the_staleness_rotation() -> None:
    """Gaps must not be able to starve refreshes forever.

    Universe discovery adds NULL rows every week, so "no gaps left" is not a
    state that reliably arrives — without a slice held back for already-attempted
    rows, a covered symbol's fundamentals could age indefinitely.
    """
    old = datetime.now(UTC) - timedelta(days=30)
    await _seed([
        {"symbol": f"G{i:02d}", "price": 100.0, "volume": 1_000_000 - i}
        for i in range(20)
    ] + [
        {"symbol": "STALE", "price": 100.0, "volume": 10,
         "last_fundamentals_at": old},
    ])
    picked = await signal_publisher._select_factor_symbols(
        Ticker.last_fundamentals_at, 10,
    )
    assert len(picked) == 10
    assert "STALE" in picked, (
        "with 20 gaps and a budget of 10, the oldest-stamped row must still "
        "get a slot — otherwise nothing covered is ever refreshed again"
    )


async def test_unused_rotation_budget_goes_back_to_gaps() -> None:
    """The rotation's slice is a reserve, not a hole in the budget.

    On the very first run nothing is stamped, so the rotation has nothing to
    do. Leaving a fifth of that run unspent — during exactly the phase this
    change exists to end — would be the wrong kind of caution.
    """
    await _seed([
        {"symbol": f"N{i:02d}", "price": 100.0, "volume": 1_000_000 - i}
        for i in range(10)
    ])
    picked = await signal_publisher._select_factor_symbols(
        Ticker.last_fundamentals_at, 10,
    )
    assert len(picked) == 10, (
        f"expected the full budget of 10 gaps, got {len(picked)}"
    )
    assert len(set(picked)) == 10, "selection must not return duplicates"


# ---------------------------------------------------------------------------
# The passes themselves: stamp on ATTEMPT, converge across runs.
# ---------------------------------------------------------------------------


async def _stamps(column: str) -> dict[str, datetime | None]:
    from sqlalchemy import select

    async with session_scope() as s:
        rows = (await s.execute(
            select(Ticker.symbol, getattr(Ticker, column))
        )).all()
    return dict(rows)  # type: ignore[arg-type]


async def test_a_symbol_the_vendor_has_nothing_for_is_not_refetched_forever(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stamped on ATTEMPT, not on success.

    Most ETFs have no fundamentals for Finnhub to return. Stamping only on
    success leaves them indistinguishable from never-attempted, so they would
    sit at the head of the gap query on every future run and starve everything
    behind them — the same starvation `last_aggregates_at` was added to end.
    """
    await _seed([
        {"symbol": "REAL", "price": 100.0, "volume": 1_000_000},
        {"symbol": "ETFX", "price": 100.0, "volume": 900_000},
    ])
    monkeypatch.setattr(
        "app.services.universe.ACTIVE_UNIVERSE_SIZE", 2, raising=False,
    )

    async def _fake_financials(sym: str) -> dict[str, float] | None:
        return {"roe": 20.0} if sym == "REAL" else None

    monkeypatch.setattr(
        "app.services.finnhub_feed.fetch_basic_financials", _fake_financials,
    )

    await signal_publisher._refresh_fundamentals_cache()

    stamps = await _stamps("last_fundamentals_at")
    assert stamps["ETFX"] is not None, (
        "a symbol the vendor returned nothing for must still be recorded as "
        "attempted — 'we asked and there is nothing' is an answer"
    )
    assert stamps["REAL"] is not None

    # And the consequence that matters: with both attempted, the gap set is
    # empty, so a third symbol added tomorrow is not stuck behind an ETF the
    # vendor will never have anything for.
    await _seed([{"symbol": "NEWB", "price": 100.0, "volume": 1}])
    assert await signal_publisher._select_factor_symbols(
        Ticker.last_fundamentals_at, 1,
    ) == ["NEWB"], (
        "a symbol the vendor has nothing for must stop counting as a gap, or "
        "it outranks every genuinely unattempted symbol forever"
    )


async def test_two_consecutive_fundamentals_runs_cover_different_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Convergence: coverage grows run over run instead of standing still."""
    await _seed([
        {"symbol": f"S{i:02d}", "price": 100.0, "volume": 1_000_000 - i}
        for i in range(6)
    ])
    monkeypatch.setattr(
        "app.services.universe.ACTIVE_UNIVERSE_SIZE", 3, raising=False,
    )
    fetched: list[str] = []

    async def _fake_financials(sym: str) -> dict[str, float]:
        fetched.append(sym)
        return {"roe": 15.0}

    monkeypatch.setattr(
        "app.services.finnhub_feed.fetch_basic_financials", _fake_financials,
    )

    await signal_publisher._refresh_fundamentals_cache()
    first = set(fetched)
    fetched.clear()
    await signal_publisher._refresh_fundamentals_cache()
    second = set(fetched)

    assert second - first, (
        f"the second run reached no new symbol (first={sorted(first)}, "
        f"second={sorted(second)}) — the frontier is not advancing"
    )
    assert len(first | second) > len(first), "coverage must grow across runs"


async def test_the_insider_pass_stamps_its_own_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two independent frontiers. A shared stamp would let whichever pass ran
    first mark the other's work done."""
    await _seed([{"symbol": "INSD", "price": 100.0, "volume": 1_000_000}])
    monkeypatch.setattr(
        "app.services.universe.ACTIVE_UNIVERSE_SIZE", 1, raising=False,
    )

    async def _fake_txns(sym: str, days_back: int = 90) -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(
        "app.services.finnhub_feed.fetch_insider_transactions", _fake_txns,
    )

    await signal_publisher._refresh_insider_cache()

    assert (await _stamps("last_smart_money_at"))["INSD"] is not None
    assert (await _stamps("last_fundamentals_at"))["INSD"] is None, (
        "the insider pass must not stamp the fundamentals frontier"
    )


# ---------------------------------------------------------------------------
# Warming: what was measured yesterday must not read as NEUTRAL today.
# ---------------------------------------------------------------------------


async def test_warm_restores_both_factor_caches_from_the_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deploy emptied the dicts; the values were on the row all along."""
    from app.services import finnhub_feed

    monkeypatch.setattr(finnhub_feed, "_FUND_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})

    await _seed([
        {"symbol": "WARM", "sub_fundamentals": 77.5, "sub_smart_money": 61.0},
        {"symbol": "HALF", "sub_fundamentals": 42.0},
        {"symbol": "NONE"},
    ])

    assert finnhub_feed.get_cached_score("WARM") is None

    funds, smart = await finnhub_feed.warm_factor_caches_from_db()

    assert finnhub_feed.get_cached_score("WARM") == 77.5
    assert finnhub_feed.get_cached_smart_money_score("WARM") == 61.0
    assert finnhub_feed.get_cached_score("HALF") == 42.0
    assert finnhub_feed.get_cached_smart_money_score("HALF") is None
    assert finnhub_feed.get_cached_score("NONE") is None
    assert (funds, smart) == (2, 1)


# One real sheet row, from the ALL SIGNALS fixture in test_sheet_feed.py.
_SHEET_CSV = (
    "Ticker,Type,Asset Class,Strategy,Conviction,Score,Raw Score,Signal,"
    "Verdict,Action,Hold Duration,Price,Above 200DMA,Market Regime,Beats SPY?,"
    "Momentum Quality,3M Return %,6M Return %,1Y Return %,RS vs SPY 3M %,"
    "RS vs SPY 6M %,RS vs SPY 1Y %,RS vs Sector 3M %,Near 52W High %\n"
    "OXY,STOCK,Stock,MOMENTUM A+,A+,100,142,BUY NOW,Strong Buy,"
    "Strong Buy & Hold,6-12 months,59.62,TRUE,STRONG BULL,Yes (+32.8%),"
    "All 3 positive,30.4,43.4,40.4,21.9,32.8,13.8,19.1,99.5\n"
)


async def _factors(symbol: str) -> tuple[float | None, float | None]:
    from sqlalchemy import select

    async with session_scope() as s:
        row = (await s.execute(
            select(Ticker.sub_fundamentals, Ticker.sub_smart_money)
            .where(Ticker.symbol == symbol)
        )).one()
    return row.sub_fundamentals, row.sub_smart_money


async def _set_factors(symbol: str, fund: float, smart: float) -> None:
    from sqlalchemy import update as sa_update

    async with session_scope() as s:
        await s.execute(
            sa_update(Ticker).where(Ticker.symbol == symbol)
            .values(sub_fundamentals=fund, sub_smart_money=smart)
        )


async def test_a_cold_cache_blanks_the_sheet_paths_two_factors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The warm is not redundant with `_merged_factor_set`. This is why.

    The tick's own merge keeps a stored sub-score when the incoming one is
    None, so a cold cache cannot blank a market-fed row. The SHEET path has no
    such protection and must not get one: `upsert_tickers` writes all six
    sub-scores unconditionally INCLUDING None, on purpose, because writing only
    non-None values would leave a stale 70 printed beside a composite computed
    as if that factor were 50 (PRs #225/#226).

    So for every sheet-governed symbol the cache is the only thing between "we
    measured this yesterday" and NEUTRAL 50 in two of six slots — and the
    process that serves the sheet-changed webhook is the API, where the daily
    Finnhub chain never runs at all.
    """
    from app.services import finnhub_feed
    from app.services.sheet_feed import parse_all_signals_csv, upsert_tickers

    monkeypatch.setattr(finnhub_feed, "_FUND_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})

    await _seed([
        {"symbol": "OXY", "sub_fundamentals": 77.5, "sub_smart_money": 61.0},
    ])

    # THE HAZARD. Cold cache -> the refresh writes None over both.
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_SHEET_CSV))
    assert await _factors("OXY") == (None, None), (
        "the sheet refresh is expected to write None on a cache miss — if this "
        "ever stops being true the warm below is guarding nothing, and the "
        "stale-sub-score desync of PR #225 is back"
    )

    # THE FIX. Same refresh, cache warmed from the row first.
    await _set_factors("OXY", 77.5, 61.0)
    await finnhub_feed.warm_factor_caches_from_db()
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_SHEET_CSV))
    assert await _factors("OXY") == (77.5, 61.0), (
        "a factor measured yesterday and still stored on the row was written "
        "away as NEUTRAL by a sheet refresh"
    )


# ---------------------------------------------------------------------------
# Wiring. AST, not text — a comment describing the fix must not vouch for it.
# ---------------------------------------------------------------------------

_SRC = pathlib.Path(inspect.getfile(signal_publisher)).read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)


def _func(name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    for node in ast.walk(_TREE):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in signal_publisher")


def _call_order(node: ast.AST) -> list[str]:
    """Names of every function CALLED inside `node`, in source order.

    Sorted by position rather than taken in `ast.walk` order, which is
    breadth-first and only coincides with source order when the calls happen to
    be siblings. Calls, not awaits: `main` runs the tick as
    `asyncio.wait_for(tick(), ...)`, so the awaited name there is `wait_for`
    and an await-only scan would report that the tick is never called.
    """
    found: list[tuple[int, int, str]] = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        name = getattr(sub.func, "id", None) or getattr(sub.func, "attr", None)
        if name:
            found.append((sub.lineno, sub.col_offset, name))
    return [name for _, _, name in sorted(found)]


# The third failure — the two factor passes sitting at the BACK of the ~2h
# chain, so a deploy-heavy day never reached them — is guarded in
# test_worker_backfill_order.py, which owns the ordering question and carries
# both halves of its history. Not duplicated here.


def test_the_caches_are_warmed_before_the_first_tick() -> None:
    """Lazily warming is not enough: the FIRST tick after a restart rewrites
    the composite for the whole universe from whatever the caches hold."""
    body = _call_order(_func("main"))
    assert "warm_factor_caches_from_db" in body, (
        "main() must warm the factor caches from the DB on boot"
    )
    assert body.index("warm_factor_caches_from_db") < body.index("tick"), (
        "the warm must happen before the first tick, not after it"
    )


def test_the_api_process_warms_before_it_runs_a_sheet_refresh() -> None:
    """The OTHER process. fly.toml runs `api` and `worker` separately and only
    the worker runs the daily Finnhub chain, so the API's factor caches are not
    merely cold after a deploy — they are empty for the life of the process.
    `routers/internal.py` is where that process recomputes sheet composites."""
    from app.routers import internal

    tree = ast.parse(
        pathlib.Path(inspect.getfile(internal)).read_text(encoding="utf-8")
    )
    node = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_run_sheet_refresh"
    )
    order = _call_order(node)
    assert "warm_factor_caches_from_db" in order, (
        "the sheet-changed webhook re-scores every sheet-governed row in a "
        "process whose factor caches nothing ever fills"
    )
    assert order.index("warm_factor_caches_from_db") < order.index(
        "refresh_all_tabs"
    ), "warming after the refresh restores nothing — the write already happened"
