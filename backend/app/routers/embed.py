"""POST /api/embed/impression — count one render of an embeddable surface.

WHY AN ENDPOINT AND NOT A PIGGYBACK
-----------------------------------
The obvious cheaper design is to forward the embedding host on the ticker fetch
the badge route ALREADY makes (`GET /api/ticker/{symbol}`) and record it as a
side effect — no extra round trip. That doesn't work here, for two reasons:

  1. That fetch is `next: { revalidate: 1800 }`. It hits our origin at most once
     per symbol per 30 minutes; every other badge render is served from Next's
     data cache and never reaches the backend. We'd learn about one embedding
     host per symbol per half hour — which is precisely the "who embeds us"
     signal we're trying to recover, destroyed.
  2. Next keys the data cache on the fetch options, so adding a per-host header
     would fragment the cache into one entry per (host, symbol) and multiply
     real backend load — the opposite of the constraint.

So the impression is its own request, and the cost is paid off the response
path instead: the frontend fires it from `after()`, so the badge SVG / iframe
HTML is already on the wire before this endpoint is called. Nothing about the
render blocks on, waits for, or fails because of it.

FAIL-OPEN, ALWAYS
-----------------
This endpoint returns 200 for every input it can parse. Bad host, junk symbol,
unknown surface, rate-limited, write error — all come back
`{"ok": true, "recorded": false}`. The caller is a fire-and-forget task with no
error path; a 4xx/5xx here would only produce log noise on the frontend.

RATE LIMITING
-------------
Two in-process token buckets:
  - per embedding host: caps how much one hotlinking site can write
  - global: caps total write volume regardless of host rotation

Over either cap the impression is dropped (still a 200). Because the table
aggregates, dropping is cheap — a rate-limited host still gets its bucket, just
with a lower count, and the counts were already directional (CDN caching, see
models/embed_impression.py).

TRUST
-----
Unauthenticated by necessity — it is called by the Next server on behalf of an
anonymous browser. The numbers are therefore self-reported and inflatable by
anyone who wants to POST at them. That is acceptable for what this is: an
internal steering metric for outreach ("which sites carry our badge"), not a
billing input and not a public claim. The rate limits bound the damage.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.embed_impressions import (
    normalize_embed_host,
    record_embed_impression,
)
from app.services.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter()

# Per-embedding-host write budget. Generous for a real site (the table only
# needs one write per distinct symbol per day to be correct-ish), tight enough
# that a single hotlinker can't drive our write volume.
_HOST_CAPACITY = 120
_HOST_WINDOW_S = 60

# Machine-wide ceiling, so rotating the claimed host doesn't bypass the above.
_GLOBAL_CAPACITY = 3000
_GLOBAL_WINDOW_S = 60


class ImpressionIn(BaseModel):
    """The whole payload. Note what is NOT here: no URL, no path, no query, no
    user agent, no IP. The frontend reduces the browser's Referer to a hostname
    before it ever leaves the Next server, and the backend re-validates it."""

    # Already a hostname when the frontend behaves; `normalize_embed_host`
    # accepts a full URL too and throws everything but the host away, so a
    # mistake at a call site can't leak a path into the column.
    host: str | None = Field(default=None, max_length=300)
    symbol: str = Field(max_length=20)
    surface: str = Field(max_length=16)


@router.post("/impression")
async def record_impression(
    payload: ImpressionIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Increment one (day, host, symbol, surface) bucket. Always 200."""
    try:
        # Normalise first so the rate-limit key is the canonical host, not
        # whatever casing/`www.` the caller sent — otherwise the same site
        # could hold several buckets.
        host = normalize_embed_host(payload.host)
        if host is None:
            # Missing / self / local / junk referer — a deliberate skip, and
            # cheap enough that it never touches a rate-limit bucket.
            return {"ok": True, "recorded": False}

        if not await limiter.consume(
            f"embedhost:{host}", _HOST_CAPACITY, _HOST_WINDOW_S
        ):
            return {"ok": True, "recorded": False}
        if not await limiter.consume(
            "embed:global", _GLOBAL_CAPACITY, _GLOBAL_WINDOW_S
        ):
            return {"ok": True, "recorded": False}

        recorded = await record_embed_impression(
            session,
            referer=host,
            symbol=payload.symbol,
            surface=payload.surface,
        )
        return {"ok": True, "recorded": recorded}
    except Exception:
        # Belt and braces — record_embed_impression already swallows its own
        # failures, so reaching here means something outside it broke. Still a
        # 200: the embed it belongs to has already rendered.
        logger.warning("embed_impression.endpoint_failed")
        return {"ok": True, "recorded": False}
