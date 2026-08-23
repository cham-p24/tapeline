"""A cold cache must never erase data we already hold.

The snapshot upsert runs every 60 seconds. The columns it writes from
in-memory caches — market_cap from _MARKET_CAP_CACHE, the bar stats from
_BAR_STATS_CACHE, and the six factors with the composite they feed — are EMPTY
for every symbol after a process start. Writing the plain value therefore
stamped NULL over good data on the first tick after each deploy and kept doing
so until the once-daily refresh repopulated the cache, up to 24 hours later.

Measured in production during a deploy: 52-week coverage fell 2,190 -> 100 and
average volume 2,486 -> 103. It also explains why market_cap crawled for a day —
its backfill was filling rows while this tick wiped them.

The fix is COALESCE on exactly those columns, listed in
``signal_publisher.CACHE_DERIVED_COLUMNS``. The snapshot fields are deliberately
NOT protected: they arrive fresh from the vendor each tick, so a NULL there is a
real "no read" and preserving a stale one would be dishonest.

These assertions read the real constant and the real statement rather than the
module's source text. The previous version matched a source LITERAL — it broke
the moment the tuple gained a column, and, worse, a passing source match never
proved the statement executes. That is precisely how the 2026-08-23 outage
shipped green (see tests/test_tick_upsert_executes.py).
"""
from __future__ import annotations

import inspect

from app.workers import signal_publisher
from app.workers.signal_publisher import CACHE_DERIVED_COLUMNS

SRC = inspect.getsource(signal_publisher)


def test_cache_derived_columns_are_coalesced():
    """Every cache-fed column is in the guarded set."""
    for col in (
        "market_cap", "week52_high", "week52_low", "avg_volume_30d",
        "sub_trend", "sub_rs", "sub_fundamentals",
        "sub_smart_money", "sub_macro", "sub_momentum",
        "score", "signal", "reason", "confidence_pct",
    ):
        assert col in CACHE_DERIVED_COLUMNS, (
            f"{col} is fed by an in-memory cache that is empty after every "
            f"restart; without COALESCE the first tick post-deploy erases it"
        )
    assert "func.coalesce(bindparam(col), getattr(Ticker, col))" in SRC


def test_snapshot_fields_are_NOT_coalesced():
    """A vendor NULL means 'no read today' and must not resurrect a stale price."""
    for fresh in (
        "price", "volume", "change_pct_1d",
        "previous_close", "day_open", "day_high", "day_low",
    ):
        assert fresh not in CACHE_DERIVED_COLUMNS, (
            f"{fresh} is written fresh from the vendor every tick; coalescing it "
            f"would preserve a stale value and hide a real gap"
        )


def test_every_guarded_column_exists_and_is_nullable():
    """A typo in the tuple would silently disable the guard for that column.

    `col in CACHE_DERIVED_COLUMNS` is a string comparison, so a misspelling
    doesn't raise — it just falls through to the unguarded branch and the
    column starts getting erased again on cold ticks. Bind the names to the
    model so a typo fails here instead of in production.
    """
    from app.models import Ticker

    for col in CACHE_DERIVED_COLUMNS:
        attr = getattr(Ticker, col, None)
        assert attr is not None, f"{col!r} is not a Ticker column — typo?"
        assert attr.nullable, (
            f"{col} is NOT NULL, so COALESCE cannot be what protects it"
        )


def test_the_tick_loop_uses_no_unguarded_bulk_update():
    """`session.execute(update(Ticker), batch)` is the shape that wiped the data.

    Scoped to the TICK loop deliberately. The same plain form is correct inside
    _backfill_key_statistics, which writes values it has just fetched — a NULL
    there means Finnhub has no coverage for that symbol, not that a cache was
    cold. Only the 60-second tick reads from caches that empty on restart.
    """
    start = SRC.index("cache_derived = CACHE_DERIVED_COLUMNS")
    tick_region = SRC[start - 3000:SRC.index("# --- Replace squeeze setups ---", start)]
    assert "await session.execute(update(Ticker), batch)" not in tick_region, (
        "the unguarded bulk update is back in the tick loop — a cold cache will "
        "erase market_cap and the bar stats on the first tick after every deploy"
    )
