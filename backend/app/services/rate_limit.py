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
            if b.capacity == 0:  # first use, initialize
                b.capacity = capacity
                b.refill_rate = capacity / per_seconds
                b.tokens = capacity
                b.last_refill = now
            else:
                elapsed = now - b.last_refill
                b.tokens = min(b.capacity, b.tokens + elapsed * b.refill_rate)
                b.last_refill = now

            if b.tokens >= cost:
                b.tokens -= cost
                return True
            return False


limiter = TokenBucket()


def _client_key(request: Request) -> str:
    """Prefer Authorization user, fall back to IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return f"tok:{auth[-20:]}"  # last 20 chars is enough to distinguish users
    xff = request.headers.get("X-Forwarded-For", "")
    ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "anon")
    return f"ip:{ip}"


async def limit_api(request: Request, capacity: int = 120, per_seconds: int = 60) -> None:
    """Default: 120 req/min per client. Strict enough to stop abusers, loose for humans."""
    ok = await limiter.consume(_client_key(request), capacity, per_seconds)
    if not ok:
        raise HTTPException(status_code=429, detail="Too many requests. Slow down.")


async def limit_strict(request: Request) -> None:
    """Tighter limit for expensive endpoints (briefing send, checkout)."""
    ok = await limiter.consume(_client_key(request), 10, 60)
    if not ok:
        raise HTTPException(status_code=429, detail="Too many requests.")


async def limit_auth(request: Request) -> None:
    """
    Tightest limit for auth endpoints — 10 attempts per minute per IP.
    Slows down credential-stuffing and trial-account-creation bots.
    Always IP-keyed (auth has no token yet).
    """
    xff = request.headers.get("X-Forwarded-For", "")
    ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else "anon")
    ok = await limiter.consume(f"auth:{ip}", 10, 60)
    if not ok:
        raise HTTPException(status_code=429, detail="Too many auth attempts. Wait a minute and try again.")
