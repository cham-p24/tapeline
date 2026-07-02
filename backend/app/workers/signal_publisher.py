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
    NewsItem,
    RegimeState,
    SqueezeSetup,
    Ticker,
)

# --- DATA-FEED IMPORTS ---
# Hybrid swap (2026-05-02): real prices + live macro from Massive (api.massive.com).
# Squeeze detection stays mock for now — running per-ticker /v2/aggs across the full
# universe each tick burns API calls; revisit once a daily back-fill job is built.
# Congress trades stay mock unless the smart_money_congress Google Sheet is
# configured — Polygon/Massive don't offer that data (deferred per CLAUDE.md
# known-issues).
from app.services.mock_feed import (
    fetch_congress_trades,
    fetch_squeezes,
    universe,
)
from app.services.news_feed import fetch_latest_news
from app.services.polygon_feed import fetch_regime, fetch_snapshots
from app.services.pubsub import broker
from app.services.scorecard_backcheck import backcheck_all_pending

logger = logging.getLogger(__name__)
settings = get_settings()

_last_news_refresh: datetime | None = None
_last_backcheck: datetime | None = None
_last_telegram_digest: datetime | None = None
_last_calendar_seed: datetime | None = None
_last_trial_check: datetime | None = None
_last_drip_check: datetime | None = None
_last_universe_refresh: datetime | None = None
_last_sheet_refresh: datetime | None = None
_last_active_universe_refresh: datetime | None = None
_last_eod_digest_date: str | None = None  # "YYYY-MM-DD" of last EOD digest run (UTC)
_last_weekly_newsletter_token: str | None = None  # "weekly_YYYYWww" of last newsletter run
_last_daily_newsletter_date: str | None = None  # "YYYY-MM-DD" of last Daily Top 10 digest run (UTC)
_last_indexnow_date: str | None = None  # "YYYY-MM-DD" of last IndexNow batch submit (UTC)
_last_stale_audit_date: str | None = None  # "YYYY-MM-DD" of last stale-link audit + alert
_last_seo_digest_token: str | None = None  # "seo_YYYYWww" of last weekly SEO digest run
_last_growth_tick_date: str | None = None  # "YYYY-MM-DD" of last growth-bot tick (UTC)
_last_fundamentals_refresh: datetime | None = None
_last_insider_refresh: datetime | None = None
_last_sector_backfill: datetime | None = None
_last_watchlisted_news_refresh: datetime | None = None
_last_aggregates_refresh: datetime | None = None
_last_inbox_tick: datetime | None = None
_last_checkout_recovery: datetime | None = None


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

    # NB: _ensure_daily_scorecard(today) used to live here, immediately after
    # the snapshot upserts. Codex (PR #226 review) flagged that ordering as
    # racy in sheet-fed prod: fetch_snapshots() writes Ticker.sub_macro from
    # polygon_feed (documented as mock for the macro factor), and only the
    # sheet refresh further down rewrites sub_macro with the Tapeline
    # composite's regime-derived score. Running the macro gate here would
    # filter on the mock/stale value, so valid high-ranked picks could be
    # nondeterministically excluded from the back-check.
    #
    # Fix: move the freeze AFTER the sheet refresh block so the gate reads
    # the freshly-written Tapeline sub_macro. Freeze is idempotent (returns
    # early if today's row already exists) so moving it later doesn't change
    # the once-per-day semantics.

    # Refresh news feed: on first tick after boot + every ~5 minutes thereafter
    global _last_news_refresh, _last_backcheck
    if _last_news_refresh is None or (started - _last_news_refresh).total_seconds() > 300:
        await _refresh_news()
        # SEC EDGAR 8-K direct — runs alongside the wire-news refresh so material
        # filings hit the news bar ~5-30 min earlier than they would via the
        # Massive/Finnhub wires. Free + zero-API-key. Idempotent (uses EDGAR accession number
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

    # Scorecard back-check: drain the pending backlog on a real daily cadence.
    # BUG FIX (2026-06-01): this was `if _last_backcheck is None`, which fired
    # ONLY on the first tick after a worker reboot. On a stable deploy the
    # worker doesn't reboot daily, so the back-check silently stopped and the
    # public scorecard froze — 91 of 140 rows (every day after ~May 20) sat
    # with no next-day price, so the headline stayed stuck on a stale 49-pick
    # sample. Mirror the calendar-seed cadence below: re-run every 6h. The job
    # itself now drains ALL pending dates (see _run_backcheck), so a day the
    # worker happened to miss is retried on the next run instead of stranded.
    if _last_backcheck is None or (started - _last_backcheck).total_seconds() >= 6 * 3600:
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
    # Quota math: 1000 unique tickers × 1/hour = 24k calls/day across
    # Massive + Finnhub (60/min), comfortably within the rate limits.
    global _last_watchlisted_news_refresh
    if _last_watchlisted_news_refresh is None or (started - _last_watchlisted_news_refresh).total_seconds() >= 3600:
        await _refresh_watchlisted_news()
        _last_watchlisted_news_refresh = started

    # Daily trial-drip emails (day 3 / 7 / 13) + 14-day re-engagement for
    # dormant non-trial users + 30/60/90-day post-cancellation win-back +
    # early-lifecycle activation nudges (first watchlist / first alert) +
    # post-conversion monthly→annual upgrade nudge + personal founder-touch to
    # high-value engaged signups + referral-milestone celebrations (3/5/10/25).
    # Worker-restart-safe — User.drip_state / winback_state / founder_touch_sent_at
    # track per-user per-stage delivery so no email fires twice.
    global _last_drip_check
    if _last_drip_check is None or (started - _last_drip_check).total_seconds() >= 86400:
        try:
            from app.services.email import (
                run_activation_drip,
                run_annual_nudge_drip,
                run_annual_renewal_reminder_drip,
                run_daily_drip,
                run_founder_touch_drip,
                run_re_engagement_drip,
                run_referral_milestone_drip,
                run_winback_drip,
            )
            async with session_scope() as drip_session:
                counts = await run_daily_drip(drip_session)
                re_counts = await run_re_engagement_drip(drip_session)
                wb_counts = await run_winback_drip(drip_session)
                act_counts = await run_activation_drip(drip_session)
                annual_counts = await run_annual_nudge_drip(drip_session)
                renewal_counts = await run_annual_renewal_reminder_drip(drip_session)
                ft_counts = await run_founder_touch_drip(drip_session)
                refm_counts = await run_referral_milestone_drip(drip_session)
            if any(counts.values()):
                logger.info("drip.sent day3=%d day7=%d day13=%d", counts["day3"], counts["day7"], counts["day13"])
            if re_counts["re14"]:
                logger.info("drip.re_engagement_sent re14=%d", re_counts["re14"])
            if any(wb_counts.values()):
                logger.info("drip.winback_sent wb30=%d wb60=%d wb90=%d", wb_counts["wb30"], wb_counts["wb60"], wb_counts["wb90"])
            if any(act_counts.values()):
                logger.info("drip.activation_sent act_wl=%d act_alert=%d", act_counts["act_wl"], act_counts["act_alert"])
            if annual_counts["annual_p"]:
                logger.info("drip.annual_nudge_sent annual_p=%d", annual_counts["annual_p"])
            if renewal_counts["renewal_reminder"]:
                logger.info("drip.renewal_reminder_sent renewal_reminder=%d", renewal_counts["renewal_reminder"])
            if ft_counts["founder_touch"]:
                logger.info("drip.founder_touch_sent founder_touch=%d", ft_counts["founder_touch"])
            if any(refm_counts.values()):
                logger.info("drip.referral_milestone_sent %s", refm_counts)
        except Exception:
            logger.exception("drip.run_failed")
        _last_drip_check = started

    # Checkout abandonment recovery — HOURLY (not daily like the drips above):
    # the targeting window is a tight 1-24h after a user mints a Stripe Checkout
    # Session without completing it, so a daily cadence would miss most of them.
    # checkout_started_at is the abandonment signal (cleared by the
    # checkout.session.completed webhook); the "abandon1" drip_state token makes
    # each attempt a one-shot. No-op without RESEND_API_KEY.
    global _last_checkout_recovery
    if _last_checkout_recovery is None or (started - _last_checkout_recovery).total_seconds() >= 3600:
        try:
            from app.services.email import run_checkout_abandonment_recovery
            async with session_scope() as recovery_session:
                rec_counts = await run_checkout_abandonment_recovery(recovery_session)
            if rec_counts["abandon1"]:
                logger.info("drip.checkout_recovery_sent abandon1=%d", rec_counts["abandon1"])
        except Exception:
            logger.exception("checkout_recovery.run_failed")
        _last_checkout_recovery = started

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

    # Snapshot today's top-10 for the public scorecard (once per day).
    # Runs AFTER the sheet refresh so the macro gate + concentration filter
    # operate on the Tapeline composite's sub_macro / sector values, not
    # the polygon_feed mock values that fetch_snapshots wrote earlier in
    # this tick. Idempotent: returns early when today's row already exists.
    await _ensure_daily_scorecard(started.date())

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

    # Daily Top 10 digest to newsletter_subscribers. Fires once per UTC day
    # at/after 13:00 UTC — ~9am ET pre-market open. Process-level token +
    # DB-side `last_sent_at` give us two layers of dedupe so a worker
    # restart can't double-send. Only US weekdays — Sat/Sun there's no
    # fresh tape to send, so we skip cleanly.
    global _last_daily_newsletter_date
    if (
        started.hour >= 13                                # 13:00 UTC onward
        and started.weekday() < 5                         # Mon-Fri
        and _last_daily_newsletter_date != today_str
    ):
        try:
            from app.services.newsletter import run_daily_digest
            async with session_scope() as ndl_session:
                count = await run_daily_digest(ndl_session, now=started)
            logger.info("newsletter_daily.sent count=%d date=%s", count, today_str)
        except Exception:
            logger.exception("newsletter_daily.run_failed")
        _last_daily_newsletter_date = today_str

    # IndexNow batch submit — daily, fires once per UTC day at/after
    # 06:00 UTC (Sydney evening, so any new pages shipped today are
    # already deployed by Vercel). Pushes every URL in the sitemap to
    # Bing + Yandex + DuckDuckGo + Seznam in one batch — they pick up
    # new content within hours instead of waiting on Googlebot's crawl
    # schedule. Free, no auth, gracefully no-ops if endpoint is down.
    global _last_indexnow_date
    if started.hour >= 6 and _last_indexnow_date != today_str:
        # Latch BEFORE spawning so this fires at most once per UTC day even if
        # the batch runs long, then run it detached — a slow sitemap fetch or
        # submit must never eat the 60s tick-watchdog budget.
        _last_indexnow_date = today_str
        asyncio.create_task(_run_daily_indexnow())

    # Daily stale-link audit — fires once per UTC day at/after 08:00
    # UTC. Crawls every URL in the sitemap; alerts the founder via
    # Telegram ONLY if broken URLs are present (no broken = no noise).
    # Catches 404s introduced by route renames, 5xx outages, and
    # accidental disconnects between sitemap entries and live pages
    # within ~24 hours instead of relying on the next user/Google to
    # surface them.
    global _last_stale_audit_date
    if started.hour >= 8 and _last_stale_audit_date != today_str:
        # Latch BEFORE spawning, then run detached. The audit crawls the full
        # sitemap (~1k URLs, minutes) — far longer than the 60s tick watchdog.
        # Awaiting it inline previously WEDGED the worker: wait_for killed
        # tick() mid-audit before the latch was set, so the audit re-ran every
        # cycle — a self-inflicted crawl storm that hammered /api/ticker
        # (cold-news 15s with a DB connection held) and spammed the
        # tick.timeout_streak CRITICAL. Detached + latched, it runs once/day
        # and tick() returns in ~6s.
        _last_stale_audit_date = today_str
        asyncio.create_task(_run_daily_stale_audit())

    # Weekly SEO digest — Monday at/after 09:00 UTC (~7pm Sydney
    # post-Monday-close, ~5am ET pre-market). Sends a Markdown summary
    # to the founder's Telegram: sitemap size, broken-URL count,
    # ticker-universe stats, and suggested next steps. Process-level
    # token + Telegram-side dedupe make double-fires harmless.
    global _last_seo_digest_token
    seo_digest_token = f"seo_{iso_year}W{iso_week:02d}"
    if (
        iso_dow == 1                                    # Monday
        and started.hour >= 9                           # 09:00 UTC onward
        and _last_seo_digest_token != seo_digest_token
    ):
        try:
            from app.services.seo_health import run_weekly_digest
            async with session_scope() as seo_session:
                sent = await run_weekly_digest(seo_session)
            logger.info("seo_digest.weekly.ran sent=%s token=%s", sent, seo_digest_token)
        except Exception:
            logger.exception("seo_digest.weekly.failed")
        _last_seo_digest_token = seo_digest_token

    # Daily growth-bot tick. Fires once per UTC day at/after 22:00 UTC
    # — ~8am Melbourne the next morning AEST, ~6pm ET the prior evening.
    # Generates copy-paste-ready X / LinkedIn / fintwit drafts + a
    # conversion-funnel snapshot, emails the package to the founder.
    # No-op when GROWTH_BOT_ENABLED is false (default — opt-in).
    # Weekdays only — no growth tick on Sat/Sun so the founder's inbox
    # doesn't ping at 8am on the weekend.
    global _last_growth_tick_date
    if (
        settings.growth_bot_enabled
        and started.hour >= 22                            # 22:00 UTC onward
        and started.weekday() < 5                         # Mon-Fri
        and _last_growth_tick_date != today_str
    ):
        try:
            from app.services.growth_bot import run_daily_growth_tick
            async with session_scope() as gb_session:
                result = await run_daily_growth_tick(gb_session)
            logger.info(
                "growth_bot.tick_complete picks=%d fintwit=%d skipped=%s",
                result.get("picks_count", 0),
                result.get("fintwit_candidates_count", 0),
                result.get("skipped", False),
            )
        except Exception:
            logger.exception("growth_bot.tick_failed")
        _last_growth_tick_date = today_str

    # Inbox auto-handler tick: poll Reddit (the only channel that needs
    # polling — email is webhook-driven via /api/inbox/email; Telegram
    # alerts are dispatched at classification time). Cadence: 5 min
    # during US market hours (more chatter), 15 min off-hours. No-ops
    # cleanly when REDDIT_* credentials are unset.
    global _last_inbox_tick
    is_inbox_market_hours = (
        started.weekday() < 5 and 13 <= started.hour < 21  # 9am-5pm ET ≈ 13-21 UTC
    )
    inbox_interval = 300 if is_inbox_market_hours else 900
    if _last_inbox_tick is None or (started - _last_inbox_tick).total_seconds() >= inbox_interval:
        _last_inbox_tick = started
        try:
            await _run_inbox_tick()
        except Exception:
            logger.exception("inbox.tick_failed")

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


def _macro_gate_active() -> bool:
    """The macro gate only applies when Ticker.sub_macro is the Tapeline
    composite's regime-derived value (set by sheet_feed.refresh_from_workbook).

    Without the sheet, polygon_feed's fetch_snapshots writes a mock/random
    value to sub_macro on every tick — gating on that would nondeterministically
    drop valid high-ranked picks from the public scorecard. We tie the gate
    to `signal_sheet_csv_url` being set: that's the env var that switches
    sub_macro from mock to Tapeline-composite-derived.

    In dev (no sheet URL), the gate is off and all top-10 candidates pass
    the macro check. That's the right behaviour: dev runs against mock
    data; the back-check isn't meaningful there anyway."""
    return bool(get_settings().signal_sheet_csv_url)


async def _run_daily_indexnow() -> None:
    """Detached daily IndexNow batch (spawned, never awaited, from tick()).

    Pushes every sitemap URL to Bing/Yandex/DuckDuckGo/Seznam. Self-contained
    so a slow sitemap fetch/submit can't stall the 60s tick watchdog; swallows
    its own exceptions so the fire-and-forget task never raises unretrieved."""
    try:
        from app.services.index_now import submit_urls
        from app.services.seo_health import fetch_sitemap_urls
        urls = await fetch_sitemap_urls()
        if urls:
            result = await submit_urls(urls)
            logger.info(
                "indexnow.daily_batch submitted=%d accepted=%d queued=%d failed=%d",
                result["submitted"], result["accepted"],
                result["queued"], result["failed"],
            )
        else:
            logger.warning("indexnow.daily_batch.empty no_sitemap_urls")
    except Exception:
        logger.exception("indexnow.daily_batch.failed")


async def _run_daily_stale_audit() -> None:
    """Detached daily stale-link audit (spawned, never awaited, from tick()).

    Crawls the full sitemap (~1k URLs, minutes) and alerts the founder via
    Telegram only if broken URLs are present. Opens its own session and
    swallows its own exceptions so the fire-and-forget task is self-contained
    and can't stall or wedge the 60s tick watchdog."""
    try:
        from app.services.seo_health import run_stale_audit_alert
        async with session_scope() as audit_session:
            alerted = await run_stale_audit_alert(audit_session)
        logger.info("stale_audit.daily.ran alerted=%s", alerted)
    except Exception:
        logger.exception("stale_audit.daily.failed")


async def _run_inbox_tick() -> None:
    """One inbox-poll cycle.

    Currently only polls Reddit — email + Telegram inbound are both
    webhook-driven so don't need a poller. The Reddit poller is the
    safety net for the only inbound channel that doesn't get a push.

    Honours the per-channel + global kill switches via the called
    services; no need to re-check here.
    """
    try:
        from app.services.reddit_inbox import poll_reddit_inbox
        async with session_scope() as session:
            counts = await poll_reddit_inbox(session)
        if counts.get("total"):
            logger.info(
                "inbox.reddit_poll dms=%d comments=%d mentions=%d",
                counts["dms"], counts["comments"], counts["mentions"],
            )
    except Exception:
        logger.exception("inbox.reddit_poll_failed")


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
        # Freshness + data-quality floor — never freeze a stale ghost row OR a
        # corrupt (score>100 / emoji-symbol / <2-factor) row into the permanent
        # public scorecard record. (score IS NOT NULL is part of the floor.)
        # See app.services.ticker_freshness.
        from app.services.ticker_freshness import live_clauses
        _cand_stmt = select(Ticker)
        for _clause in await live_clauses(session):
            _cand_stmt = _cand_stmt.where(_clause)
        candidates = await session.execute(
            _cand_stmt.order_by(desc(Ticker.score)).limit(50)
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
            #
            # Only enforce the gate when the sheet feed is the source of
            # truth — otherwise sub_macro is whatever polygon_feed's mock
            # branch wrote (per the docstring on fetch_snapshots, the macro
            # factor is still mock data) and gating on it would skip valid
            # picks based on a random number. Codex flagged this on PR #226.
            if (
                _macro_gate_active()
                and t.sub_macro is not None
                and t.sub_macro < _MIN_MACRO_FOR_INCLUSION
            ):
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
                # Defensive cap: live_clauses() above already excludes any
                # score>100 candidate, but clamp at the write too so a corrupt
                # composite can never be frozen onto the permanent public trust
                # record (the 2026-05-22..06-05 137-score rows came from a
                # pre-live_clauses snapshot path).
                score_at_flag=min(t.score, 100.0) if t.score else 0,
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
    # the column-width check (tickers VARCHAR(200) and one round-up article
    # tagged with 50+ symbols), the entire batch rolled back, leaving DB
    # 14h+ stale. Per-article isolation means a bad row can't poison the
    # rest. Tracked: 2026-05-09 production incident.
    inserted = 0
    skipped_dup = 0
    failed = 0
    for it in items:
        # Defense-in-depth: a mock row must never be persisted in prod. The
        # boot wipe + news_feed's vendor guard should already prevent this,
        # but belt-and-suspenders here too.
        if str(it.get("id", "")).startswith("mock-"):
            continue
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
    broad sweep because the wires prioritise trending US large-caps. This
    fan-out fetches per-ticker news for every symbol on every Premium-
    tier user's watchlist, using the Massive + Finnhub parallel merge.

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
            # Defense-in-depth: never persist a mock row in prod.
            if str(it.get("id", "")).startswith("mock-"):
                continue
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
    """Drain the scorecard back-check backlog.

    Scores EVERY prior date that still has entries without a next-day price,
    not just yesterday. This is what makes the job self-healing: if the worker
    missed a day (reboot gap, transient feed outage, SPY window not yet
    complete), those dates stay pending and get retried on the next run instead
    of being stranded forever — which is exactly the failure that froze the
    public scorecard on a stale 49-pick sample for ~10 days.
    """
    async with session_scope() as session:
        try:
            scored = await backcheck_all_pending(session)
            if scored:
                logger.info("scorecard.backcheck_scored total=%d", scored)
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

    # Deliberately NO email from this path. The daily drip's T+0 "expired"
    # stage (email.run_daily_drip) owns the end-of-trial email — it dedupes
    # via users.drip_state, respects the TRIAL_DRIP email preference, and
    # carries the List-Unsubscribe headers. This function used to also send
    # render_trial_ended_email here (no dedup, no unsubscribe header), which
    # double-emailed every non-converting user within ~24h of expiry.


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


def _init_sentry() -> None:
    """Initialise Sentry for the STANDALONE worker process.

    The worker runs as its own ``python -m app.workers.signal_publisher``
    process — it never imports app.main, so the Sentry init there (main.py:60)
    does NOT run here. Without this, the ``tick.timeout_streak`` capture below
    (and any unhandled worker exception) goes nowhere. Mirrors main.py's
    env-gated config exactly: no-op when SENTRY_DSN is blank (dev / opt-out),
    and any init failure is swallowed so the worker still runs unmonitored.
    """
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk

        from app.sentry_filter import before_send

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            before_send=before_send,
            environment=settings.sentry_environment or settings.app_env,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            release="tapeline@0.1.0",
            # No request lifecycle in the worker — APM tracing isn't useful, but
            # we keep the rate consistent with the API for spend predictability.
            send_default_pii=False,
        )
        logger.info(
            "sentry.initialized component=worker env=%s",
            settings.sentry_environment or settings.app_env,
        )
    except Exception:
        logger.exception("sentry.init_failed — worker continuing unmonitored")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _init_sentry()
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
                # logger.critical alone goes only to stdout/Fly logs — nobody
                # is paged. Capture to Sentry (level=fatal) so the timeout
                # streak actually surfaces. Guarded: a no-op when SENTRY_DSN is
                # unset (sentry_sdk.init never ran) and never crashes the loop.
                try:
                    import sentry_sdk

                    sentry_sdk.capture_message(
                        f"signal_publisher tick timeout streak "
                        f"(consecutive={consecutive_timeouts}, "
                        f"limit={TICK_TIMEOUT_SECONDS}s) — worker appears "
                        f"wedged; consider `fly machine restart`",
                        level="fatal",
                    )
                except Exception:
                    logger.exception("tick.timeout_streak.sentry_capture_failed")
        except Exception:
            logger.exception("tick.failure")
        await asyncio.sleep(settings.score_refresh_seconds)


if __name__ == "__main__":
    asyncio.run(main())
