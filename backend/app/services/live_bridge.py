"""API-side bridge: turn database writes into SSE ``update`` events.

Why this exists
---------------
The worker publishes ``scores_updated`` / ``regime_updated`` to
``services.pubsub.broker`` at the end of every pass. That broker is an
in-process object, and in production the worker and the API are separate Fly
processes on separate machines (fly.toml ``[processes]``). A publish in the
worker can never reach a browser, which is connected to the API.

Measured on Mon 14 Sep 2026 during the US session: one ``curl`` on
``/api/stream/live`` from 14:02:11 to 14:07:11 UTC received 1 ``hello``, 11
``ping`` and 0 ``update`` events, while a DB poll over the same window saw 4
complete worker passes (71s, 73s, 71s apart). The in-app pages showed a
pulsing "Live" badge and never refetched.

What it does
------------
Each API process runs one :class:`LiveBridge`. Every ``POLL_INTERVAL_SECONDS``
it reads two stamps over scored ``tickers`` rows in one query:

* ``pass_at``: the ``updated_at`` of the row at the lower quartile of the
  scored universe, oldest first (``n // PASS_QUANTILE_DIVISOR + 1``). This is
  the pass marker.
* ``latest_at``: ``max(updated_at)``, used only to tell when writing stopped.

Why a quartile and not the max. ``updated_at`` means "live data was written to
this row" (see the comment on ``Ticker.updated_at``), but three writers move
it. A worker pass rewrites every scored non-crypto row (11,569 of 11,679
scored rows in one pass, read on production 14 Sep 2026 18:01 UTC). The SIGNAL
sheet refresh (``sheet_feed.upsert_tickers``, up to every 30s) rewrites only
sheet-governed rows whose values changed. The daily crypto refresh rewrites
~110 ``X:`` rows. ``max(updated_at)`` advances for all three, so it fired
extra events between passes, and each one could push a page's next refetch
back by the browser's 40s refetch gap. The lower quartile moves only once
three quarters of the universe has been rewritten, which only a pass does; a
partial writer cannot move it however often it runs.

An advance of ``pass_at`` is published as ONE ``scores_updated`` event, and
only once writing has *settled*: ``latest_at`` is at least ``SETTLE_SECONDS``
old, or unchanged since the previous poll (which covers clock skew between
machines). A pass commits in 500-row chunks, so a poll can land after three
quarters of it and before its end; waiting for the writes to stop keeps that
pass to one event. There is no separate regime event: the pass writes the
regime row too, and a regime-only advance (the sheet's MARKET tab) is picked up
by the next pass's refetch. Latency from the end of a pass to the event is
roughly 10-30 seconds.

Cost. One statement: a sequential scan of ``tickers`` and a sort of the
~11,700 scored stamps. There is no index on ``tickers.updated_at`` and this
deliberately does not add one: every pass rewrites that column on every scored
row, so an index on it would turn every row update of every pass into an index
write. ``EXPLAIN (ANALYZE, BUFFERS)`` on production (14 Sep 2026, 11,680 scored
rows): 13.2 ms execution, 3,340 shared buffer hits, a 385 kB in-memory
quicksort. At one query per 15s per API process that is under 0.1% of one
core.

Not LISTEN/NOTIFY. The production DATABASE_URL is a transaction-pooled Neon
endpoint (``db.is_transaction_pooled`` is True, checked 14 Sep 2026), and
LISTEN does not survive transaction pooling.

Failure handling. Any exception while polling is logged and retried with
exponential backoff (capped at ``MAX_BACKOFF_SECONDS``). The watermarks it has
already published are kept, so a DB blip neither crashes the API nor replays
an old event. Cancellation (app shutdown) is the only way out of the loop.

A read that never returns (a connection that hangs after checkout; the engine
has a pool timeout but no statement timeout) is cut off after
``READ_TIMEOUT_SECONDS`` and handled like any other failure, so the loop can
never stall silently.

US session only. The worker does not pause when the market is closed: its main
loop has no market-hours check and every pass re-stamps ``updated_at`` on every
scored row, nights and weekends included, while the prices it writes do not
move. Forwarding those writes would make the in-app badge read
"Auto-refreshing · updated 03:14" on a Sunday next to Friday's closing prices.
So the bridge polls and publishes only inside the US extended session
(``SESSION_OPEN_ET`` to ``SESSION_CLOSE_ET`` Eastern, pre-market through
after-hours, on trading days per ``scorecard_backcheck.is_trading_day``).
Outside it the bridge sends nothing and does not query the database. The first
poll after the session opens publishes the overnight advance once, so an open
page loads the newest data a single time. Browsers keep their SSE connection
and heartbeat pings the whole time; the badge falls back to "Updated HH:MM".

Multiple API machines. Each machine's process has its own broker, its own
subscribers and its own bridge. They do not coordinate and do not need to.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)

#: How often each API process reads the watermarks.
POLL_INTERVAL_SECONDS = 15.0
#: Writes whose latest stamp is this old (or unchanged since the previous poll)
#: have stopped, so the pass that moved the marker is finished.
SETTLE_SECONDS = 10.0
#: The pass marker is the stamp of row n // 4 + 1 of the scored rows, oldest
#: first. A pass rewrites ~99% of them; any other writer would have to rewrite
#: more than three quarters of the universe to move it.
PASS_QUANTILE_DIVISOR = 4
#: Ceiling for the retry delay after consecutive poll failures.
MAX_BACKOFF_SECONDS = 300.0
#: A watermark read slower than this is abandoned and counted as a failure.
READ_TIMEOUT_SECONDS = 10.0
#: On shutdown, how long stop() lets an in-flight read finish (session closed,
#: connection returned) before cancelling it. Well under Fly's 5s kill timeout.
STOP_GRACE_SECONDS = 2.0
#: US extended session, Eastern time: pre-market open to after-hours close.
SESSION_OPEN_ET = time(4, 0)
SESSION_CLOSE_ET = time(20, 0)

#: Event name, shared with the worker's in-process publish
#: (workers/signal_publisher.py) so the browser handles both identically.
SCORES_EVENT = "scores_updated"

# Window functions run on Postgres (prod) and SQLite >= 3.25 (tests); `n / 4`
# is integer division on both. An empty table returns no row.
WATERMARK_SQL = text(
    "select updated_at as pass_at, latest_at from ("
    " select updated_at,"
    " row_number() over (order by updated_at) as rn,"
    " count(*) over () as n,"
    " max(updated_at) over () as latest_at"
    " from tickers where score is not null"
    f") q where rn = n / {PASS_QUANTILE_DIVISOR} + 1"
)


def _nth_sunday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    first_sunday = first + timedelta(days=(6 - first.weekday()) % 7)
    return first_sunday + timedelta(weeks=n - 1)


def us_eastern(now: datetime) -> datetime:
    """``now`` as naive US Eastern wall-clock time.

    Computed from the US DST rule (second Sunday of March 02:00 local to first
    Sunday of November 02:00 local) rather than ``zoneinfo``, so it does not
    depend on the host having a tz database installed.
    """
    utc = now.astimezone(UTC).replace(tzinfo=None)
    year = utc.year
    dst_start = datetime.combine(_nth_sunday(year, 3, 2), time(7, 0))  # 02:00 EST
    dst_end = datetime.combine(_nth_sunday(year, 11, 1), time(6, 0))   # 02:00 EDT
    offset = -4 if dst_start <= utc < dst_end else -5
    return utc + timedelta(hours=offset)


def in_us_extended_session(now: datetime) -> bool:
    """True from ``SESSION_OPEN_ET`` to ``SESSION_CLOSE_ET`` on a US trading day."""
    from app.services.scorecard_backcheck import is_trading_day

    et = us_eastern(now)
    if not is_trading_day(et.date()):
        return False
    return SESSION_OPEN_ET <= et.time() < SESSION_CLOSE_ET


@dataclass(frozen=True)
class Watermarks:
    #: updated_at at the lower quartile of scored rows: moves once per pass.
    pass_at: datetime | None
    #: max(updated_at) over scored rows: moves on every write.
    latest_at: datetime | None


def _as_utc(value: Any) -> datetime | None:
    """Normalise a DB timestamp to an aware UTC datetime.

    Postgres returns aware datetimes. SQLite (dev, CI, e2e) returns naive
    datetimes or ISO strings; both are UTC by convention in this codebase.
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def read_watermarks() -> Watermarks:
    """Read the pass marker and the latest write in one statement.

    ``SessionLocal`` is looked up at call time, not import time, so the test
    suite's per-test re-binding of the session factory applies here too.
    """
    from app import db

    async with db.SessionLocal() as session:
        row = (await session.execute(WATERMARK_SQL)).mappings().one_or_none()
    if row is None:
        return Watermarks(pass_at=None, latest_at=None)
    return Watermarks(
        pass_at=_as_utc(row["pass_at"]),
        latest_at=_as_utc(row["latest_at"]),
    )


Publish = Callable[[str, dict[str, Any]], Awaitable[None]]


class LiveBridge:
    """Poll the pass marker and publish one event per settled pass."""

    def __init__(
        self,
        *,
        publish: Publish,
        read: Callable[[], Awaitable[Watermarks]] = read_watermarks,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        interval: float = POLL_INTERVAL_SECONDS,
        settle: float = SETTLE_SECONDS,
        max_backoff: float = MAX_BACKOFF_SECONDS,
        read_timeout: float = READ_TIMEOUT_SECONDS,
        in_session: Callable[[datetime], bool] = in_us_extended_session,
    ) -> None:
        self._publish = publish
        self._read = read
        self._clock = clock
        self._sleep = sleep
        self._interval = interval
        self._settle = settle
        self._max_backoff = max_backoff
        self._read_timeout = read_timeout
        self._in_session = in_session
        self._baselined = False
        # Pass marker we last published (or baselined on).
        self._published_pass: datetime | None = None
        # latest_at observed on the previous successful poll.
        self._seen_latest: datetime | None = None
        self.failures = 0
        self._task: asyncio.Task[None] | None = None
        # Set whenever no read is in flight, so stop() never cancels a read
        # while its session is closing (see stop()).
        self._idle = asyncio.Event()
        self._idle.set()

    async def poll_once(self) -> str | None:
        """One read. Returns the event name published, or None.

        Raises whatever the read raises, or ``TimeoutError`` if it takes longer
        than ``read_timeout``; :meth:`run` owns retry and backoff. Does not check
        the session; :meth:`run` does.
        """
        marks = await asyncio.wait_for(self._read(), timeout=self._read_timeout)
        now = self._clock()
        previous_latest, self._seen_latest = self._seen_latest, marks.latest_at

        if not self._baselined:
            # First successful read: a browser that connects now loads the
            # current data on mount, so there is nothing to announce yet.
            self._published_pass = marks.pass_at
            self._baselined = True
            return None

        if marks.pass_at is None:
            return None
        if self._published_pass is not None and marks.pass_at <= self._published_pass:
            # No new pass. Sheet and crypto writes move latest_at only.
            return None
        latest = marks.latest_at or marks.pass_at
        aged = (now - latest).total_seconds() >= self._settle
        if not (aged or latest == previous_latest):
            # Most of a pass is in, but rows are still being written. Publishing
            # now would announce the same pass again on the next poll.
            return None

        # Mark published BEFORE publishing so a publish error cannot make the
        # next poll replay the same pass.
        self._published_pass = marks.pass_at
        payload = {"ts": latest.isoformat()}
        await self._publish(SCORES_EVENT, payload)
        logger.info("live_bridge.published event=%s ts=%s", SCORES_EVENT, payload["ts"])
        return SCORES_EVENT

    def next_delay(self) -> float:
        """Delay before the next poll given the current failure count."""
        if self.failures == 0:
            return self._interval
        return min(self._interval * (2 ** self.failures), self._max_backoff)

    async def run(self) -> None:
        """Poll forever. Only cancellation stops it."""
        logger.info("live_bridge.started interval=%.0fs settle=%.0fs",
                    self._interval, self._settle)
        while True:
            if not self._in_session(self._clock()):
                # Market closed: the worker's writes carry no new prices.
                # Neither query nor publish; a failure streak does not carry
                # over into the next session.
                self.failures = 0
                await self._sleep(self._interval)
                continue
            self._idle.clear()
            try:
                await self.poll_once()
                self.failures = 0
            except asyncio.CancelledError:
                raise
            except Exception:
                self.failures += 1
                logger.warning(
                    "live_bridge.poll_failed failures=%d retry_in=%.0fs",
                    self.failures, self.next_delay(), exc_info=True,
                )
            finally:
                self._idle.set()
            await self._sleep(self.next_delay())

    def start(self) -> asyncio.Task[None]:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run(), name="live_bridge")
        return self._task

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        # AsyncSession.__aexit__ closes the session in a SHIELDED child task.
        # Cancelling mid-read cancels only the waiter: the close keeps running
        # after stop() returns, and the loop is closed under it (aiosqlite:
        # "RuntimeError: Event loop is closed" in its worker thread). Let the
        # read finish first; cancel only the sleep, or a read past the grace.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._idle.wait(), STOP_GRACE_SECONDS)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("live_bridge.stop_failed")
        logger.info("live_bridge.stopped")
