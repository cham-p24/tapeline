"""Every stock and ETF must be re-read once a minute - the cycle, and the list.

MEASURED IN PRODUCTION, 2026-09-14 14:30 UTC, US session open (read-only SQL)
-----------------------------------------------------------------------------
* Passes started 71-76 seconds apart, never 60. The loop slept the full
  SCORE_REFRESH_SECONDS AFTER each tick, so the period was 60s plus an 11-16s
  tick.
* 250 non-crypto rows were 15-60 minutes stale while 11,562 were written in the
  last two minutes. They were exactly the never-scored rows outside the hourly
  bootstrap window - many with a live price and real volume (HONIV 7.1M shares,
  UCFI 5.4M, ADBT 6.6M). The window also counted never-scored crypto that it
  could never return, so it wrapped against the wrong total and came back
  short.
* A row first scored or added mid-session waited for an HOURLY list rebuild.

The founder's requirement, 2026-09-15: every ticker, minute by minute. Each test
here was watched failing against the code it replaces.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import textwrap
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.models import Ticker
from app.services import universe as universe_mod
from app.workers import signal_publisher as sp

# NO pytestmark: pytest.ini sets asyncio_mode = auto.


class _StopLoop(BaseException):
    """Escapes main()'s `except Exception` arms to end the infinite loop."""


# =============================================================================
# 1. The cycle: passes START every interval.
# =============================================================================


@pytest.fixture
def one_cycle(monkeypatch: pytest.MonkeyPatch):
    """Run main() for one cycle on a fake monotonic clock.

    Returns (clock, slept, warnings, set_tick). The tick advances the clock by
    whatever the test says a tick took; the loop's sleep is recorded and ends
    the loop.
    """
    clock = [1_000.0]
    slept: list[float] = []
    warnings: list[str] = []

    async def _noop() -> None:
        return None

    async def _refresh() -> int:
        return 11_812

    async def _sleep(seconds: float, *_a, **_k) -> None:
        slept.append(seconds)
        raise _StopLoop

    def _warning(msg: str, *args, **_k) -> None:
        warnings.append(msg % args if args else msg)

    monkeypatch.setattr(sp.settings, "score_refresh_seconds", 60, raising=False)
    monkeypatch.setattr(sp, "_init_sentry", lambda: None)
    monkeypatch.setattr(sp, "seed_universe", _noop)
    monkeypatch.setattr(sp, "warm_factor_caches_from_db", _noop)
    monkeypatch.setattr(sp, "refresh_active_universe", _refresh)
    monkeypatch.setattr(sp, "monotonic", lambda: clock[0])
    monkeypatch.setattr(sp.logger, "warning", _warning)
    monkeypatch.setattr(sp.logger, "error", lambda *a, **k: None)
    monkeypatch.setattr(sp.logger, "critical", lambda *a, **k: None)
    monkeypatch.setattr(asyncio, "sleep", _sleep)

    def set_tick(seconds: float, *, raises: BaseException | None = None) -> None:
        async def _tick() -> None:
            clock[0] += seconds
            if raises is not None:
                raise raises

        monkeypatch.setattr(sp, "tick", _tick)

    return clock, slept, warnings, set_tick


async def test_cycles_start_every_interval_not_an_interval_after_the_tick(one_cycle) -> None:
    """The regression. A 13-second tick must be followed by a 47-second pause,
    so the next pass starts 60 seconds after this one did. The old loop slept
    60 after it, and production ran a pass every ~73 seconds."""
    _clock, slept, _warnings, set_tick = one_cycle
    set_tick(13.0)

    with pytest.raises(_StopLoop):
        await sp.main()

    assert slept == [47.0], (
        f"after a 13s tick the loop slept {slept}; a pass must START every 60s, "
        "not 60s after the previous one finished"
    )


async def test_an_overrun_starts_the_next_cycle_promptly_and_says_so(one_cycle) -> None:
    """A tick longer than the interval already missed a minute. The next cycle
    starts after a short breath, and the miss is logged rather than absorbed."""
    _clock, slept, warnings, set_tick = one_cycle
    set_tick(75.0)

    with pytest.raises(_StopLoop):
        await sp.main()

    assert slept == [sp._MIN_CYCLE_PAUSE_SECONDS]
    assert sp._MIN_CYCLE_PAUSE_SECONDS <= 1.0, "a 'breath' longer than a second is a delay"
    assert any("tick.overrun" in w for w in warnings), warnings


async def test_a_killed_cycle_does_not_add_a_whole_interval(one_cycle) -> None:
    """The watchdog kills a hung tick at TICK_TIMEOUT_SECONDS. Waiting another
    full minute after that only widened the gap."""
    _clock, slept, _warnings, set_tick = one_cycle
    set_tick(float(sp.TICK_TIMEOUT_SECONDS), raises=TimeoutError())

    with pytest.raises(_StopLoop):
        await sp.main()

    assert slept == [sp._MIN_CYCLE_PAUSE_SECONDS]


async def test_a_quiet_tick_logs_no_overrun(one_cycle) -> None:
    """Guards the other direction: the warning must mean something."""
    _clock, _slept, warnings, set_tick = one_cycle
    set_tick(12.0)

    with pytest.raises(_StopLoop):
        await sp.main()

    assert not any("tick.overrun" in w for w in warnings), warnings


# =============================================================================
# 2. The list: every never-scored stock and ETF, on every rebuild.
# =============================================================================


async def _seed(*rows: Ticker) -> list[str]:
    async with session_scope() as s:
        for row in rows:
            s.add(row)
    return [r.symbol for r in rows]


async def _cleanup(symbols: list[str]) -> None:
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(symbols)))


async def _listed() -> set[str]:
    """Rebuild the list; fail on any symbol listed twice.

    A duplicate is not harmless: it is a second snapshot request for the same
    name, and for a symbol new to the table the tick stages two inserts of one
    primary key."""
    await universe_mod.refresh_active_universe()
    symbols = [row[0] for row in universe_mod.active_universe()]
    doubled = sorted({s for s in symbols if symbols.count(s) > 1})
    assert not doubled, f"listed more than once: {doubled[:10]}"
    return set(symbols)


def _unscored_equity(symbol: str) -> Ticker:
    return Ticker(symbol=symbol, name=f"{symbol} Inc", sector="Unknown", asset_class="equity")


@pytest.fixture(autouse=True)
def _reset_cursor():
    before = universe_mod._bootstrap_cursor
    universe_mod._bootstrap_cursor = 0
    yield
    universe_mod._bootstrap_cursor = before


async def test_every_never_scored_stock_is_in_every_rebuild(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stale 250. With room for all of them, every rebuild must list every
    one, once - not the first rebuild, then a window that has moved past half
    of them. Mutation: rotating a backlog that already fits (the old window
    came back short; a window that reads round lists names twice)."""
    monkeypatch.setattr(universe_mod, "BOOTSTRAP_SLOTS", 10)
    tag = uuid.uuid4().hex[:4].upper()
    made = await _seed(*(_unscored_equity(f"MM{tag}{i}") for i in range(8)))
    try:
        for attempt in range(3):
            missing = set(made) - await _listed()
            assert not missing, (
                f"rebuild {attempt + 1} left out {sorted(missing)}: never-scored "
                "stocks that fit in the slots must be priced every minute"
            )
    finally:
        await _cleanup(made)


async def test_never_scored_crypto_does_not_shrink_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """The window counted never-scored crypto it could never return, so the
    cursor wrapped against the wrong total: rebuilds came back short, and a
    window that reads round lists names twice. Mutation: counting without the
    crypto exclusion."""
    monkeypatch.setattr(universe_mod, "BOOTSTRAP_SLOTS", 10)
    tag = uuid.uuid4().hex[:4].upper()
    made = await _seed(
        *(_unscored_equity(f"MC{tag}{i}") for i in range(8)),
        *(Ticker(symbol=f"X:C{tag}{i}USD", name="pair", sector="Crypto", asset_class="crypto")
          for i in range(5)),
    )
    stocks = [m for m in made if not m.startswith("X:")]
    try:
        for attempt in range(3):
            listed = await _listed()
            missing = set(stocks) - listed
            assert not missing, f"rebuild {attempt + 1} left out {sorted(missing)}"
            assert not any(m.startswith("X:") for m in listed & set(made))
    finally:
        await _cleanup(made)


async def test_a_backlog_larger_than_the_slots_rotates_in_full_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the backlog does exceed the slots, the window still reaches everyone
    and is never short near the end of the table. Mutation: a window that stops
    at the end instead of reading round."""
    from sqlalchemy import select

    tag = uuid.uuid4().hex[:4].upper()
    made = await _seed(*(_unscored_equity(f"MR{tag}{i}") for i in range(7)))
    try:
        async with session_scope() as s:
            never_scored = set((await s.execute(
                select(Ticker.symbol).where(
                    Ticker.score.is_(None), Ticker.asset_class != "crypto",
                )
            )).scalars().all())
        slots = len(never_scored) - 2  # always smaller than the backlog
        monkeypatch.setattr(universe_mod, "BOOTSTRAP_SLOTS", slots)

        offered: set[str] = set()
        for rebuild in range(len(never_scored) + 1):
            admitted = await _listed() & never_scored
            assert len(admitted) == slots, (
                f"rebuild {rebuild + 1} admitted {len(admitted)} of {slots} slots; a "
                "rotating window near the end of the table must read round, not come "
                "back short"
            )
            offered |= admitted
        assert set(made) <= offered, f"never offered: {sorted(set(made) - offered)}"
    finally:
        await _cleanup(made)


#: Never-scored stocks and ETFs in production, measured 2026-09-14 (read-only):
#: 91 equities + 159 ETFs stale, plus the 15 the old window happened to hold.
PRODUCTION_NEVER_SCORED = 265


def test_the_default_slots_hold_the_whole_production_backlog() -> None:
    """The default must admit every never-scored row production has, or some
    of them fall back to a rotating, not-every-minute window. Mutation: the old
    default of 250."""
    assert universe_mod.BOOTSTRAP_SLOTS >= PRODUCTION_NEVER_SCORED, (
        f"UNIVERSE_BOOTSTRAP_SLOTS={universe_mod.BOOTSTRAP_SLOTS} is below the "
        f"{PRODUCTION_NEVER_SCORED} never-scored stocks and ETFs production holds"
    )


# =============================================================================
# 3. The list is rebuilt within minutes, and not twice at boot.
# =============================================================================


def test_the_snapshot_list_is_rebuilt_within_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A row added or first scored mid-session waited up to an HOUR for its
    first minute-by-minute price. Mutation: the old 3,600-second gate."""
    now = datetime(2026, 9, 14, 14, 30, tzinfo=UTC)
    monkeypatch.setattr(sp, "_last_active_universe_refresh", now - timedelta(minutes=5, seconds=1))
    assert sp._active_universe_refresh_due(now) is True
    monkeypatch.setattr(sp, "_last_active_universe_refresh", now - timedelta(minutes=4, seconds=59))
    assert sp._active_universe_refresh_due(now) is False
    monkeypatch.setattr(sp, "_last_active_universe_refresh", None)
    assert sp._active_universe_refresh_due(now) is True


def _code(fn) -> str:
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))
            and body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_the_tick_uses_that_gate() -> None:
    """The gate above is only worth testing if the tick actually asks it."""
    code = _code(sp.tick)
    assert "_active_universe_refresh_due(started)" in code


async def test_boot_does_not_rebuild_the_list_twice(one_cycle) -> None:
    """main() loads the list before the first tick; the first tick then rebuilt
    it again because nothing recorded the boot load. Mutation: not stamping."""
    _clock, _slept, _warnings, set_tick = one_cycle
    set_tick(1.0)
    sp._last_active_universe_refresh = None
    try:
        with pytest.raises(_StopLoop):
            await sp.main()
        assert sp._last_active_universe_refresh is not None
        assert sp._active_universe_refresh_due(datetime.now(UTC)) is False
    finally:
        sp._last_active_universe_refresh = None


async def test_a_failed_boot_warm_leaves_the_rebuild_due(one_cycle, monkeypatch: pytest.MonkeyPatch) -> None:
    """Found in review. The real refresh swallows a failed read and returns 0,
    so main()'s except arm never runs. Stamping anyway held the rebuild back five
    minutes while every tick priced the 112-symbol fallback. Mutation: stamping
    whatever the warm returned."""
    _clock, _slept, _warnings, set_tick = one_cycle
    set_tick(1.0)

    def _db_down(*_a, **_k):
        raise ConnectionError("pgbouncer: server closed the connection")

    monkeypatch.setattr(sp, "refresh_active_universe", universe_mod.refresh_active_universe)
    monkeypatch.setattr("app.db.session_scope", _db_down)
    monkeypatch.setattr(universe_mod, "_active_universe", [])
    sp._last_active_universe_refresh = None
    try:
        with pytest.raises(_StopLoop):
            await sp.main()
        assert sp._active_universe_refresh_due(datetime.now(UTC)) is True, (
            "a boot warm that loaded nothing was recorded as a rebuild, so the "
            "first ticks price the mock fallback instead of retrying"
        )
    finally:
        sp._last_active_universe_refresh = None
