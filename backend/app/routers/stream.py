"""
GET /api/stream/live — Server-Sent Events.

Browser opens an EventSource to this endpoint and receives push events each
time the worker completes a tick. The browser applies the patch to the
dashboard state without a full refetch.
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
                except asyncio.TimeoutError:
                    # Heartbeat to keep proxy connections alive
                    yield {"event": "ping", "data": "{}"}
        finally:
            broker.unsubscribe(queue)

    return EventSourceResponse(event_source())
