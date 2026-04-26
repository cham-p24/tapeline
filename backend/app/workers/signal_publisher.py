"""
Scoring worker — writes mock (or Polygon) data to the DB each tick and
publishes a change event for the SSE stream.

To swap mock → Polygon: change the import line below.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from datetime import UTC, date, datetime
from sqlalchemy import delete, desc, select

from app.config import get_settings
from app.db import is_sqlite, session_scope
from app.models import (
    CongressTrade,
    DailyScorecardEntry,
    InstitutionalHolding,
    NewsItem,
    RegimeState,
    SqueezeSetup,
    Ticker,
    User,
)
from app.services.mock_feed import (
    fetch_congress_trades,
    fetch_regime,
    fetch_snapshots,
    fetch_squeezes,
    universe,
)
from app.services.news_feed import fetch_latest_news
from app.services.pubsub import broker
from app.services.scorecard_backcheck import backcheck_yesterday

logger = logging.getLogger(__name__)
settings = get_settings()

_last_news_refresh: datetime | None = None
_last_backcheck: datetime | None = None
_last_telegram_digest: datetime | None = None
_last_calendar_seed: datetime | None = None
_last_trial_check: datetime | None = None
_last_holdings_refresh: datetime | None = None


async def seed_universe() -> None:
    """Insert the ticker master list on first boot."""
    async with session_scope() as session:
        result = await session.execute(select(Ticker.symbol).limit(1))
        if result.scalar() is not None:
            return
        for row in universe():
            session.add(Ticker(**row))
        logger.info("seed_universe.inserted count=%d", len(universe()))


async def tick() -> None:
    """One scoring cycle — refresh all four product tabs."""
    started = datetime.now(UTC)

    snapshots = fetch_snapshots()
    squeezes = fetch_squeezes()
    regime = fetch_regime()
    new_trades = fetch_congress_trades()

    async with session_scope() as session:
        # --- Update ticker snapshots (dialect-neutral upsert) ---
        existing = {
            t.symbol: t
            for t in (await session.execute(select(Ticker))).scalars().all()
        }
        for snap in snapshots:
            row = existing.get(snap["symbol"])
            data = {
                "score": snap["score"],
                "signal": snap["signal"],
                "price": snap["price"],
                "change_pct_1d": snap["change_pct_1d"],
                "change_pct_5d": snap["change_pct_5d"],
                "change_pct_1m": snap["change_pct_1m"],
                "volume": snap["volume"],
                "sub_trend": snap["sub_trend"],
                "sub_rs": snap["sub_rs"],
                "sub_fundamentals": snap["sub_fundamentals"],
                "sub_momentum": snap["sub_momentum"],
                "sub_macro": snap["sub_macro"],
                "sub_smart_money": snap["sub_smart_money"],
                "reason": snap["reason"],
            }
            if row is None:
                session.add(Ticker(symbol=snap["symbol"], name=snap["symbol"], **data))
            else:
                for k, v in data.items():
                    setattr(row, k, v)

        # --- Replace squeeze setups ---
        await session.execute(delete(SqueezeSetup))
        for s in squeezes:
            session.add(SqueezeSetup(**s))

        # --- Upsert regime (single row) ---
        await session.execute(delete(RegimeState))
        session.add(RegimeState(id=1, **regime))

        # --- Append new congress trades ---
        for t in new_trades:
            session.add(CongressTrade(**t))

    # Publish to SSE
    await broker.publish("scores_updated", {"ts": started.isoformat(), "count": len(snapshots)})
    await broker.publish("regime_updated", regime)
    await broker.publish("squeeze_updated", {"count": len(squeezes)})

    # Snapshot today's top-10 for the public scorecard (once per day)
    await _ensure_daily_scorecard(started.date())

    # Refresh news feed: on first tick after boot + every ~5 minutes thereafter
    global _last_news_refresh, _last_backcheck  # noqa: PLW0603
    if _last_news_refresh is None or (started - _last_news_refresh).total_seconds() > 300:
        await _refresh_news()
        _last_news_refresh = started

    # Scorecard back-check: run once per day, within ~10 minutes of boot
    if _last_backcheck is None:
        await _run_backcheck()
        _last_backcheck = started

    # Seed mock calendar (IPOs + earnings) on first boot
    global _last_calendar_seed  # noqa: PLW0603
    if _last_calendar_seed is None:
        await _seed_calendar()
        _last_calendar_seed = started

    # Hourly Telegram digest to premium users
    global _last_telegram_digest  # noqa: PLW0603
    if _last_telegram_digest is None or (started - _last_telegram_digest).total_seconds() >= 3600:
        await _run_telegram_digest()
        _last_telegram_digest = started

    # Hourly trial-expiry enforcement: drop unpaid expired-trial users to Free.
    # Without this the trial converts to free Premium forever (zero conversion).
    global _last_trial_check  # noqa: PLW0603
    if _last_trial_check is None or (started - _last_trial_check).total_seconds() >= 3600:
        await _downgrade_expired_trials()
        _last_trial_check = started

    # Daily 13F holdings refresh (Quiver, with mock fallback).
    # 24h cadence is conservative — SEC reporting window is 45 days anyway.
    global _last_holdings_refresh  # noqa: PLW0603
    if _last_holdings_refresh is None or (started - _last_holdings_refresh).total_seconds() >= 86400:
        await _refresh_elite_13f()
        _last_holdings_refresh = started

    elapsed = (datetime.now(UTC) - started).total_seconds()
    logger.info(
        "tick.done snapshots=%d squeezes=%d regime=%s trades_added=%d elapsed=%.2fs",
        len(snapshots), len(squeezes), regime["regime"], len(new_trades), elapsed,
    )


async def _ensure_daily_scorecard(today: date) -> None:
    """Record today's top-10 picks once per day, for the public scorecard page."""
    async with session_scope() as session:
        existing = await session.execute(
            select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == today).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            return
        top = await session.execute(
            select(Ticker).where(Ticker.score.isnot(None)).order_by(desc(Ticker.score)).limit(10)
        )
        for rank, t in enumerate(top.scalars().all(), start=1):
            session.add(DailyScorecardEntry(
                as_of=today,
                symbol=t.symbol,
                rank=rank,
                score_at_flag=t.score or 0,
                price_at_flag=t.price or 0,
            ))
        logger.info("scorecard.snapshot saved for %s", today)


async def _refresh_news() -> None:
    """Pull latest news into local cache. In dev this is synthetic."""
    try:
        items = await fetch_latest_news(limit=40)
    except Exception:
        logger.exception("news.refresh_failed")
        return
    async with session_scope() as session:
        for it in items:
            exists = await session.execute(select(NewsItem).where(NewsItem.id == it["id"]))
            if exists.scalar_one_or_none() is not None:
                continue
            session.add(NewsItem(**it))
    logger.info("news.refreshed count=%d", len(items))


async def _run_backcheck() -> None:
    """Populate next-day performance on yesterday's scorecard entries."""
    async with session_scope() as session:
        try:
            await backcheck_yesterday(session)
        except Exception:
            logger.exception("scorecard.backcheck_failed")


async def _run_telegram_digest() -> None:
    """Hourly Telegram watchlist digest for premium users."""
    from app.services.telegram import run_hourly_digest
    async with session_scope() as session:
        try:
            await run_hourly_digest(session)
        except Exception:
            logger.exception("telegram.hourly_digest_failed")


async def _downgrade_expired_trials() -> None:
    """
    End-of-trial enforcement.

    Drops `tier` to 'free' for users whose 14-day trial expired AND who
    never added a Stripe customer (i.e. never started paying). Without
    this the trial silently converts to free-Premium-forever, killing
    conversion entirely.

    Safe to run hourly — it's idempotent (a free user with no trial_ends_at
    isn't matched by any of the conditions).
    """
    from sqlalchemy import update
    from app.models import User as UserModel

    now = datetime.now(UTC)
    async with session_scope() as session:
        # Find candidates first so we can log them
        candidates = (await session.execute(
            select(UserModel.id, UserModel.email, UserModel.tier)
            .where(
                UserModel.trial_ends_at.isnot(None),
                UserModel.trial_ends_at < now,
                UserModel.tier.in_(["pro", "premium"]),
                UserModel.stripe_customer_id.is_(None),
                UserModel.is_lifetime.is_(False),
            )
        )).all()

        if not candidates:
            return

        await session.execute(
            update(UserModel)
            .where(
                UserModel.trial_ends_at.isnot(None),
                UserModel.trial_ends_at < now,
                UserModel.tier.in_(["pro", "premium"]),
                UserModel.stripe_customer_id.is_(None),
                UserModel.is_lifetime.is_(False),
            )
            .values(tier="free")
        )

    logger.info("trial.downgraded count=%d", len(candidates))
    for user_id, email, prev_tier in candidates[:5]:
        logger.info("  trial.downgrade user=%s email=%s prev_tier=%s", user_id, email, prev_tier)


async def _refresh_elite_13f() -> None:
    """
    Daily 24h refresh of elite-fund 13F holdings.

    Tries Quiver first; if QUIVER_API_KEY is unset OR every fund fetch fails,
    falls back to deterministic mock data so the /api/holdings endpoint
    never returns empty in dev.
    """
    from app.models import InstitutionalHolding
    from app.services.quiver_feed import fetch_elite_13f_holdings, mock_elite_13f_holdings

    rows = await fetch_elite_13f_holdings()
    source = "quiver"
    if rows is None:
        rows = mock_elite_13f_holdings()
        source = "mock"

    async with session_scope() as session:
        await session.execute(delete(InstitutionalHolding))
        for r in rows:
            session.add(InstitutionalHolding(**r))

    logger.info("holdings.13f_refreshed source=%s count=%d", source, len(rows))


async def _seed_calendar() -> None:
    """Seed mock IPO + earnings events on first boot (idempotent)."""
    from app.models import EarningsEvent, IPOEvent
    from app.services.calendar_feed import mock_upcoming_earnings, mock_upcoming_ipos

    async with session_scope() as session:
        ipos_r = await session.execute(select(IPOEvent).limit(1))
        if ipos_r.scalar_one_or_none() is None:
            for row in mock_upcoming_ipos():
                session.add(IPOEvent(**row))
            logger.info("calendar.ipos_seeded")

        earnings_r = await session.execute(select(EarningsEvent).limit(1))
        if earnings_r.scalar_one_or_none() is None:
            for row in mock_upcoming_earnings():
                session.add(EarningsEvent(**row))
            logger.info("calendar.earnings_seeded")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("signal_publisher.start interval=%ds", settings.score_refresh_seconds)

    # Seed universe on first boot (idempotent)
    await seed_universe()

    while True:
        try:
            await tick()
        except Exception:
            logger.exception("tick.failure")
        await asyncio.sleep(settings.score_refresh_seconds)


if __name__ == "__main__":
    asyncio.run(main())
