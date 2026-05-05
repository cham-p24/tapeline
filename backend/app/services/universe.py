"""
Active scoring universe — top N tickers by daily dollar-volume.

The DB tracks 5,757 tickers from Massive's reference API. Most are sub-$1
micro-caps with bid-ask spreads that make any "score" non-actionable. We
score the top N by `volume * price` (rough $-volume proxy) — the cutoff
naturally lands around the bottom of the S&P MidCap 400, which is where
liquidity drops off.

The list is cached in-process for ~1 hour because a stock's daily $-volume
doesn't churn meaningfully on a faster cadence and we don't want the
worker doing a DB roundtrip on every tick. Worker calls
`refresh_active_universe()` once on boot + hourly thereafter via the
existing universe-refresh schedule.

Falls back to `mock_feed.TICKER_UNIVERSE` when the DB query returns empty
(first boot before the universe-discovery cron has run, schema-empty
test environments, etc.) so dev / staging never hard-fail on this path.
"""
from __future__ import annotations

import logging
import time
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Default size of the active scoring universe. Tunable via the env var
# ACTIVE_UNIVERSE_SIZE (read at module import). 2,500 covers everything
# liquid down to mid-/small-cap territory; below that the bid-ask spreads
# make any score non-actionable.
#
# Finnhub fundamentals refresh on the free tier (60 calls/min) takes
# ~42 minutes for 2,500 names — well under the daily refresh cycle.
# Bump to 5,000 needs paid Finnhub or a cached-fundamentals approach.
import os as _os
ACTIVE_UNIVERSE_SIZE = int(_os.environ.get("ACTIVE_UNIVERSE_SIZE", "2500"))

# Module-level cache of (symbol, name, sector) tuples.
_active_universe: List[Tuple[str, str, str]] = []
_refreshed_at: float = 0.0


async def refresh_active_universe(target_size: int | None = None) -> int:
    """Refresh the cached active universe from the DB.

    Returns the number of tickers in the new cache. Worker calls this on
    boot + hourly. Falls back to the hardcoded mock list if the DB query
    returns no rows (which only happens before the universe-discovery
    cron has run).
    """
    global _active_universe, _refreshed_at
    size = target_size or ACTIVE_UNIVERSE_SIZE

    try:
        from sqlalchemy import desc, select

        from app.db import session_scope
        from app.models import Ticker

        async with session_scope() as session:
            # ORDER BY volume * price DESC NULLS LAST — gives us the most
            # liquid actively-tradeable names first. NULLs (newly-discovered
            # tickers without a snapshot yet) sort to the bottom.
            # Without NULLS LAST, Postgres puts NULL first in DESC ordering,
            # which would crowd out real high-$-volume mega-caps with
            # unscored newly-discovered tickers.
            #
            # Filter `volume IS NOT NULL AND price IS NOT NULL` is the
            # belt-and-suspenders version that works on every dialect (SQLite
            # doesn't natively support NULLS LAST in older versions).
            r = await session.execute(
                select(Ticker.symbol, Ticker.name, Ticker.sector)
                .where(Ticker.volume.is_not(None), Ticker.price.is_not(None))
                .order_by(desc(Ticker.volume * Ticker.price))
                .limit(size)
            )
            rows: list[Tuple[str, str, str]] = [
                (row[0], row[1] or row[0], row[2] or "Unknown")
                for row in r.all()
                if row[0]
            ]
    except Exception:
        logger.exception("universe.refresh_failed — keeping previous cache")
        return len(_active_universe)

    if rows:
        _active_universe = rows
        _refreshed_at = time.time()
        logger.info("universe.refreshed count=%d", len(rows))
    else:
        logger.warning("universe.refresh returned 0 rows — keeping previous cache or fallback")
    return len(_active_universe)


def active_universe() -> List[Tuple[str, str, str]]:
    """Sync getter. Returns the cached active universe, or the hardcoded
    fallback if the cache is empty (first call before any refresh).
    """
    if _active_universe:
        return _active_universe
    # Fallback path — same shape as the cache.
    from app.services.mock_feed import TICKER_UNIVERSE
    return list(TICKER_UNIVERSE)


def active_universe_size() -> int:
    """Diagnostic — current size of the cached universe (or fallback)."""
    return len(active_universe())
