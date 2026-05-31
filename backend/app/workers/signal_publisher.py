"""
Scoring worker — writes mock (or Polygon) data to the DB each tick and
publishes a change event for the SSE stream.

To swap mock → Polygon: change the import line below.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime

from sqlalchemy import delete, desc, select

from app.config import get_settings
from app.db import session_scope
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

# --- DATA-FEED IMPORTS ---
# Hybrid swap (2026-05-02): real prices + live macro from Massive (api.massive.com).
# Squeeze detection stays mock for now — running per-ticker /v2/aggs across the full
# universe each tick burns API calls; revisit once a daily back-fill job is built.
# Congress trades stay mock — Polygon/Massive don't offer that data; Quiver
# Commercial tier needed for real (deferred per CLAUDE.md known-issues).
from app.services.mock_feed import (
    fetch_congress_trades,
    fetch_squeezes,
    universe,
)
from app.services.news_feed import fetch_latest_news
from app.services.polygon_feed import fetch_regime, fetch_snapshots
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
_last_drip_check: datetime | None = None
_last_universe_refresh: datetime | None = None
_last_sheet_refresh: datetime | None = None
_last_active_universe_refresh: datetime | None = None
_last_eod_digest_date: str | None = None  # "YYYY-MM-DD" of last EOD digest run (UTC)
_last_weekly_newsletter_token: str | None = None  # "weekly_YYYYWww" of last newsletter run
_last_fundamentals_refresh: datetime | None = None
_last_insider_refresh: datetime | None = None
_last_sector_backfill: datetime | None = None
_last_watchlisted_news_refresh: datetime | None = None
_last_aggregates_refresh: datetime | None = None


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

    # polygon_feed.fetch_snapshots / fetch_regime are async (HTTP calls);
    # mock_feed.fetch_squeezes / fetch_congress_trades are sync.
    # Await the async ones so we get actual data instead of a coroutine object.
    import inspect
    snapshots = await fetch_snapshots() if inspect.iscoroutinefunction(fetch_snapshots) else fetch_snapshots()
    squeezes = await fetch_squeezes() if inspect.iscoroutinefunction(fetch_squeezes) else fetch_squeezes()
    regime = await fetch_regime() if inspect.iscoroutinefunction(fetch_regime) else fetch_regime()
    new_trades = await fetch_congress_trades() if inspect.iscoroutinefunction(fetch_congress_trades) else fetch_congress_trades()

    # Live breadth: % of universe with sub_trend > 50 (proxy for "above
    # the 200DMA" since the trend factor incorporates that). Replaces the
    # last hardcoded macro indicator. Computed from the snapshots we just
    # fetched — no extra DB round-trip.
    trends = [s.get("sub_trend") for s in snapshots if s.get("sub_trend") is not None]
    if trends:
        above_mid = sum(1 for t in trends if t > 50)
        regime["breadth_pct"] = round(100 * above_mid / len(trends), 1)

    # Live sector_leaders: top 3 sectors ranked by average composite score.
    # Replaces the second hardcoded regime placeholder. Joins each snapshot to
    # its Ticker.sector by walking the universe() helper rather than hitting DB.
    try:
        sector_map = {row["symbol"]: row.get("sector") for row in universe()}
        sector_scores: dict[str, list[float]] = {}
        for s in snapshots:
            sec = sector_map.get(s["symbol"])
            score = s.get("score")
            if sec and score is not None and sec != "Unknown":
                sector_scores.setdefault(sec, []).append(score)
        if sector_scores:
            ranked = sorted(
                ((sec, sum(vals) / len(vals)) for sec, vals in sector_scores.items() if vals),
                key=lambda kv: kv[1],
                reverse=True,
            )
            regime["sector_leaders"] = ", ".join(sec for sec, _ in ranked[:3])
    except Exception:
        # Don't let regime breakage propagate — keep whatever fetch_regime returned
        logger.exception("regime.sector_leaders_compute_failed")

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
                "confidence_pct": snap.get("confidence_pct"),
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

    # Evaluate alert rules against the freshly-updated state.
    # Each evaluator is debounced internally (15min), safe to run every tick.
    async with session_scope() as alert_session:
        try:
            from app.services.alerts import evaluate_all_rules
            fired = await evaluate_all_rules(alert_session)
            if fired:
                logger.info("alerts.fired count=%d", fired)
        except Exception:
            logger.exception("alerts.eval_failed")

    # Snapshot today's top-10 for the public scorecard (once per day)
    await _ensure_daily_scorecard(started.date())

    # Refresh news feed: on first tick after boot + every ~5 minutes thereafter
    global _last_news_refresh, _last_backcheck
    if _last_news_refresh is None or (started - _last_news_refresh).total_seconds() > 300:
        await _refresh_news()
        # SEC EDGAR 8-K direct — runs alongside the wire-news refresh so material
        # filings hit the news bar ~5-30 min earlier than they would via Benzinga/
        # Massive. Free + zero-API-key. Idempotent (uses EDGAR accession number
        # as the NewsItem.id PK) so re-runs don't duplicate rows.
        try:
            from app.services.edgar_feed import refresh_8k_into_news_items
            counts = await refresh_8k_into_news_items()
            if counts.get("inserted"):
                logger.info(
                    "edgar.8k_added inserted=%d fetched=%d",
                    counts["inserted"], counts["fetched"],
                )
        except Exception:
            logger.exception("edgar.8k_tick_failed")
        _last_news_refresh = started

    # Scorecard back-check: run once per day, within ~10 minutes of boot
    if _last_backcheck is None:
        await _run_backcheck()
        _last_backcheck = started

    # Calendar refresh (IPOs + earnings) — daily cadence. Finnhub-aware
    # via calendar_feed.upcoming_*; mock fallback when no FINNHUB_API_KEY.
    global _last_calendar_seed
    if _last_calendar_seed is None or (started - _last_calendar_seed).total_seconds() >= 86400:
        await _seed_calendar()
        _last_calendar_seed = started

    # Hourly Telegram digest to premium users
    global _last_telegram_digest
    if _last_telegram_digest is None or (started - _last_telegram_digest).total_seconds() >= 3600:
        await _run_telegram_digest()
        _last_telegram_digest = started

    # Hourly trial-expiry enforcement: drop unpaid expired-trial users to Free.
    # Without this the trial converts to free Premium forever (zero conversion).
    global _last_trial_check
    if _last_trial_check is None or (started - _last_trial_check).total_seconds() >= 3600:
        await _downgrade_expired_trials()
        _last_trial_check = started

    # Hourly per-watchlisted-ticker news refresh (Premium tier feature).
    # Broad sweep + Massive cover the loud names; this fan-out covers the
    # tickers users specifically care about — small-caps, UK ADRs (BUR
    # etc.), niche names where the broad sweep doesn't surface anything.
    # Quota math: 1000 unique tickers × 1/hour = 24k Benzinga calls/day,
    # well under the 4000/min limit. Finnhub (60/min) handled via fallback.
    global _last_watchlisted_news_refresh
    if _last_watchlisted_news_refresh is None or (started - _last_watchlisted_news_refresh).total_seconds() >= 3600:
        await _refresh_watchlisted_news()
        _last_watchlisted_news_refresh = started

    # Daily 13F holdings refresh (Quiver, with mock fallback).
    # 24h cadence is conservative — SEC reporting window is 45 days anyway.
    global _last_holdings_refresh
    if _last_holdings_refresh is None or (started - _last_holdings_refresh).total_seconds() >= 86400:
        await _refresh_elite_13f()
        _last_holdings_refresh = started

    # Daily trial-drip emails (day 3 / 7 / 13) + 14-day re-engagement for
    # dormant non-trial users. Worker-restart-safe — User.drip_state tracks
    # per-user per-stage delivery so no email fires twice.
    global _last_drip_check
    if _last_drip_check is None or (started - _last_drip_check).total_seconds() >= 86400:
        try:
            from app.services.email import run_daily_drip, run_re_engagement_drip
            async with session_scope() as drip_session:
                counts = await run_daily_drip(drip_session)
                re_counts = await run_re_engagement_drip(drip_session)
            if any(counts.values()):
                logger.info("drip.sent day3=%d day7=%d day13=%d", counts["day3"], counts["day7"], counts["day13"])
            if re_counts["re14"]:
                logger.info("drip.re_engagement_sent re14=%d", re_counts["re14"])
        except Exception:
            logger.exception("drip.run_failed")
        _last_drip_check = started

    # Signal-system Google Sheet refresh — pulls ALL SIGNALS + the Phase 2
    # intelligence tabs (SPIKE / MARKET / SMART MONEY / ETF) and upserts to
    # the matching Tapeline tables. Each tab is gated by its own env var so
    # the user can light them up independently. Same 5-min throttle for all.
    # Bypasses cleanly when no URLs are set (worker continues with mock_feed).
    global _last_sheet_refresh
    if (
        settings.signal_sheet_csv_url
        or settings.spike_intelligence_csv_url
        or settings.market_intelligence_csv_url
        or settings.smart_money_congress_csv_url
        or settings.etf_benchmarks_csv_url
    ) and (
        _last_sheet_refresh is None
        or (started - _last_sheet_refresh).total_seconds() >= settings.signal_sheet_refresh_seconds
    ):
        try:
            from app.services.sheet_feed import (
                refresh_etfs_from_workbook,
                refresh_from_workbook,
                refresh_market_from_workbook,
                refresh_smart_money_from_workbook,
                refresh_spikes_from_workbook,
            )
            async with session_scope() as sheet_session:
                if settings.signal_sheet_csv_url:
                    counts = await refresh_from_workbook(sheet_session)
                    if counts.get("total"):
                        logger.info(
                            "sheet_feed.tick rows=%d ins=%d upd=%d",
                            counts["total"], counts["inserted"], counts["updated"],
                        )
                if settings.spike_intelligence_csv_url:
                    spike_counts = await refresh_spikes_from_workbook(sheet_session)
                    if spike_counts.get("total"):
                        logger.info(
                            "sheet_feed.spikes_tick rows=%d ins=%d upd=%d",
                            spike_counts["total"], spike_counts["inserted"], spike_counts["updated"],
                        )
                if settings.etf_benchmarks_csv_url:
                    etf_counts = await refresh_etfs_from_workbook(sheet_session)
                    if etf_counts.get("total"):
                        logger.info(
                            "sheet_feed.etfs_tick rows=%d ins=%d upd=%d",
                            etf_counts["total"], etf_counts["inserted"], etf_counts["updated"],
                        )
                if settings.market_intelligence_csv_url:
                    market_counts = await refresh_market_from_workbook(sheet_session)
                    if market_counts.get("total"):
                        logger.info("sheet_feed.market_tick total=%d", market_counts["total"])
                if settings.smart_money_congress_csv_url:
                    smart_counts = await refresh_smart_money_from_workbook(sheet_session)
                    if smart_counts.get("total"):
                        logger.info(
                            "sheet_feed.smart_money_tick rows=%d (skipped=%d)",
                            smart_counts["total"], smart_counts.get("skipped", 0),
                        )
        except Exception:
            logger.exception("sheet_feed.tick_failed")
        _last_sheet_refresh = started

    # Weekly universe refresh from Massive's reference API.
    # Only fires when a vendor key is set — discovers new IPOs and ETF
    # listings without needing manual ticker-list maintenance.
    global _last_universe_refresh
    if (settings.massive_api_key or settings.polygon_api_key) and (
        _last_universe_refresh is None
        or (started - _last_universe_refresh).total_seconds() >= 604800
    ):
        await _refresh_universe()
        _last_universe_refresh = started

    # Hourly active-scoring-universe refresh (top-N by daily $-volume from
    # the DB-tracked 5,757). Cheap query — keeps the cache that
    # polygon_feed.fetch_snapshots reads each tick within an hour of fresh.
    global _last_active_universe_refresh
    if _last_active_universe_refresh is None or (
        started - _last_active_universe_refresh
    ).total_seconds() >= 3600:
        from app.services.universe import refresh_active_universe
        try:
            n = await refresh_active_universe()
            logger.info("active_universe.refreshed count=%d", n)
        except Exception:
            logger.exception("active_universe.refresh_failed")
        _last_active_universe_refresh = started

    # Daily Finnhub refreshes (fundamentals, insider Form 4, sector backfill).
    # All three hit the same Finnhub free-tier 60-calls/min budget — so we
    # serialize them inside a single background task instead of spawning
    # three concurrent tasks that combined would 3x the budget and trigger
    # 429s. Latches are set BEFORE the task runs so subsequent ticks don't
    # re-fire while the in-flight run is still working.
    global _last_fundamentals_refresh, _last_insider_refresh, _last_sector_backfill
    needs_finnhub = settings.finnhub_api_key and (
        _last_fundamentals_refresh is None
        or (started - _last_fundamentals_refresh).total_seconds() >= 86400
        or _last_insider_refresh is None
        or (started - _last_insider_refresh).total_seconds() >= 86400
        or _last_sector_backfill is None
        or (started - _last_sector_backfill).total_seconds() >= 86400
    )
    if needs_finnhub:
        _last_fundamentals_refresh = started
        _last_insider_refresh = started
        _last_sector_backfill = started

        async def _serial_finnhub_refreshes() -> None:
            """Run the three Finnhub-using refreshes back-to-back.
            Combined wall time at 1.1s/req × 500 + 500 + ~rare-sector backfill
            is ~18-20 min — long, but always under the per-minute API limit."""
            try:
                await _refresh_fundamentals_cache()
            except Exception:
                logger.exception("fundamentals.refresh_failed")
            try:
                await _refresh_insider_cache()
            except Exception:
                logger.exception("insider.refresh_failed")
            try:
                await _backfill_sectors()
            except Exception:
                logger.exception("sectors.backfill_failed")

        asyncio.create_task(_serial_finnhub_refreshes())

    # Daily Massive aggregates refresh — pre-fetches 250 days of OHLC bars per
    # ticker, computes trend/RS/momentum, populates the in-memory caches that
    # polygon_feed.fetch_snapshots reads per tick.
    global _last_aggregates_refresh
    if (settings.massive_api_key or settings.polygon_api_key) and (
        _last_aggregates_refresh is None
        or (started - _last_aggregates_refresh).total_seconds() >= 86400
    ):
        _last_aggregates_refresh = started
        asyncio.create_task(_refresh_aggregates_cache())

    # End-of-day watchlist email digest. Fires once per UTC day shortly after
    # 21:00 UTC (~5pm ET, after US market close). Tracks last-sent date in
    # process memory to avoid double-fires within the same day. Worker restart
    # mid-day will re-fire — acceptable since users would rather get two than zero.
    global _last_eod_digest_date
    today_str = started.strftime("%Y-%m-%d")
    if started.hour >= 21 and _last_eod_digest_date != today_str:
        try:
            from app.services.email import run_eod_watchlist_digest
            async with session_scope() as eod_session:
                count = await run_eod_watchlist_digest(eod_session)
            if count:
                logger.info("eod_digest.sent count=%d", count)
        except Exception:
            logger.exception("eod_digest.run_failed")
        _last_eod_digest_date = today_str

    # Weekly market digest (newsletter). Fires Monday at/after 13:00 UTC
    # (~9am ET pre-open / ~11pm Sydney post-Monday-close). Per-week dedupe
    # is also enforced inside run_weekly_newsletter via User.drip_state, so
    # the process-level token here is a cheap short-circuit — DB stays
    # the source of truth for "did THIS user get THIS week's edition".
    global _last_weekly_newsletter_token
    iso_year, iso_week, iso_dow = started.isocalendar()
    weekly_token = f"weekly_{iso_year}W{iso_week:02d}"
    if (
        iso_dow == 1                                    # Monday
        and started.hour >= 13                          # 13:00 UTC onward
        and _last_weekly_newsletter_token != weekly_token
    ):
        try:
            from app.services.email import run_weekly_newsletter
            async with session_scope() as nl_session:
                count = await run_weekly_newsletter(nl_session, now=started)
            logger.info("weekly_newsletter.sent count=%d token=%s", count, weekly_token)
        except Exception:
            logger.exception("weekly_newsletter.run_failed")
        _last_weekly_newsletter_token = weekly_token

    elapsed = (datetime.now(UTC) - started).total_seconds()
    logger.info(
        "tick.done snapshots=%d squeezes=%d regime=%s trades_added=%d elapsed=%.2fs",
        len(snapshots), len(squeezes), regime["regime"], len(new_trades), elapsed,
    )


_MAX_PER_SECTOR = 3
"""Concentration cap on the daily top-10. Without it the freeze frequently
holds 5+ semiconductors or 5+ regional banks because the sheet ranks them
all high in sympathy moves. They co-move next day, so a single hostile
session for the cluster blows up the whole top-10's back-check. Capping
at 3 per sector forces some diversification on the public record without
hand-curating picks. Set to 0 to disable."""

_MIN_MACRO_FOR_INCLUSION = 30.0
"""Picks whose Tapeline sub_macro falls in the FALLING band (mapped to 25
in services/score) are skipped from the top-10 freeze. We still keep the
Ticker row in the DB and surface it on /scanner — this filter only
governs which picks make the public scorecard, where a hostile-macro
pick almost certainly fights the next-day tape regardless of how strong
its other factors look."""


async def _ensure_daily_scorecard(today: date) -> None:
    """Record today's top-10 picks once per day, for the public scorecard page.

    Only logs on US trading days. The back-check job assumes every row maps
    to a real "next trading day" close — writing rows on Sat/Sun/holidays
    breaks that assumption and causes the back-check to skip entries forever
    or write 0% return values comparing same-day snapshots.

    Also skips tickers with a missing/zero price (bad upstream data) — a $0
    flag price would cause divide-by-zero when computing return.

    Concentration controls (2026-06-01, fix 3 of SCORING_AUDIT_2026-06-01.md):
    - At most _MAX_PER_SECTOR picks from any single sector
    - Skip picks where sub_macro indicates FALLING regime (< _MIN_MACRO_FOR_INCLUSION)
    These reduce next-day correlation in the top-10 and improve the
    back-check's resilience to sector or regime shocks. Both are tunable
    constants at the top of this module.
    """
    from app.services.scorecard_backcheck import is_trading_day

    if not is_trading_day(today):
        # Worker still ticks on weekends/holidays for other tasks; just skip
        # the scorecard snapshot. Tomorrow's trading day will get its row.
        return

    async with session_scope() as session:
        existing = await session.execute(
            select(DailyScorecardEntry).where(DailyScorecardEntry.as_of == today).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            return

        # Pull a wider candidate pool (50) so the concentration filter has
        # room to skip clustered picks without running out before reaching 10.
        candidates = await session.execute(
            select(Ticker).where(Ticker.score.isnot(None)).order_by(desc(Ticker.score)).limit(50)
        )

        sector_counts: dict[str, int] = {}
        skipped_zero_price = 0
        skipped_macro_hostile = 0
        skipped_sector_cap = 0
        rank = 0

        for t in candidates.scalars().all():
            if rank >= 10:
                break

            if not t.price or t.price <= 0:
                # Don't poison the public record with $0-price entries — these
                # come from tier-restricted snapshot fields or partial fetches.
                skipped_zero_price += 1
                continue

            # Macro gate: skip picks in a clearly hostile regime. sub_macro
            # of None means "no signal" (don't filter); a value below the
            # threshold means the Tapeline composite read the regime as
            # FALLING / BEAR. Same pick is still on /scanner — it just
            # doesn't get put on the public scorecard where it would drag
            # the median alpha down on day 1.
            if t.sub_macro is not None and t.sub_macro < _MIN_MACRO_FOR_INCLUSION:
                skipped_macro_hostile += 1
                continue

            # Sector concentration cap. Use the canonical sector field;
            # tickers with NULL/unknown sectors fall into the "Unknown"
            # bucket which gets its own cap (so we don't dump all unknowns
            # into the top-10 either).
            sector_key = (t.sector or "Unknown").strip()
            if _MAX_PER_SECTOR > 0 and sector_counts.get(sector_key, 0) >= _MAX_PER_SECTOR:
                skipped_sector_cap += 1
                continue
            sector_counts[sector_key] = sector_counts.get(sector_key, 0) + 1

            rank += 1
            session.add(DailyScorecardEntry(
                as_of=today,
                symbol=t.symbol,
                rank=rank,
                score_at_flag=t.score or 0,
                price_at_flag=float(t.price),
            ))

        logger.info(
            "scorecard.snapshot saved for %s rows=%d "
            "skipped_zero_price=%d skipped_macro_hostile=%d skipped_sector_cap=%d "
            "sector_mix=%s",
            today, rank, skipped_zero_price, skipped_macro_hostile,
            skipped_sector_cap, sector_counts,
        )


_news_cache_wiped: bool = False


async def _refresh_news() -> None:
    """Pull latest news into local cache. Real source = Massive (formerly Polygon).

    On worker boot we one-shot wipe any leftover mock entries (id starts with
    'mock-') so the per-ticker page stops serving the stale mock corpus when
    real news becomes available.
    """
    global _news_cache_wiped
    if not _news_cache_wiped:
        from sqlalchemy import delete
        async with session_scope() as session:
            res = await session.execute(
                delete(NewsItem).where(NewsItem.id.like("mock-%"))
            )
            wiped = res.rowcount or 0
        if wiped:
            logger.info("news.mock_wiped count=%d", wiped)
        _news_cache_wiped = True

    try:
        items = await fetch_latest_news(limit=40)
    except Exception:
        logger.exception("news.refresh_failed")
        return

    # Insert each article in its own session/transaction. Previous version
    # used a single session for the whole batch — when ONE article failed
    # the column-width check (tickers VARCHAR(200) and one Benzinga article
    # tagged with 50+ symbols), the entire batch rolled back, leaving DB
    # 14h+ stale. Per-article isolation means a bad row can't poison the
    # rest. Tracked: 2026-05-09 production incident.
    inserted = 0
    skipped_dup = 0
    failed = 0
    for it in items:
        try:
            async with session_scope() as session:
                exists = await session.execute(
                    select(NewsItem).where(NewsItem.id == it["id"])
                )
                if exists.scalar_one_or_none() is not None:
                    skipped_dup += 1
                    continue
                session.add(NewsItem(**it))
            inserted += 1
        except Exception:
            failed += 1
            logger.exception("news.insert_failed id=%s title=%s", it.get("id"), str(it.get("title", ""))[:50])
    logger.info(
        "news.refreshed fetched=%d inserted=%d duplicate=%d failed=%d",
        len(items), inserted, skipped_dup, failed,
    )


async def _refresh_watchlisted_news() -> None:
    """Hourly per-watchlisted-ticker news refresh — Premium-tier feature.

    The 5-min broad sweep covers high-volume names. Long-tail tickers
    (small-caps, UK ADRs like BUR, niche ETFs) often never appear in the
    broad sweep because Benzinga prioritises trending US large-caps. This
    fan-out fetches per-ticker news for every symbol on every Premium-
    tier user's watchlist, using the Benzinga → Massive → Finnhub chain.

    Cap at 1000 unique tickers per cycle to bound work. Inserts use the
    same per-article isolation pattern as `_refresh_news` so one bad row
    can't poison the rest. Logs `inserted` / `duplicate` / `failed`
    counts for the same observability reasons.
    """
    from app.models import User
    from app.models.watchlist import WatchlistItem
    from app.services.news_feed import fetch_news_for_ticker

    try:
        async with session_scope() as session:
            # Union of all symbols on Premium-tier users' watchlists.
            # Trial users count as Premium for the trial window — they're
            # already in tier="premium" until _downgrade_expired_trials drops
            # them. So this query naturally covers them.
            rows = await session.execute(
                select(WatchlistItem.symbol)
                .join(User, User.id == WatchlistItem.user_id)
                .where(User.tier == "premium")
                .distinct()
                .limit(1000)
            )
            symbols = [s[0] for s in rows.all() if s[0]]
    except Exception:
        logger.exception("watchlisted_news.symbols_query_failed")
        return

    if not symbols:
        logger.info("watchlisted_news.skipped reason=no_premium_watchlists")
        return

    inserted = 0
    skipped_dup = 0
    failed = 0
    for sym in symbols:
        try:
            articles = await fetch_news_for_ticker(sym, limit=5)
        except Exception:
            logger.exception("watchlisted_news.fetch_failed symbol=%s", sym)
            continue
        for it in articles:
            try:
                async with session_scope() as session:
                    exists = await session.execute(
                        select(NewsItem).where(NewsItem.id == it["id"])
                    )
                    if exists.scalar_one_or_none() is not None:
                        skipped_dup += 1
                        continue
                    session.add(NewsItem(**it))
                inserted += 1
            except Exception:
                failed += 1
                logger.exception(
                    "watchlisted_news.insert_failed symbol=%s id=%s",
                    sym, it.get("id"),
                )
    logger.info(
        "watchlisted_news.refreshed unique_tickers=%d inserted=%d duplicate=%d failed=%d",
        len(symbols), inserted, skipped_dup, failed,
    )


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

    # Send the "trial ended" soft-reengagement email to each downgraded user.
    # No-op if Resend isn't configured.
    try:
        from app.services.email import render_trial_ended_email, send_email
        # Need user names — fetch in one round-trip
        async with session_scope() as session2:
            for user_id, email, _prev in candidates:
                user_r = await session2.execute(select(User).where(User.id == user_id))
                u = user_r.scalar_one_or_none()
                name = (u.name if u else None) or "trader"
                await send_email(
                    email,
                    "Tapeline — your trial just ended",
                    render_trial_ended_email(name),
                    persona="sales",  # win-back, fronted by Christian
                )
    except Exception:
        logger.exception("trial.downgrade_email_failed")


async def _refresh_fundamentals_cache() -> None:
    """
    Daily pre-fetch of Finnhub fundamentals for the top-liquidity slice of
    the universe. Populates finnhub_feed._FUND_SCORE_CACHE so
    polygon_feed.fetch_snapshots can read real sub_fundamentals values
    per tick (instead of random mock).

    LIQUIDITY CAP: Massive auto-discovers ~5700 tickers including thousands
    of sub-$1 micro-caps no real user looks at. Cap matches the active
    scoring universe (2,500) so every ticker we score has fresh
    fundamentals — refresh takes ~42 min on Finnhub free tier (60/min),
    well inside the 24h cycle.
    """
    from app.services.universe import ACTIVE_UNIVERSE_SIZE
    FUNDAMENTALS_CAP = ACTIVE_UNIVERSE_SIZE

    from sqlalchemy import desc

    from app.services.finnhub_feed import (
        compute_fundamentals_score,
        fetch_basic_financials,
        fund_cache_size,
        set_cached_score,
    )

    async with session_scope() as session:
        # Order by an approximation of $-volume. NULLs land last via the desc
        # sort (NULLs are treated as min in most dialects under DESC).
        result = await session.execute(
            select(Ticker.symbol, Ticker.volume, Ticker.price)
            .order_by(desc(Ticker.volume * Ticker.price))
            .limit(FUNDAMENTALS_CAP)
        )
        symbols = [row[0] for row in result.all()]

    logger.info("fundamentals.refresh_started count=%d", len(symbols))
    refreshed = 0
    for sym in symbols:
        try:
            metrics = await fetch_basic_financials(sym)
            if metrics:
                score = compute_fundamentals_score(metrics)
                set_cached_score(sym, score)
                refreshed += 1
        except Exception:
            logger.exception("fundamentals.fetch_failed symbol=%s", sym)
        # Stay well under 60/min cap — sleep ~1.1s between calls
        await asyncio.sleep(1.1)

    logger.info("fundamentals.refreshed scored=%d cache_size=%d", refreshed, fund_cache_size())


async def _refresh_aggregates_cache() -> None:
    """
    Daily pre-fetch of OHLC aggregates for every ticker. Computes trend, RS,
    and momentum scores from the bars and populates the in-memory caches that
    polygon_feed.fetch_snapshots reads per tick.

    Strategy:
    1. Fetch SPY first (needed for RS comparisons across all other tickers)
    2. For each ticker, fetch 250 days of daily bars from Massive
    3. Compute trend / rs / momentum scores
    4. Store in module-level caches in polygon_feed

    Massive Stocks Starter is unlimited API calls so the 870 calls take
    ~5-10 minutes wall time at moderate parallelism. Sleep between calls
    to be polite.
    """
    from datetime import date as _d
    from datetime import timedelta as _td

    from app.services.polygon_feed import (
        aggregate_cache_sizes,
        compute_momentum_score,
        compute_rs_score,
        compute_trend_score,
        fetch_aggregates,
        set_cached_momentum,
        set_cached_rs,
        set_cached_trend,
    )

    # Fetch SPY first as the RS benchmark
    today = _d.today()
    start = today - _td(days=365)
    try:
        spy_bars = await fetch_aggregates("SPY", from_date=start, to_date=today)
    except Exception:
        logger.exception("aggregates.spy_fetch_failed — skipping aggregates refresh this cycle")
        return

    if not spy_bars or len(spy_bars) < 63:
        logger.warning("aggregates.spy_insufficient_bars count=%d — skipping refresh", len(spy_bars) if spy_bars else 0)
        return

    # Same liquidity cap as the Finnhub refreshes — Massive Stocks Starter
    # IS unlimited on call volume, but iterating 5700 tickers at 0.3s each
    # is still ~28 minutes of background work that we don't need to do for
    # micro-caps no scanner user filters into. Cap matches the active
    # scoring universe (2,500) — ~12 min refresh, every scored ticker
    # has real OHLC-derived trend/RS/momentum sub-scores.
    from app.services.universe import ACTIVE_UNIVERSE_SIZE
    AGGREGATES_CAP = ACTIVE_UNIVERSE_SIZE

    from sqlalchemy import desc as _desc

    async with session_scope() as session:
        result = await session.execute(
            select(Ticker.symbol)
            .order_by(_desc(Ticker.volume * Ticker.price))
            .limit(AGGREGATES_CAP)
        )
        symbols = [row[0] for row in result.all() if row[0] != "SPY"]

    logger.info("aggregates.refresh_started count=%d", len(symbols))
    refreshed = 0
    for sym in symbols:
        try:
            bars = await fetch_aggregates(sym, from_date=start, to_date=today)
            if bars:
                t = compute_trend_score(bars)
                r = compute_rs_score(bars, spy_bars)
                m = compute_momentum_score(bars)
                set_cached_trend(sym, t)
                set_cached_rs(sym, r)
                set_cached_momentum(sym, m)
                if any(v is not None for v in (t, r, m)):
                    refreshed += 1
        except Exception:
            logger.exception("aggregates.fetch_failed symbol=%s", sym)
        await asyncio.sleep(0.3)  # gentle pacing — Starter is unlimited but still

    sizes = aggregate_cache_sizes()
    logger.info(
        "aggregates.refreshed scored=%d trend_cache=%d rs_cache=%d mom_cache=%d",
        refreshed, sizes["trend"], sizes["rs"], sizes["momentum"],
    )


async def _refresh_insider_cache() -> None:
    """
    Daily pre-fetch of Finnhub insider Form 4 transactions for the
    top-liquidity slice. Populates _SMART_MONEY_SCORE_CACHE so polygon_feed
    reads real values per tick instead of random mock for sub_smart_money.

    Same liquidity cap as fundamentals — matches active scoring universe
    (2,500) so every scored ticker has fresh insider transactions data.
    """
    from app.services.universe import ACTIVE_UNIVERSE_SIZE
    INSIDER_CAP = ACTIVE_UNIVERSE_SIZE

    from sqlalchemy import desc

    from app.services.finnhub_feed import (
        compute_smart_money_score,
        fetch_insider_transactions,
        insider_feed_size_db,
        set_cached_smart_money_score,
        set_recent_insider_transactions_db,
        smart_money_cache_size,
    )

    async with session_scope() as session:
        result = await session.execute(
            select(Ticker.symbol)
            .order_by(desc(Ticker.volume * Ticker.price))
            .limit(INSIDER_CAP)
        )
        symbols = [row[0] for row in result.all()]

    logger.info("insider.refresh_started count=%d", len(symbols))
    refreshed = 0
    for sym in symbols:
        try:
            txns = await fetch_insider_transactions(sym, days_back=90)
            if txns:
                score = compute_smart_money_score(txns)
                set_cached_smart_money_score(sym, score)
                # Persist to the DB-backed insider feed (cross-process, so
                # the api machine can read what the worker writes).
                await set_recent_insider_transactions_db(sym, txns)
                refreshed += 1
        except Exception:
            logger.exception("insider.fetch_failed symbol=%s", sym)
        await asyncio.sleep(1.1)  # stay well under 60/min

    logger.info(
        "insider.refreshed scored=%d score_cache=%d feed_size=%d",
        refreshed, smart_money_cache_size(), await insider_feed_size_db(),
    )


async def _backfill_sectors(cap: int = 2500) -> None:
    """
    Find Tickers with sector="Unknown" / "N/A" / NULL and fetch their sector
    from Finnhub /stock/profile2. Useful after universe-discovery adds new
    tickers (which arrive with sector="Unknown" because Finnhub /stock/profile2
    is too slow to call inline during discovery).

    Cap bumped from 200 → 2500 on 2026-05-16 after a user observed 1,430
    tickers stuck in "Uncategorized" on the heatmap. At 200/day the catch-up
    would take 7+ days; at 2,500 it's one ~46-minute run. Finnhub free tier
    is 60 req/min so 2,500 × 1.1s = ~46 min stays well under the rate cap.

    Whatever sector string Finnhub returns is normalised through
    services/sector.canonical_sector before being written, so the DB
    stores GICS-canonical strings ("Information Technology" not
    "Software—Application", "Health Care" not "Biotechnology"). The
    heatmap can then render them directly without re-canonicalizing
    every read.
    """
    from sqlalchemy import or_, update

    from app.services.finnhub_feed import fetch_company_profile
    from app.services.sector import canonical_sector

    async with session_scope() as session:
        result = await session.execute(
            select(Ticker.symbol, Ticker.asset_class).where(
                or_(
                    Ticker.sector.is_(None),
                    Ticker.sector == "Unknown",
                    Ticker.sector == "N/A",
                    Ticker.sector == "Uncategorized",
                )
            ).limit(cap)
        )
        rows = result.all()

    if not rows:
        logger.info("sector_backfill.no_unknown_tickers")
        return

    backfilled = 0
    async with session_scope() as session:
        for sym, asset_class in rows:
            try:
                profile = await fetch_company_profile(sym)
                raw_sector = (profile or {}).get("sector") if profile else None
                # Apply the canonical mapping at write time so storage matches
                # the heatmap's render-time grouping. If Finnhub returned no
                # sector, canonical_sector still routes by asset_class (e.g.
                # ETFs → Funds & ETFs) instead of leaving "Unknown" in the DB.
                target = canonical_sector(raw_sector, asset_class)
                await session.execute(
                    update(Ticker).where(Ticker.symbol == sym)
                    .values(sector=target)
                )
                backfilled += 1
            except Exception:
                logger.exception("sector_backfill.fetch_failed symbol=%s", sym)
            await asyncio.sleep(1.1)
        await session.commit()

    logger.info("sector_backfill.done backfilled=%d candidates=%d cap=%d",
                backfilled, len(rows), cap)


async def _refresh_universe() -> None:
    """
    Weekly universe refresh from Polygon /v3/reference/tickers.
    Adds newly-listed equities + ETFs to the Ticker table; does NOT
    delete delistings (delisted tickers just stop receiving snapshot updates).
    """
    from app.services.polygon_feed import discover_active_us_tickers

    new_rows = await discover_active_us_tickers()
    if not new_rows:
        logger.info("universe.refresh_skipped reason=empty_response")
        return

    async with session_scope() as session:
        existing_r = await session.execute(select(Ticker.symbol))
        existing = {r[0] for r in existing_r.all()}
        added = 0
        for row in new_rows:
            if row["symbol"] not in existing:
                session.add(Ticker(**row))
                added += 1

    logger.info("universe.refreshed added=%d total_polygon=%d", added, len(new_rows))


async def _refresh_elite_13f() -> None:
    """
    Daily 24h refresh of elite-fund 13F holdings.

    Tries Quiver first; if QUIVER_API_KEY is unset OR every fund fetch fails,
    falls back to deterministic mock data so the /api/holdings endpoint
    never returns empty in dev.
    """
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
    """
    Refresh IPO + earnings events daily.

    Uses Finnhub when FINNHUB_API_KEY is set (real upcoming events); falls
    back to mock generators otherwise. Replaces the existing tables on each
    refresh so stale events drop off naturally — Finnhub returns the rolling
    window, no need to track which rows were inserted previously.
    """
    from sqlalchemy import delete

    from app.models import EarningsEvent, IPOEvent
    from app.services.calendar_feed import upcoming_earnings, upcoming_ipos

    async with session_scope() as session:
        # IPOs — replace whole table with the fresh window
        await session.execute(delete(IPOEvent))
        for row in await upcoming_ipos():
            session.add(IPOEvent(**row))

        # Earnings — same pattern
        await session.execute(delete(EarningsEvent))
        for row in await upcoming_earnings():
            session.add(EarningsEvent(**row))

    logger.info("calendar.refreshed")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("signal_publisher.start interval=%ds", settings.score_refresh_seconds)

    # Seed universe on first boot (idempotent)
    await seed_universe()

    # Watchdog: a healthy tick completes in ~6s. If one ever stalls past
    # TICK_TIMEOUT_SECONDS we kill it and continue — better to drop one
    # cycle than to hang the worker indefinitely. The 2026-05-17 outage
    # froze tick() for 20+ minutes (worker process alive, tick coroutine
    # stuck waiting on something async that never resolved) before a
    # manual `fly machine restart` cleared it. wait_for prevents that.
    TICK_TIMEOUT_SECONDS = 60
    consecutive_timeouts = 0

    while True:
        cycle_started = datetime.now(UTC)
        try:
            await asyncio.wait_for(tick(), timeout=TICK_TIMEOUT_SECONDS)
            consecutive_timeouts = 0
        except TimeoutError:
            consecutive_timeouts += 1
            elapsed = (datetime.now(UTC) - cycle_started).total_seconds()
            logger.error(
                "tick.timeout elapsed=%.1fs limit=%ds consecutive=%d — "
                "killing this cycle and moving on",
                elapsed, TICK_TIMEOUT_SECONDS, consecutive_timeouts,
            )
            # If we're racking up timeouts something is fundamentally
            # broken — surface to Sentry so it pages instead of silently
            # dropping cycles.
            if consecutive_timeouts >= 3:
                logger.critical(
                    "tick.timeout_streak count=%d — worker appears wedged, "
                    "consider `fly machine restart`",
                    consecutive_timeouts,
                )
        except Exception:
            logger.exception("tick.failure")
        await asyncio.sleep(settings.score_refresh_seconds)


if __name__ == "__main__":
    asyncio.run(main())
