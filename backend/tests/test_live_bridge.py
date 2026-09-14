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


def wm(tickers_s: float | None, regime_s: float | None = None) -> Watermarks:
    """Watermarks as offsets in seconds from T0."""
    return Watermarks(
        tickers_at=None if tickers_s is None else T0 + timedelta(seconds=tickers_s),
        regime_at=None if regime_s is None else T0 + timedelta(seconds=regime_s),
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


async def test_regime_only_advance_publishes_regime_updated_once():
    clock, pub = FakeClock(T0 + timedelta(seconds=60)), Recorder()
    bridge = make_bridge([wm(0, 0), wm(0, 30), wm(0, 30)], clock, pub)
    await bridge.poll_once()
    assert await bridge.poll_once() == lb.REGIME_EVENT
    assert await bridge.poll_once() is None
    assert [e for e, _ in pub.events] == [lb.REGIME_EVENT]


async def test_regime_landing_before_its_pass_settles_waits_for_one_scores_event():
    clock, pub = FakeClock(T0), Recorder()
    # Regime row stamped at 1s and already 12s old; tickers still climbing.
    bridge = make_bridge([wm(-70, -70), wm(4, 1), wm(6, 1), wm(6, 1)], clock, pub)
    await bridge.poll_once()
    clock.now = T0 + timedelta(seconds=13)
    assert await bridge.poll_once() is None     # would have been regime_updated
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
    assert empty == Watermarks(tickers_at=None, regime_at=None)

    async with db.SessionLocal() as s:
        s.add(Ticker(symbol="AAA", name="Scored", score=50.0))
        s.add(Ticker(symbol="BBB", name="Unscored", score=None))
        await s.commit()

    marks = await lb.read_watermarks()
    assert marks.tickers_at is not None and marks.tickers_at.tzinfo is not None
    assert marks.regime_at is None


def test_as_utc_normalises_naive_and_string_stamps():
    assert lb._as_utc(None) is None
    naive = datetime(2026, 9, 14, 14, 0, 0)
    assert lb._as_utc(naive) == T0
    assert lb._as_utc("2026-09-14 14:00:00") == T0
    assert lb._as_utc(T0.astimezone()) == T0


def test_app_lifespan_starts_and_stops_the_bridge(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    calls: list[str] = []

    def fake_start(self):
        calls.append("start")

    async def fake_stop(self):
        calls.append("stop")

    monkeypatch.setattr(LiveBridge, "start", fake_start)
    monkeypatch.setattr(LiveBridge, "stop", fake_stop)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code in (200, 503)
        assert calls == ["start"]
    assert calls == ["start", "stop"]


def test_frontend_timing_constants_fit_the_bridge_cadence():
    """frontend/lib/useLiveStream.ts timing is pinned to this bridge.

    * The "auto-refreshing" window must outlast the normal gap between events:
      a pass every ~70-80s plus up to one poll interval and the settle delay.
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
