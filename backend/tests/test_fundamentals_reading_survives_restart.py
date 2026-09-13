"""A fundamentals reading must be on its row before a restart can lose it.

MEASURED ON PRODUCTION 2026-09-13 (read-only SQL)
-------------------------------------------------
The fundamentals pass put each reading only into the worker's in-memory cache
and stamped `last_fundamentals_at`, leaving the row to a later writer. For the
rows the ALL SIGNALS sheet owns (about 3,700), that writer is the sheet upsert,
which runs only when the sheet changes. A deploy in between took the reading
with it, and the stamp hid the row for 8 days.

Ownership was read off the rows themselves: the tick re-renders `reason` on
every row it writes, and the sheet never writes it, so a reason unchanged
across three ticks marks a sheet-owned row. Among equities carrying key
statistics from the same Finnhub blob, the sheet-owned rows of the last five
interrupted runs were NULL 15/15, 37/37, 31/31, 64/64 and 56/56, and the
tick-owned rows ~0. That left 1,548 such equities at NEUTRAL 50, ADBE, JPM,
COST, V, CAT, PEP, MRK and BA among them. Nothing could rebuild them: the metric
blob lives on Fly's ephemeral disk.

The pass now writes the reading, with the composite recomputed beside it, in
the same statement that stamps the row. Every test here was watched failing
against the mutation its docstring names.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select, update

from app.db import session_scope
from app.models import Ticker
from app.services import finnhub_feed
from app.services.finnhub_feed import FinnhubThrottledError, compute_fundamentals_score
from app.services.mock_feed import _signal_from_score
from app.services.polygon_feed import _composite_from_subs
from app.workers import signal_publisher as sp

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

OLD = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
METRICS = {"roe": 20.0, "margin": 15.0}
READING = compute_fundamentals_score(METRICS)

#: The other five factors, as a previous writer left them.
HELD = {
    "sub_trend": 80.0, "sub_rs": 70.0, "sub_smart_money": 10.0,
    "sub_macro": 50.0, "sub_momentum": 65.0,
}

_SHEET_CSV = (
    "Ticker,Type,Asset Class,Strategy,Conviction,Score,Raw Score,Signal,"
    "Verdict,Action,Hold Duration,Price,Above 200DMA,Market Regime,Beats SPY?,"
    "Momentum Quality,3M Return %,6M Return %,1Y Return %,RS vs SPY 3M %,"
    "RS vs SPY 6M %,RS vs SPY 1Y %,RS vs Sector 3M %,Near 52W High %\n"
    "OXY,STOCK,Stock,MOMENTUM A+,A+,100,142,BUY NOW,Strong Buy,"
    "Strong Buy & Hold,6-12 months,59.62,TRUE,STRONG BULL,Yes (+32.8%),"
    "All 3 positive,30.4,43.4,40.4,21.9,32.8,13.8,19.1,99.5\n"
)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_sleep(seconds: float, *a: Any, **k: Any) -> None:
        return None

    monkeypatch.setattr(sp.asyncio, "sleep", _fake_sleep)


@pytest.fixture(autouse=True)
def _fresh_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(finnhub_feed, "_FUND_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})


def _vendor(monkeypatch: pytest.MonkeyPatch, script: dict[str, list[str]] | None = None) -> None:
    """fetch_basic_financials: `ok` answers, `none` has no coverage, `throttle`
    raises when asked to. The last outcome per symbol repeats."""
    script = script or {}

    async def _fetch(sym: str, *, raise_failures: bool = False) -> dict[str, float] | None:
        queue = script.get(sym, ["ok"])
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if outcome == "throttle":
            if raise_failures:
                raise FinnhubThrottledError("stock/metric", 429)
            return None
        if outcome == "none":
            return None
        return dict(METRICS)

    monkeypatch.setattr("app.services.finnhub_feed.fetch_basic_financials", _fetch)


async def _seed(symbol: str, **row: Any) -> None:
    async with session_scope() as s:
        s.add(Ticker(**{
            "symbol": symbol, "name": f"{symbol} Inc", "asset_class": "equity",
            "price": 100.0, "volume": 1_000, **HELD, **row,
        }))
    # updated_at has a server default; pin it so "held still" is observable.
    async with session_scope() as s:
        await s.execute(
            update(Ticker).where(Ticker.symbol == symbol).values(updated_at=OLD)
        )


async def _row(symbol: str) -> Ticker:
    async with session_scope() as s:
        return (await s.execute(select(Ticker).where(Ticker.symbol == symbol))).scalar_one()


def _restart(monkeypatch: pytest.MonkeyPatch) -> None:
    """Process memory is gone; only what reached the database survives."""
    monkeypatch.setattr(finnhub_feed, "_FUND_SCORE_CACHE", {})


def _composite(row: Ticker) -> float | None:
    return _composite_from_subs({c: getattr(row, c) for c in sp.FACTOR_COLUMNS})


async def test_a_reading_is_on_the_row_when_its_stamp_lands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The regression: pass, then restart, then look at the row.

    Mutation: flush with `_stamp_factor_attempts` alone (the old code) - the
    stamp lands and sub_fundamentals is NULL."""
    await _seed("ADBE")
    _vendor(monkeypatch)

    await sp._refresh_fundamentals_cache(limit=1)
    _restart(monkeypatch)

    row = await _row("ADBE")
    assert row.last_fundamentals_at is not None
    assert row.sub_fundamentals == READING


async def test_the_composite_is_recomputed_beside_the_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A factor must never land beside a score that ignored it.

    Mutation: write the factor and the stamp without `score` / `signal` - the
    stored score stays the one computed without fundamentals."""
    before = _composite_from_subs({**HELD, "sub_fundamentals": None})
    await _seed("JPM", score=before, signal=_signal_from_score(before))
    _vendor(monkeypatch)

    await sp._refresh_fundamentals_cache(limit=1)

    row = await _row("JPM")
    assert row.score == _composite(row)
    assert row.score != before, "the fixture must move the composite, or this proves nothing"
    assert row.signal == _signal_from_score(row.score)


async def test_the_write_holds_updated_at_still(monkeypatch: pytest.MonkeyPatch) -> None:
    """A reading is not proof the row's price is live. Mutation: drop
    `updated_at=Ticker.updated_at` - updated_at moves (and conftest's runtime
    guard rejects the UPDATE)."""
    await _seed("COST")
    _vendor(monkeypatch)

    await sp._refresh_fundamentals_cache(limit=1)

    row = await _row("COST")
    assert row.sub_fundamentals == READING
    assert row.updated_at.replace(tzinfo=UTC) == OLD


async def test_a_sheet_owned_reading_survives_a_restart_and_the_boot_sheet_upsert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The path that lost 1,548 rows. The pass scores OXY; the process dies
    before the sheet changes; the new process warms from the database and its
    first sheet refresh upserts every sheet row from that cache.

    Mutation: the old stamp-only flush - the upsert writes NULL."""
    from app.services.sheet_feed import parse_all_signals_csv, upsert_tickers

    await _seed("OXY")
    _vendor(monkeypatch)
    await sp._refresh_fundamentals_cache(limit=1)
    _restart(monkeypatch)

    await finnhub_feed.warm_factor_caches_from_db()
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_SHEET_CSV))

    row = await _row("OXY")
    assert row.sub_fundamentals == READING
    assert row.score == _composite(row)


async def test_the_stamp_never_lands_without_its_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the write fails, the row must stay due, not be hidden for 8 days.

    Mutation: stamp the answered symbols in `_flush_fundamentals_attempts`'s
    except branch (or before the write) - the stamp lands on a NULL row."""
    await _seed("CAT")
    _vendor(monkeypatch)

    def _broken(subs: dict[str, Any]) -> float | None:
        raise RuntimeError("database went away mid-write")

    monkeypatch.setattr("app.services.polygon_feed._composite_from_subs", _broken)
    await sp._refresh_fundamentals_cache(limit=1)

    row = await _row("CAT")
    assert row.sub_fundamentals is None
    assert row.last_fundamentals_at is None, "stamped without its reading: hidden for 8 days"


async def test_a_factor_changed_mid_write_is_not_overwritten_by_a_stale_composite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Another writer moves sub_trend between the read and the write.

    Mutation: drop the `is_not_distinct_from` guards - the score is written from
    the stale trend beside the new one."""
    await _seed("PEP")
    _vendor(monkeypatch)
    real = sp._held_factors
    calls = 0

    async def _read_then_race(symbols: list[str], columns: list[str]) -> Any:
        nonlocal calls
        calls += 1
        held = await real(symbols, columns)
        if calls == 1:
            async with session_scope() as s:
                await s.execute(
                    update(Ticker).where(Ticker.symbol == "PEP").values(sub_trend=10.0)
                )
        return held

    monkeypatch.setattr(sp, "_held_factors", _read_then_race)
    await sp._refresh_fundamentals_cache(limit=1)

    row = await _row("PEP")
    assert row.sub_trend == 10.0, "the other writer's factor must survive"
    assert row.sub_fundamentals == READING
    assert row.score == _composite(row)
    assert calls == 2


async def test_a_row_that_keeps_changing_is_stamped_without_the_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A row the pass can never write must not head every selection forever.

    Mutations: not stamping the contended symbols - the stamp stays NULL; an
    unbounded retry - more reads than _FACTOR_SAVE_ATTEMPTS."""
    await _seed("MRK")
    _vendor(monkeypatch)
    real = sp._held_factors
    calls = 0

    async def _always_racing(symbols: list[str], columns: list[str]) -> Any:
        nonlocal calls
        calls += 1
        if calls > 10:
            raise AssertionError("unbounded retry")
        held = await real(symbols, columns)
        async with session_scope() as s:
            await s.execute(
                update(Ticker).where(Ticker.symbol == "MRK").values(sub_trend=float(calls))
            )
        return held

    monkeypatch.setattr(sp, "_held_factors", _always_racing)
    await sp._refresh_fundamentals_cache(limit=1)

    row = await _row("MRK")
    assert calls == sp._FACTOR_SAVE_ATTEMPTS
    assert row.last_fundamentals_at is not None
    assert row.sub_fundamentals is None


async def test_readings_stamped_before_a_throttle_pause_are_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pass flushes what it has before waiting out a throttle.

    Mutation: that flush drops the readings - V is stamped and never written."""
    await _seed("V", volume=2_000)
    await _seed("BA", volume=1_000)
    _vendor(monkeypatch, {"BA": ["throttle", "ok"]})

    await sp._refresh_fundamentals_cache(limit=2)
    _restart(monkeypatch)

    for sym in ("V", "BA"):
        row = await _row(sym)
        assert row.last_fundamentals_at is not None, sym
        assert row.sub_fundamentals == READING, sym


async def test_no_coverage_is_stamped_and_leaves_the_row_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: writing a None reading - the stored value is erased."""
    await _seed("ETFX", asset_class="etf", sub_fundamentals=61.0)
    _vendor(monkeypatch, {"ETFX": ["none"]})

    await sp._refresh_fundamentals_cache(limit=1)

    row = await _row("ETFX")
    assert row.last_fundamentals_at is not None
    assert row.sub_fundamentals == 61.0


async def test_a_crypto_pair_is_stamped_not_written(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pairs are scored on a different factor set. Mutation: drop the `X:`
    filter - the equity composite is written over the pair's."""
    await _seed("X:BTCUSD", asset_class="crypto", score=44.0)
    _vendor(monkeypatch)

    await sp._refresh_fundamentals_cache(limit=1)

    row = await _row("X:BTCUSD")
    assert row.last_fundamentals_at is not None
    assert row.sub_fundamentals is None
    assert row.score == 44.0
