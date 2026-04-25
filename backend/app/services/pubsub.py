"""
In-process pub/sub for SSE fan-out.

Keeps the MVP simple — later this swaps to Redis pub/sub when we scale past
one API container. The interface stays identical so only the internals change.
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
