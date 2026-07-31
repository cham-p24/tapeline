"""
In-process token-bucket rate limiter. Good enough for single-instance API.
Swap to Redis-backed when scaling past one box.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass

from fastapi import HTTPException, Request


@dataclass
class Bucket:
    tokens: float
    last_refill: float
    capacity: float
    refill_rate: float  # tokens per second


class TokenBucket:
    def __init__(self) -> None:
        self._buckets: dict[str, Bucket] = defaultdict(lambda: Bucket(0, 0, 0, 0))
        self._lock = asyncio.Lock()

    async def consume(self, key: str, capacity: int, per_seconds: int, cost: int = 1) -> bool:
        async with self._lock:
            now = time.monotonic()
            b = self._buckets[key]
            refill_rate = capacity / per_seconds
            if b.capacity == 0:  # first use for this key
                b.tokens = float(capacity)
            else:
                # Honor the CURRENT (capacity, per_seconds), not whatever the
                # first caller froze in. Previously this else-branch reused
                # b.capacity/b.refill_rate, so if a key was ever consumed with
                # two different caps the FIRST one won forever — which silently
                # killed limit_strict's 10/min cap once the 120/min middleware
                # limiter initialized the shared key. Callers now also namespace
                # their keys (api:/strict:/auth:), so a key maps to one cap; this
                # keeps it correct even if that ever changes.
                b.tokens = min(float(capacity), b.tokens + (now - b.last_refill) * refill_rate)
            b.last_refill = now
            b.capacity = float(capacity)
            b.refill_rate = refill_rate

            if b.tokens >= cost:
                b.tokens -= cost
                return True
            return False


limiter = TokenBucket()


def client_ip(request: Request) -> str:
    """Best client IP. Prefer Cloudflare's un-forgeable cf-connecting-ip header
    (set by the proxy, not the client), then fall back to the leftmost
    X-Forwarded-For token, then the direct socket peer."""
    xff = request.headers.get("X-Forwarded-For", "")
    return (
        request.headers.get("cf-connecting-ip")
        or (xff.split(",")[0].strip() if xff else "")
        or (request.client.host if request.client else "anon")
    )


def _client_key(request: Request) -> str:
    """Prefer Authorization user, fall back to IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return f"tok:{auth[-20:]}"  # last 20 chars is enough to distinguish users
    return f"ip:{client_ip(request)}"


async def limit_api(request: Request, capacity: int = 120, per_seconds: int = 60) -> None:
    """Default: 120 req/min per client. Strict enough to stop abusers, loose for humans."""
    # Namespaced key: the global middleware calls this on every /api/* request,
    # so it must NOT share a bucket with limit_strict (which would let the
    # 120/min budget satisfy the strict endpoints' intended 10/min cap).
    ok = await limiter.consume(f"api:{_client_key(request)}", capacity, per_seconds)
    if not ok:
        raise HTTPException(status_code=429, detail="Too many requests. Slow down.")


async def limit_strict(request: Request) -> None:
    """Tighter limit (10/min) for expensive endpoints (briefing send, checkout).

    Its own `strict:` namespace so the always-first middleware limit_api bucket
    can't pre-initialize and swallow this cap.
    """
    ok = await limiter.consume(f"strict:{_client_key(request)}", 10, 60)
    if not ok:
        raise HTTPException(status_code=429, detail="Too many requests.")


async def limit_auth(request: Request) -> None:
    """
    Tightest limit for auth endpoints — 10 attempts per minute per IP.
    Slows down credential-stuffing and trial-account-creation bots.
    Always IP-keyed (auth has no token yet).
    """
    ip = client_ip(request)
    ok = await limiter.consume(f"auth:{ip}", 10, 60)
    if not ok:
        raise HTTPException(status_code=429, detail="Too many auth attempts. Wait a minute and try again.")
