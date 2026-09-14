"""
GET /api/stream/live — Server-Sent Events.

Browser opens an EventSource to this endpoint. Events:

* ``hello`` once on connect.
* ``update`` when this API process's broker receives a publish. In production
  those come from services/live_bridge.py, which publishes once per settled
  database write (about once per worker pass, ~70-80s apart during US market
  hours, 10-30s after the pass finishes). The payload is
  ``{"event": <name>, "payload": {...}}``; the browser does not patch from it,
  it refetches the page's data (frontend/lib/useLiveStream.ts).
* ``ping`` after 25s with no update, to keep proxies from closing the
  connection. A ping says only that the connection is open. It is not evidence
  that any data changed, and the client must not treat it as such.

The prices behind those writes are the vendor's ~15-minute-delayed prices, so
nothing on this stream is real-time market data.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.services.pubsub import broker

router = APIRouter()


@router.get("/live")
async def live_stream() -> EventSourceResponse:
    queue = broker.subscribe()

    async def event_source() -> AsyncIterator[dict]:
        try:
            # Initial hello so the client confirms the connection
            yield {"event": "hello", "data": "{\"status\":\"connected\"}"}
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield {"event": "update", "data": msg}
                except TimeoutError:
                    # Heartbeat to keep proxy connections alive
                    yield {"event": "ping", "data": "{}"}
        finally:
            broker.unsubscribe(queue)

    return EventSourceResponse(event_source())
