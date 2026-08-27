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

# Extra slots handed to NEVER-SCORED tickers on every refresh, on top of
# ACTIVE_UNIVERSE_SIZE.
#
# Without these the universe cannot grow. The main selection below requires
# `score IS NOT NULL`, and a freshly discovered ticker has no score — so it
# is excluded from the active universe, therefore never included in
# `fetch_snapshots`, therefore never gets a price or volume, therefore never
# gets a score. Excluded forever, having never once been looked at.
#
# That is the SAME chicken-and-egg the comment inside refresh_active_universe
# describes fixing on 2026-05-24 for `volume IS NOT NULL AND price IS NOT
# NULL`. Swapping the predicate to `score IS NOT NULL` moved the trap up one
# level rather than removing it. Discovery (#658) made it visible: it added
# thousands of real tickers and not one of them could ever be scored, so the
# published universe stayed frozen at ~2,460 rows — 750 A-tickers, 626 B, 671
# C, and a single E-ticker.
#
# These slots are ADDITIVE and only widen the bulk `/v3/snapshot` call, which
# batches 250 symbols per request — so this costs one extra request per tick.
# The expensive per-symbol passes (aggregates, fundamentals, insider, key
# stats) cap themselves at ACTIVE_UNIVERSE_SIZE by dollar volume
# independently, and are untouched by this.
#
# The point is to let liquidity be MEASURED rather than assumed. A ticker
# that gets its snapshot and turns out to be illiquid then loses on dollar
# volume like everything else — which is a real answer. Never looking is not.
BOOTSTRAP_SLOTS = int(_os.environ.get("UNIVERSE_BOOTSTRAP_SLOTS", "250"))

# Module-level cache of (symbol, name, sector) tuples.
_active_universe: list[tuple[str, str, str]] = []
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
            # 2026-05-24: was `WHERE volume IS NOT NULL AND price IS NOT NULL`.
            # That created a chicken-and-egg trap: any newly-inserted sheet
            # ticker without a price snapshot yet was excluded from the
            # universe → never got a price snapshot → stayed excluded forever.
            # Founder hit this when the sheet grew to 1969 tickers but the
            # price feed was only seeing the older ~800.
            #
            # Fix: include EVERY ticker that has a score (the sheet/scorer
            # decided it's worth tracking) regardless of price-coverage
            # status. Sort by (volume * price) DESC NULLS LAST so liquid
            # mega-caps still come first in the snapshot batches, and the
            # newly-discovered NULL-volume tickers ride along at the tail —
            # they pick up their first snapshot in the next tick and on
            # subsequent calls sort into their natural position.
            #
            # `coalesce(volume * price, -1)` is the cross-dialect way to
            # express NULLS LAST in DESC order: NULL → -1 → sorts last.
            from sqlalchemy import func

            sort_key = func.coalesce(Ticker.volume * Ticker.price, -1)
            r = await session.execute(
                select(Ticker.symbol, Ticker.name, Ticker.sector)
                .where(Ticker.score.is_not(None))
                .order_by(desc(sort_key))
                .limit(size)
            )
            rows: list[tuple[str, str, str]] = [
                (row[0], row[1] or row[0], row[2] or "Unknown")
                for row in r.all()
                if row[0]
            ]

            # Bootstrap slots for never-scored tickers. See BOOTSTRAP_SLOTS —
            # without this the `score IS NOT NULL` predicate above makes the
            # universe unable to grow, because a ticker needs a snapshot to
            # earn a score and needs a score to be snapshotted.
            #
            # Ordered by symbol so the intake is deterministic and every
            # discovered ticker gets its turn: once a symbol is scored it
            # drops out of this query, so the next refresh picks up where this
            # one left off rather than re-offering the same names.
            if BOOTSTRAP_SLOTS > 0:
                seen = {row[0] for row in rows}
                b = await session.execute(
                    select(Ticker.symbol, Ticker.name, Ticker.sector)
                    .where(Ticker.score.is_(None))
                    .order_by(Ticker.symbol.asc())
                    .limit(BOOTSTRAP_SLOTS)
                )
                added = [
                    (row[0], row[1] or row[0], row[2] or "Unknown")
                    for row in b.all()
                    if row[0] and row[0] not in seen
                ]
                if added:
                    logger.info(
                        "universe.bootstrap admitting %d never-scored tickers "
                        "(first=%s last=%s)",
                        len(added), added[0][0], added[-1][0],
                    )
                rows.extend(added)
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


def active_universe() -> list[tuple[str, str, str]]:
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
