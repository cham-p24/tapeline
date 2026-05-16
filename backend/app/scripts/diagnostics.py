"""One-shot diagnostics — quickly count users, subscriptions, watchlist items,
alert rules, and the most recent activity timestamps in prod.

Run via:
    fly ssh console -a tapeline-backend -C "python -m app.scripts.diagnostics"

Read-only. Safe to run anytime. Outputs a compact summary so the founder
can answer "has anyone signed up yet?" without firing up psql.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select

from app.db import session_scope
from app.models import (
    AlertEvent,
    AlertRule,
    InsiderTransaction,
    NewsItem,
    StripeWebhookEvent,
    Subscription,
    Ticker,
    User,
    WatchlistItem,
)


async def main() -> None:
    now = datetime.now(UTC)
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    async with session_scope() as s:
        # ---- Users
        total_users = (await s.execute(select(func.count(User.id)))).scalar_one()
        # Owner account is seeded, so subtract it to get organic count
        non_owner = (await s.execute(
            select(func.count(User.id)).where(User.email != "owner@tapeline.io")
        )).scalar_one()
        recent_24h = (await s.execute(
            select(func.count(User.id)).where(User.created_at >= last_24h)
        )).scalar_one()
        recent_7d = (await s.execute(
            select(func.count(User.id)).where(User.created_at >= last_7d)
        )).scalar_one()

        # Breakdown by tier
        tier_counts = {}
        for tier in ("free", "pro", "premium"):
            tier_counts[tier] = (await s.execute(
                select(func.count(User.id)).where(User.tier == tier)
            )).scalar_one()

        # Most recent N signups
        recent_signups = (await s.execute(
            select(User.email, User.tier, User.created_at, User.last_seen_at)
            .order_by(desc(User.created_at))
            .limit(10)
        )).all()

        # ---- Subscriptions (paying customers)
        paid_subs = (await s.execute(
            select(func.count(Subscription.id)).where(Subscription.status == "active")
        )).scalar_one()
        total_subs = (await s.execute(select(func.count(Subscription.id)))).scalar_one()

        # ---- Stripe webhooks (StripeWebhookEvent uses `processed_at`, not received_at)
        total_webhooks = (await s.execute(select(func.count(StripeWebhookEvent.id)))).scalar_one()
        recent_webhooks = (await s.execute(
            select(StripeWebhookEvent.event_type, StripeWebhookEvent.processed_at)
            .order_by(desc(StripeWebhookEvent.processed_at))
            .limit(5)
        )).all()

        # ---- Engagement (AlertEvent uses `created_at`, not fired_at)
        total_watchlist = (await s.execute(select(func.count(WatchlistItem.id)))).scalar_one()
        total_rules = (await s.execute(select(func.count(AlertRule.id)))).scalar_one()
        rules_24h = (await s.execute(
            select(func.count(AlertEvent.id)).where(AlertEvent.created_at >= last_24h)
        )).scalar_one()

        # ---- Universe / data freshness — Ticker primary key is `symbol`, not `id`
        total_tickers = (await s.execute(select(func.count(Ticker.symbol)))).scalar_one()
        scored = (await s.execute(
            select(func.count(Ticker.symbol)).where(Ticker.score.isnot(None))
        )).scalar_one()
        sectors = (await s.execute(
            select(func.count(func.distinct(Ticker.sector)))
        )).scalar_one()

        # Sector breakdown
        sector_rows = (await s.execute(
            select(Ticker.sector, func.count(Ticker.symbol))
            .group_by(Ticker.sector)
            .order_by(desc(func.count(Ticker.symbol)))
        )).all()

        # Most recent ticker update
        latest_tick = (await s.execute(
            select(Ticker.updated_at).order_by(desc(Ticker.updated_at)).limit(1)
        )).scalar()
        worker_lag = (now - latest_tick).total_seconds() / 60 if latest_tick else None

        # News feed health
        total_news = (await s.execute(select(func.count(NewsItem.id)))).scalar_one()
        latest_news = (await s.execute(
            select(NewsItem.published_at, NewsItem.publisher)
            .order_by(desc(NewsItem.published_at))
            .limit(3)
        )).all()

        # Insider feed health (NEW DB-backed table)
        total_insider = (await s.execute(select(func.count(InsiderTransaction.id)))).scalar_one()

    # ---- Report
    print("=" * 64)
    print(f"TAPELINE DIAGNOSTICS @ {now.isoformat()}")
    print("=" * 64)

    print(f"\n[USERS]   total={total_users}  organic={non_owner}  last_24h={recent_24h}  last_7d={recent_7d}")
    print(f"          tiers: free={tier_counts['free']}  pro={tier_counts['pro']}  premium={tier_counts['premium']}")

    print("\n[SIGNUPS] last 10:")
    for email, tier, created, last_seen in recent_signups:
        last_seen_str = f"  last_seen={last_seen.isoformat()}" if last_seen else "  never-seen-again"
        print(f"  {created.isoformat()}  [{tier:7s}]  {email}{last_seen_str}")

    print(f"\n[PAID]    subscriptions: active={paid_subs}  total={total_subs}")
    print(f"          stripe_webhook_events_total={total_webhooks}")
    print("          recent webhooks:")
    for evt, ts in recent_webhooks:
        print(f"            {ts.isoformat()}  {evt}")

    print(f"\n[ENGAGE]  watchlist_items={total_watchlist}  alert_rules={total_rules}  alerts_fired_24h={rules_24h}")

    print(f"\n[DATA]    tickers={total_tickers}  scored={scored}  distinct_sectors={sectors}")
    print(f"          worker_lag={worker_lag:.1f} min" if worker_lag is not None else "          worker_lag=NEVER_RAN")
    print(f"          news_items={total_news}  insider_transactions={total_insider}")
    print("          latest news:")
    for pub_at, pub in latest_news:
        print(f"            {pub_at.isoformat()}  {pub}")

    print("\n[SECTORS] (top 10 by ticker count):")
    for sector, n in sector_rows[:10]:
        print(f"  {sector or '<null>':30s} {n:5d}")
    if len(sector_rows) > 10:
        print(f"  ... and {len(sector_rows) - 10} more sectors")
    print("=" * 64)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
