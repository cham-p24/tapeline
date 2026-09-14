"""An empty insider answer retires the smart-money reading it replaces.

MEASURED ON PRODUCTION 2026-09-13 (read-only SQL)
-------------------------------------------------
`_refresh_insider_cache` wrote a reading only when Finnhub returned trades. When
a symbol's last Form 4 trade aged out of the 90-day window, Finnhub answered
`[]`, and every path kept the old value: the tick's `_merged_factor_set` fell
back to the row, the boot warm reloaded the row, and the Form 4 rows were never
deleted, so /app/holdings kept serving them. 1,077 non-crypto rows held a
sub_smart_money with no stored trade inside 90 days - 184 whose newest trade was
92-184 days old, 893 with no Form 4 rows at all - and 773 symbols' stored trades
were all older than the window.

`[]` is an answer - "no filings in 90 days" - and `compute_smart_money_score([])`
is None, the same NEUTRAL a never-measured symbol gets. `None` is not an answer,
and failures raise. So:

1. The pass clears the reading and deletes the Form 4 rows in one transaction,
   recomputing the composite beside the factor. On a sheet-owned row it writes
   only what the sheet itself writes.
2. Nothing is cleared on None, on a failure, or on a throttle - nor on an empty
   answer that a stored filing inside the window contradicts, which counts as a
   failed call so an outage of empty bodies stops the pass.
3. A tick that read the old value before the clear commits must not write it
   back - from its snapshot, or from the row it read - and releases only the
   marks it actually read.
4. The API process's webhook warm must not keep the retired value in its cache,
   where the sheet refresh would write it back; but it must keep a reading that
   has Form 4 rows on file.

Every test here was watched failing against a named mutation before it was kept.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select

from app.db import session_scope
from app.models import InsiderTransaction, Ticker
from app.services import finnhub_feed
from app.services.finnhub_feed import FinnhubThrottledError, FinnhubUnavailableError
from app.services.score import composite_from_factors
from app.workers import signal_publisher as sp

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

OLD = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
SYM = "AGED"

#: Chosen so the retired reading moves the label: 75.0 STRONG SETUP with smart
#: money at 90, 69.0 CONSTRUCTIVE with it at NEUTRAL.
FACTORS: dict[str, float] = {
    "sub_trend": 80.0, "sub_rs": 75.0, "sub_fundamentals": 70.0,
    "sub_smart_money": 90.0, "sub_macro": 60.0, "sub_momentum": 70.0,
}
BEFORE, AFTER = 75.0, 69.0


def _composite(factors: dict[str, float | None]) -> float | None:
    return composite_from_factors({k.removeprefix("sub_"): v for k, v in factors.items()})


def test_the_fixture_moves_the_composite_and_the_label() -> None:
    assert _composite(FACTORS) == BEFORE
    assert _composite({**FACTORS, "sub_smart_money": None}) == AFTER


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})
    # raising=False only so the suite runs, and fails on its assertions,
    # against the code before the fix.
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_CLEARED", set(), raising=False)
    monkeypatch.setattr(sp, "_sheet_is_scoring_source", lambda: False)

    async def _no_sleep(seconds: float, *a: Any, **k: Any) -> None:
        return None

    monkeypatch.setattr(sp.asyncio, "sleep", _no_sleep)


async def _seed(symbol: str = SYM, **overrides: Any) -> None:
    row: dict[str, Any] = {
        "symbol": symbol, "name": f"{symbol} Corp", "asset_class": "equity",
        "sector": "Energy", "price": 10.0, "volume": 1_000,
        **FACTORS, "score": BEFORE, "signal": "STRONG SETUP",
        "reason": "the reason written beside the old reading",
        "confidence_pct": 100.0, "updated_at": OLD,
    }
    row.update(overrides)
    async with session_scope() as s:
        s.add(Ticker(**row))


async def _seed_form4(symbol: str = SYM, lines: int = 3) -> None:
    async with session_scope() as s:
        for i in range(lines):
            s.add(InsiderTransaction(
                symbol=symbol, insider_name="Jane Q Insider",
                transaction_date=f"2026-03-0{i + 1}", share_change=2_000,
                transaction_price=25.0, transaction_value=50_000.0, code="P",
                fetched_at=OLD,
            ))


async def _row(symbol: str = SYM) -> Ticker:
    async with session_scope() as s:
        t = (await s.execute(select(Ticker).where(Ticker.symbol == symbol))).scalar_one()
        s.expunge(t)
        return t


async def _form4_count(symbol: str = SYM) -> int:
    async with session_scope() as s:
        return int(await s.scalar(
            select(func.count()).select_from(InsiderTransaction)
            .where(InsiderTransaction.symbol == symbol)
        ) or 0)


def _naive(ts: datetime) -> datetime:
    return ts.astimezone(UTC).replace(tzinfo=None) if ts.tzinfo else ts


def _vendor(monkeypatch: pytest.MonkeyPatch, outcome: str) -> list[str]:
    """fetch_insider_transactions honouring its real contract."""
    calls: list[str] = []

    async def _fetch(
        sym: str, days_back: int = 90, *, raise_failures: bool = False,
    ) -> list[dict[str, Any]] | None:
        calls.append(sym)
        if outcome == "empty":
            return []
        if outcome == "no_key":
            return None
        if outcome == "throttle":
            if raise_failures:
                raise FinnhubThrottledError("stock/insider-transactions", 429)
            return None
        if outcome == "down":
            if raise_failures:
                raise FinnhubUnavailableError("stock/insider-transactions", "status=503")
            return None
        if outcome == "boom":
            raise RuntimeError("scoring blew up")
        raise AssertionError(outcome)

    monkeypatch.setattr("app.services.finnhub_feed.fetch_insider_transactions", _fetch)
    return calls


# ===========================================================================
# 1. An empty answer clears the reading, its composite and its Form 4 rows.
# ===========================================================================


async def test_an_empty_answer_retires_the_reading_beside_a_recomputed_composite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The regression. Mutations that turn this red: dropping the empty-answer
    branch (the row keeps 90 and 75.0); writing the factor without the
    composite (90 -> None beside 75.0); dropping the updated_at hold."""
    await _seed()
    await _seed_form4()
    finnhub_feed.set_cached_smart_money_score(SYM, 90.0)
    calls = _vendor(monkeypatch, "empty")

    await sp._refresh_insider_cache(limit=1)

    assert calls == [SYM]
    t = await _row()
    assert t.sub_smart_money is None, "an empty answer must retire the old reading"
    assert (t.score, t.signal) == (AFTER, "CONSTRUCTIVE"), (
        f"the composite beside the cleared factor is {t.score} {t.signal}; "
        f"the remaining factors make {AFTER} CONSTRUCTIVE"
    )
    assert t.score == _composite({c: getattr(t, c) for c in sp.FACTOR_COLUMNS})
    assert t.reason and t.reason != "the reason written beside the old reading"
    assert t.confidence_pct == round(100.0 * 6 / 7, 1), "coverage is five factors + a price"
    assert (t.sub_trend, t.sub_macro, t.sub_momentum) == (80.0, 60.0, 70.0)
    assert _naive(t.updated_at) == _naive(OLD), "no live data changed; updated_at must hold"
    assert t.last_smart_money_at is not None, "the answer is still stamped"

    assert await _form4_count() == 0, "Form 4 rows from outside the window are still served"
    assert finnhub_feed.get_cached_smart_money_score(SYM) is None
    assert SYM in finnhub_feed.smart_money_cleared_symbols()


async def test_an_empty_answer_deletes_only_that_symbols_form4_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Also when the row holds no reading - 589 production rows had a NULL factor
    and trades older than 90 days on file. Mutations: deleting only when a
    reading was held; a delete missing its symbol filter."""
    await _seed(**{"sub_smart_money": None, "score": AFTER, "signal": "CONSTRUCTIVE"})
    await _seed("OTHER")
    await _seed_form4()
    await _seed_form4("OTHER")
    _vendor(monkeypatch, "empty")

    async def _only_aged(stamp_col: Any, cap: int, **k: Any) -> list[str]:
        return [SYM]

    monkeypatch.setattr(sp, "_select_factor_symbols", _only_aged)
    await sp._refresh_insider_cache(limit=1)

    assert await _form4_count() == 0
    assert await _form4_count("OTHER") == 3, "another symbol's filings were deleted"
    t = await _row()
    assert (t.sub_smart_money, t.score, t.signal) == (None, AFTER, "CONSTRUCTIVE")


async def test_the_clear_writes_only_what_the_sheet_writes_on_a_sheet_owned_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sheet's confidence_pct is a conviction grade, not factor coverage, and
    the sheet writes no reason. Mutation: writing the tick's full set."""
    monkeypatch.setattr(sp, "_sheet_is_scoring_source", lambda: True)
    monkeypatch.setattr(sp, "_sheet_governed_symbols", frozenset({SYM}))
    await _seed(confidence_pct=90.0)
    _vendor(monkeypatch, "empty")

    await sp._refresh_insider_cache(limit=1)

    t = await _row()
    assert (t.sub_smart_money, t.score, t.signal) == (None, AFTER, "CONSTRUCTIVE")
    assert t.confidence_pct == 90.0, "the sheet's conviction grade was overwritten"
    assert t.reason == "the reason written beside the old reading"


# ===========================================================================
# 2. No answer, a failure or a throttle clears nothing.
# ===========================================================================


@pytest.mark.parametrize("outcome", ["no_key", "down", "boom", "throttle"])
async def test_nothing_is_cleared_without_an_answer(
    monkeypatch: pytest.MonkeyPatch, outcome: str,
) -> None:
    """None means no answer; failures raise. Mutations: `else` instead of
    `elif txns is not None` (no_key red); clearing in an except arm."""
    await _seed()
    await _seed_form4()
    finnhub_feed.set_cached_smart_money_score(SYM, 90.0)
    _vendor(monkeypatch, outcome)

    await sp._refresh_insider_cache(limit=1)

    t = await _row()
    assert (t.sub_smart_money, t.score, t.signal) == (90.0, BEFORE, "STRONG SETUP")
    assert await _form4_count() == 3
    assert finnhub_feed.get_cached_smart_money_score(SYM) == 90.0
    assert finnhub_feed.smart_money_cleared_symbols() == frozenset()


async def test_a_failed_clear_changes_nothing_and_counts_as_a_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """The cache is dropped only after the commit. Mutation: dropping it first -
    the tick would then clear a row whose Form 4 rows the rollback kept."""
    await _seed()
    await _seed_form4()
    finnhub_feed.set_cached_smart_money_score(SYM, 90.0)
    _vendor(monkeypatch, "empty")

    real_merge = sp._merged_factor_set

    def _broken(*a: Any, **k: Any) -> dict[str, Any]:
        if k.get("cleared"):
            raise RuntimeError("database went away mid-clear")
        return real_merge(*a, **k)

    monkeypatch.setattr(sp, "_merged_factor_set", _broken)
    with caplog.at_level("ERROR", logger=sp.logger.name):
        await sp._refresh_insider_cache(limit=1)

    assert "insider.fetch_failed symbol=AGED" in caplog.text
    t = await _row()
    assert (t.sub_smart_money, t.score) == (90.0, BEFORE)
    assert await _form4_count() == 3, "the delete must roll back with the failed update"
    assert finnhub_feed.get_cached_smart_money_score(SYM) == 90.0
    assert finnhub_feed.smart_money_cleared_symbols() == frozenset()


@pytest.mark.parametrize(("days_ago", "believed"), [(10, False), (80, False), (81, True)])
async def test_an_empty_answer_is_not_believed_over_a_recent_stored_filing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    days_ago: int, believed: bool,
) -> None:
    """A filing dated inside the window cannot have left it. Mutations: no
    contradiction check (10 and 80 red); `>` for `>=` (80 red); a margin of the
    full window (81 red)."""
    await _seed()
    filed = (date.today() - timedelta(days=days_ago)).isoformat()
    async with session_scope() as s:
        s.add(InsiderTransaction(
            symbol=SYM, insider_name="Jane Q Insider", transaction_date=filed,
            share_change=2_000, transaction_price=25.0, transaction_value=50_000.0,
            code="P", fetched_at=OLD,
        ))
    finnhub_feed.set_cached_smart_money_score(SYM, 90.0)
    _vendor(monkeypatch, "empty")

    with caplog.at_level("WARNING", logger=sp.logger.name):
        await sp._refresh_insider_cache(limit=1)

    t = await _row()
    if believed:
        assert (t.sub_smart_money, await _form4_count()) == (None, 0)
        return
    assert (t.sub_smart_money, t.score) == (90.0, BEFORE), (
        f"an empty answer wiped a reading backed by a filing dated {filed}"
    )
    assert await _form4_count() == 1
    assert finnhub_feed.get_cached_smart_money_score(SYM) == 90.0
    assert f"contradicts a stored filing dated {filed}" in caplog.text


async def test_an_outage_of_empty_answers_stops_the_pass_instead_of_wiping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A vendor answering [] for everyone. Each contradicted answer is a failed
    call, so the failure stop ends the pass after 10. Mutation: a contradiction
    skipped quietly instead of failing - all 40 are asked and the pass reports
    no stop."""
    recent = (date.today() - timedelta(days=5)).isoformat()
    symbols = [f"R{i:02d}" for i in range(40)]
    for sym in symbols:
        await _seed(sym)
    async with session_scope() as s:
        for sym in symbols:
            s.add(InsiderTransaction(
                symbol=sym, insider_name="Jane Q Insider", transaction_date=recent,
                share_change=2_000, transaction_price=25.0,
                transaction_value=50_000.0, code="P", fetched_at=OLD,
            ))
    calls = _vendor(monkeypatch, "empty")

    stopped = await sp._refresh_insider_cache(limit=40)

    assert stopped is True
    assert len(calls) == sp._FACTOR_FAILURE_STOP
    async with session_scope() as s:
        held = await s.scalar(
            select(func.count()).select_from(Ticker).where(Ticker.sub_smart_money.is_not(None))
        )
    assert held == 40


def test_a_new_reading_lifts_the_mark() -> None:
    """Mutation: set_cached_smart_money_score not discarding the mark - every
    tick would then blank a symbol whose insiders have filed again."""
    finnhub_feed.clear_cached_smart_money_score(SYM)
    assert SYM in finnhub_feed.smart_money_cleared_symbols()
    finnhub_feed.set_cached_smart_money_score(SYM, 40.0)
    assert SYM not in finnhub_feed.smart_money_cleared_symbols()
    assert finnhub_feed.get_cached_smart_money_score(SYM) == 40.0


# ===========================================================================
# 3. A tick that read the old value cannot write it back.
# ===========================================================================


class _StoppedAtPublishError(Exception):
    """Raised from the tick's first publish, reached only after the score upsert
    has committed, so none of the cadence-gated jobs below it run."""


def _snapshot(symbol: str, smart_money: float | None) -> dict[str, Any]:
    return {
        "symbol": symbol, "price": 10.0, "change_pct_1d": 0.5,
        "change_pct_5d": None, "change_pct_1m": None, "volume": 1_000,
        "market_cap": None, "sector": "Energy",
        **FACTORS, "sub_smart_money": smart_money,
    }


def _drive_tick(monkeypatch: pytest.MonkeyPatch, fetch_snapshots: Any) -> None:
    async def _fetch_regime(_snapshots: list[dict[str, Any]]) -> dict[str, Any]:
        return {}

    async def _publish(event: str, payload: Any) -> None:
        raise _StoppedAtPublishError

    monkeypatch.setattr(sp, "fetch_snapshots", fetch_snapshots)
    monkeypatch.setattr(sp, "fetch_regime", _fetch_regime)
    monkeypatch.setattr(sp, "_mock_writes_enabled", lambda: False)
    monkeypatch.setattr(sp.broker, "publish", _publish)


async def test_a_tick_cannot_write_back_the_value_its_snapshot_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The snapshots are built from the cache at the top of the tick; the insider
    pass runs concurrently and clears the row before the upsert. Mutation: the
    tick not passing `cleared` - the row is back to 90 and 75.0."""
    await _seed()
    await _seed_form4()
    _vendor(monkeypatch, "empty")

    async def _fetch_snapshots() -> list[dict[str, Any]]:
        stale = [_snapshot(SYM, 90.0)]
        await sp._refresh_insider_cache(limit=1)  # commits mid-tick
        assert (await _row()).sub_smart_money is None
        return stale

    _drive_tick(monkeypatch, _fetch_snapshots)
    with pytest.raises(_StoppedAtPublishError):
        await sp.tick()

    t = await _row()
    assert t.sub_smart_money is None, "the tick wrote the retired reading back"
    assert (t.score, t.signal) == (AFTER, "CONSTRUCTIVE")
    assert finnhub_feed.smart_money_cleared_symbols() == frozenset(), (
        "a mark the tick read and wrote must be released"
    )


async def test_the_next_tick_repairs_a_value_written_back_before_the_mark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tick whose merge ran before the mark existed can still land its write
    after the clear. The row then holds the old value and the cache is empty, so
    the next tick's merge would keep the ROW's value. Mutation: `cleared`
    overriding only the snapshot, not the previous row."""
    await _seed()
    finnhub_feed.clear_cached_smart_money_score(SYM)

    async def _fetch_snapshots() -> list[dict[str, Any]]:
        return [_snapshot(SYM, None)]

    _drive_tick(monkeypatch, _fetch_snapshots)
    with pytest.raises(_StoppedAtPublishError):
        await sp.tick()

    t = await _row()
    assert (t.sub_smart_money, t.score, t.signal) == (None, AFTER, "CONSTRUCTIVE")


async def test_the_tick_releases_only_the_marks_it_read_for_rows_it_wrote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutations: releasing every mark (LATE, set after the tick read them, must
    survive for the next tick to act on); releasing marks for symbols the tick
    never wrote (IDLE)."""
    await _seed()
    await _seed("LATE")
    finnhub_feed.clear_cached_smart_money_score(SYM)
    finnhub_feed.clear_cached_smart_money_score("IDLE")

    async def _fetch_snapshots() -> list[dict[str, Any]]:
        return [_snapshot(SYM, None), _snapshot("LATE", 90.0)]

    real_merge = sp._merged_factor_set

    def _merge_then_a_clear_lands(*a: Any, **k: Any) -> dict[str, Any]:
        out = real_merge(*a, **k)
        finnhub_feed.clear_cached_smart_money_score("LATE")
        return out

    monkeypatch.setattr(sp, "_merged_factor_set", _merge_then_a_clear_lands)
    _drive_tick(monkeypatch, _fetch_snapshots)
    with pytest.raises(_StoppedAtPublishError):
        await sp.tick()

    assert finnhub_feed.smart_money_cleared_symbols() == frozenset({"LATE", "IDLE"})
    assert (await _row()).sub_smart_money is None
    assert (await _row("LATE")).sub_smart_money == 90.0, "LATE's mark arrived after the read"


# ===========================================================================
# 4. The webhook warm drops what the pass retired, and keeps the rest.
# ===========================================================================

_SHEET_CSV = (
    "Ticker,Type,Asset Class,Strategy,Conviction,Score,Raw Score,Signal,"
    "Verdict,Action,Hold Duration,Price,Above 200DMA,Market Regime,Beats SPY?,"
    "Momentum Quality,3M Return %,6M Return %,1Y Return %,RS vs SPY 3M %,"
    "RS vs SPY 6M %,RS vs SPY 1Y %,RS vs Sector 3M %,Near 52W High %\n"
    "OXY,STOCK,Stock,MOMENTUM A+,A+,100,142,BUY NOW,Strong Buy,"
    "Strong Buy & Hold,6-12 months,59.62,TRUE,STRONG BULL,Yes (+32.8%),"
    "All 3 positive,30.4,43.4,40.4,21.9,32.8,13.8,19.1,99.5\n"
)


async def test_the_webhook_warm_does_not_hand_the_sheet_a_retired_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The API process warms on every sheet-changed webhook and never runs the
    insider pass, so its cache still holds what the row said last time. The
    worker then clears the row. Mutation: a warm that only ever adds entries -
    the refresh writes 90 back onto the sheet-owned row."""
    from app.services.sheet_feed import parse_all_signals_csv, upsert_tickers

    await _seed("OXY")
    await _seed_form4("OXY")
    await finnhub_feed.warm_factor_caches_from_db()  # an earlier webhook
    api_process_cache = dict(finnhub_feed._SMART_MONEY_SCORE_CACHE)
    assert api_process_cache["OXY"] == 90.0

    _vendor(monkeypatch, "empty")
    await sp._refresh_insider_cache(limit=1)  # the worker, another machine
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", api_process_cache)
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_CLEARED", set(), raising=False)

    await finnhub_feed.warm_factor_caches_from_db()  # the next webhook
    assert finnhub_feed.get_cached_smart_money_score("OXY") is None
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_SHEET_CSV))

    t = await _row("OXY")
    assert t.sub_smart_money is None, "the sheet refresh wrote the retired reading back"
    assert t.score == _composite({c: getattr(t, c) for c in sp.FACTOR_COLUMNS})


async def test_the_warm_keeps_a_reading_that_has_form4_rows_on_file() -> None:
    """A reading on no row but WITH Form 4 rows is one the pass computed and no
    writer has saved yet - the loss #812 repaired. Mutation: dropping every
    entry whose row is NULL."""
    await _seed(**{"sub_smart_money": None, "score": AFTER})
    await _seed("NOROWS", **{"sub_smart_money": None, "score": AFTER})
    await _seed_form4()
    finnhub_feed._SMART_MONEY_SCORE_CACHE.update({SYM: 70.0, "NOROWS": 70.0})

    _, smart = await finnhub_feed.warm_factor_caches_from_db()

    assert finnhub_feed.get_cached_smart_money_score(SYM) == 70.0
    assert finnhub_feed.get_cached_smart_money_score("NOROWS") is None
    assert smart == 0
