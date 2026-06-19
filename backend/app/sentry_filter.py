"""Sentry before_send filter — drop handled operational noise.

Vendor feeds (Massive/Polygon, Finnhub, Benzinga, EDGAR, FRED) throw transient
network/timeout errors constantly on free tiers; each is caught with a graceful
fallback, but Sentry's LoggingIntegration still turns every ``logger.exception``
into a billable event + alert email. Likewise the scan worker logs
``tick.timeout`` every cycle the scan runs long. Left unfiltered these flood the
error quota (and the founder's inbox) and bury genuine bugs.

This drops that *handled* noise while letting real errors through:
- logic bugs (ValueError, KeyError, ...), DB errors, and any UNHANDLED
  exception still reach Sentry, and
- the wedged-worker pager (``tick.timeout_streak``) still reaches Sentry —
  only the routine per-cycle ``tick.timeout`` line is dropped.
"""
from __future__ import annotations

import asyncio
import socket
from typing import Any

# Transient network/timeout exceptions — all handled upstream with fallbacks.
_TRANSIENT_EXC: tuple[type[BaseException], ...] = (
    TimeoutError,        # builtin (asyncio.TimeoutError aliases this on 3.11+)
    asyncio.TimeoutError,
    ConnectionError,     # builtin base: ConnectionReset / Refused / Aborted
    socket.timeout,
)
try:  # httpx is the vendor HTTP client — add its timeout + transport families
    import httpx

    _TRANSIENT_EXC = _TRANSIENT_EXC + (httpx.TimeoutException, httpx.TransportError)
except Exception:  # pragma: no cover - httpx is always present in prod
    pass

# Routine operational log events that are not bugs (still visible in Fly logs).
_NOISE_PREFIXES: tuple[str, ...] = (
    "tick.timeout elapsed",  # per-cycle scan-over-budget; the *_streak pager stays
)


def before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Return the event to send it to Sentry, or None to drop it."""
    exc_info = hint.get("exc_info")
    if exc_info and len(exc_info) >= 2 and isinstance(exc_info[1], _TRANSIENT_EXC):
        return None

    message = ""
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        message = logentry.get("message") or ""
    message = message or event.get("message") or ""
    if any(message.startswith(p) for p in _NOISE_PREFIXES):
        return None

    return event
