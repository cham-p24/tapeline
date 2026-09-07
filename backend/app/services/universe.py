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
# ACTIVE_UNIVERSE_SIZE (read at module import).
#
# 2026-09-07: raised 2,500 -> 12,000, which is above the whole tickers table,
# so in practice NOTHING scored is cut. It stays an env var as an emergency
# brake, not as a product decision.
#
# The old comment here read: "Finnhub fundamentals refresh on the free tier
# (60 calls/min) takes ~42 minutes for 2,500 names. Bump to 5,000 needs paid
# Finnhub or a cached-fundamentals approach." That was true about FUNDAMENTALS
# and false about this constant, and the confusion cost us most of the product.
# This list feeds exactly ONE consumer — polygon_feed.fetch_snapshots, which
# batches 250 symbols per `/v3/snapshot` request. The fundamentals / insider /
# key-stats passes run DAILY on their own 20-symbol batches and never read this
# list at all (grep: active_universe has one non-test caller). So the cost of
# this number is (size / 250) HTTP requests per 60s tick: 2,500 was 11 requests
# taking ~3s, and the whole scored universe is ~30 requests taking ~8s.
#
# What the 2,500 cutoff actually did, measured in production on 2026-09-07:
# the selection below ranks by `coalesce(volume * price, -1)`, so a row with no
# volume reading sorts LAST. Below the cutoff it got no snapshot; with no
# snapshot it never got a volume reading; so it sorted last forever. 3,633
# scored rows were stuck in that loop, and because the honesty gate in
# ticker_freshness requires `change_pct_1d IS NOT NULL` (a snapshot field),
# every one of them was hidden from the scanner. Among them: TSM, Toyota,
# Sony, Mitsubishi UFJ, HubSpot, Qiagen — 1,389 companies above $2B. Searching
# "TSM" on Tapeline returned nothing.
#
# It was never a data problem. Asked directly, the provider returns all of
# them, complete, in one batched call (TSM: $427.88, -0.24%, 12.3M shares).
# We had simply stopped asking.
#
# If you lower this again, read test_universe_covers_what_we_score.py first —
# it fails on exactly the regression described above.
import os as _os

ACTIVE_UNIVERSE_SIZE = int(_os.environ.get("ACTIVE_UNIVERSE_SIZE", "12000"))

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

# Rotating offset into the never-scored backlog. See the bootstrap block in
# refresh_active_universe: without it the intake window is pinned to the front
# of the alphabet and unscoreable symbols block everything behind them.
_bootstrap_cursor: int = 0


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

            # Crypto is EXCLUDED. This list feeds the equity snapshot pass,
            # and the vendor answers NOT_ENTITLED for a pair on that endpoint.
            #
            # It is not merely wasted requests. A crypto row that reaches the
            # equity tick gets upserted from a snapshot that carries no data,
            # which NULLs the price, volume and daily move the crypto feed had
            # just written. Observed within minutes of the first crypto deploy:
            # 66 of 67 pairs lost price/volume/change_pct_1d, and because
            # `live_clauses` requires change_pct_1d they became invisible on
            # every surface — the second time in one day that correctly-scored
            # coins were in the table and unfindable.
            #
            # The predicate is `score IS NOT NULL`, so this only started once
            # crypto rows HAD scores. Nothing about crypto changed; giving them
            # a score is what let them into a pass that was never for them.
            sort_key = func.coalesce(Ticker.volume * Ticker.price, -1)
            r = await session.execute(
                select(Ticker.symbol, Ticker.name, Ticker.sector)
                .where(Ticker.score.is_not(None))
                .where(func.coalesce(Ticker.asset_class, "") != "crypto")
                .order_by(desc(sort_key))
                .limit(size)
            )
            rows: list[tuple[str, str, str]] = [
                (row[0], row[1] or row[0], row[2] or "Unknown")
                for row in r.all()
                if row[0]
            ]

            # A binding cap is the failure mode that hid TSM, Toyota and Sony
            # for months, and it hid them SILENTLY — the universe simply
            # stopped at 2,500 and nothing said so. If the limit ever bites
            # again, say it loudly and name what fell off the end, because the
            # rows it drops are the ones with no volume reading and they can
            # never climb back into range on their own.
            if len(rows) >= size:
                total_scored = (
                    await session.execute(
                        select(func.count())
                        .select_from(Ticker)
                        .where(Ticker.score.is_not(None))
                    )
                ).scalar_one()
                if total_scored > size:
                    logger.warning(
                        "universe.capped size=%d scored=%d hidden=%d — %d scored "
                        "tickers get no snapshot, so no change_pct_1d, so the "
                        "scanner cannot show them. Raise ACTIVE_UNIVERSE_SIZE.",
                        size, total_scored, total_scored - size, total_scored - size,
                    )

            # Bootstrap slots for never-scored tickers. See BOOTSTRAP_SLOTS —
            # without this the `score IS NOT NULL` predicate above makes the
            # universe unable to grow, because a ticker needs a snapshot to
            # earn a score and needs a score to be snapshotted.
            #
            # Ordered by symbol so the intake is deterministic, and WINDOWED by
            # a rotating cursor so it actually drains.
            #
            # The original comment here claimed "once a symbol is scored it
            # drops out of this query, so the next refresh picks up where this
            # one left off". That only holds for symbols that CAN be scored. A
            # symbol the provider has no data for never scores, never drops
            # out, and — being alphabetically early — occupies the same slot on
            # every refresh, forever. Verified in production on 2026-09-07:
            # 4,414 unscored rows, and the worker log showed the same window
            # (ACQQ, ACRT, ACSP, ADAMK, ADBT, ADIGW, ...) going out tick after
            # tick. The intake was pinned to the front of the alphabet and the
            # other ~4,150 had never once been looked at.
            #
            # The cursor advances a window per refresh and wraps, so every
            # unscored ticker gets its turn regardless of whether the ones
            # ahead of it are scoreable. At 250 slots on the hourly refresh the
            # whole backlog is offered inside a day.
            if BOOTSTRAP_SLOTS > 0:
                global _bootstrap_cursor
                seen = {row[0] for row in rows}
                unscored_total = (
                    await session.execute(
                        select(func.count())
                        .select_from(Ticker)
                        .where(Ticker.score.is_(None))
                    )
                ).scalar_one()
                # Wrap before use so the offset can never run past the end and
                # return an empty window (which would stall intake silently).
                if unscored_total:
                    _bootstrap_cursor %= unscored_total
                else:
                    _bootstrap_cursor = 0
                b = await session.execute(
                    select(Ticker.symbol, Ticker.name, Ticker.sector)
                    .where(Ticker.score.is_(None))
                    # Same exclusion as above: a never-scored crypto pair must
                    # not be handed to the equity snapshot either.
                    .where(func.coalesce(Ticker.asset_class, "") != "crypto")
                    .order_by(Ticker.symbol.asc())
                    .offset(_bootstrap_cursor)
                    .limit(BOOTSTRAP_SLOTS)
                )
                _bootstrap_cursor += BOOTSTRAP_SLOTS
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
