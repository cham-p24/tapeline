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
it reads two watermarks in one query:

* ``max(tickers.updated_at)`` over scored rows. ``updated_at`` means "live
  data was written to this row" (see the comment on ``Ticker.updated_at``;
  metadata writers hold it still), so it advances once per worker pass, on
  the sheet refresh and on the daily crypto refresh.
* ``max(regime_state.updated_at)`` (a single row).

When a watermark advances and has *settled*, it publishes ONE event to the
local broker, with the event names the worker already uses. The browser treats
every event the same way (it refetches), so one event per advance is what
keeps a page to one refetch per pass.

Settling. A pass rewrites ~11,500 rows over ~5 seconds, stamping each row as
it goes, so a poll can land mid-pass and see a max that is still climbing.
Publishing that would refetch a half-written pass and then refetch again 15s
later. An advance is therefore published only once the new max is at least
``SETTLE_SECONDS`` old, or has been observed unchanged on two consecutive
polls (which covers clock skew between machines). Latency from the end of a
pass to the event is roughly 10-30 seconds.

Cost. One statement, two scalar sub-selects. There is no index on
``tickers.updated_at`` and this deliberately does not add one: every pass
rewrites that column on every scored row, so an index on it would turn every
row update of every pass into an index write. Measured on production on
14 Sep 2026 (11,925 rows, 11,657 scored): a sequential scan, 2,343 shared
buffer hits, 4.0 ms execution, ~6 ms round trip. At one query per 15s per API
process that is well under 0.1% of one core.

Not LISTEN/NOTIFY. The production DATABASE_URL is a transaction-pooled Neon
endpoint (``db.is_transaction_pooled`` is True, checked 14 Sep 2026), and
LISTEN does not survive transaction pooling.

Failure handling. Any exception while polling is logged and retried with
exponential backoff (capped at ``MAX_BACKOFF_SECONDS``). The watermarks it has
already published are kept, so a DB blip neither crashes the API nor replays
an old event. Cancellation (app shutdown) is the only way out of the loop.

Multiple API machines. Each machine's process has its own broker, its own
subscribers and its own bridge. They do not coordinate and do not need to.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)

#: How often each API process reads the watermarks.
POLL_INTERVAL_SECONDS = 15.0
#: A new watermark this old (or seen unchanged on two polls) is a finished pass.
SETTLE_SECONDS = 10.0
#: Ceiling for the retry delay after consecutive poll failures.
MAX_BACKOFF_SECONDS = 300.0

#: Event names, shared with the worker's in-process publishes
#: (workers/signal_publisher.py) so the browser handles both identically.
SCORES_EVENT = "scores_updated"
REGIME_EVENT = "regime_updated"

WATERMARK_SQL = text(
    "select "
    "(select max(updated_at) from tickers where score is not null) as tickers_at, "
    "(select max(updated_at) from regime_state) as regime_at"
)


@dataclass(frozen=True)
class Watermarks:
    tickers_at: datetime | None
    regime_at: datetime | None


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
    """Read both watermarks in one statement.

    ``SessionLocal`` is looked up at call time, not import time, so the test
    suite's per-test re-binding of the session factory applies here too.
    """
    from app import db

    async with db.SessionLocal() as session:
        row = (await session.execute(WATERMARK_SQL)).mappings().one()
    return Watermarks(
        tickers_at=_as_utc(row["tickers_at"]),
        regime_at=_as_utc(row["regime_at"]),
    )


Publish = Callable[[str, dict[str, Any]], Awaitable[None]]


class LiveBridge:
    """Poll the watermarks and publish one event per settled advance."""

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
    ) -> None:
        self._publish = publish
        self._read = read
        self._clock = clock
        self._sleep = sleep
        self._interval = interval
        self._settle = settle
        self._max_backoff = max_backoff
        self._baselined = False
        # Last value we published (or baselined on), per watermark.
        self._published: dict[str, datetime | None] = {}
        # Value observed on the previous successful poll, per watermark.
        self._seen: dict[str, datetime | None] = {}
        self.failures = 0
        self._task: asyncio.Task[None] | None = None

    def _ready(self, name: str, value: datetime | None, now: datetime) -> bool:
        """Whether ``value`` is a settled advance past what was published."""
        previous_seen = self._seen.get(name)
        self._seen[name] = value
        if value is None:
            return False
        published = self._published.get(name)
        if published is not None and value <= published:
            return False
        aged = (now - value).total_seconds() >= self._settle
        return aged or value == previous_seen

    async def poll_once(self) -> str | None:
        """One read. Returns the event name published, or None.

        Raises whatever the read raises; :meth:`run` owns retry and backoff.
        """
        marks = await self._read()
        now = self._clock()

        if not self._baselined:
            # First successful read: a browser that connects now loads the
            # current data on mount, so there is nothing to announce yet.
            self._published = {"tickers": marks.tickers_at, "regime": marks.regime_at}
            self._seen = dict(self._published)
            self._baselined = True
            return None

        tickers_ready = self._ready("tickers", marks.tickers_at, now)
        regime_ready = self._ready("regime", marks.regime_at, now)

        published_tickers = self._published.get("tickers")
        tickers_pending = marks.tickers_at is not None and (
            published_tickers is None or marks.tickers_at > published_tickers
        )

        event: str | None = None
        if regime_ready and tickers_pending and not tickers_ready:
            # The regime row landed but the same pass's ticker rows are still
            # settling. Wait: the scores event on a later poll covers both, so
            # the browser refetches once for the pass, not twice.
            return None
        if tickers_ready and marks.tickers_at is not None:
            event = SCORES_EVENT
            payload = {"ts": marks.tickers_at.isoformat()}
        elif regime_ready and marks.regime_at is not None:
            event = REGIME_EVENT
            payload = {"ts": marks.regime_at.isoformat()}

        if event is None:
            return None

        # The worker writes the regime row in the same pass as the tickers, so
        # a scores event already covers a regime advance seen in this poll.
        # Mark both published BEFORE publishing so a publish error cannot make
        # the next poll replay the same advance.
        if tickers_ready:
            self._published["tickers"] = marks.tickers_at
        if regime_ready:
            self._published["regime"] = marks.regime_at
        await self._publish(event, payload)
        logger.info("live_bridge.published event=%s ts=%s", event, payload["ts"])
        return event

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
            await self._sleep(self.next_delay())

    def start(self) -> asyncio.Task[None]:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run(), name="live_bridge")
        return self._task

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("live_bridge.stop_failed")
        logger.info("live_bridge.stopped")
