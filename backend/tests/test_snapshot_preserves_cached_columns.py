"""A cold cache must never erase data we already hold.

The snapshot upsert runs every 60 seconds. Four of the columns it writes come
from in-memory caches — market_cap from _MARKET_CAP_CACHE, and the three bar
stats from _BAR_STATS_CACHE — and both dicts are EMPTY for every symbol after a
process start. Writing the plain value therefore stamped NULL over good data on
the first tick after each deploy and kept doing so until the once-daily refresh
repopulated the cache, up to 24 hours later.

Measured in production during a deploy: 52-week coverage fell 2,190 -> 100 and
average volume 2,486 -> 103. It also explains why market_cap crawled for a day —
its backfill was filling rows while this tick wiped them.

The fix is COALESCE on exactly those four columns. The snapshot fields are
deliberately NOT protected: they arrive fresh from the vendor each tick, so a
NULL there is a real "no read" and preserving a stale one would be dishonest.
"""
from __future__ import annotations

import inspect

from app.workers import signal_publisher

SRC = inspect.getsource(signal_publisher.publish_tick) if hasattr(
    signal_publisher, "publish_tick"
) else inspect.getsource(signal_publisher)


def test_cache_derived_columns_are_coalesced():
    """Membership, not formatting — the list grows as more columns become
    cache-derived, and a test that pins the exact literal fails on a reflow
    instead of on a regression."""
    start = SRC.index("cache_derived = (")
    block = SRC[start:SRC.index(")", start)]
    for col in (
        "market_cap", "week52_high", "week52_low", "avg_volume_30d",
        # Joined the list when they stopped being random draws.
        "change_pct_5d", "change_pct_1m",
    ):
        assert f'"{col}"' in block, f"{col} is no longer protected from the restart wipe"
    assert "func.coalesce(bindparam(col), getattr(Ticker, col))" in SRC


def test_snapshot_fields_are_NOT_coalesced():
    """A vendor NULL means 'no read today' and must not resurrect a stale price."""
    start = SRC.index("cache_derived = (")
    line = SRC[start:SRC.index("\n", start)]
    for fresh in ("previous_close", "day_open", "day_high", "day_low", "price"):
        assert fresh not in line, (
            f"{fresh} is written fresh from the vendor every tick; coalescing it "
            f"would preserve a stale value and hide a real gap"
        )


def test_the_tick_loop_uses_no_unguarded_bulk_update():
    """`session.execute(update(Ticker), batch)` is the shape that wiped the data.

    Scoped to the TICK loop deliberately. The same plain form is correct inside
    _backfill_key_statistics, which writes values it has just fetched — a NULL
    there means Finnhub has no coverage for that symbol, not that a cache was
    cold. Only the 60-second tick reads from caches that empty on restart.
    """
    start = SRC.index("cache_derived = (")
    tick_region = SRC[start - 3000:SRC.index("# --- Replace squeeze setups ---", start)]
    assert "await session.execute(update(Ticker), batch)" not in tick_region, (
        "the unguarded bulk update is back in the tick loop — a cold cache will "
        "erase market_cap and the bar stats on the first tick after every deploy"
    )
