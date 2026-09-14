"""The factor refresh must keep what is DUE fresh, not only fill what was never fetched.

MEASURED ON PRODUCTION 2026-09-13 (read-only SQL)
-------------------------------------------------
The factor phase sized itself by never-attempted rows only. Once every row had a
stamp it ran ONE 400-row slice per factor per day and stopped. Between
09-11 13:41 and 09-13 12:45 exactly one 400/400 batch landed, and rows with a
stamp older than 48h grew from 5,422 to 10,005 (fundamentals) and from 7,630 to
9,805 (smart money) in two days: a ~30-day rotation for 11,918 rows. What had
looked like freshness before came from restarts re-running the chain and from
newly discovered tickers flipping it back into its three-hour mode.

Three more defects sat on top of that, and each has a test here:

* A 429 came back as the same None as "no coverage", so a throttled symbol was
  stamped as settled and sat out a whole horizon.
* Stopping to stamp throttled symbols must not stop stamping EVERY failure: a
  symbol that 5xx's every time, left unstamped, stays at the head of every
  selection, and a handful of them would stall the refresh for everyone. An
  earlier design did exactly that; the poison-pill test below is its guard.
* The insider pass's score lived only in process memory until a later writer
  saved it. A restart in between lost it, and the stamp hid the symbol: 3,231
  rows on 2026-09-13, NVDA, AAPL, MSFT, GOOGL, AMZN and META among them.

Review found three more, each with tests in section 7:

* The phase stopped when a round did not LOWER the due count. Rows cross their
  horizon mid-round at the pace an earlier run stamped them, so a healthy phase
  ended with thousands of equities still due. It now stops only when a round
  lands no stamps.
* The budget was checked between slices, so a slice of throttle pauses could
  run on long past it. Each pass now checks it per symbol.
* A Finnhub outage answers every call with an error, which came back as the
  same None as "no coverage" and was stamped as settled. With the phase now
  reaching every due row, that would have pushed thousands of rows out a
  horizon. The passes now see failures, stop on a window of them - a run
  missed a brownout - and the phase backs off and tries again rather than
  losing the day to a blip.

Every test here was watched failing against a named mutation before it was kept.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import pathlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.db import session_scope
from app.models import InsiderTransaction, Ticker
from app.services import finnhub_feed
from app.services.finnhub_feed import FinnhubThrottledError, FinnhubUnavailableError
from app.workers import signal_publisher as sp

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

NOW = datetime.now(UTC)
H = timedelta(hours=1)


class _RunawayError(BaseException):
    """Raised by a fake after far more calls than any correct run makes.

    A BaseException, so the passes' `except Exception` cannot swallow it. Used
    where a mutation would otherwise loop forever and hang the suite instead
    of failing it.
    """


async def _seed(rows: list[dict[str, Any]]) -> None:
    async with session_scope() as s:
        for row in rows:
            s.add(Ticker(**{
                "name": f"{row['symbol']} Inc", "asset_class": "equity",
                "price": 100.0, "volume": 1_000, **row,
            }))


async def _stamps(column: str) -> dict[str, datetime | None]:
    async with session_scope() as s:
        rows = (await s.execute(select(Ticker.symbol, getattr(Ticker, column)))).all()
    return {sym: (ts if ts is None or ts.tzinfo else ts.replace(tzinfo=UTC)) for sym, ts in rows}


@pytest.fixture(autouse=True)
def slept(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Pacing and throttle pauses, recorded instead of slept."""
    record: list[float] = []

    async def _fake_sleep(seconds: float, *a: Any, **k: Any) -> None:
        record.append(seconds)

    monkeypatch.setattr(sp.asyncio, "sleep", _fake_sleep)
    return record


#: The fake clock's epoch. Clock-driven tests seed relative to this, not NOW.
T0 = datetime(2026, 11, 11, 2, 0, tzinfo=UTC)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch, slept: list[float]) -> list[datetime]:
    """A wall clock that only the passes' own sleeps move, starting at T0.

    `datetime.now` and `monotonic` inside signal_publisher both read it, so the
    due predicate, the stamps and the budget are all evaluated at the instants
    production would evaluate them - which is what a row crossing its horizon
    mid-round needs."""
    now = [T0]

    class _FakeDT(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return now[0]

    async def _sleep(seconds: float, *a: Any, **k: Any) -> None:
        slept.append(seconds)
        now[0] = now[0] + timedelta(seconds=seconds)

    monkeypatch.setattr(sp, "datetime", _FakeDT)
    monkeypatch.setattr(sp, "monotonic", lambda: (now[0] - T0).total_seconds())
    monkeypatch.setattr(sp.asyncio, "sleep", _sleep)
    return now


@pytest.fixture(autouse=True)
def _fresh_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(finnhub_feed, "_FUND_SCORE_CACHE", {})
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})


@pytest.fixture(autouse=True)
def _no_dated_backlog_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests pin the HORIZONS, seeding stamps relative to the wall clock.

    `_FUNDAMENTALS_UNSAVED_BEFORE` is a fixed instant: until it has aged past
    the 8-day horizon, a seeded equity stamped "a day ago" with no reading also
    matches it, and a horizon test would be measuring the wrong rule. It is
    tested on its own, at fixed instants, in
    tests/test_fundamentals_reading_survives_restart.py."""
    monkeypatch.setattr(sp, "_FUNDAMENTALS_UNSAVED_BEFORE", datetime(1970, 1, 1, tzinfo=UTC))


def _fundamentals_vendor(
    monkeypatch: pytest.MonkeyPatch, script: dict[str, list[str]] | None = None,
) -> list[str]:
    """Stand-in for fetch_basic_financials that honours the REAL contract.

    Outcomes per call, consumed in order (the last one repeats):
      ok        -> real metrics
      none      -> None ("no coverage")
      throttle  -> raises FinnhubThrottledError ONLY if the caller asked for it,
                   otherwise None - exactly like the real fetcher. So a pass
                   that forgets `raise_failures=True` is caught.
      down      -> raises FinnhubUnavailableError (a 5xx or timeout) ONLY if the
                   caller asked for it, otherwise None
      boom      -> RuntimeError (an error after the call: scoring, saving)
    """
    script = script or {}
    calls: list[str] = []

    async def _fetch(sym: str, *, raise_failures: bool = False) -> dict[str, float] | None:
        calls.append(sym)
        if len(calls) > 200:
            raise _RunawayError(f"{len(calls)} calls")
        queue = script.get(sym, ["ok"])
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if outcome == "throttle":
            if raise_failures:
                raise FinnhubThrottledError("stock/metric", 429)
            return None
        if outcome == "down":
            if raise_failures:
                raise FinnhubUnavailableError("stock/metric", "status=503")
            return None
        if outcome == "boom":
            raise RuntimeError("503")
        if outcome == "none":
            return None
        return {"roe": 20.0, "margin": 15.0}

    monkeypatch.setattr("app.services.finnhub_feed.fetch_basic_financials", _fetch)
    return calls


def _insider_vendor(
    monkeypatch: pytest.MonkeyPatch, script: dict[str, list[str]] | None = None,
) -> list[str]:
    """Same contract for fetch_insider_transactions. `ok` returns net selling."""
    script = script or {}
    calls: list[str] = []

    async def _fetch(
        sym: str, days_back: int = 90, *, raise_failures: bool = False,
    ) -> list[dict[str, Any]] | None:
        calls.append(sym)
        if len(calls) > 200:
            raise _RunawayError(f"{len(calls)} calls")
        queue = script.get(sym, ["ok"])
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if outcome == "throttle":
            if raise_failures:
                raise FinnhubThrottledError("stock/insider-transactions", 429)
            return None
        if outcome == "down":
            if raise_failures:
                raise FinnhubUnavailableError("stock/insider-transactions", "status=503")
            return None
        if outcome == "boom":
            raise RuntimeError("503")
        if outcome == "none":
            return []
        return [
            {"filer_name": "Jane Q Insider", "transaction_date": f"2026-09-0{d}",
             "share_change": -1_000, "transaction_price": 50.0, "code": "S"}
            for d in (1, 2, 3)
        ]

    monkeypatch.setattr("app.services.finnhub_feed.fetch_insider_transactions", _fetch)
    return calls


# ===========================================================================
# 1. THE STALL: a fully attempted universe must still refresh what is due.
# ===========================================================================


async def test_a_fully_attempted_universe_still_refreshes_what_is_due(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """The regression. No NULL stamps anywhere - the state production settled
    into - yet every equity's insider stamp is 3 days old. All of them must be
    refreshed in one phase, across as many slices as it takes.

    Mutations that turn this red: a NULL-only due predicate (nothing is due, no
    calls); stopping after the first round (2 of 5 refreshed); not re-reading
    the due counts between rounds (the phase then ends every healthy day on a
    false `no_progress` warning)."""
    monkeypatch.setattr(sp, "_FACTOR_SLICE", 2)
    old = NOW - 72 * H
    await _seed([
        {"symbol": f"EQ{i}", "last_smart_money_at": old, "last_fundamentals_at": NOW - 24 * H}
        for i in range(5)
    ])
    fundamentals = _fundamentals_vendor(monkeypatch)
    insider = _insider_vendor(monkeypatch)

    with caplog.at_level("INFO", logger=sp.logger.name):
        await asyncio.wait_for(sp._run_factor_phase(), timeout=30)

    assert "factor_phase.nothing_due" in caplog.text
    assert "factor_phase.no_progress" not in caplog.text
    assert sorted(insider) == [f"EQ{i}" for i in range(5)], (
        f"due rows were left stale: asked for {insider}"
    )
    stamps = await _stamps("last_smart_money_at")
    assert all(stamps[f"EQ{i}"] > NOW - H for i in range(5))
    assert fundamentals == [], "fundamentals stamped a day ago are not due and must not be fetched"
    assert await sp._factor_due_counts() == (0, 0)


async def test_rows_inside_their_horizon_cost_no_vendor_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A restart re-runs the chain. With nothing due that must be free."""
    await _seed([
        {"symbol": "FRESH", "last_smart_money_at": NOW - 10 * H,
         "last_fundamentals_at": NOW - 48 * H},
    ])
    fundamentals = _fundamentals_vendor(monkeypatch)
    insider = _insider_vendor(monkeypatch)

    await sp._run_factor_phase()

    assert (fundamentals, insider) == ([], [])


def test_the_horizons_outlive_the_vendor_caches() -> None:
    """A row due inside its cache window is answered from disk, re-stamped, and
    pushed out another horizon having learned nothing."""
    due = sp._EQUITY_FACTOR_DUE_AFTER
    assert due["last_smart_money_at"] > timedelta(hours=finnhub_feed.CACHE_TTL_INSIDER_HOURS)
    assert due["last_fundamentals_at"] > timedelta(
        hours=finnhub_feed.CACHE_TTL_FUNDAMENTALS_HOURS,
    )
    assert due["last_fundamentals_at"] <= sp._NON_EQUITY_FACTOR_DUE_AFTER


# ===========================================================================
# 2. Selection: due rows only, equities first, and the count agrees with it.
# ===========================================================================


async def test_non_equities_rotate_monthly_not_daily() -> None:
    await _seed([
        {"symbol": "ETFNEW", "asset_class": "etf", "last_smart_money_at": NOW - 72 * H},
        {"symbol": "ETFOLD", "asset_class": "etf", "last_smart_money_at": NOW - 31 * 24 * H},
    ])
    picked = await sp._select_factor_symbols(Ticker.last_smart_money_at, 10)
    assert picked == ["ETFOLD"], (
        f"an ETF three days after its last attempt is not due; one after a month is: {picked}"
    )


async def test_equities_are_served_before_non_equities() -> None:
    """Under a plain stamp order a 60-day-old ETF stamp beat a 40-hour-old equity."""
    await _seed([
        {"symbol": "OLDETF", "asset_class": "etf", "last_smart_money_at": NOW - 60 * 24 * H},
        {"symbol": "DUEEQ", "last_smart_money_at": NOW - 40 * H},
    ])
    assert await sp._select_factor_symbols(Ticker.last_smart_money_at, 1) == ["DUEEQ"]


async def test_the_due_count_covers_exactly_what_selection_can_return() -> None:
    """The phase loops while this count is non-zero. If it counted a row the
    selection can never return, the phase would run rounds that ask for nothing."""
    await _seed([
        {"symbol": "NEVER"},
        {"symbol": "EQFRESH", "last_smart_money_at": NOW - 5 * H},
        {"symbol": "EQSTALE", "last_smart_money_at": NOW - 50 * H},
        {"symbol": "ETFFRESH", "asset_class": "etf", "last_smart_money_at": NOW - 50 * H},
        {"symbol": "ETFSTALE", "asset_class": "etf", "last_smart_money_at": NOW - 40 * 24 * H},
        {"symbol": "COIN", "asset_class": "crypto", "last_smart_money_at": NOW - 40 * 24 * H},
    ])
    picked = await sp._select_factor_symbols(Ticker.last_smart_money_at, 100)
    _, smart_due = await sp._factor_due_counts()
    assert sorted(picked) == ["COIN", "EQSTALE", "ETFSTALE", "NEVER"]
    assert smart_due == len(picked)


# ===========================================================================
# 3. Throttling: not an answer, retried, bounded - and ONLY throttling.
# ===========================================================================


async def test_a_throttled_symbol_is_retried_not_stamped_as_settled(
    monkeypatch: pytest.MonkeyPatch, slept: list[float],
) -> None:
    """Mutations: dropping `raise_failures=True` from the pass (the fake then
    returns None, the symbol is stamped after one call); stamping on a throttle
    instead of retrying."""
    await _seed([{"symbol": "RETRY"}])
    calls = _fundamentals_vendor(monkeypatch, {"RETRY": ["throttle", "ok"]})

    stopped = await sp._refresh_fundamentals_cache(limit=1)

    assert stopped is False
    assert calls == ["RETRY", "RETRY"], f"a throttled symbol must be asked again: {calls}"
    assert sp._FACTOR_THROTTLE_PAUSE_SECONDS in slept
    assert finnhub_feed.get_cached_score("RETRY") is not None
    assert (await _stamps("last_fundamentals_at"))["RETRY"] is not None


async def test_a_sustained_throttle_stops_the_pass_and_leaves_rows_due(
    monkeypatch: pytest.MonkeyPatch, slept: list[float],
) -> None:
    await _seed([{"symbol": f"T{i}", "volume": 1_000 - i} for i in range(3)])
    calls = _fundamentals_vendor(monkeypatch, {f"T{i}": ["throttle"] for i in range(3)})

    stopped = await sp._refresh_fundamentals_cache(limit=3)

    assert stopped is True
    assert len(calls) == sp._FACTOR_THROTTLE_MAX_PAUSES + 1
    assert slept.count(sp._FACTOR_THROTTLE_PAUSE_SECONDS) == sp._FACTOR_THROTTLE_MAX_PAUSES
    assert all(v is None for v in (await _stamps("last_fundamentals_at")).values()), (
        "nothing was answered, so nothing may be stamped as settled"
    )


async def test_throttles_must_be_consecutive_to_stop_a_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: never resetting the counter after an answer. Scattered throttles
    across a long slice would then add up and end a healthy pass."""
    max_pauses = sp._FACTOR_THROTTLE_MAX_PAUSES
    await _seed([{"symbol": "A", "volume": 2_000}, {"symbol": "B", "volume": 1_000}])
    _fundamentals_vendor(monkeypatch, {
        "A": ["throttle"] * max_pauses + ["ok"],
        "B": ["throttle"] * max_pauses + ["ok"],
    })

    stopped = await sp._refresh_fundamentals_cache(limit=2)

    assert stopped is False
    stamps = await _stamps("last_fundamentals_at")
    assert stamps["A"] is not None and stamps["B"] is not None


async def test_the_insider_pass_obeys_the_same_throttle_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed([{"symbol": "INS1", "volume": 2_000}, {"symbol": "INS2", "volume": 1_000}])
    calls = _insider_vendor(monkeypatch, {"INS1": ["throttle", "ok"], "INS2": ["throttle"]})

    stopped = await sp._refresh_insider_cache(limit=2)

    assert stopped is True
    assert calls[:2] == ["INS1", "INS1"], f"INS1 must be retried after its throttle: {calls}"
    stamps = await _stamps("last_smart_money_at")
    assert stamps["INS1"] is not None, "answered on retry, so stamped"
    assert stamps["INS2"] is None, "never answered, so still due"


async def test_a_symbol_that_errors_every_time_cannot_block_the_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The poison pill. Six symbols at the head of the queue fail on every call
    with a non-throttle error. They must be stamped and passed over, so the rows
    behind them still refresh.

    Mutation: treating every failure like a throttle (no stamp). The six stay at
    the head, the phase sees no progress, and the two good rows never refresh."""
    monkeypatch.setattr(sp, "_FACTOR_SLICE", 3)
    await _seed(
        [{"symbol": f"BAD{i}", "volume": 10_000 - i} for i in range(6)]
        + [{"symbol": "GOOD1", "volume": 10}, {"symbol": "GOOD2", "volume": 9}]
    )
    _fundamentals_vendor(monkeypatch, {f"BAD{i}": ["down"] for i in range(6)})
    _insider_vendor(monkeypatch)

    await sp._run_factor_phase()

    stamps = await _stamps("last_fundamentals_at")
    assert all(v is not None for v in stamps.values()), f"rows left unrefreshed: {stamps}"
    assert finnhub_feed.get_cached_score("GOOD1") is not None
    assert finnhub_feed.get_cached_score("GOOD2") is not None


# ===========================================================================
# 4. The phase's exits.
# ===========================================================================


async def test_a_throttled_pass_ends_the_phase_without_running_the_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The throttle is on the key; the other pass would only hit it too.
    Mutation: running the insider pass regardless."""
    await _seed([{"symbol": "BOTH"}])
    _fundamentals_vendor(monkeypatch, {"BOTH": ["throttle"]})
    insider = _insider_vendor(monkeypatch)

    await sp._run_factor_phase()

    assert insider == []
    assert await sp._factor_due_counts() == (1, 1)


async def test_the_phase_ends_when_stamps_do_not_land(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If stamps are not being written, every round would re-ask the vendor for
    the same rows until the budget. Mutation: no progress check (the runaway
    guard in the fake then fails the test instead of hanging it)."""
    monkeypatch.setattr(sp, "_FACTOR_SLICE", 2)

    async def _stamps_lost(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(sp, "_stamp_factor_attempts", _stamps_lost)
    await _seed([
        {"symbol": f"NP{i}", "volume": 100 - i, "last_fundamentals_at": NOW}
        for i in range(5)
    ])
    _fundamentals_vendor(monkeypatch)
    insider = _insider_vendor(monkeypatch)

    await sp._run_factor_phase()

    assert len(insider) == 2, f"expected one round of 2, got {len(insider)} calls"


async def test_the_phase_ends_at_its_budget(
    monkeypatch: pytest.MonkeyPatch, clock: list[datetime], caplog: pytest.LogCaptureFixture,
) -> None:
    """A 3-second budget at 1.1s a call: three calls, then the budget exit.

    Mutation: no budget check in the phase. The passes still stop at the
    deadline, but the phase then runs an empty round and leaves through
    `no_progress`, a warning that says stamps are failing when they are not."""
    monkeypatch.setattr(sp, "_FACTOR_SLICE", 2)
    monkeypatch.setattr(sp, "_FACTOR_PHASE_BUDGET_SECONDS", 3)
    await _seed([
        {"symbol": f"BG{i}", "volume": 100 - i, "last_fundamentals_at": T0}
        for i in range(5)
    ])
    _fundamentals_vendor(monkeypatch)
    insider = _insider_vendor(monkeypatch)

    with caplog.at_level("INFO", logger=sp.logger.name):
        # Bounded: a phase that loops without asking the vendor never trips the
        # fakes' runaway guard, and would hang the suite instead of failing it.
        await asyncio.wait_for(sp._run_factor_phase(), timeout=30)

    assert insider == ["BG0", "BG1", "BG2"]
    assert await sp._factor_due_counts() == (0, 2)
    assert "factor_phase.budget_exhausted" in caplog.text
    assert "factor_phase.no_progress" not in caplog.text


def test_the_chain_guards_the_factor_phase() -> None:
    """A failure inside the phase must not take the display backfills down with
    it: their 24h latch is already claimed when the chain starts."""
    tree = ast.parse(pathlib.Path(inspect.getfile(sp)).read_text(encoding="utf-8"))
    chain = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_serial_finnhub_refreshes"
    )
    guarded = [
        t for t in ast.walk(chain) if isinstance(t, ast.Try)
        and any(
            isinstance(c, ast.Call) and getattr(c.func, "id", None) == "_run_factor_phase"
            for stmt in t.body for c in ast.walk(stmt)
        )
    ]
    assert guarded, "_run_factor_phase is called outside a try in the chain"
    # A try that only catches something narrower, or re-raises, guards nothing.
    containing = [
        h for t in guarded for h in t.handlers
        if (h.type is None or getattr(h.type, "id", None) in {"Exception", "BaseException"})
        and not any(isinstance(n, ast.Raise) for n in ast.walk(h))
    ]
    assert containing, "the chain's guard around _run_factor_phase does not contain a failure"


# ===========================================================================
# 5. The vendor client: only a 200 is an answer, and it raises only when asked.
# ===========================================================================


#: A payload that makes `_Resp.json()` raise, the way httpx does on a body that
#: is not JSON at all - an HTML error page served with status 200.
_UNPARSEABLE = object()


class _Resp:
    def __init__(self, status: int, payload: Any = None) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> Any:
        if self._payload is _UNPARSEABLE:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


def _client(status: int, payload: Any = None, raises: Exception | None = None) -> type:
    class _Client:
        calls = 0

        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_a: Any) -> bool:
            return False

        async def get(self, *_a: Any, **_k: Any) -> _Resp:
            type(self).calls += 1
            if raises is not None:
                raise raises
            return _Resp(status, payload)

    return _Client


@pytest.fixture
def vendor(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path):
    monkeypatch.setattr(finnhub_feed.settings, "finnhub_api_key", "test_key", raising=False)
    monkeypatch.setattr(finnhub_feed, "CACHE_DIR", tmp_path)

    def _use(status: int, payload: Any = None, raises: Exception | None = None) -> type:
        cls = _client(status, payload, raises)
        monkeypatch.setattr(finnhub_feed.httpx, "AsyncClient", cls)
        return cls

    return _use


@pytest.mark.parametrize("status", [429, 401])
async def test_a_throttled_metric_call_raises_only_when_asked(vendor, status: int) -> None:
    cls = vendor(status)
    with pytest.raises(FinnhubThrottledError):
        await finnhub_feed.fetch_basic_financials("THRTL", raise_failures=True)
    assert await finnhub_feed.fetch_basic_financials("THRTL") is None, (
        "every other caller keeps the old None"
    )
    await finnhub_feed.fetch_basic_financials("THRTL")
    assert cls.calls == 3, "a throttled answer must never be cached"


@pytest.mark.parametrize("status", [302, 400, 403, 404, 408, 422, 500, 503])
async def test_a_failed_call_raises_unavailable_only_when_asked(vendor, status: int) -> None:
    """Finnhub says "nothing for this symbol" with a 200 and an empty body. Any
    other status is not an answer, and read as one it stamped the universe in
    silence. Mutations: raising only for 5xx; ignoring the flag."""
    cls = vendor(status)
    with pytest.raises(FinnhubUnavailableError):
        await finnhub_feed.fetch_basic_financials("DOWNX", raise_failures=True)
    with pytest.raises(FinnhubUnavailableError):
        await finnhub_feed.fetch_insider_transactions("DOWNX", raise_failures=True)
    assert await finnhub_feed.fetch_basic_financials("DOWNX") is None
    assert await finnhub_feed.fetch_insider_transactions("DOWNX") is None
    await finnhub_feed.fetch_basic_financials("DOWNX")
    assert cls.calls == 5, "a failed call must never be cached"


@pytest.mark.parametrize("payload", [_UNPARSEABLE, [], "oops", None])
async def test_a_200_that_is_not_a_json_object_is_not_an_answer(vendor, payload: Any) -> None:
    """An outage page served with status 200 must trip the breaker, not read as
    "no coverage". Mutations: catching the parse error as None; dropping the
    object check (a list or string body then escaped as AttributeError)."""
    cls = vendor(200, payload)
    with pytest.raises(FinnhubUnavailableError):
        await finnhub_feed.fetch_basic_financials("HTMLX", raise_failures=True)
    with pytest.raises(FinnhubUnavailableError):
        await finnhub_feed.fetch_insider_transactions("HTMLX", raise_failures=True)
    assert await finnhub_feed.fetch_basic_financials("HTMLX") is None
    assert await finnhub_feed.fetch_insider_transactions("HTMLX") is None
    await finnhub_feed.fetch_basic_financials("HTMLX")
    assert cls.calls == 5, "a body that is not an answer must never be negative-cached"


async def test_a_transport_error_raises_unavailable_only_when_asked(vendor) -> None:
    import httpx

    vendor(200, raises=httpx.ConnectTimeout("timed out"))
    with pytest.raises(FinnhubUnavailableError):
        await finnhub_feed.fetch_basic_financials("SLOWX", raise_failures=True)
    with pytest.raises(FinnhubUnavailableError):
        await finnhub_feed.fetch_insider_transactions("SLOWX", raise_failures=True)
    assert await finnhub_feed.fetch_basic_financials("SLOWX") is None
    assert await finnhub_feed.fetch_insider_transactions("SLOWX") is None


def test_an_outage_is_not_a_throttle() -> None:
    """The passes leave a throttle unstamped. An outage-shaped failure that
    were a throttle would be the poison pill again."""
    assert not issubclass(FinnhubUnavailableError, FinnhubThrottledError)


async def test_a_throttled_insider_call_raises_only_when_asked(vendor) -> None:
    vendor(429)
    with pytest.raises(FinnhubThrottledError):
        await finnhub_feed.fetch_insider_transactions("THRTL", raise_failures=True)
    assert await finnhub_feed.fetch_insider_transactions("THRTL") is None


# ===========================================================================
# 6. A restart no longer loses a smart-money reading.
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


async def test_a_restart_no_longer_loses_a_reading_the_pass_computed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole loop, on the path that lost 2,404 sheet-owned rows.

    The pass scores OXY into memory; the process dies before any writer saves
    it; the new process warms; the sheet refresh writes the cache onto the row.
    Mutation: not calling the rebuild from the warm - the row ends up NULL."""
    from app.services.sheet_feed import parse_all_signals_csv, upsert_tickers

    await _seed([{"symbol": "OXY"}])
    _insider_vendor(monkeypatch)
    await sp._refresh_insider_cache(limit=1)
    expected = finnhub_feed.get_cached_smart_money_score("OXY")
    assert expected == 10.0

    # The restart: memory gone, and nothing ever put the value on the row.
    monkeypatch.setattr(finnhub_feed, "_SMART_MONEY_SCORE_CACHE", {})
    async with session_scope() as s:
        row = (await s.execute(select(Ticker).where(Ticker.symbol == "OXY"))).scalar_one()
        assert row.sub_smart_money is None

    await finnhub_feed.warm_factor_caches_from_db()
    async with session_scope() as s:
        await upsert_tickers(s, parse_all_signals_csv(_SHEET_CSV))

    async with session_scope() as s:
        row = (await s.execute(select(Ticker).where(Ticker.symbol == "OXY"))).scalar_one()
    assert row.sub_smart_money == expected


async def _seed_insider(symbol: str, fetched: datetime, lines: int = 2) -> None:
    async with session_scope() as s:
        for i in range(lines):
            s.add(InsiderTransaction(
                symbol=symbol, insider_name="Jane Q Insider",
                transaction_date=f"2026-09-0{i + 1}", share_change=-500,
                transaction_price=20.0, transaction_value=10_000.0, code="S",
                fetched_at=fetched,
            ))


async def test_the_rebuild_only_trusts_the_stamped_fetch() -> None:
    """Mutation: dropping the eligibility check - the stale fetch comes back."""
    stamp = NOW - 30 * H
    await _seed([
        {"symbol": "MATCH", "last_smart_money_at": stamp},
        {"symbol": "STALE", "last_smart_money_at": stamp},
        {"symbol": "X:BTCUSD", "asset_class": "crypto", "last_smart_money_at": stamp},
        {"symbol": "KEPT", "last_smart_money_at": stamp, "sub_smart_money": 77.0},
    ])
    await _seed_insider("MATCH", stamp - timedelta(seconds=40))
    await _seed_insider("STALE", stamp - 48 * H)
    await _seed_insider("X:BTCUSD", stamp - timedelta(seconds=40))
    await _seed_insider("KEPT", stamp - timedelta(seconds=40))

    await finnhub_feed.warm_factor_caches_from_db()

    assert finnhub_feed.get_cached_smart_money_score("MATCH") == 10.0
    assert finnhub_feed.get_cached_smart_money_score("STALE") is None, (
        "rows from an older fetch than the stamp are not the reading the stamp records"
    )
    assert finnhub_feed.get_cached_smart_money_score("X:BTCUSD") is None
    assert finnhub_feed.get_cached_smart_money_score("KEPT") == 77.0, (
        "a value already on the row is loaded as it is, not recomputed"
    )


def test_the_rebuild_rule_is_the_backfill_scripts_rule() -> None:
    """One rule for "a lost reading", so the boot warm and #812's repair script
    can never disagree. Mutation: moving INSIDER_STAMP_LAG or the skew."""
    from app.scripts import backfill_smart_money as bsm

    stamp = datetime(2026, 9, 9, 14, 0, tzinfo=UTC)
    offsets = [timedelta(minutes=m) for m in (-60, -16, -15, -14, -1, 0, 1, 2, 3, 30)]
    # Both boundaries exactly, where a `<` vs `<=` slip would hide.
    offsets += [timedelta(seconds=s) for s in (-121, -120, -119, 899, 900, 901)]
    for lag in offsets:
        for multi in (False, True):
            first = stamp - lag
            last = first + (timedelta(seconds=5) if multi else timedelta(0))
            script = bsm._classify(bsm._Group("SYM", stamp, first, last)) == "eligible"
            ours = finnhub_feed.insider_rows_are_the_stamped_fetch(stamp, first, last)
            assert ours == script, f"disagree at lag={lag} multi={multi}: warm={ours} script={script}"


# ===========================================================================
# 7. Found in review: each test names the defect it reproduces.
# ===========================================================================

#: pass name -> (stamp column, vendor fake, pass function name)
_PASSES = {
    "fundamentals": ("last_fundamentals_at", _fundamentals_vendor, "_refresh_fundamentals_cache"),
    "insider": ("last_smart_money_at", _insider_vendor, "_refresh_insider_cache"),
}


async def test_rows_crossing_their_horizon_mid_round_do_not_end_the_phase(
    monkeypatch: pytest.MonkeyPatch, clock: list[datetime],
) -> None:
    """Six equities are due. Two ETFs reach their 30-day horizon one and two
    seconds into the first slice, so round one stamps two rows and two more
    become due: the count does not move, yet stamps landed fine.

    Mutation: ending the phase when the due count does not fall. It stopped
    here with four due equities never asked for."""
    monkeypatch.setattr(sp, "_FACTOR_SLICE", 2)
    await _seed(
        [{"symbol": f"EQ{i}", "last_fundamentals_at": T0 - 24 * H,
          "last_smart_money_at": T0 - 72 * H - timedelta(minutes=i)} for i in range(6)]
        + [
            {"symbol": f"ETF{s}", "asset_class": "etf", "last_fundamentals_at": T0,
             "last_smart_money_at": T0 - timedelta(days=30) + timedelta(seconds=s)}
            for s in (1, 2)
        ]
    )
    _fundamentals_vendor(monkeypatch)
    insider = _insider_vendor(monkeypatch)

    await sp._run_factor_phase()

    assert sorted(s for s in insider if s.startswith("EQ")) == [f"EQ{i}" for i in range(6)]
    assert await sp._factor_due_counts() == (0, 0)


async def test_a_wave_of_rows_coming_due_does_not_end_the_phase(
    monkeypatch: pytest.MonkeyPatch, clock: list[datetime],
) -> None:
    """The production shape: a run 36 hours ago stamped a row every 1.1s, so
    today those rows come due at exactly the pace this run stamps. Six older
    rows are waiting behind nothing.

    Mutation: ending the phase when the due count does not fall."""
    monkeypatch.setattr(sp, "_FACTOR_SLICE", 2)
    await _seed(
        [{"symbol": f"OLD{i}", "last_fundamentals_at": T0,
          "last_smart_money_at": T0 - 72 * H - timedelta(minutes=i)} for i in range(6)]
        + [{"symbol": f"WAVE{i:02d}", "last_fundamentals_at": T0,
            "last_smart_money_at": T0 - 36 * H + timedelta(seconds=1.1 * (i + 1))}
           for i in range(20)]
    )
    _fundamentals_vendor(monkeypatch)
    _insider_vendor(monkeypatch)

    await sp._run_factor_phase()

    stamps = await _stamps("last_smart_money_at")
    stale = sorted(s for s, ts in stamps.items() if s.startswith("OLD") and ts < T0)
    assert stale == [], f"the phase ended with 72-hour-old rows never asked for: {stale}"


@pytest.mark.parametrize("which", sorted(_PASSES))
async def test_a_slice_cannot_run_past_the_budget(
    monkeypatch: pytest.MonkeyPatch, clock: list[datetime], which: str,
) -> None:
    """The budget used to be checked only between slices, so a 400-row slice
    started a second before it ran its full ~7 minutes, or far longer through
    throttle pauses. Mutation: no deadline check inside the pass."""
    column, vendor, pass_name = _PASSES[which]
    await _seed([{"symbol": f"S{i}", "volume": 100 - i} for i in range(10)])
    calls = vendor(monkeypatch)

    stopped = await getattr(sp, pass_name)(limit=10, deadline=3.0)

    assert stopped is False, "a spent budget is not a vendor failure"
    assert calls == ["S0", "S1", "S2"]
    stamps = await _stamps(column)
    assert sorted(s for s, ts in stamps.items() if ts is not None) == ["S0", "S1", "S2"]


@pytest.mark.parametrize("which", sorted(_PASSES))
async def test_throttle_pauses_count_against_the_budget(
    monkeypatch: pytest.MonkeyPatch, clock: list[datetime], which: str,
) -> None:
    """Mutation: checking the deadline only after an answer, not after a pause."""
    _, vendor, pass_name = _PASSES[which]
    await _seed([{"symbol": "P0", "volume": 2}, {"symbol": "P1", "volume": 1}])
    calls = vendor(monkeypatch, {"P0": ["throttle", "throttle", "throttle", "ok"]})

    stopped = await getattr(sp, pass_name)(limit=2, deadline=100.0)

    assert stopped is False
    assert calls == ["P0", "P0"], f"two pauses reach the 100s budget: {calls}"


@pytest.mark.parametrize("which", sorted(_PASSES))
async def test_answered_symbols_are_stamped_before_a_throttle_pause(
    monkeypatch: pytest.MonkeyPatch, clock: list[datetime], which: str,
) -> None:
    """Answers used to wait in the batch through every pause. For the insider
    pass that matters twice: the boot rebuild trusts stored Form 4 rows only
    within INSIDER_STAMP_LAG of their stamp. Mutation: no flush before the pause."""
    column, vendor, pass_name = _PASSES[which]
    await _seed([{"symbol": "ANS", "volume": 2}, {"symbol": "WAIT", "volume": 1}])
    vendor(monkeypatch, {"WAIT": ["throttle", "ok"]})

    await getattr(sp, pass_name)(limit=2)

    stamps = await _stamps(column)
    assert stamps["ANS"] - T0 < timedelta(seconds=sp._FACTOR_THROTTLE_PAUSE_SECONDS), (
        f"ANS was answered before the pause but stamped at T0+{stamps['ANS'] - T0}"
    )
    assert stamps["WAIT"] is not None


@pytest.mark.parametrize("which", sorted(_PASSES))
async def test_an_outage_stops_the_pass(
    monkeypatch: pytest.MonkeyPatch, which: str,
) -> None:
    """Every call fails the way a Finnhub outage fails. Mutations: no breaker
    (every row is stamped having learned nothing); the pass not asking the
    client to raise (the outage reads as "no coverage"); stopping one failure
    late."""
    column, vendor, pass_name = _PASSES[which]
    stop = sp._FACTOR_FAILURE_STOP
    syms = [f"O{i:02d}" for i in range(stop + 5)]
    await _seed([{"symbol": s, "volume": 1_000 - i} for i, s in enumerate(syms)])
    calls = vendor(monkeypatch, {s: ["down"] for s in syms})

    stopped = await getattr(sp, pass_name)(limit=stop + 5)

    assert stopped is True
    assert len(calls) == stop
    stamps = await _stamps(column)
    assert sum(ts is not None for ts in stamps.values()) == stop, (
        "the failures it did see are stamped, so a cluster of bad symbols rotates out"
    )


@pytest.mark.parametrize("which", sorted(_PASSES))
async def test_a_brownout_stops_the_pass(
    monkeypatch: pytest.MonkeyPatch, which: str,
) -> None:
    """Two calls in three fail. That never builds a long run of failures, so a
    run-based stop never fired and the pass stamped two-thirds of its rows having
    learned nothing. Mutation: counting a run instead of a window."""
    column, vendor, pass_name = _PASSES[which]
    window = sp._FACTOR_FAILURE_WINDOW
    syms = [f"W{i:02d}" for i in range(2 * window)]
    await _seed([{"symbol": s, "volume": 1_000 - i} for i, s in enumerate(syms)])
    vendor(monkeypatch, {s: ["ok" if i % 3 == 2 else "down"] for i, s in enumerate(syms)})

    stopped = await getattr(sp, pass_name)(limit=2 * window)

    assert stopped is True
    stamped = sum(ts is not None for ts in (await _stamps(column)).values())
    assert stamped <= window, f"a brownout stamped {stamped} rows before the pass noticed"


@pytest.mark.parametrize("which", sorted(_PASSES))
async def test_scattered_failures_do_not_stop_a_pass(
    monkeypatch: pytest.MonkeyPatch, which: str,
) -> None:
    """One call in five fails, spread across twice the window: a few broken
    symbols, not an outage. Mutation: a window that never forgets."""
    column, vendor, pass_name = _PASSES[which]
    window = sp._FACTOR_FAILURE_WINDOW
    syms = [f"M{i:02d}" for i in range(2 * window)]
    await _seed([{"symbol": s, "volume": 1_000 - i} for i, s in enumerate(syms)])
    vendor(monkeypatch, {s: ["down" if i % 5 == 0 else "ok"] for i, s in enumerate(syms)})

    stopped = await getattr(sp, pass_name)(limit=2 * window)

    assert stopped is False
    assert all(ts is not None for ts in (await _stamps(column)).values())


async def test_a_short_outage_does_not_cost_the_day(
    monkeypatch: pytest.MonkeyPatch, slept: list[float], caplog: pytest.LogCaptureFixture,
) -> None:
    """Enough failures to stop the pass, then Finnhub recovers. The phase used to
    return there, and with the chain's 24h latch already claimed every row still
    due waited a day. Mutation: returning on a stop instead of backing off."""
    stop = sp._FACTOR_FAILURE_STOP
    await _seed([
        {"symbol": f"B{i:02d}", "volume": 1_000 - i, "last_smart_money_at": NOW - H}
        for i in range(30)
    ])
    calls: list[str] = []

    async def _recovering(sym: str, *, raise_failures: bool = False) -> dict[str, float] | None:
        calls.append(sym)
        if len(calls) <= stop:
            if raise_failures:
                raise FinnhubUnavailableError("stock/metric", "status=502")
            return None
        return {"roe": 20.0, "margin": 15.0}

    monkeypatch.setattr("app.services.finnhub_feed.fetch_basic_financials", _recovering)
    _insider_vendor(monkeypatch)

    with caplog.at_level("INFO", logger=sp.logger.name):
        await asyncio.wait_for(sp._run_factor_phase(), timeout=30)

    assert sp._FACTOR_PHASE_BACKOFF_SECONDS in slept
    assert "factor_phase.nothing_due" in caplog.text
    assert all(finnhub_feed.get_cached_score(f"B{i:02d}") is not None for i in range(stop, 30))
    assert await sp._factor_due_counts() == (0, 0)


async def test_a_lasting_outage_gives_up_after_its_backoffs(
    monkeypatch: pytest.MonkeyPatch, slept: list[float], caplog: pytest.LogCaptureFixture,
) -> None:
    """Both endpoints fail on every call. The phase backs off its allowance and
    then gives up for the day, having stamped one breaker's worth of rows per
    attempt, and never sends the other pass into the outage. Mutations: no cap on
    backoffs; a backoff that does not wait."""
    stop, backoffs = sp._FACTOR_FAILURE_STOP, sp._FACTOR_PHASE_MAX_BACKOFFS
    syms = [f"L{i:03d}" for i in range(120)]
    await _seed([{"symbol": s, "volume": 10_000 - i} for i, s in enumerate(syms)])
    fundamentals = _fundamentals_vendor(monkeypatch, {s: ["down"] for s in syms})
    insider = _insider_vendor(monkeypatch, {s: ["down"] for s in syms})

    with caplog.at_level("INFO", logger=sp.logger.name):
        await asyncio.wait_for(sp._run_factor_phase(), timeout=30)

    assert len(fundamentals) == stop * (1 + backoffs)
    assert insider == [], "an outage on the key is an outage for the other endpoint too"
    assert slept.count(sp._FACTOR_PHASE_BACKOFF_SECONDS) == backoffs
    assert "factor_phase.gave_up" in caplog.text


async def test_a_backoff_never_runs_past_the_budget(
    monkeypatch: pytest.MonkeyPatch, clock: list[datetime], slept: list[float],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mutation: backing off without checking the deadline."""
    monkeypatch.setattr(sp, "_FACTOR_PHASE_BUDGET_SECONDS", 300)
    syms = [f"K{i:02d}" for i in range(30)]
    await _seed([
        {"symbol": s, "volume": 1_000 - i, "last_smart_money_at": T0} for i, s in enumerate(syms)
    ])
    _fundamentals_vendor(monkeypatch, {s: ["down"] for s in syms})
    _insider_vendor(monkeypatch)

    with caplog.at_level("INFO", logger=sp.logger.name):
        await asyncio.wait_for(sp._run_factor_phase(), timeout=30)

    assert sp._FACTOR_PHASE_BACKOFF_SECONDS not in slept
    assert "factor_phase.gave_up" in caplog.text


@pytest.mark.parametrize("broken", sorted(_PASSES))
async def test_a_pass_that_raises_does_not_cost_the_other_pass(
    monkeypatch: pytest.MonkeyPatch, broken: str,
) -> None:
    """A pass can still raise - its selection query, say. Mutation: no guard
    around that pass in the phase, so the exception leaves the phase and the
    other factor waits a day."""
    monkeypatch.setattr(sp, "_FACTOR_SLICE", 1)
    await _seed([{"symbol": f"R{i}", "volume": 100 - i} for i in range(3)])

    async def _raise(*_a: Any, **_k: Any) -> bool:
        raise RuntimeError("selection query failed")

    monkeypatch.setattr(sp, _PASSES[broken][2], _raise)
    _, working_vendor, _ = _PASSES["insider" if broken == "fundamentals" else "fundamentals"]
    calls = working_vendor(monkeypatch)

    await asyncio.wait_for(sp._run_factor_phase(), timeout=30)

    assert sorted(calls) == ["R0", "R1", "R2"]


async def test_a_failure_before_any_stamp_is_retried_not_read_as_no_progress(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """Only smart money is due, and its pass fails once before stamping anything -
    a database blip in its selection. That ended the phase as `no_progress`, a
    warning meant for stamps that do not land. Mutation: treating a failed round
    like a round whose stamps did not land."""
    await _seed([
        {"symbol": f"T{i}", "volume": 100 - i, "last_fundamentals_at": NOW} for i in range(3)
    ])
    real_select = sp._select_factor_symbols
    blips = [1]

    async def _flaky(*a: Any, **k: Any) -> list[str]:
        if blips[0]:
            blips[0] -= 1
            raise RuntimeError("connection reset")
        return await real_select(*a, **k)

    monkeypatch.setattr(sp, "_select_factor_symbols", _flaky)
    insider = _insider_vendor(monkeypatch)

    with caplog.at_level("INFO", logger=sp.logger.name):
        await asyncio.wait_for(sp._run_factor_phase(), timeout=30)

    assert sorted(insider) == ["T0", "T1", "T2"]
    assert "factor_phase.no_progress" not in caplog.text


async def test_the_phase_hands_its_budget_to_the_fundamentals_pass(
    monkeypatch: pytest.MonkeyPatch, clock: list[datetime],
) -> None:
    """The budget test above only has smart money due. Mutation: dropping
    `deadline=` from the fundamentals pass's call inside the phase."""
    monkeypatch.setattr(sp, "_FACTOR_PHASE_BUDGET_SECONDS", 3)
    await _seed([
        {"symbol": f"FB{i}", "volume": 100 - i, "last_smart_money_at": T0} for i in range(5)
    ])
    fundamentals = _fundamentals_vendor(monkeypatch)
    _insider_vendor(monkeypatch)

    await asyncio.wait_for(sp._run_factor_phase(), timeout=30)

    assert fundamentals == ["FB0", "FB1", "FB2"]


async def test_rows_just_inside_their_horizon_are_not_due() -> None:
    """The other horizon tests use rows far from the lines. Mutation: loosening
    a horizon toward its cache TTL - smart money at 25h is every equity every
    day, about four times the calls the phase budget is sized for."""
    await _seed([
        {"symbol": "SM30H", "last_smart_money_at": NOW - 30 * H, "last_fundamentals_at": NOW - H},
        {"symbol": "F7D12H", "last_smart_money_at": NOW - H,
         "last_fundamentals_at": NOW - (7 * 24 + 12) * H},
        {"symbol": "ETF20D", "asset_class": "etf", "last_smart_money_at": NOW - 20 * 24 * H,
         "last_fundamentals_at": NOW - 20 * 24 * H},
    ])
    assert await sp._factor_due_counts() == (0, 0)


async def test_only_fundamentals_due_still_runs_to_completion(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """Mutation: looping only while smart money is due."""
    monkeypatch.setattr(sp, "_FACTOR_SLICE", 2)
    await _seed([
        {"symbol": f"F{i}", "volume": 100 - i, "last_smart_money_at": NOW - H,
         "last_fundamentals_at": NOW - 9 * 24 * H}
        for i in range(5)
    ])
    fundamentals = _fundamentals_vendor(monkeypatch)
    _insider_vendor(monkeypatch)

    with caplog.at_level("INFO", logger=sp.logger.name):
        await asyncio.wait_for(sp._run_factor_phase(), timeout=30)

    assert sorted(fundamentals) == [f"F{i}" for i in range(5)]
    assert "factor_phase.nothing_due" in caplog.text


async def test_an_insider_symbol_that_errors_every_time_cannot_block_the_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The poison pill, on the insider pass. Mutation: leaving its failures unstamped."""
    monkeypatch.setattr(sp, "_FACTOR_SLICE", 3)
    await _seed(
        [{"symbol": f"BAD{i}", "volume": 10_000 - i} for i in range(6)]
        + [{"symbol": "GOOD1", "volume": 10}, {"symbol": "GOOD2", "volume": 9}]
    )
    _fundamentals_vendor(monkeypatch)
    _insider_vendor(monkeypatch, {f"BAD{i}": ["boom"] for i in range(6)})

    await sp._run_factor_phase()

    stamps = await _stamps("last_smart_money_at")
    assert all(ts is not None for ts in stamps.values()), stamps
    assert finnhub_feed.get_cached_smart_money_score("GOOD2") is not None


async def test_an_insider_throttle_stops_every_attempt_until_the_phase_gives_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: the phase ignoring the insider pass's stop."""
    monkeypatch.setattr(sp, "_FACTOR_SLICE", 1)
    await _seed([{"symbol": "A", "volume": 2}, {"symbol": "B", "volume": 1}])
    _fundamentals_vendor(monkeypatch)
    insider = _insider_vendor(monkeypatch, {"A": ["throttle"], "B": ["throttle"]})

    await asyncio.wait_for(sp._run_factor_phase(), timeout=30)

    attempts = 1 + sp._FACTOR_PHASE_MAX_BACKOFFS
    assert len(insider) == (sp._FACTOR_THROTTLE_MAX_PAUSES + 1) * attempts, insider


async def test_insider_throttles_must_be_consecutive_to_stop_the_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    n = sp._FACTOR_THROTTLE_MAX_PAUSES
    await _seed([{"symbol": "A", "volume": 2_000}, {"symbol": "B", "volume": 1_000}])
    _insider_vendor(monkeypatch, {"A": ["throttle"] * n + ["ok"], "B": ["throttle"] * n + ["ok"]})

    assert await sp._refresh_insider_cache(limit=2) is False


async def test_the_throttle_pause_is_a_minute_in_both_passes(
    monkeypatch: pytest.MonkeyPatch, slept: list[float],
) -> None:
    """Finnhub's window is per minute. Mutation: a shorter pause, which the
    other tests (reading the constant) would not notice."""
    await _seed([{"symbol": "R"}])
    _fundamentals_vendor(monkeypatch, {"R": ["throttle", "ok"]})
    _insider_vendor(monkeypatch, {"R": ["throttle", "ok"]})

    await sp._refresh_fundamentals_cache(limit=1)
    assert 60.0 in slept
    slept.clear()
    await sp._refresh_insider_cache(limit=1)
    assert 60.0 in slept


async def test_a_throttle_stop_stamps_the_answered_and_not_the_throttled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: stamping the symbol the pass stopped on."""
    await _seed([{"symbol": "OK1", "volume": 2_000}, {"symbol": "THR", "volume": 1_000}])
    _fundamentals_vendor(monkeypatch, {"THR": ["throttle"]})

    assert await sp._refresh_fundamentals_cache(limit=2) is True

    stamps = await _stamps("last_fundamentals_at")
    assert stamps["OK1"] is not None and stamps["THR"] is None


async def test_equity_fundamentals_come_due_after_eight_days() -> None:
    """Mutation: widening the fundamentals horizon toward the monthly one."""
    await _seed([
        {"symbol": "D9", "last_fundamentals_at": NOW - 9 * 24 * H},
        {"symbol": "D6", "last_fundamentals_at": NOW - 6 * 24 * H},
    ])
    assert await sp._select_factor_symbols(Ticker.last_fundamentals_at, 10) == ["D9"]


async def test_the_oldest_due_equity_is_served_first() -> None:
    """Mutation: rotating newest stamp first."""
    await _seed([
        {"symbol": "NEWER", "last_smart_money_at": NOW - 50 * H},
        {"symbol": "OLDER", "last_smart_money_at": NOW - 100 * H},
    ])
    assert await sp._select_factor_symbols(Ticker.last_smart_money_at, 1) == ["OLDER"]


async def test_the_rebuild_scores_every_stored_row() -> None:
    """Mutation: scoring only one row per symbol. A buy and a sale must net."""
    stamp = NOW - 30 * H
    await _seed([{"symbol": "MIX", "last_smart_money_at": stamp}])
    async with session_scope() as s:
        for i, change in enumerate((1_000, -500)):
            s.add(InsiderTransaction(
                symbol="MIX", insider_name="Jane Q Insider",
                transaction_date=f"2026-09-0{i + 1}", share_change=change,
                transaction_price=10.0, transaction_value=abs(change) * 10.0,
                code="P" if change > 0 else "S", fetched_at=stamp - timedelta(seconds=30),
            ))

    await finnhub_feed.warm_factor_caches_from_db()

    assert finnhub_feed.get_cached_smart_money_score("MIX") == 63.3


async def test_an_unstamped_row_does_not_sink_the_rebuild() -> None:
    """Mutation: letting a NULL stamp into the eligibility rule, which raises."""
    stamp = NOW - 30 * H
    await _seed([{"symbol": "MATCH", "last_smart_money_at": stamp}, {"symbol": "NOSTAMP"}])
    await _seed_insider("MATCH", stamp - timedelta(seconds=30), lines=1)
    await _seed_insider("NOSTAMP", stamp - timedelta(seconds=30), lines=1)

    await finnhub_feed.warm_factor_caches_from_db()

    assert finnhub_feed.get_cached_smart_money_score("MATCH") == 10.0


async def test_a_failing_rebuild_query_is_contained(monkeypatch: pytest.MonkeyPatch) -> None:
    """The warm is awaited unguarded at worker boot and on the sheet webhook.
    Mutation: no try around the rebuild's reads."""
    await _seed([{"symbol": "W", "sub_fundamentals": 70.0, "last_smart_money_at": NOW - H}])
    await _seed_insider("W", NOW - H, lines=1)

    def _boom(*_a: Any, **_k: Any) -> bool:
        raise RuntimeError("db hiccup")

    monkeypatch.setattr(finnhub_feed, "insider_rows_are_the_stamped_fetch", _boom)

    funds, _ = await finnhub_feed.warm_factor_caches_from_db()

    assert funds == 1 and finnhub_feed.get_cached_score("W") == 70.0


async def test_a_failing_rebuild_score_is_contained(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutation: scoring outside the try, where review found it."""
    stamp = NOW - 30 * H
    await _seed([{"symbol": "SC", "sub_fundamentals": 70.0, "last_smart_money_at": stamp}])
    await _seed_insider("SC", stamp - timedelta(seconds=40))

    def _boom(*_a: Any, **_k: Any) -> float:
        raise ValueError("unexpected row shape")

    monkeypatch.setattr(finnhub_feed, "compute_smart_money_score", _boom)

    assert await finnhub_feed.warm_factor_caches_from_db() == (1, 0)
    assert finnhub_feed.get_cached_score("SC") == 70.0


async def test_a_failing_feed_count_does_not_hide_a_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pass's closing log line reads the feed size from the DB. Mutation:
    awaiting it unguarded - its error replaced the pass's True, and the phase
    carried on into the same throttle."""
    await _seed([{"symbol": "T"}])
    _insider_vendor(monkeypatch, {"T": ["throttle"]})

    async def _boom() -> int:
        raise RuntimeError("count failed")

    monkeypatch.setattr(finnhub_feed, "insider_feed_size_db", _boom)

    assert await sp._refresh_insider_cache(limit=1) is True
