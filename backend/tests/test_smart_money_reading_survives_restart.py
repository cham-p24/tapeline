"""A smart-money reading must be on its row before a restart can lose it.

MEASURED ON PRODUCTION 2026-09-14 (read-only SQL)
-------------------------------------------------
#825 made the fundamentals pass write each reading onto its row with its stamp.
The insider pass still put its reading only into the worker's in-memory cache
and stamped `last_smart_money_at`, leaving the row to a later writer - for the
~3,700 rows the ALL SIGNALS sheet owns, the sheet upsert, which runs only when
the sheet changes. #822's boot rebuild repairs a lost reading from the stored
Form 4 rows, but only where `sub_smart_money` is NULL. A new reading that
replaced an OLDER stored value was therefore lost to every deploy before the
sheet next changed, and the stamp hid the row. Observed live 2026-09-13: BXP
stored 18.0 beside a fresh, unsaved reading near 90.

The insider pass now writes through `_save_factor_readings` too. Every test
here was watched failing against the mutation its docstring names.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select, update

from app.db import session_scope
from app.models import Ticker
from app.services import finnhub_feed
from app.services.finnhub_feed import FinnhubThrottledError
from app.services.polygon_feed import _composite_from_subs
from app.workers import signal_publisher as sp

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

OLD = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

#: What the row held before the pass: an older reading, NOT NULL, so the boot
#: rebuild will not touch it.
STALE = 18.0
#: Net buying on every line - compute_smart_money_score maps it to 90.0.
READING = 90.0

#: The other five factors, as a previous writer left them.
HELD = {
    "sub_trend": 80.0, "sub_rs": 70.0, "sub_fundamentals": 60.0,
    "sub_macro": 50.0, "sub_momentum": 65.0,
}

_SHEET_HEADER = (
    "Ticker,Type,Asset Class,Strategy,Conviction,Score,Raw Score,Signal,"
    "Verdict,Action,Hold Duration,Price,Above 200DMA,Market Regime,Beats SPY?,"
    "Momentum Quality,3M Return %,6M Return %,1Y Return %,RS vs SPY 3M %,"
    "RS vs SPY 6M %,RS vs SPY 1Y %,RS vs Sector 3M %,Near 52W High %\n"
)
_SHEET_ROW = (
    "{sym},STOCK,Stock,MOMENTUM A+,A+,100,142,BUY NOW,Strong Buy,"
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
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_CLEARED", set())
    monkeypatch.setattr(sp, "_sheet_is_scoring_source", lambda: False)


def _vendor(
    monkeypatch: pytest.MonkeyPatch, script: dict[str, list[str]] | None = None,
) -> list[str]:
    """fetch_insider_transactions: `ok` answers with net buying, `throttle`
    raises when asked to. The last outcome per symbol repeats."""
    script = script or {}
    calls: list[str] = []

    async def _fetch(
        sym: str, days_back: int = 90, *, raise_failures: bool = False,
    ) -> list[dict[str, Any]] | None:
        calls.append(sym)
        queue = script.get(sym, ["ok"])
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if outcome == "throttle":
            if raise_failures:
                raise FinnhubThrottledError("stock/insider-transactions", 429)
            return None
        return [
            {"filer_name": "Jane Q Insider", "transaction_date": f"2026-09-0{d}",
             "share_change": 1_000, "transaction_price": 50.0, "code": "P"}
            for d in (1, 2, 3)
        ]

    monkeypatch.setattr("app.services.finnhub_feed.fetch_insider_transactions", _fetch)
    return calls


async def _seed(symbol: str, **row: Any) -> None:
    async with session_scope() as s:
        s.add(Ticker(**{
            "symbol": symbol, "name": f"{symbol} Inc", "asset_class": "equity",
            "price": 100.0, "volume": 1_000, **HELD, "sub_smart_money": STALE,
            "last_smart_money_at": OLD, **row,
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
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_CLEARED", set())


def _composite(row: Ticker) -> float | None:
    return _composite_from_subs({c: getattr(row, c) for c in sp.FACTOR_COLUMNS})


async def test_a_reading_that_replaces_an_older_value_survives_a_restart_and_the_sheet_upsert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The regression, on the path the boot rebuild cannot see. BXP holds an
    older reading; the pass scores a new one; the process dies before the sheet
    changes; the new process warms from the database - the rebuild skips BXP,
    its factor is not NULL - and its first sheet refresh upserts every sheet
    row from that cache.

    Mutations: the old stamp-only flush (`_stamp_factor_attempts` in place of
    `_flush_insider_attempts`) - the upsert writes 18.0 back; writing the reading
    to the wrong factor or stamp column."""
    from app.services.sheet_feed import parse_all_signals_csv, upsert_tickers

    before = _composite_from_subs({**HELD, "sub_smart_money": STALE})
    await _seed("BXP", score=before)
    _vendor(monkeypatch)

    await sp._refresh_insider_cache(limit=1)
    assert finnhub_feed.get_cached_smart_money_score("BXP") == READING
    _restart(monkeypatch)

    await finnhub_feed.warm_factor_caches_from_db()
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_SHEET_HEADER + _SHEET_ROW.format(sym="BXP")))

    row = await _row("BXP")
    assert row.sub_smart_money == READING, "a deploy lost the new reading"
    assert row.last_smart_money_at.replace(tzinfo=UTC) > OLD
    assert row.score == _composite(row)


async def test_the_pass_writes_the_reading_beside_a_recomputed_composite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without any later writer at all. Mutation: the old stamp-only flush -
    the row keeps 18.0 and the score computed from it."""
    before = _composite_from_subs({**HELD, "sub_smart_money": STALE})
    await _seed("AYI", score=before)
    _vendor(monkeypatch)

    await sp._refresh_insider_cache(limit=1)
    _restart(monkeypatch)

    row = await _row("AYI")
    assert row.sub_smart_money == READING
    assert row.score == _composite(row)
    assert row.score != before, "the fixture must move the composite, or this proves nothing"
    assert row.updated_at.replace(tzinfo=UTC) == OLD


async def test_readings_stamped_before_a_throttle_pause_are_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The throttle-pause flush stays, and carries the readings.

    Mutations: that flush stamping only (`_stamp_factor_attempts`) - ACLS is
    stamped and keeps 18.0; not flushing before the pause at all is caught by
    test_answered_symbols_are_stamped_before_a_throttle_pause."""
    await _seed("ACLS")
    await _seed("CLS")
    calls = _vendor(monkeypatch, {"CLS": ["throttle", "ok"]})

    await sp._refresh_insider_cache(limit=2)
    _restart(monkeypatch)

    assert calls == ["ACLS", "CLS", "CLS"], (
        f"ACLS must be answered before CLS's pause, or no reading waits through it: {calls}"
    )
    for sym in ("ACLS", "CLS"):
        row = await _row(sym)
        assert row.last_smart_money_at.replace(tzinfo=UTC) > OLD, sym
        assert row.sub_smart_money == READING, sym


async def test_the_stamp_never_lands_without_its_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the write fails, the row must stay due, not be hidden with its old
    value. Mutation: stamping the answered symbols in `_flush_insider_attempts`'s
    except branch (or before the write) - the stamp moves beside 18.0."""
    await _seed("AMX")
    _vendor(monkeypatch)

    def _broken(subs: dict[str, Any]) -> float | None:
        raise RuntimeError("database went away mid-write")

    monkeypatch.setattr("app.services.polygon_feed._composite_from_subs", _broken)
    await sp._refresh_insider_cache(limit=1)

    row = await _row("AMX")
    assert row.sub_smart_money == STALE
    assert row.last_smart_money_at.replace(tzinfo=UTC) == OLD, (
        "stamped without its reading: the old value is hidden behind a fresh stamp"
    )


async def test_the_reading_is_written_even_when_storing_its_form4_rows_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cache already holds the reading, and the tick publishes it on the rows
    it owns; a sheet-owned row must not be left disagreeing with it. Mutation:
    recording the reading only after `set_recent_insider_transactions_db`
    returns - the row keeps 18.0."""
    await _seed("FAIL")
    _vendor(monkeypatch)

    async def _write_fails(symbol: str, txns: list[dict[str, Any]]) -> None:
        raise RuntimeError("insider_transactions write failed")

    monkeypatch.setattr(
        "app.services.finnhub_feed.set_recent_insider_transactions_db", _write_fails,
    )
    await sp._refresh_insider_cache(limit=1)

    row = await _row("FAIL")
    assert finnhub_feed.get_cached_smart_money_score("FAIL") == READING
    assert row.sub_smart_money == READING
    assert row.score == _composite(row)


async def test_a_row_the_pass_cannot_write_keeps_its_old_reading_and_its_stamp_moves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The compare-and-set misses on every attempt: the row is stamped without
    the write, so it cannot head every selection forever, and the other writer's
    factor is not overwritten by a composite computed from a stale one.

    Mutation: dropping the compare-and-set guards for this factor - the stale
    composite lands beside the other writer's trend."""
    await _seed("RACE")
    _vendor(monkeypatch)
    real = sp._held_factors
    calls = 0

    async def _always_racing(symbols: list[str], columns: list[str]) -> Any:
        nonlocal calls
        calls += 1
        held = await real(symbols, columns)
        async with session_scope() as s:
            await s.execute(
                update(Ticker).where(Ticker.symbol == "RACE").values(sub_trend=float(calls))
            )
        return held

    monkeypatch.setattr(sp, "_held_factors", _always_racing)
    await sp._refresh_insider_cache(limit=1)

    row = await _row("RACE")
    assert calls == sp._FACTOR_SAVE_ATTEMPTS
    assert row.last_smart_money_at.replace(tzinfo=UTC) > OLD
    assert row.sub_smart_money == STALE
    assert row.sub_trend == float(calls)
    assert finnhub_feed.get_cached_smart_money_score("RACE") == READING, (
        "the reading stays in the cache for the row's owner to write"
    )
