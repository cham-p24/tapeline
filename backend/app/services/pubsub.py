"""
In-process pub/sub for SSE fan-out.

IN-PROCESS ONLY. A publish reaches subscribers in the same Python process and
nowhere else. In production the worker (workers/signal_publisher.py) and the
API (routers/stream.py) are separate Fly processes on separate machines, so
the worker's own publishes never reach a browser. Measured 14 Sep 2026: 300s
of /api/stream/live during the US session delivered 0 update events across 4
worker passes.

What actually feeds API subscribers is services/live_bridge.py, which runs in
each API process, watches the database for new writes and publishes here.
Anything that needs to reach a browser must be published from the API process
(or detected by that bridge), not from the worker.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any


class InMemoryBroker:
    """Single-process pub/sub. Subscribers get async queues."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    async def publish(self, event: str, payload: dict[str, Any]) -> None:
        msg = json.dumps({"event": event, "payload": payload})
        for q in list(self._subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                # Slow consumer — drop silently
                pass

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        self._subscribers.discard(q)


broker = InMemoryBroker()
