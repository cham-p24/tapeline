"""
Historical daily OHLCV bar provider — used by the walk-forward backtest.

This module wraps Massive's (formerly Polygon's) historical aggregates endpoint
behind a small, deterministic, file-cached interface. It is intentionally
separate from `polygon_feed.py` because the runtime adapter is async + tied to
the worker's snapshot pipeline, whereas the backtest needs a sync, single-
process, cache-first reader that doesn't depend on the worker being up.

Why a dedicated module:
    - Backtests are CLI-invoked, often re-run repeatedly on overlapping windows.
      Hitting the network every time would be slow + would burn the free-tier
      rate budget. A 24h on-disk cache means the second run of a 2-year
      back-test is essentially free.
    - The runtime adapter (`polygon_feed.fetch_aggregates`) is async; the
      backtest is a sync script. Bridging async into a sync CLI for every bar
      fetch would be awkward — far cleaner to have a sync provider here.
    - The backtest needs a synthetic fallback so devs / CI can run the script
      without ever needing a MASSIVE_API_KEY. That fallback is best kept on
      this side of the boundary so the live adapter stays a thin, real-only
      wrapper.

Auth:
    - Reads MASSIVE_API_KEY first, then POLYGON_API_KEY (Massive accepts both
      during the rebrand grace period — same posture as `polygon_feed`).
    - Both unset → falls back to the deterministic GBM-style synthetic series
      that the walk-forward backtest used in v1.

Rate limits:
    - Massive Starter tier: 5 calls/min. Token-bucket throttling enforced via
      `_acquire_slot()` — sleeps until a fresh slot is available rather than
      letting a 429 leak through.

Cache:
    - 24h TTL. Files at $TAPELINE_BAR_CACHE_DIR (default
      `~/.cache/tapeline/historical_bars/`). Bar files named
      `{symbol}_{start}_{end}.json` for trivial debuggability.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Default cache directory. Overridable via TAPELINE_BAR_CACHE_DIR so CI and
# integration tests can point at a tmp_path without polluting the user's $HOME.
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "tapeline" / "historical_bars"

# 24h cache TTL — Massive aggregates for completed trading days never change,
# but we still expire daily so re-runs after a new trading session pick up
# any newly-completed bar without manual cache eviction.
CACHE_TTL_SECONDS = 24 * 3600

# Massive Starter rate limit: 5 calls / minute. Token bucket enforces this
# at the call site so we never get 429'd.
RATE_LIMIT_CALLS = 5
RATE_LIMIT_WINDOW_SECONDS = 60.0

# Default Massive base URL. Overridable for sandbox / failover targets, same as
# the runtime adapter at `polygon_feed.py`.
DEFAULT_BASE_URL = "https://api.massive.com"


# ---------------------------------------------------------------------------
# BarData — the public schema returned by `fetch_daily_bars`
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BarData:
    """A single daily OHLCV bar.

    Schema is intentionally a subset of Massive's `/v2/aggs` row — only the
    fields the back-test actually needs. Frozen + ordered for trivial JSON
    serialisation in the cache.
    """

    symbol: str
    bar_date: date      # the trading day (UTC date — Massive ts is end-of-day)
    open: float
    high: float
    low: float
    close: float
    volume: int

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["bar_date"] = self.bar_date.isoformat()
        return d

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> BarData:
        return cls(
            symbol=d["symbol"],
            bar_date=date.fromisoformat(d["bar_date"]),
            open=float(d["open"]),
            high=float(d["high"]),
            low=float(d["low"]),
            close=float(d["close"]),
            volume=int(d["volume"]),
        )


# ---------------------------------------------------------------------------
# Configuration accessors
# ---------------------------------------------------------------------------


def _api_key() -> str:
    """Whichever vendor key is configured. Prefer MASSIVE_API_KEY (post-rebrand)
    then POLYGON_API_KEY (grace-period legacy). Empty string when neither is set
    — the caller treats that as the synthetic-fallback signal."""
    return os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY") or ""


def _base_url() -> str:
    return os.environ.get("MASSIVE_BASE_URL", DEFAULT_BASE_URL)


def cache_dir() -> Path:
    """Resolved cache directory, honouring TAPELINE_BAR_CACHE_DIR.

    Exposed (not underscore-prefixed) so tests can introspect where files
    actually land. Creates the directory lazily — callers can call this in
    tests without setting any state up front.
    """
    p = Path(os.environ.get("TAPELINE_BAR_CACHE_DIR", str(DEFAULT_CACHE_DIR)))
    p.mkdir(parents=True, exist_ok=True)
    return p


def configured() -> bool:
    """Whether a real Massive key is available. False → synthetic fallback."""
    return bool(_api_key())


# ---------------------------------------------------------------------------
# Token-bucket throttle — 5 calls / 60s
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Simple sliding-window throttle. Not async — the backtest is sync.

    Each `acquire()` blocks (via time.sleep) until the call would fit within
    the configured rate. Tests inject a fake sleep_fn so we can verify the
    throttle without actually sleeping.
    """

    def __init__(
        self,
        max_calls: int = RATE_LIMIT_CALLS,
        window: float = RATE_LIMIT_WINDOW_SECONDS,
        time_fn: Any = time.monotonic,
        sleep_fn: Any = time.sleep,
    ):
        self._max = max_calls
        self._window = window
        self._calls: deque[float] = deque()
        self._time = time_fn
        self._sleep = sleep_fn

    def acquire(self) -> None:
        """Block until a call slot is free, then record the call."""
        now = self._time()
        # Drop expired entries
        while self._calls and self._calls[0] <= now - self._window:
            self._calls.popleft()
        if len(self._calls) >= self._max:
            # Sleep until the oldest call expires
            sleep_for = (self._calls[0] + self._window) - now
            if sleep_for > 0:
                self._sleep(sleep_for)
            # After sleep, recompute and drop expired
            now = self._time()
            while self._calls and self._calls[0] <= now - self._window:
                self._calls.popleft()
        self._calls.append(now)


# Module-level limiter — shared across all `fetch_daily_bars` calls in a
# process so a multi-symbol back-test correctly serialises into the budget.
_LIMITER = _RateLimiter()


def reset_rate_limiter(
    *,
    max_calls: int = RATE_LIMIT_CALLS,
    window: float = RATE_LIMIT_WINDOW_SECONDS,
    sleep_fn: Any = time.sleep,
) -> None:
    """Test helper: wipe the limiter state between tests.

    Tests can pass a no-op `sleep_fn` (lambda _: None) so the rate limiter's
    sleep-to-wait branch fires instantly instead of blocking the test for
    a real minute. Production code never calls this with overrides — it's
    purely a test hook.
    """
    global _LIMITER
    _LIMITER = _RateLimiter(max_calls=max_calls, window=window, sleep_fn=sleep_fn)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_path(symbol: str, start: date, end: date) -> Path:
    """Per-(symbol, window) cache file. The filename embeds the dates so a
    debugger can `ls` the cache dir + see what's there without parsing JSON.
    """
    safe_sym = symbol.replace("/", "_").replace(".", "_")
    return cache_dir() / f"{safe_sym}_{start.isoformat()}_{end.isoformat()}.json"


def _load_cached_bars(symbol: str, start: date, end: date) -> list[BarData] | None:
    """Return cached bars if present + fresh (within TTL). None otherwise.

    A corrupt/unparsable cache file is treated as a miss and silently dropped
    so the next call will repopulate it.
    """
    p = _cache_path(symbol, start, end)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        ts = float(raw.get("_ts", 0))
        if (time.time() - ts) > CACHE_TTL_SECONDS:
            return None
        rows = raw.get("bars", [])
        return [BarData.from_json(r) for r in rows]
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        logger.warning("historical_bars.cache_read_failed sym=%s", symbol)
        return None


def _save_cached_bars(symbol: str, start: date, end: date, bars: list[BarData]) -> None:
    """Persist a fetched bar series to disk. Best-effort — a write failure
    just means the next call will re-fetch."""
    p = _cache_path(symbol, start, end)
    try:
        payload = {
            "_ts": time.time(),
            "symbol": symbol,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "bars": [b.to_json() for b in bars],
        }
        p.write_text(json.dumps(payload), encoding="utf-8")
    except (OSError, TypeError):
        logger.warning("historical_bars.cache_write_failed sym=%s", symbol)


# ---------------------------------------------------------------------------
# Synthetic-fallback generator (matches the v1 walk_forward_backtest series)
# ---------------------------------------------------------------------------


def _synthetic_bars(symbol: str, start: date, end: date) -> list[BarData]:
    """Deterministic GBM-style daily bars for `symbol` over [start, end].

    Mirrors `walk_forward_backtest._simulate_price_series` exactly: same
    anchor (2024-01-01), same per-symbol baseline + drift + RNG seed scheme,
    same SPY tuning, same weekday-only emission. Keeping the two in sync
    matters because tests in test_walk_forward_backtest assert determinism
    across re-runs — the live-mode fallback path must produce the same
    series as the mock-mode path used to, so the synthetic-fallback footer
    is the *only* observable change when running without a key.
    """
    seed = sum(ord(c) for c in symbol + "price") * 7919
    rng = random.Random(seed)
    baseline = rng.uniform(25, 500)
    drift = rng.uniform(-0.0002, 0.0004)
    if symbol == "SPY":
        baseline = 450.0
        drift = 0.00035

    anchor = date(2024, 1, 1)
    out: list[BarData] = []
    price = baseline
    current = anchor
    walk_end = end + timedelta(days=7)

    # For dates before the anchor, emit baseline bars (rare/edge case, mirrors
    # the v1 behaviour).
    if start < anchor:
        d = start
        while d < anchor:
            if d.weekday() < 5:
                out.append(BarData(
                    symbol=symbol,
                    bar_date=d,
                    open=round(baseline, 2),
                    high=round(baseline, 2),
                    low=round(baseline, 2),
                    close=round(baseline, 2),
                    volume=0,
                ))
            d = d + timedelta(days=1)

    while current <= walk_end:
        if current.weekday() < 5:
            shock = rng.gauss(0, 0.012)
            price *= max(0.5, 1 + drift + shock)
            if start <= current <= end:
                p = round(price, 2)
                out.append(BarData(
                    symbol=symbol,
                    bar_date=current,
                    open=p,
                    high=p,
                    low=p,
                    close=p,
                    volume=0,
                ))
        current = current + timedelta(days=1)

    return out


# ---------------------------------------------------------------------------
# Public fetch — the one function the back-test (and tests) call
# ---------------------------------------------------------------------------


def fetch_daily_bars(
    symbol: str,
    start: date,
    end: date,
    *,
    client: httpx.Client | None = None,
) -> list[BarData]:
    """Daily OHLCV bars for `symbol` over the inclusive window [start, end].

    Order of resolution:
        1. On-disk cache (24h TTL) — exact (symbol, start, end) match
        2. Massive `/v2/aggs/ticker/{sym}/range/1/day/{from}/{to}` — if a key
           is set. Rate-throttled to 5 calls/min on the module-level limiter.
        3. Synthetic GBM-style fallback — no key required, deterministic per
           symbol so a backtest is reproducible across machines.

    The `client` parameter lets tests inject a mocked httpx.Client (transport=
    MockTransport) so no real network call fires in CI.
    """
    if end < start:
        return []

    # 1. Cache hit
    cached = _load_cached_bars(symbol, start, end)
    if cached is not None:
        return cached

    # 2. Real fetch (when configured)
    if configured():
        try:
            bars = _fetch_from_massive(symbol, start, end, client=client)
            if bars:
                _save_cached_bars(symbol, start, end, bars)
                return bars
            # Empty response (e.g. weekend-only window, suspended ticker) —
            # cache the empty result too so we don't re-hammer the API for
            # the same window. Use synthetic fallback to keep the back-test
            # from blowing up on a missing symbol.
            logger.info("historical_bars.empty_response sym=%s — falling back to synthetic", symbol)
        except Exception:
            logger.exception("historical_bars.fetch_failed sym=%s — falling back to synthetic", symbol)

    # 3. Synthetic fallback
    return _synthetic_bars(symbol, start, end)


def _fetch_from_massive(
    symbol: str,
    start: date,
    end: date,
    *,
    client: httpx.Client | None = None,
) -> list[BarData]:
    """Hit Massive's historical aggregates endpoint + parse the response.

    Separate from `fetch_daily_bars` so tests can mock this layer directly
    when they want to assert real-mode behaviour without engaging the
    cache + fallback branches.
    """
    _LIMITER.acquire()

    path = f"/v2/aggs/ticker/{symbol}/range/1/day/{start.isoformat()}/{end.isoformat()}"
    # Annotated as str values throughout so mypy doesn't infer the dict as
    # dict[str, object], which httpx.Client.get() rejects. Stringifying the
    # limit is fine — Massive parses it back to int server-side.
    params: dict[str, str] = {
        "adjusted": "true",
        "sort": "asc",
        "limit": "50000",  # Massive caps at 50k bars/req — plenty for ~200 trading days
        "apiKey": _api_key(),
    }
    url = f"{_base_url()}{path}"

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=30.0)
    try:
        assert client is not None  # narrow the type for mypy
        resp = client.get(url, params=params)
        resp.raise_for_status()
        body = resp.json()
    finally:
        if owns_client and client is not None:
            client.close()

    results = body.get("results") or []
    bars: list[BarData] = []
    for r in results:
        ts = r.get("t")  # ms since epoch, UTC, end-of-bar
        if ts is None:
            continue
        bar_date = date.fromtimestamp(ts / 1000.0)
        bars.append(BarData(
            symbol=symbol,
            bar_date=bar_date,
            open=float(r.get("o", 0.0)),
            high=float(r.get("h", 0.0)),
            low=float(r.get("l", 0.0)),
            close=float(r.get("c", 0.0)),
            volume=int(r.get("v", 0) or 0),
        ))
    return bars
