"""The sheet ingest must neither tear a row nor revert a factor reading.

FOUND IN REVIEW 2026-09-17 (adversarially verified, reproduced on SQLite)
------------------------------------------------------------------------
Since #825/#829 the worker's factor passes write each fundamentals and smart-
money reading onto its row themselves. `sheet_feed.upsert_tickers` still set all
six factors, score and signal on each loaded Ticker from the parse-time caches
and committed once, minutes later:

* A reading saved after a row was LOADED survived beside a score and label
  computed without it, because the ORM's UPDATE only carries attributes that
  differ from what it loaded (sub_smart_money 90.0 beside 48.9 NEUTRAL).
* A reading saved after the CSV was PARSED but before the row was loaded was
  overwritten with the parse-time value, and lost to the next restart.

Review of the first fix found three more ways to put the wrong value on a
sheet-owned row, each with a test below: a reading or retirement whose own write
lost its compare-and-set never reached the row, and the API webhook wrote back
a reading the worker had retired mid-ingest.

Found with them, and fixed here too:

* The SMART MONEY & CONGRESS tab wrote an appearance count over the EDGAR reading
  without the composite (dormant: its secret is not set on Fly). Retired.
* The ETF BENCHMARKS tab wrote the workbook's own Score as Ticker.score, beside
  factors that did not make it (dormant: the tab parsed to 0 rows).
* The worker refreshed the sheet's symbol set AFTER its multi-minute ingest, so
  ticks in between wrote their own composite over sheet-owned rows, and it
  stayed until the sheet next changed.
* Since EDGAR, twenty heavy filers could keep a batch's stamp more than
  INSIDER_STAMP_LAG after its Form 4 rows, hiding a contended row from the boot
  rebuild.

Every test here was watched failing against the mutation its docstring names.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, update

from app.db import session_scope
from app.models import InsiderTransaction, Ticker
from app.services import finnhub_feed, sheet_feed
from app.services.score import composite_from_factors
from app.services.sheet_feed import parse_all_signals_csv, score_to_signal, upsert_tickers
from app.workers import signal_publisher as sp

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

SYM = "BXP"
OLD = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
STALE, READING = 18.0, 90.0

_HEADER = (
    "Ticker,Type,Asset Class,Strategy,Conviction,Score,Raw Score,Signal,"
    "Verdict,Action,Hold Duration,Price,Above 200DMA,Market Regime,Beats SPY?,"
    "Momentum Quality,3M Return %,6M Return %,1Y Return %,RS vs SPY 3M %,"
    "RS vs SPY 6M %,RS vs SPY 1Y %,RS vs Sector 3M %,Near 52W High %\n"
)
#: Version 1 and version 2 of the workbook: v2 moves trend, RS and momentum.
_V1 = (
    "{sym},STOCK,Stock,MOMENTUM A+,A+,100,142,BUY NOW,Strong Buy,"
    "Strong Buy & Hold,6-12 months,59.62,TRUE,STRONG BULL,Yes (+32.8%),"
    "All 3 positive,30.4,43.4,40.4,21.9,32.8,13.8,19.1,99.5\n"
)
_V2 = (
    "{sym},STOCK,Stock,MOMENTUM A+,A+,100,142,BUY NOW,Strong Buy,"
    "Strong Buy & Hold,6-12 months,48.10,FALSE,BEAR,No (-12.0%),"
    "Mixed,-8.0,-15.0,-20.0,-12.0,-18.0,-25.0,-9.0,61.0\n"
)


def _csv(version: str, sym: str = SYM) -> str:
    return _HEADER + version.format(sym=sym)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(finnhub_feed, "_FUND_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_CLEARED", set())


async def _row(symbol: str = SYM) -> Ticker:
    async with session_scope() as s:
        return (await s.execute(select(Ticker).where(Ticker.symbol == symbol))).scalar_one()


def _composite(t: Ticker) -> float | None:
    return composite_from_factors({
        k: getattr(t, f"sub_{k}")
        for k in ("trend", "rs", "fundamentals", "smart_money", "macro", "momentum")
    })


async def _ingest_v1_with_stale_reading() -> None:
    """BXP as the sheet last left it: v1's factors beside smart money 18.0."""
    finnhub_feed.set_cached_smart_money_score(SYM, STALE)
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_csv(_V1)))
    t = await _row()
    assert t.sub_smart_money == STALE and t.score == _composite(t)


async def _save_reading() -> None:
    """The insider pass, from another task, saving a new reading onto the row."""
    finnhub_feed.set_cached_smart_money_score(SYM, READING)
    await sp._save_factor_readings(
        "last_smart_money_at", "sub_smart_money", {SYM: READING}, datetime.now(UTC),
    )


def _assert_consistent_v2_with_reading(t: Ticker, v2: dict[str, Any]) -> None:
    assert t.sub_smart_money == READING, "the ingest reverted a newer reading"
    assert (t.sub_trend, t.sub_rs, t.sub_momentum) == (
        v2["sub_trend"], v2["sub_rs"], v2["sub_momentum"],
    ), "the workbook's own factors were not written"
    assert t.score == _composite(t), (
        f"torn row: score {t.score} beside factors whose composite is {_composite(t)}"
    )
    assert t.signal == score_to_signal(t.score)


async def test_a_reading_saved_while_the_ingest_holds_the_row_is_kept_beside_its_composite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The torn row. The ingest has loaded BXP (18.0) and parsed v2 with 18.0 in
    the cache; the insider pass saves 90.0; the ingest then writes.

    Mutations: the old ORM write (all six factors, score and signal set on the
    loaded object) - 90.0 beside a score computed from 18.0; not retrying a
    row the compare-and-set missed - v2's trend is never written."""
    await _ingest_v1_with_stale_reading()
    rows = parse_all_signals_csv(_csv(_V2))

    async with session_scope() as s:
        real_commit = s.commit
        saved = []

        async def _save_then_commit() -> None:
            # upsert_tickers' first commit comes after its loop has loaded every
            # row and before any factor is written.
            if not saved:
                saved.append(True)
                await _save_reading()
            await real_commit()

        monkeypatch.setattr(s, "commit", _save_then_commit)
        await upsert_tickers(s, rows)

    assert saved, "the save must have run inside the ingest, or this proves nothing"
    _assert_consistent_v2_with_reading(await _row(), rows[0])


async def test_a_reading_saved_after_the_parse_is_not_reverted_by_the_ingest() -> None:
    """The reverted reading. v2 is parsed with 18.0 in the cache; the insider
    pass saves 90.0; only then does the ingest load and write BXP.

    Mutation: taking fundamentals and smart money from the parse again - the
    ingest writes 18.0 over the saved 90.0."""
    await _ingest_v1_with_stale_reading()
    rows = parse_all_signals_csv(_csv(_V2))
    await _save_reading()

    async with session_scope() as s:
        await upsert_tickers(s, rows)

    _assert_consistent_v2_with_reading(await _row(), rows[0])


async def test_a_reading_retired_after_the_parse_is_not_written_back() -> None:
    """#824: an empty EDGAR answer clears the row and drops the cache entry. The
    parse ran before that, with the old value. The row is NULL when loaded.

    Mutation: falling back to the PARSE-time value for a NULL row instead of
    the cache as it is at write time - the retired 90.0 is resurrected."""
    finnhub_feed.set_cached_smart_money_score(SYM, READING)
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_csv(_V1)))
    rows = parse_all_signals_csv(_csv(_V2))
    assert rows[0]["sub_smart_money"] == READING

    # The clear, as `_clear_smart_money_reading` leaves things.
    async with session_scope() as s:
        await s.execute(
            update(Ticker).where(Ticker.symbol == SYM)
            .values(sub_smart_money=None, updated_at=Ticker.updated_at)
        )
    finnhub_feed.clear_cached_smart_money_score(SYM)

    async with session_scope() as s:
        await upsert_tickers(s, rows)

    t = await _row()
    assert t.sub_smart_money is None, "the ingest wrote a retired reading back"
    assert t.score == _composite(t)


async def _seed_form4(symbol: str = SYM) -> None:
    async with session_scope() as s:
        s.add(InsiderTransaction(
            symbol=symbol, insider_name="Jane Q Insider", transaction_date="2026-09-01",
            share_change=1_000, transaction_price=50.0, transaction_value=50_000.0, code="P",
        ))


async def test_a_rebuilt_reading_reaches_a_null_row() -> None:
    """The boot rebuild restores a lost reading into the cache from the stored
    Form 4 rows, leaving the row NULL. For a sheet-owned row the ingest is what
    puts it there.

    Mutation: never consulting the cache for a NULL row - it stays NULL."""
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_csv(_V1)))
    assert (await _row()).sub_smart_money is None
    await _seed_form4()
    finnhub_feed.set_cached_smart_money_score(SYM, READING, from_row=True)

    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_csv(_V2)))

    t = await _row()
    assert t.sub_smart_money == READING
    assert t.score == _composite(t)


async def test_the_webhook_does_not_write_back_a_reading_the_worker_retired() -> None:
    """The API process warms its cache from the rows (BXP 90), then ingests for
    minutes. Meanwhile the worker retires the reading: row NULL, Form 4 rows
    deleted, and only the WORKER's cache dropped. The API's still holds 90.

    Mutation: writing a NULL row's cached smart money without requiring its
    Form 4 rows - the retired 90.0 is published again."""
    finnhub_feed.set_cached_smart_money_score(SYM, READING, from_row=True)
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_csv(_V1)))
    rows = parse_all_signals_csv(_csv(_V2))

    # The worker's clear, seen from the API process.
    async with session_scope() as s:
        await s.execute(
            update(Ticker).where(Ticker.symbol == SYM)
            .values(sub_smart_money=None, updated_at=Ticker.updated_at)
        )
    assert finnhub_feed.get_cached_smart_money_score(SYM) == READING

    async with session_scope() as s:
        await upsert_tickers(s, rows)

    t = await _row()
    assert t.sub_smart_money is None, "a retired reading with no Form 4 rows was published"
    assert t.sub_trend == rows[0]["sub_trend"]
    assert t.score == _composite(t)


async def test_a_retirement_whose_own_write_lost_reaches_a_sheet_owned_row() -> None:
    """`_clear_smart_money_reading` lost its compare-and-set on every attempt:
    the row still holds 90, and the pass left the retirement for the row's
    owner. For a sheet-owned row that is this ingest.

    Mutation: preferring the row over what this process's pass learned - 90.0
    stays published with no Form 4 filing behind it."""
    await _ingest_v1_with_stale_reading()
    finnhub_feed.clear_cached_smart_money_score(SYM)

    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_csv(_V2)))

    t = await _row()
    assert t.sub_smart_money is None
    assert t.score == _composite(t)


async def test_a_reading_whose_own_write_lost_reaches_a_sheet_owned_row() -> None:
    """`_save_factor_readings` lost its compare-and-set on every attempt and
    stamped the row without the write: 18.0 on the row, 90.0 in this process.

    Mutation: preferring the row over what this process's pass learned - the
    new reading never reaches the row, and the stamp hides it for 36h."""
    await _ingest_v1_with_stale_reading()
    finnhub_feed.set_cached_smart_money_score(SYM, READING)

    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_csv(_V2)))

    t = await _row()
    assert t.sub_smart_money == READING
    assert t.score == _composite(t)


async def test_the_factor_write_holds_updated_at_still() -> None:
    """A factor set is not live data. Mutation: dropping `updated_at` from the
    factor statement - its onupdate moves it (and the runtime guard in conftest
    rejects the UPDATE)."""
    await _ingest_v1_with_stale_reading()
    async with session_scope() as s:
        await s.execute(update(Ticker).where(Ticker.symbol == SYM).values(updated_at=OLD))
    # Only relative strength moves: price, returns and conviction are v1's, so
    # nothing this ingest writes is live data.
    rows = parse_all_signals_csv(_csv(_V1.replace("21.9,32.8,13.8", "5.0,6.0,7.0")))
    before = await _row()
    assert rows[0]["sub_rs"] != before.sub_rs, "the fixture must move a factor"

    async with session_scope() as s:
        await upsert_tickers(s, rows)

    t = await _row()
    assert t.sub_rs == rows[0]["sub_rs"]
    assert t.updated_at.replace(tzinfo=UTC) == OLD


# ---------------------------------------------------------------------------
# The SMART MONEY & CONGRESS tab is retired.
# ---------------------------------------------------------------------------


async def test_the_smart_money_tab_no_longer_writes_the_factor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: the pre-retirement ingest - the tab's appearance count (60.0)
    replaces the EDGAR reading, and the score stays the one computed from it."""
    finnhub_feed.set_cached_smart_money_score(SYM, READING)
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_csv(_V1)))
    before = await _row()

    monkeypatch.setattr(
        sheet_feed.get_settings(), "smart_money_congress_csv_url", "https://example.invalid/tab",
    )
    fetched: list[str] = []

    async def _fetch(url: str, *, dedup: bool = True) -> str:
        fetched.append(url)
        return "Ticker,Category,Recent Buy / Holding Signal\nBXP,Congress,bought\n"

    monkeypatch.setattr(sheet_feed, "fetch_csv", _fetch)
    async with session_scope() as s:
        counts = await sheet_feed.refresh_all_tabs(s)

    t = await _row()
    assert t.sub_smart_money == READING
    assert t.score == before.score
    assert counts["smart_money"].get("total") == 0
    assert "https://example.invalid/tab" not in fetched


async def test_a_webhook_ingest_keeps_a_reading_saved_after_its_warm() -> None:
    """The API process warms its caches from the rows (BXP 18.0), parses and
    starts ingesting; the worker - another process - saves 90.0 onto the row.
    What the warm loaded is the row's past, not a newer reading.

    Mutation: the warm recording what it loads as the process's own readings -
    the ingest writes 18.0 over the saved 90.0."""
    finnhub_feed.set_cached_smart_money_score(SYM, STALE, from_row=True)
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_csv(_V1)))

    finnhub_feed._SMART_MONEY_SCORE_CACHE.clear()
    await finnhub_feed.warm_factor_caches_from_db()
    assert finnhub_feed.get_cached_smart_money_score(SYM) == STALE
    rows = parse_all_signals_csv(_csv(_V2))
    # The worker's save: the row changes, this process's cache does not.
    await sp._save_factor_readings(
        "last_smart_money_at", "sub_smart_money", {SYM: READING}, datetime.now(UTC),
    )

    async with session_scope() as s:
        await upsert_tickers(s, rows)

    _assert_consistent_v2_with_reading(await _row(), rows[0])


# ---------------------------------------------------------------------------
# The ETF BENCHMARKS tab does not publish the workbook's own score.
# ---------------------------------------------------------------------------

_ETF_CSV = (
    "Ticker,Name,Note,Score,Signal,3M Return %,6M Return %,1Y Return %,"
    "Above 200DMA,Beats SPY (6M),vs SPY 6M %,Action\n"
    "{sym},SPDR S&P 500 ETF,core,131,BUY NOW,5.0,8.0,20.0,TRUE,Yes,1.0,Buy\n"
)


async def test_the_etf_tab_does_not_overwrite_the_composite() -> None:
    """Mutation: writing the tab's Score and label - a clamped 100 HIGH
    CONVICTION beside six stored factors whose composite is something else."""
    sym = "SPY"
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_csv(_V2, sym=sym)))
    before = await _row(sym)
    assert before.score is not None and before.score < 85

    async with session_scope() as s:
        await sheet_feed.upsert_etfs(s, sheet_feed.parse_etf_benchmarks_csv(_ETF_CSV.format(sym=sym)))

    t = await _row(sym)
    assert t.asset_class == "etf"
    assert (t.score, t.signal) == (before.score, before.signal)
    assert t.score == _composite(t)


# ---------------------------------------------------------------------------
# The sheet's symbol set is known before the ingest writes a sheet-owned row.
# ---------------------------------------------------------------------------


async def test_the_workbook_refresh_learns_the_sheets_symbols_before_ingesting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ingest takes minutes; ticks run meanwhile. Mutation: refreshing the
    symbol set after the ingest (the old order) - it is empty during it."""
    monkeypatch.setattr(sp, "_sheet_governed_symbols", frozenset())
    # The worker reads its module-level `settings`; the helpers read
    # get_settings(). They are different objects once any earlier test has
    # cleared the settings cache, so both are set.
    for settings in {id(o): o for o in (sp.settings, sheet_feed.get_settings())}.values():
        monkeypatch.setattr(settings, "signal_sheet_csv_url", "https://example.invalid/all")
        for name in ("spike_intelligence_csv_url", "etf_benchmarks_csv_url",
                     "market_intelligence_csv_url", "smart_money_congress_csv_url"):
            monkeypatch.setattr(settings, name, "")

    async def _fetch(url: str, *, dedup: bool = True) -> str:
        return _csv(_V1)

    seen_during_ingest: list[frozenset[str]] = []

    async def _ingest(session: Any) -> dict[str, int]:
        seen_during_ingest.append(sp._sheet_governed_symbols)
        return {"inserted": 0, "updated": 0, "total": 0}

    monkeypatch.setattr(sheet_feed, "fetch_csv", _fetch)
    monkeypatch.setattr(sheet_feed, "refresh_from_workbook", _ingest)

    await sp._refresh_workbook_tabs()

    assert seen_during_ingest == [frozenset({SYM})]


# ---------------------------------------------------------------------------
# A batch's stamp stays within INSIDER_STAMP_LAG of its Form 4 rows.
# ---------------------------------------------------------------------------


async def test_a_slow_insider_batch_is_stamped_within_the_rebuilds_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Twenty heavy EDGAR filers at a minute each. The boot rebuild trusts a
    row's Form 4 rows only within INSIDER_STAMP_LAG (15 min) of its stamp.

    Mutation: flushing on count alone - the first symbol's stamp lands 19
    minutes after its answer."""
    t0 = datetime(2026, 11, 11, 2, 0, tzinfo=UTC)
    now = [t0]

    class _FakeDT(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return now[0]

    async def _sleep(seconds: float, *a: Any, **k: Any) -> None:
        now[0] += timedelta(seconds=seconds)

    monkeypatch.setattr(sp, "datetime", _FakeDT)
    monkeypatch.setattr(sp, "monotonic", lambda: (now[0] - t0).total_seconds())
    monkeypatch.setattr(sp.asyncio, "sleep", _sleep)
    monkeypatch.setattr(sp, "_INSIDER_PACE_SECONDS", 0.0)

    symbols = [f"HV{i:02d}" for i in range(20)]
    async with session_scope() as s:
        for i, sym in enumerate(symbols):
            s.add(Ticker(
                symbol=sym, name=f"{sym} Inc", asset_class="equity",
                price=100.0, volume=10_000 - i,
            ))

    answered_at: dict[str, datetime] = {}

    async def _heavy_filer(
        sym: str, days_back: int = 90, *, raise_failures: bool = False, listing: Any = None,
    ) -> list[dict[str, Any]]:
        now[0] += timedelta(seconds=60)
        answered_at[sym] = now[0]
        return [{"filer_name": "Jane Q Insider", "transaction_date": "2026-11-01",
                 "share_change": 1_000, "transaction_price": 50.0, "code": "P"}]

    monkeypatch.setattr("app.services.edgar_form4.fetch_insider_transactions", _heavy_filer)

    await sp._refresh_insider_cache(limit=20)

    async with session_scope() as s:
        stamps = dict((await s.execute(
            select(Ticker.symbol, Ticker.last_smart_money_at).where(Ticker.symbol.in_(symbols))
        )).all())
        assert (await s.execute(
            select(InsiderTransaction.symbol).where(InsiderTransaction.symbol.in_(symbols))
        )).first() is not None
    assert sorted(answered_at) == symbols
    lags = {
        sym: stamps[sym].replace(tzinfo=UTC) - answered_at[sym] for sym in symbols
    }
    worst = max(lags.values())
    assert worst <= finnhub_feed.INSIDER_STAMP_LAG, f"stamped {worst} after its answer"
