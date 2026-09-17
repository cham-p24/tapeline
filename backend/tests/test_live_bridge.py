"""The API-side live bridge publishes one SSE event per settled database write.

Background (measured Mon 14 Sep 2026, US session): the worker publishes to an
in-process broker on a different machine, so /api/stream/live delivered 0
update events in 300s while the database took 4 worker passes. The bridge in
services/live_bridge.py runs in the API process and turns new writes into the
events the browser already handles.

These tests drive it with a fake clock, a fake watermark reader and a fake
sleep, so nothing waits on real time.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services import live_bridge as lb
from app.services.live_bridge import LiveBridge, Watermarks

T0 = datetime(2026, 9, 14, 14, 0, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def __call__(self, event: str, payload: dict) -> None:
        self.events.append((event, payload))


def make_bridge(marks: list, clock: FakeClock, publish, **kw) -> LiveBridge:
    """A bridge whose reader returns (or raises) the queued items in order."""
    queue = list(marks)

    async def read() -> Watermarks:
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    return LiveBridge(publish=publish, read=read, clock=clock, **kw)


def wm(pass_s: float | None, latest_s: float | None = None) -> Watermarks:
    """Watermarks as offsets in seconds from T0. latest defaults to the pass."""
    if latest_s is None:
        latest_s = pass_s
    return Watermarks(
        pass_at=None if pass_s is None else T0 + timedelta(seconds=pass_s),
        latest_at=None if latest_s is None else T0 + timedelta(seconds=latest_s),
    )


async def test_first_read_is_a_baseline_and_publishes_nothing():
    clock, pub = FakeClock(T0 + timedelta(seconds=30)), Recorder()
    bridge = make_bridge([wm(0, 0)], clock, pub)
    assert await bridge.poll_once() is None
    assert pub.events == []


async def test_one_settled_advance_publishes_exactly_once():
    clock, pub = FakeClock(T0 + timedelta(seconds=30)), Recorder()
    # baseline at 0s; a pass finishes at 70s; the next three polls all see it.
    bridge = make_bridge([wm(0, 0), wm(70, 70), wm(70, 70), wm(70, 70)], clock, pub)
    await bridge.poll_once()
    clock.now = T0 + timedelta(seconds=85)  # 15s after the pass: settled
    assert await bridge.poll_once() == lb.SCORES_EVENT
    clock.advance(15)
    assert await bridge.poll_once() is None
    clock.advance(15)
    assert await bridge.poll_once() is None
    assert pub.events == [(lb.SCORES_EVENT, {"ts": (T0 + timedelta(seconds=70)).isoformat()})]


async def test_a_poll_landing_mid_pass_does_not_publish_a_half_written_pass():
    """A pass stamps ~11,500 rows over ~5s. Seeing it mid-write must not fire."""
    clock, pub = FakeClock(T0), Recorder()
    bridge = make_bridge(
        [wm(-60, -60), wm(2, None), wm(5, 5), wm(5, 5)],
        clock, pub,
    )
    await bridge.poll_once()                      # baseline
    clock.now = T0 + timedelta(seconds=3)         # mid-pass: max is 1s old
    assert await bridge.poll_once() is None
    clock.now = T0 + timedelta(seconds=18)        # pass ended at 5s: 13s old
    assert await bridge.poll_once() == lb.SCORES_EVENT
    clock.advance(15)
    assert await bridge.poll_once() is None
    assert [e for e, _ in pub.events] == [lb.SCORES_EVENT]


async def test_an_unaged_value_seen_on_two_polls_counts_as_settled():
    """Clock skew between machines can make a finished pass look young."""
    clock, pub = FakeClock(T0), Recorder()
    # The stamp reads 60s in the FUTURE relative to this machine's clock.
    bridge = make_bridge([wm(-100), wm(60), wm(60)], clock, pub)
    await bridge.poll_once()
    assert await bridge.poll_once() is None
    clock.advance(15)
    assert await bridge.poll_once() == lb.SCORES_EVENT


async def test_one_event_per_pass_across_several_passes():
    clock, pub = FakeClock(T0), Recorder()
    marks = [wm(0, 0)]
    polls = []
    # Passes end every 72s; polls every 15s for 5 minutes.
    for i in range(1, 21):
        t = i * 15
        last_pass_end = (t // 72) * 72
        marks.append(wm(last_pass_end, last_pass_end))
        polls.append(t)
    bridge = make_bridge(marks, clock, pub)
    await bridge.poll_once()
    for t in polls:
        clock.now = T0 + timedelta(seconds=t)
        await bridge.poll_once()
    # Passes ended at 72, 144, 216, 288 inside the 300s window.
    assert [p["ts"] for _, p in pub.events] == [
        (T0 + timedelta(seconds=s)).isoformat() for s in (72, 144, 216, 288)
    ]


async def test_writes_that_do_not_move_the_pass_marker_publish_nothing():
    """A sheet or crypto write moves latest_at, never the quartile marker."""
    clock, pub = FakeClock(T0 + timedelta(seconds=60)), Recorder()
    bridge = make_bridge([wm(0, 0), wm(0, 30), wm(0, 45), wm(0, 45)], clock, pub)
    await bridge.poll_once()
    for _ in range(3):
        assert await bridge.poll_once() is None
        clock.advance(15)
    assert pub.events == []


async def test_marker_moved_but_rows_still_being_written_waits_for_one_event():
    clock, pub = FakeClock(T0), Recorder()
    # Three quarters of a pass stamped from 1s; its last chunks still landing.
    bridge = make_bridge([wm(-70), wm(1, 4), wm(1.2, 6), wm(1.2, 6)], clock, pub)
    await bridge.poll_once()
    clock.now = T0 + timedelta(seconds=13)
    assert await bridge.poll_once() is None     # latest write 9s old, still moving
    clock.now = T0 + timedelta(seconds=28)
    assert await bridge.poll_once() == lb.SCORES_EVENT
    clock.advance(15)
    assert await bridge.poll_once() is None
    assert [e for e, _ in pub.events] == [lb.SCORES_EVENT]


async def test_empty_tables_then_a_first_write():
    clock, pub = FakeClock(T0 + timedelta(seconds=60)), Recorder()
    bridge = make_bridge([wm(None, None), wm(None, None), wm(30, 30)], clock, pub)
    await bridge.poll_once()
    assert await bridge.poll_once() is None
    assert await bridge.poll_once() == lb.SCORES_EVENT


async def test_run_survives_a_db_error_backs_off_and_does_not_replay(caplog):
    clock, pub = FakeClock(T0 + timedelta(seconds=100)), Recorder()
    marks = [
        wm(0, 0),                               # baseline
        RuntimeError("connection reset"),       # fail 1
        OSError("pool timeout"),                # fail 2
        wm(70, 70),                             # recovers, advance -> publish
        wm(70, 70),                             # same -> nothing
    ]
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)
        if len(delays) == len(marks):
            raise asyncio.CancelledError

    bridge = make_bridge(marks, clock, pub, sleep=fake_sleep, interval=15, max_backoff=300)
    with (
        caplog.at_level(logging.WARNING, logger="app.services.live_bridge"),
        pytest.raises(asyncio.CancelledError),
    ):
        await bridge.run()

    assert delays == [15, 30, 60, 15, 15]
    assert pub.events == [(lb.SCORES_EVENT, {"ts": (T0 + timedelta(seconds=70)).isoformat()})]
    failures = [r for r in caplog.records if "live_bridge.poll_failed" in r.getMessage()]
    assert len(failures) == 2
    assert bridge.failures == 0


async def test_a_read_that_never_returns_times_out_and_is_retried(caplog):
    """A connection that hangs after checkout must not stall the loop silently."""
    clock, pub = FakeClock(T0 + timedelta(seconds=100)), Recorder()
    calls = 0

    async def read() -> Watermarks:
        nonlocal calls
        calls += 1
        if calls == 2:
            await asyncio.Event().wait()  # never returns
        return wm(0, 0) if calls == 1 else wm(70, 70)

    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)
        if len(delays) == 3:
            raise asyncio.CancelledError

    bridge = LiveBridge(
        publish=pub, read=read, clock=clock, sleep=fake_sleep,
        interval=15, read_timeout=0.05,
    )
    with (
        caplog.at_level(logging.WARNING, logger="app.services.live_bridge"),
        pytest.raises(asyncio.CancelledError),
    ):
        await asyncio.wait_for(bridge.run(), timeout=5)

    assert calls == 3
    assert delays == [15, 30, 15]
    assert [e for e, _ in pub.events] == [lb.SCORES_EVENT]
    assert any("live_bridge.poll_failed" in r.getMessage() for r in caplog.records)


async def test_outside_the_us_session_it_neither_reads_nor_publishes():
    """The worker re-stamps rows all night; those passes carry no new prices."""
    # Sun 13 Sep 2026 07:14 UTC = 03:14 EDT.
    clock, pub = FakeClock(datetime(2026, 9, 13, 7, 14, tzinfo=UTC)), Recorder()
    reads = 0

    async def read() -> Watermarks:
        nonlocal reads
        reads += 1
        return wm(reads * 70, reads * 70)

    sleeps = 0

    async def fake_sleep(seconds: float) -> None:
        nonlocal sleeps
        sleeps += 1
        clock.advance(seconds)
        if sleeps == 20:
            raise asyncio.CancelledError

    bridge = LiveBridge(publish=pub, read=read, clock=clock, sleep=fake_sleep, interval=15)
    with pytest.raises(asyncio.CancelledError):
        await bridge.run()
    assert reads == 0
    assert pub.events == []


async def test_first_poll_after_the_open_publishes_the_overnight_advance_once():
    # Mon 14 Sep 2026 07:59:30 UTC = 03:59:30 EDT, 30s before pre-market opens.
    start = datetime(2026, 9, 14, 7, 59, 30, tzinfo=UTC)
    clock, pub = FakeClock(start), Recorder()
    overnight = start - timedelta(hours=1)
    reads = 0

    async def read() -> Watermarks:
        nonlocal reads
        reads += 1
        return Watermarks(pass_at=overnight, latest_at=overnight)

    sleeps = 0

    async def fake_sleep(seconds: float) -> None:
        nonlocal sleeps
        sleeps += 1
        clock.advance(seconds)
        if sleeps == 6:
            raise asyncio.CancelledError

    bridge = LiveBridge(publish=pub, read=read, clock=clock, sleep=fake_sleep, interval=15)
    # Pretend a previous session published an older write.
    bridge._baselined = True
    bridge._published_pass = overnight - timedelta(hours=10)
    with pytest.raises(asyncio.CancelledError):
        await bridge.run()
    assert reads == 4  # 03:59:30 and 03:59:45 skipped; 04:00:00 onwards read
    assert [e for e, _ in pub.events] == [lb.SCORES_EVENT]


@pytest.mark.parametrize(
    ("utc", "expected"),
    [
        (datetime(2026, 9, 14, 7, 59, tzinfo=UTC), False),   # Mon 03:59 EDT
        (datetime(2026, 9, 14, 8, 0, tzinfo=UTC), True),     # Mon 04:00 EDT
        (datetime(2026, 9, 14, 14, 0, tzinfo=UTC), True),    # Mon 10:00 EDT
        (datetime(2026, 9, 14, 23, 59, tzinfo=UTC), True),   # Mon 19:59 EDT
        (datetime(2026, 9, 15, 0, 0, tzinfo=UTC), False),    # Mon 20:00 EDT
        (datetime(2026, 9, 12, 14, 0, tzinfo=UTC), False),   # Saturday
        (datetime(2026, 9, 13, 14, 0, tzinfo=UTC), False),   # Sunday
        (datetime(2026, 9, 7, 14, 0, tzinfo=UTC), False),    # Labor Day
        (datetime(2026, 11, 26, 15, 0, tzinfo=UTC), False),  # Thanksgiving
        (datetime(2026, 12, 14, 8, 30, tzinfo=UTC), False),  # Mon 03:30 EST
        (datetime(2026, 12, 14, 9, 0, tzinfo=UTC), True),    # Mon 04:00 EST
        (datetime(2027, 1, 5, 0, 59, tzinfo=UTC), True),     # Mon 19:59 EST
        (datetime(2027, 1, 5, 1, 0, tzinfo=UTC), False),     # Mon 20:00 EST
    ],
)
def test_in_us_extended_session(utc, expected):
    assert lb.in_us_extended_session(utc) is expected


def test_us_eastern_follows_the_dst_rule():
    # 2026: DST from Sun 8 Mar 07:00 UTC to Sun 1 Nov 06:00 UTC.
    assert lb.us_eastern(datetime(2026, 3, 8, 6, 59, tzinfo=UTC)).hour == 1
    assert lb.us_eastern(datetime(2026, 3, 8, 7, 0, tzinfo=UTC)).hour == 3
    assert lb.us_eastern(datetime(2026, 11, 1, 5, 59, tzinfo=UTC)).hour == 1
    assert lb.us_eastern(datetime(2026, 11, 1, 6, 0, tzinfo=UTC)).hour == 1


async def test_backoff_is_capped():
    bridge = LiveBridge(publish=Recorder(), interval=15, max_backoff=300)
    bridge.failures = 10
    assert bridge.next_delay() == 300


async def test_start_and_stop_cancel_cleanly():
    clock, pub = FakeClock(T0), Recorder()
    reads = 0

    async def read() -> Watermarks:
        nonlocal reads
        reads += 1
        return wm(0, 0)

    bridge = LiveBridge(publish=pub, read=read, clock=clock, interval=0.01)
    task = bridge.start()
    await asyncio.sleep(0.05)
    await bridge.stop()
    assert task.cancelled()
    assert reads >= 1
    await bridge.stop()  # idempotent


async def test_stop_while_a_read_closes_its_session_leaves_nothing_running(monkeypatch):
    """stop() must not cancel a real read while its session is closing.

    AsyncSession.__aexit__ closes the session in a shielded child task.
    Cancelling the bridge at that moment cancels only the waiter: the close
    outlives stop(), and when the loop is then closed under it aiosqlite's
    worker thread raises "RuntimeError: Event loop is closed" (on Postgres the
    pooled connection is dropped instead). Nothing may still be running once
    stop() returns.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    closing = asyncio.Event()
    real_close = AsyncSession.close

    async def close(self: AsyncSession) -> None:
        closing.set()
        await real_close(self)

    monkeypatch.setattr(AsyncSession, "close", close)
    bridge = LiveBridge(
        publish=Recorder(), read=lb.read_watermarks, in_session=lambda _now: True,
    )
    bridge.start()
    await asyncio.wait_for(closing.wait(), 5)
    await bridge.stop()

    me = asyncio.current_task()
    still_running = [
        t.get_coro().__qualname__
        for t in asyncio.all_tasks()
        if t is not me and not t.done()
    ]
    assert still_running == []


async def test_stop_cancels_a_read_that_outlasts_the_grace(monkeypatch):
    """A hung read cannot hold shutdown past STOP_GRACE_SECONDS."""
    monkeypatch.setattr(lb, "STOP_GRACE_SECONDS", 0.05)
    reading = asyncio.Event()

    async def read() -> Watermarks:
        reading.set()
        await asyncio.Event().wait()  # never returns
        raise AssertionError("unreachable")

    bridge = LiveBridge(
        publish=Recorder(), read=read, read_timeout=60, in_session=lambda _now: True,
    )
    task = bridge.start()
    await asyncio.wait_for(reading.wait(), 5)
    loop = asyncio.get_running_loop()
    began = loop.time()
    await bridge.stop()
    assert task.cancelled()
    assert loop.time() - began < 1.0


def test_stop_grace_fits_inside_the_platform_kill_timeout():
    """Fly sends SIGKILL 5s after SIGINT by default; shutdown must finish first."""
    assert 0 < lb.STOP_GRACE_SECONDS <= 2.0


async def test_published_event_reaches_a_stream_subscriber():
    from app.services.pubsub import InMemoryBroker

    broker = InMemoryBroker()
    queue = broker.subscribe()
    clock = FakeClock(T0 + timedelta(seconds=60))
    bridge = make_bridge([wm(0, 0), wm(30, 30)], clock, broker.publish)
    await bridge.poll_once()
    await bridge.poll_once()
    msg = json.loads(queue.get_nowait())
    assert msg == {
        "event": lb.SCORES_EVENT,
        "payload": {"ts": (T0 + timedelta(seconds=30)).isoformat()},
    }


async def test_read_watermarks_runs_against_the_real_schema():
    """The SQL executes on the test database (SQLite) and returns UTC stamps."""
    from app import db
    from app.models.ticker import Ticker

    empty = await lb.read_watermarks()
    assert empty == Watermarks(pass_at=None, latest_at=None)

    async with db.SessionLocal() as s:
        s.add(Ticker(symbol="AAA", name="Scored", score=50.0))
        s.add(Ticker(symbol="BBB", name="Unscored", score=None))
        await s.commit()

    marks = await lb.read_watermarks()
    assert marks.pass_at is not None and marks.pass_at.tzinfo is not None
    assert marks.latest_at is not None and marks.latest_at.tzinfo is not None


def test_as_utc_normalises_naive_and_string_stamps():
    assert lb._as_utc(None) is None
    naive = datetime(2026, 9, 14, 14, 0, 0)
    assert lb._as_utc(naive) == T0
    assert lb._as_utc("2026-09-14 14:00:00") == T0
    assert lb._as_utc(T0.astimezone()) == T0


def test_app_lifespan_starts_and_stops_the_real_bridge(monkeypatch):
    """The one test that runs the real startup path (conftest disables it)."""
    from fastapi.testclient import TestClient

    from app import main

    tasks: list[asyncio.Task[None]] = []
    calls: list[str] = []
    real_start, real_stop = LiveBridge.start, LiveBridge.stop

    def spy_start(self: LiveBridge) -> asyncio.Task[None]:
        calls.append("start")
        task = real_start(self)
        tasks.append(task)
        return task

    async def spy_stop(self: LiveBridge) -> None:
        calls.append("stop")
        await real_stop(self)

    monkeypatch.setattr(main.settings, "live_bridge_enabled", True)
    monkeypatch.setattr(LiveBridge, "start", spy_start)
    monkeypatch.setattr(LiveBridge, "stop", spy_stop)
    with TestClient(main.app) as client:
        assert client.get("/api/health").status_code in (200, 503)
        assert calls == ["start"]
        assert len(tasks) == 1 and not tasks[0].done()
    assert calls == ["start", "stop"]
    assert tasks[0].done()


def test_the_suite_runs_the_app_without_the_bridge(monkeypatch):
    from fastapi.testclient import TestClient

    from app import main

    assert main.settings.live_bridge_enabled is False  # tests/conftest.py
    started: list[LiveBridge] = []
    monkeypatch.setattr(LiveBridge, "start", lambda self: started.append(self))
    with TestClient(main.app) as client:
        assert client.get("/api/health").status_code in (200, 503)
    assert started == []


def test_frontend_timing_constants_fit_the_bridge_cadence():
    """frontend/lib/useLiveStream.ts timing is pinned to this bridge.

    * The "auto-refreshing" window must outlast the normal gap between events:
      a pass every ~60s plus up to one poll interval and the settle delay.
    * The refetch floor must be shorter than the smallest gap between two
      passes' events (the worker sleeps 60s between passes; publish latency
      can differ by up to one poll interval), so it only merges events from
      the SAME pass and never swallows a new pass.
    """
    src = (
        Path(__file__).resolve().parents[2] / "frontend" / "lib" / "useLiveStream.ts"
    ).read_text(encoding="utf-8")

    def ms(name: str) -> float:
        m = re.search(rf"export const {name} = ([\d_]+);", src)
        assert m, f"{name} not found in useLiveStream.ts"
        return int(m.group(1).replace("_", "")) / 1000

    worst_normal_gap = 80 + lb.POLL_INTERVAL_SECONDS + lb.SETTLE_SECONDS
    assert ms("AUTO_REFRESH_WINDOW_MS") > worst_normal_gap
    assert ms("MIN_REFETCH_GAP_MS") <= 60 - lb.POLL_INTERVAL_SECONDS


# ── One event per worker pass, not per write ────────────────────────────────
#
# tickers.updated_at also advances outside a pass: the SIGNAL sheet refresh
# (sheet_feed.upsert_tickers, up to every 30s, sheet-governed rows only) and
# the daily crypto refresh (~110 X: rows). A watermark on max(updated_at) fired
# for those too, adding refetches between passes and resetting the browser's
# 40s refetch gap. A pass rewrites every scored non-crypto row (11,569 of
# 11,679 scored rows in one pass, read on production 14 Sep 2026 18:01 UTC).


async def _seed_universe(n: int, stamp: datetime, crypto: int = 0) -> list[str]:
    from app import db
    from app.models.ticker import Ticker

    symbols = [f"PASS{i:04d}" for i in range(n)]
    async with db.SessionLocal() as s:
        for sym in symbols:
            s.add(Ticker(symbol=sym, name=sym, score=50.0, updated_at=stamp))
        for i in range(crypto):
            s.add(Ticker(symbol=f"X:C{i}USD", name="coin", score=50.0,
                         asset_class="crypto", updated_at=stamp))
        await s.commit()
    return symbols


async def _stamp(symbols: list[str], stamp: datetime) -> None:
    from sqlalchemy import update

    from app import db
    from app.models.ticker import Ticker

    async with db.SessionLocal() as s:
        await s.execute(
            update(Ticker).where(Ticker.symbol.in_(symbols)).values(updated_at=stamp)
        )
        await s.commit()


async def test_sheet_and_crypto_writes_between_passes_publish_nothing():
    """Real SQL, real schema: only a worker pass produces an event."""
    clock, pub = FakeClock(T0), Recorder()
    symbols = await _seed_universe(200, T0, crypto=10)
    bridge = LiveBridge(publish=pub, clock=clock)

    clock.now = T0 + timedelta(seconds=20)
    assert await bridge.poll_once() is None                    # baseline

    # The sheet refresh rewrites 70 sheet-governed rows at +30s.
    await _stamp(symbols[:70], T0 + timedelta(seconds=30))
    clock.now = T0 + timedelta(seconds=45)
    assert await bridge.poll_once() is None
    clock.now = T0 + timedelta(seconds=60)
    assert await bridge.poll_once() is None

    # The daily crypto refresh at +62s.
    from sqlalchemy import update

    from app import db
    from app.models.ticker import Ticker

    async with db.SessionLocal() as s:
        await s.execute(update(Ticker).where(Ticker.asset_class == "crypto")
                        .values(updated_at=T0 + timedelta(seconds=62)))
        await s.commit()
    clock.now = T0 + timedelta(seconds=75)
    assert await bridge.poll_once() is None
    assert pub.events == []

    # A worker pass rewrites every row at +72s: exactly one event.
    await _stamp(symbols, T0 + timedelta(seconds=72))
    clock.now = T0 + timedelta(seconds=90)
    assert await bridge.poll_once() == lb.SCORES_EVENT
    for _ in range(3):
        clock.advance(15)
        assert await bridge.poll_once() is None

    # Another sheet write after the pass: still nothing.
    await _stamp(symbols[100:170], T0 + timedelta(seconds=100))
    clock.now = T0 + timedelta(seconds=150)
    assert await bridge.poll_once() is None
    assert [e for e, _ in pub.events] == [lb.SCORES_EVENT]


async def test_a_poll_inside_a_pass_waits_for_the_pass_to_finish():
    """Real SQL: a pass commits 500-row chunks. A poll that lands when most of
    the universe is rewritten but the pass is still writing must not publish,
    or the next poll would publish the same pass again."""
    clock, pub = FakeClock(T0), Recorder()
    symbols = await _seed_universe(200, T0)
    bridge = LiveBridge(publish=pub, clock=clock)
    clock.now = T0 + timedelta(seconds=20)
    await bridge.poll_once()

    # A slow pass started at +60s; 90% of rows are written, the last at +71s.
    for i, chunk_start in enumerate(range(0, 180, 20)):
        await _stamp(symbols[chunk_start:chunk_start + 20], T0 + timedelta(seconds=60 + i * 1.4))
    await _stamp(symbols[178:180], T0 + timedelta(seconds=71))
    clock.now = T0 + timedelta(seconds=72)
    assert await bridge.poll_once() is None
    # The last chunk lands at +73s.
    await _stamp(symbols[180:], T0 + timedelta(seconds=73))
    clock.now = T0 + timedelta(seconds=87)
    assert await bridge.poll_once() == lb.SCORES_EVENT
    clock.advance(15)
    assert await bridge.poll_once() is None
    assert len(pub.events) == 1
