"""
Scoring worker — writes mock (or Polygon) data to the DB each tick and
publishes a change event for the SSE stream.

To swap mock → Polygon: change the import line below.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime

from sqlalchemy import delete, desc, select, update

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
# Squeeze detection and congress trades have NO real source wired: both come from
# mock_feed, which fabricates rows (including invented trades attributed to real,
# named politicians). Those generators are therefore only ever PERSISTED outside
# production — see `_mock_writes_enabled()`. In production the SqueezeSetup table
# is owned by the SPIKE INTELLIGENCE sheet tab (sheet_feed.upsert_spikes) and the
# congress_trades table simply stops accruing rows until a real disclosure feed
# is wired.
from app.services.mock_feed import (
    fetch_congress_trades,
    fetch_squeezes,
    universe,
)
from app.services.news_feed import fetch_latest_news
from app.services.polygon_feed import fetch_regime, fetch_snapshots
from app.services.pubsub import broker
from app.services.scorecard_backcheck import backcheck_all_pending, is_trading_day

logger = logging.getLogger(__name__)
settings = get_settings()

# Strong references to detached fire-and-forget tasks. asyncio only keeps a
# weak reference to a running task, so without this a long-running background
# job can be garbage-collected mid-flight. Same pattern as
# routers/ticker.py:_news_bg_tasks.
_bg_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:  # type: ignore[no-untyped-def]
    """Fire-and-forget `coro` as a detached task, holding a strong reference."""
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


_last_news_refresh: datetime | None = None
_last_backcheck: datetime | None = None
_last_telegram_digest: datetime | None = None
_last_calendar_seed: datetime | None = None
_last_trial_check: datetime | None = None
_last_drip_check: datetime | None = None  # set ONLY after a fully successful drip run
_last_drip_failed_at: datetime | None = None  # last failed drip attempt (1h retry backoff)
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
_last_aggregates_failed_at: datetime | None = None  # last failed aggregates run (short retry backoff)
_last_inbox_tick: datetime | None = None
_last_checkout_recovery: datetime | None = None

# Symbols the ALL SIGNALS sheet governs. Refreshed alongside the sheet tick;
# consumed by the per-tick snapshot upsert so the market feed can't clobber the
# authoritative Tapeline composite. Empty when no sheet is configured.
_sheet_governed_symbols: frozenset[str] = frozenset()


def _mock_writes_enabled() -> bool:
    """May fabricated (mock_feed) rows be PERSISTED to the DB?

    Only outside production. `mock_feed.fetch_squeezes` /
    `fetch_congress_trades` invent rows on every call — the congress generator
    attributes randomly-generated trades to real, named politicians. Persisting
    those in production publishes fabrication as fact (routers/congress.py
    serves them as disclosures, services/alerts.py emails users about them), so
    the write path is gated to dev/test where mock data is the point.

    When a real source for either dataset is wired, gate on that source's
    config here instead of (or in addition to) the env check.
    """
    return get_settings().app_env != "production"


def _sheet_is_scoring_source() -> bool:
    """True when the signal-system sheet owns Ticker.score + the sub-scores.

    `sheet_feed.upsert_tickers` writes the authoritative Tapeline composite
    (score, signal, all six sub_* factors, confidence_pct) for the symbols it
    covers. It runs on a 5-minute throttle AND skips entirely when the CSV
    content hash is unchanged, whereas `fetch_snapshots` runs every 60s — so
    without a guard the market-feed snapshot (whose macro factor and reason
    string are still synthesised) overwrites the sheet composite within one
    tick of every sheet refresh and keeps it overwritten indefinitely.
    """
    return bool(get_settings().signal_sheet_csv_url)


async def _refresh_sheet_governed_symbols() -> None:
    """Cache the symbol set the ALL SIGNALS tab covers.

    Deliberately scoped to the sheet's OWN symbols: the discovered universe is
    far larger than the sheet, and freezing the composite for symbols the sheet
    never publishes would leave them ranked on a permanently stale score.
    Failures leave the previous set in place (fail-soft)."""
    global _sheet_governed_symbols
    url = get_settings().signal_sheet_csv_url
    if not url:
        return
    try:
        from app.services.sheet_feed import fetch_csv, parse_all_signals_csv

        # dedup=False: refresh_from_workbook consumes the content-hash dedupe,
        # so a deduped fetch here would return None on every steady-state tick
        # and the set could never be (re)built after a worker restart.
        text = await fetch_csv(url, dedup=False)
        if not text:
            return
        symbols = frozenset(
            r["symbol"] for r in parse_all_signals_csv(text) if r.get("symbol")
        )
        if symbols:
            _sheet_governed_symbols = symbols
    except Exception:
        logger.exception("sheet_feed.governed_symbols_refresh_failed")


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
    regime = await fetch_regime() if inspect.iscoroutinefunction(fetch_regime) else fetch_regime()

    # Squeezes + congress trades are FABRICATED by mock_feed (no real source is
    # wired for either). Don't even generate them in production — see
    # `_mock_writes_enabled()`.
    mock_writes = _mock_writes_enabled()
    squeezes: list[dict] = []
    new_trades: list[dict] = []
    if mock_writes:
        squeezes = await fetch_squeezes() if inspect.iscoroutinefunction(fetch_squeezes) else fetch_squeezes()
        new_trades = (
            await fetch_congress_trades()
            if inspect.iscoroutinefunction(fetch_congress_trades)
            else fetch_congress_trades()
        )

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

    # Symbols whose composite the sheet owns — the snapshot upsert below writes
    # only market-feed fields for those (see _sheet_is_scoring_source).
    sheet_owned = _sheet_governed_symbols if _sheet_is_scoring_source() else frozenset()

    async with session_scope() as session:
        # --- Update ticker snapshots (dialect-neutral upsert) ---
        # Only the PK is selected: loading full ORM Ticker objects for the whole
        # table made per-tick memory scale with the universe (5.7k rows and
        # growing) for what is just an exists-check.
        existing_symbols = {
            s for (s,) in (await session.execute(select(Ticker.symbol))).all()
        }
        full_updates: list[dict] = []
        market_updates: list[dict] = []
        for snap in snapshots:
            market_only = {
                "price": snap["price"],
                "change_pct_1d": snap["change_pct_1d"],
                "change_pct_5d": snap["change_pct_5d"],
                "change_pct_1m": snap["change_pct_1m"],
                "volume": snap["volume"],
            }
            is_sheet_owned = snap["symbol"] in sheet_owned
            if is_sheet_owned:
                # Sheet-governed: price/volume/changes come from the market feed,
                # but the composite, the six sub-scores and confidence stay
                # whatever sheet_feed.upsert_tickers last wrote.
                data = market_only
            else:
                data = {
                    **market_only,
                    "score": snap["score"],
                    "signal": snap["signal"],
                    "sub_trend": snap["sub_trend"],
                    "sub_rs": snap["sub_rs"],
                    "sub_fundamentals": snap["sub_fundamentals"],
                    "sub_momentum": snap["sub_momentum"],
                    "sub_macro": snap["sub_macro"],
                    "sub_smart_money": snap["sub_smart_money"],
                    "confidence_pct": snap.get("confidence_pct"),
                    "reason": snap["reason"],
                }
            if snap["symbol"] not in existing_symbols:
                session.add(Ticker(symbol=snap["symbol"], name=snap["symbol"], **data))
            elif is_sheet_owned:
                market_updates.append({"symbol": snap["symbol"], **data})
            else:
                full_updates.append({"symbol": snap["symbol"], **data})

        # Bulk UPDATE ... WHERE symbol = :symbol, executemany'd per column set.
        for batch in (full_updates, market_updates):
            if batch:
                await session.execute(update(Ticker), batch)

        # --- Replace squeeze setups ---
        # ONLY when the rows we're about to write are real enough to persist.
        # In production this table is owned by the SPIKE INTELLIGENCE sheet tab
        # (5-min throttle, skipped entirely when the CSV is unchanged), so
        # wiping it every 60s here deleted real data and served ~15 fabricated
        # setups in its place.
        if mock_writes:
            await session.execute(delete(SqueezeSetup))
            for s in squeezes:
                session.add(SqueezeSetup(**s))

        # --- Upsert regime (single row) ---
        await session.execute(delete(RegimeState))
        session.add(RegimeState(id=1, **regime))

        # --- Append new congress trades ---
        # Idempotent on the natural key (politician + symbol + trade_date +
        # direction + amount band) so a real disclosure feed re-reporting the
        # same filing can't duplicate it. Existing rows are never deleted here
        # — purging the fabricated backlog is an operator decision.
        for t in new_trades:
            dupe = await session.execute(
                select(CongressTrade.id)
                .where(
                    CongressTrade.politician == t["politician"],
                    CongressTrade.symbol == t["symbol"],
                    CongressTrade.trade_date == t["trade_date"],
                    CongressTrade.direction == t["direction"],
                    CongressTrade.amount_min == t["amount_min"],
                    CongressTrade.amount_max == t["amount_max"],
                )
                .limit(1)
            )
            if dupe.scalar_one_or_none() is None:
                session.add(CongressTrade(**t))

    # Publish to SSE
    await broker.publish("scores_updated", {"ts": started.isoformat(), "count": len(snapshots)})
    await broker.publish("regime_updated", regime)
    if mock_writes:
        # Only announce a squeeze change when this tick actually wrote one —
        # otherwise the event carried count=0 while the table held real rows.
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
        # Isolated: a calendar-feed failure must not abort the rest of the tick.
        # Latch only on success so a transient failure retries next tick rather
        # than burning the 24h window.
        try:
            await _seed_calendar()
            _last_calendar_seed = started
        except Exception:
            logger.exception("calendar.seed_failed")

    # Hourly Telegram digest to premium users
    global _last_telegram_digest
    if _last_telegram_digest is None or (started - _last_telegram_digest).total_seconds() >= 3600:
        await _run_telegram_digest()
        _last_telegram_digest = started

    # Hourly trial-expiry enforcement: drop unpaid expired-trial users to Free.
    # Without this the trial converts to free Premium forever (zero conversion).
    global _last_trial_check
    if _last_trial_check is None or (started - _last_trial_check).total_seconds() >= 3600:
        # Isolated + latch-on-success. The downgrade is idempotent, so a retry
        # on the next tick after a transient DB failure is safe.
        try:
            await _downgrade_expired_trials()
            _last_trial_check = started
        except Exception:
            logger.exception("trial.downgrade_failed")

    # Hourly per-watchlisted-ticker news refresh (Premium tier feature).
    # Broad sweep + Massive cover the loud names; this fan-out covers the
    # tickers users specifically care about — small-caps, UK ADRs (BUR
    # etc.), niche names where the broad sweep doesn't surface anything.
    # Quota math: 200 unique tickers × 1/hour = 4.8k calls/day across
    # Massive + Finnhub (60/min), comfortably within the rate limits.
    global _last_watchlisted_news_refresh
    if _last_watchlisted_news_refresh is None or (started - _last_watchlisted_news_refresh).total_seconds() >= 3600:
        # Latch BEFORE dispatch, then run detached — same pattern as the daily
        # IndexNow / stale-audit jobs below. This fan-out makes 2 live HTTP
        # calls per symbol across hundreds of symbols, so awaiting it inline
        # WEDGED the worker: it blew the 60s tick watchdog, and wait_for
        # cancels tick() with CancelledError (a BaseException, so none of the
        # `except Exception` handlers here caught it) BEFORE the latch was set.
        # Every subsequent tick then re-entered and died the same way, so every
        # stage below this line (sheet refresh, universe refresh, digests,
        # newsletters, inbox) stopped running permanently.
        _last_watchlisted_news_refresh = started
        _spawn(_refresh_watchlisted_news())

    # Daily trial-drip emails (day 3 / 7 / 13, plus the T+30 lapsed no-card
    # trial win-back inside run_daily_drip) + 14-day re-engagement for
    # dormant non-trial users + 30/60/90-day post-cancellation win-back +
    # early-lifecycle activation nudges (first watchlist / first alert) +
    # post-conversion monthly→annual upgrade nudge + personal founder-touch to
    # high-value engaged signups + referral-milestone celebrations (3/5/10/25).
    # Worker-restart-safe — User.drip_state / winback_state / founder_touch_sent_at
    # track per-user per-stage delivery so no email fires twice. The gate +
    # latch live in _maybe_run_daily_drips: the 24h latch is set ONLY after a
    # fully successful run, so a transient failure (Neon cold-start, DB blip)
    # retries after a short backoff instead of silently skipping a whole day
    # of stage windows.
    await _maybe_run_daily_drips(started)

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
                    # Which symbols the sheet owns — consumed by the snapshot
                    # upsert so the market feed can't clobber their composite.
                    await _refresh_sheet_governed_symbols()
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
    # Isolated so a freeze failure can't abort every stage below it; the
    # once-per-day semantics are enforced in-DB, so a retry next tick is safe.
    #
    # Only AFTER the as_of session's close (see _SCORECARD_FREEZE_UTC_*): the
    # back-check computes `change_pct_1d_after` as
    # close(next trading day) / price_at_flag, so price_at_flag has to BE the
    # as_of session's close. Freezing at the top of the UTC day (the old
    # behaviour) captured the PREVIOUS session's close, making every published
    # "1-day" move actually span 2 sessions — and 4 across a long weekend.
    if (started.hour, started.minute) >= (
        _SCORECARD_FREEZE_UTC_HOUR,
        _SCORECARD_FREEZE_UTC_MINUTE,
    ):
        try:
            await _ensure_daily_scorecard(started.date())
        except Exception:
            logger.exception("scorecard.snapshot_failed")

    # Weekly universe refresh from Massive's reference API.
    # Only fires when a vendor key is set — discovers new IPOs and ETF
    # listings without needing manual ticker-list maintenance.
    global _last_universe_refresh
    if (settings.massive_api_key or settings.polygon_api_key) and (
        _last_universe_refresh is None
        or (started - _last_universe_refresh).total_seconds() >= 604800
    ):
        # Isolated + latch-on-success — a failed discovery must not burn the
        # 7-day window (or abort the stages below).
        try:
            await _refresh_universe()
            _last_universe_refresh = started
        except Exception:
            logger.exception("universe.refresh_failed")

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
    global _last_aggregates_refresh, _last_aggregates_failed_at
    aggregates_due = (
        _last_aggregates_refresh is None
        or (started - _last_aggregates_refresh).total_seconds() >= 86400
    )
    aggregates_backoff_elapsed = (
        _last_aggregates_failed_at is None
        or (started - _last_aggregates_failed_at).total_seconds()
        >= _AGGREGATES_RETRY_BACKOFF_SECONDS
    )
    if (settings.massive_api_key or settings.polygon_api_key) and (
        aggregates_due and aggregates_backoff_elapsed
    ):
        # Latch BEFORE dispatch so concurrent ticks can't double-run it; the
        # runner CLEARS the latch on failure (see _run_aggregates_refresh) so a
        # single bad benchmark fetch can't disable the trend/RS/momentum caches
        # for a full 24h.
        _last_aggregates_refresh = started
        _spawn(_run_aggregates_refresh())

    # End-of-day watchlist email digest. Fires once per UTC day shortly after
    # 21:00 UTC (~5pm ET, after US market close). Tracks last-sent date in
    # process memory to avoid double-fires within the same day. Worker restart
    # mid-day will re-fire — acceptable since users would rather get two than zero.
    # Trading days only — on Sat/Sun/market holidays there's no fresh close to
    # report, so a digest is pure noise (and shows stale prices). Reuses the
    # same market calendar the scorecard freeze + back-check run on.
    global _last_eod_digest_date
    today_str = started.strftime("%Y-%m-%d")
    if (
        started.hour >= 21
        and is_trading_day(started.date())
        and _last_eod_digest_date != today_str
    ):
        try:
            from app.services.email import run_eod_watchlist_digest
            async with session_scope() as eod_session:
                count = await run_eod_watchlist_digest(eod_session)
            if count:
                logger.info("eod_digest.sent count=%d", count)
            # Latch only on success — a transient failure must retry on the
            # next tick, not silently skip the whole day.
            _last_eod_digest_date = today_str
        except Exception:
            logger.exception("eod_digest.run_failed")

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
            # Latch only on success — otherwise one transient failure skips the
            # whole week. Per-user dedupe in run_weekly_newsletter makes the
            # retry safe.
            _last_weekly_newsletter_token = weekly_token
        except Exception:
            logger.exception("weekly_newsletter.run_failed")

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
            # Latch only on success — the DB-side last_sent_at still dedupes,
            # so retrying on the next tick can't double-send.
            _last_daily_newsletter_date = today_str
        except Exception:
            logger.exception("newsletter_daily.run_failed")

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
            # Latch only on success — a failed run retries on the next tick
            # instead of skipping the week. Telegram-side dedupe covers repeats.
            _last_seo_digest_token = seo_digest_token
        except Exception:
            logger.exception("seo_digest.weekly.failed")

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
            # Latch only on success so a transient failure retries on the next
            # tick rather than skipping the day's growth package entirely.
            _last_growth_tick_date = today_str
        except Exception:
            logger.exception("growth_bot.tick_failed")

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


_SCORECARD_FREEZE_UTC_HOUR = 21
_SCORECARD_FREEZE_UTC_MINUTE = 15
"""Earliest UTC wall-clock the daily top-10 may be frozen.

The US cash session closes at 16:00 ET — 20:00 UTC on EDT, 21:00 UTC on EST —
and 21:15 UTC clears the later of the two with a margin for the closing print
to land in the snapshot feed. It is also still the same calendar date in ET, so
`started.date()` remains the session date the frozen close belongs to.

Consequence: the freeze window is ~21:15-24:00 UTC instead of the whole UTC day.
A worker outage spanning that window means no scorecard row for that session —
deliberately preferred over publishing a mislabelled multi-session return."""

_AGGREGATES_RETRY_BACKOFF_SECONDS = 900
"""Wait before retrying the daily aggregates refresh after a failed run. Short
enough that a transient SPY/vendor blip costs minutes rather than the full 24h
the success latch would otherwise burn, long enough that a sustained vendor
outage isn't hammered every 60s tick."""

_SPY_BENCHMARK_ATTEMPTS = 3
"""Attempts at the SPY benchmark bars before giving up on an aggregates run.
SPY is a hard prerequisite (it's the RS denominator for every other ticker), so
one transient failure must not silently strand the caches."""

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

_MIN_DOLLAR_VOLUME_FOR_SCORECARD = 250_000.0
"""Liquidity floor for the public scorecard freeze. A high Tapeline Score on a
near-untradeable instrument (a bond/strategy ETF trading a few hundred dollars a
day) is not a pick anyone could act on, and its noisy next-day move drags the
back-check's alpha around for no real reason. Skip a candidate when its
dollar-volume (price*volume) is KNOWN and below this floor; a null volume is
kept (no read = no penalty), so the gate only ever removes genuinely
untradeable names. Forward-only — historical scorecard rows are never touched.
Mirrors routers/scanner.SCANNER_MIN_DOLLAR_VOLUME. Set 0 to disable."""


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

    `price_at_flag` is the baseline the back-check divides by, so it must be
    `today`'s close: the caller therefore only invokes this after the US
    session closes (see _SCORECARD_FREEZE_UTC_HOUR). Called earlier in the UTC
    day, `Ticker.price` is still the PREVIOUS session's close and every
    resulting "1-day" figure silently spans 2-4 sessions.

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

        # Pull a wider candidate pool (80) so the concentration + liquidity
        # filters have room to skip clustered/untradeable picks without running
        # out before reaching 10.
        # Freshness + data-quality floor — never freeze a stale ghost row OR a
        # corrupt (score>100 / emoji-symbol / <2-factor) row into the permanent
        # public scorecard record. (score IS NOT NULL is part of the floor.)
        # See app.services.ticker_freshness.
        from app.services.ticker_freshness import live_clauses
        _cand_stmt = select(Ticker)
        for _clause in await live_clauses(session):
            _cand_stmt = _cand_stmt.where(_clause)
        candidates = await session.execute(
            _cand_stmt.order_by(desc(Ticker.score)).limit(80)
        )

        sector_counts: dict[str, int] = {}
        skipped_zero_price = 0
        skipped_macro_hostile = 0
        skipped_sector_cap = 0
        skipped_illiquid = 0
        rank = 0

        for t in candidates.scalars().all():
            if rank >= 10:
                break

            if not t.price or t.price <= 0:
                # Don't poison the public record with $0-price entries — these
                # come from tier-restricted snapshot fields or partial fetches.
                skipped_zero_price += 1
                continue

            # Liquidity floor: don't freeze a near-untradeable name onto the
            # permanent public record. A high score on a bond/strategy ETF
            # trading a few hundred dollars a day isn't a pick anyone could act
            # on, and its noisy next-day move drags the back-check's alpha for
            # no real reason. Skip when dollar-volume is KNOWN and below the
            # floor; a null volume is kept (no read = no penalty). Same pick is
            # still on /scanner — this only governs the public scorecard.
            if (
                _MIN_DOLLAR_VOLUME_FOR_SCORECARD > 0
                and t.volume is not None
                and t.price is not None
                and t.price * t.volume < _MIN_DOLLAR_VOLUME_FOR_SCORECARD
            ):
                skipped_illiquid += 1
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
            "skipped_illiquid=%d sector_mix=%s",
            today, rank, skipped_zero_price, skipped_macro_hostile,
            skipped_sector_cap, skipped_illiquid, sector_counts,
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


_WATCHLISTED_NEWS_MAX_SYMBOLS = 200
"""Unique tickers per hourly watchlisted-news cycle. Was 1000, which at two
live HTTP calls + a DB round-trip per symbol could not finish inside the
hourly cadence (let alone the 60s tick watchdog it used to run under). 200 at
~0.5s pacing is a ~2-5 min run, comfortably inside the hour."""

_WATCHLISTED_NEWS_BUDGET_SECONDS = 15 * 60
"""Hard wall-clock ceiling for one cycle, checked between symbols. Guarantees
a cycle always ends well before the next hourly dispatch even if the vendor is
crawling; the unprocessed tail is simply picked up next hour."""

_WATCHLISTED_NEWS_PACING_SECONDS = 0.5
"""Sleep between symbols. Keeps this fan-out inside the shared Finnhub 60/min
free-tier budget alongside the fundamentals / insider / sector refreshes."""


async def _refresh_watchlisted_news() -> None:
    """Hourly per-watchlisted-ticker news refresh — Premium-tier feature.

    The 5-min broad sweep covers high-volume names. Long-tail tickers
    (small-caps, UK ADRs like BUR, niche ETFs) often never appear in the
    broad sweep because the wires prioritise trending US large-caps. This
    fan-out fetches per-ticker news for every symbol on every Premium-
    tier user's watchlist, using the Massive + Finnhub parallel merge.

    Runs DETACHED from tick() (see the dispatch site) because it is far
    slower than the 60s tick watchdog. Bounded three ways so an hourly
    cadence can always finish before the next one is due:
      - at most _WATCHLISTED_NEWS_MAX_SYMBOLS unique tickers per cycle;
      - a hard _WATCHLISTED_NEWS_BUDGET_SECONDS wall-clock budget, checked
        between symbols (a slow vendor can't make a cycle run for hours);
      - _WATCHLISTED_NEWS_PACING_SECONDS between symbols so the fan-out
        stays inside the Finnhub 60/min free-tier budget shared with the
        other refreshes.

    Inserts use the same per-article isolation pattern as `_refresh_news`
    so one bad row can't poison the rest. Logs `inserted` / `duplicate` /
    `failed` counts for the same observability reasons.
    """
    from app.models import User
    from app.models.watchlist import WatchlistItem
    from app.services.news_feed import fetch_news_for_ticker

    run_started = datetime.now(UTC)

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
                .limit(_WATCHLISTED_NEWS_MAX_SYMBOLS)
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
    processed = 0
    budget_hit = False
    for sym in symbols:
        if (datetime.now(UTC) - run_started).total_seconds() >= _WATCHLISTED_NEWS_BUDGET_SECONDS:
            budget_hit = True
            logger.warning(
                "watchlisted_news.budget_exhausted processed=%d of=%d budget=%ds",
                processed, len(symbols), _WATCHLISTED_NEWS_BUDGET_SECONDS,
            )
            break
        processed += 1
        # Pace the fan-out — this shares the Finnhub 60/min free-tier budget
        # with the fundamentals / insider / sector refreshes.
        if processed > 1:
            await asyncio.sleep(_WATCHLISTED_NEWS_PACING_SECONDS)
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
        "watchlisted_news.refreshed unique_tickers=%d processed=%d inserted=%d "
        "duplicate=%d failed=%d budget_hit=%s elapsed=%.1fs",
        len(symbols), processed, inserted, skipped_dup, failed, budget_hit,
        (datetime.now(UTC) - run_started).total_seconds(),
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


async def _maybe_run_daily_drips(started: datetime) -> None:
    """Daily lifecycle-email suite, gated + latched.

    LATCH-ON-SUCCESS (2026-07-18): `_last_drip_check` used to be set even
    when the run RAISED, so a single transient failure (e.g. a documented
    Neon cold-start) silently skipped the next 24h of drip processing.
    Every user inside a stage window during the failed run aged out and was
    permanently skipped — including the day-11 / day-13 / expired stages
    that carry the one-click signed Stripe checkout links. Now:

      - the 24h latch is set ONLY after every runner completed;
      - a failed run leaves the latch untouched and retries on the next
        tick once a 1h backoff (`_last_drip_failed_at`) has elapsed — the
        backoff keeps a persistent outage from hammering the DB/email
        provider every ~60s tick while still recovering within the hour;
      - retries are safe: every stage dedupes per-user via drip_state /
        winback_state / founder_touch_sent_at, so nothing double-sends.

    The stage windows themselves are 48h wide (see email.run_daily_drip),
    so even a full missed day can't age a user out of their stage.
    """
    global _last_drip_check, _last_drip_failed_at
    due = (
        _last_drip_check is None
        or (started - _last_drip_check).total_seconds() >= 86400
    )
    backoff_elapsed = (
        _last_drip_failed_at is None
        or (started - _last_drip_failed_at).total_seconds() >= 3600
    )
    if not (due and backoff_elapsed):
        return

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
            logger.info(
                "drip.sent day3=%d day7=%d day13=%d lapse30=%d",
                counts["day3"], counts["day7"], counts["day13"],
                counts.get("lapse30", 0),
            )
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
        # Do NOT latch — a failed run must retry, not burn the day.
        logger.exception("drip.run_failed")
        _last_drip_failed_at = started
        return

    _last_drip_check = started
    _last_drip_failed_at = None


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


async def _run_aggregates_refresh() -> None:
    """Run the daily aggregates refresh, un-latching it if it didn't succeed.

    The dispatch site latches `_last_aggregates_refresh` for 24h BEFORE
    spawning (so concurrent ticks can't double-run a ~12 minute job). That
    latch used to survive a failed run, so one bad SPY fetch left
    trend/RS/momentum served from the synthesised fallback for a full day —
    and on a cold start the caches simply stayed empty. Clearing the latch here
    hands the retry decision back to the tick gate, which re-tries after
    `_AGGREGATES_RETRY_BACKOFF_SECONDS`.
    """
    global _last_aggregates_refresh, _last_aggregates_failed_at
    try:
        succeeded = await _refresh_aggregates_cache()
    except Exception:
        logger.exception("aggregates.refresh_failed")
        succeeded = False

    if succeeded:
        _last_aggregates_failed_at = None
        return

    _last_aggregates_refresh = None
    _last_aggregates_failed_at = datetime.now(UTC)
    logger.error(
        "aggregates.refresh_unsuccessful — trend/RS/momentum caches NOT "
        "refreshed; retrying in %ds",
        _AGGREGATES_RETRY_BACKOFF_SECONDS,
    )


async def _refresh_aggregates_cache() -> bool:
    """
    Daily pre-fetch of OHLC aggregates for every ticker. Computes trend, RS,
    and momentum scores from the bars and populates the in-memory caches that
    polygon_feed.fetch_snapshots reads per tick.

    Returns True only when the run actually populated caches; False means the
    caller should NOT treat the 24h refresh as done (see
    `_run_aggregates_refresh`).

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

    # Fetch SPY first as the RS benchmark. Retried: SPY is a hard prerequisite
    # for the whole run, so a single transient vendor error must not cost the
    # day's caches.
    today = _d.today()
    start = today - _td(days=365)
    spy_bars: list[dict] | None = None
    for attempt in range(1, _SPY_BENCHMARK_ATTEMPTS + 1):
        try:
            spy_bars = await fetch_aggregates("SPY", from_date=start, to_date=today)
        except Exception:
            logger.exception(
                "aggregates.spy_fetch_failed attempt=%d/%d",
                attempt, _SPY_BENCHMARK_ATTEMPTS,
            )
            spy_bars = None
        if spy_bars and len(spy_bars) >= 63:
            break
        logger.warning(
            "aggregates.spy_insufficient_bars count=%d attempt=%d/%d",
            len(spy_bars) if spy_bars else 0, attempt, _SPY_BENCHMARK_ATTEMPTS,
        )
        spy_bars = None
        if attempt < _SPY_BENCHMARK_ATTEMPTS:
            await asyncio.sleep(5 * attempt)

    if not spy_bars:
        logger.error(
            "aggregates.spy_unavailable attempts=%d — aggregates refresh NOT "
            "completed (caches left as-is, run will be retried)",
            _SPY_BENCHMARK_ATTEMPTS,
        )
        return False

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
    # An empty result is a failure, not a successful no-op — don't let it latch
    # the 24h window and leave the caches stranded.
    return refreshed > 0


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


_SECTOR_BACKFILL_BATCH = 20
"""Rows written per short-lived transaction in _backfill_sectors. Small enough
that no connection is held across more than ~22s of Finnhub pacing."""


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

    async def _flush(batch: list[tuple[str, str]]) -> int:
        """Write one small batch in its own short-lived transaction."""
        if not batch:
            return 0
        try:
            async with session_scope() as session:
                for sym, target in batch:
                    await session.execute(
                        update(Ticker).where(Ticker.symbol == sym)
                        .values(sector=target)
                    )
            return len(batch)
        except Exception:
            logger.exception("sector_backfill.flush_failed size=%d", len(batch))
            return 0

    # Fetch + sleep OUTSIDE any session. This loop runs for ~46 minutes at the
    # 2500 cap; holding one write transaction (and its pooled connection) open
    # across all of it pinned a connection for the whole run and kept an
    # uncommitted write txn open against Neon. Now the network work happens
    # unsessioned and results land in short batched transactions.
    backfilled = 0
    pending: list[tuple[str, str]] = []
    for sym, asset_class in rows:
        try:
            profile = await fetch_company_profile(sym)
            raw_sector = (profile or {}).get("sector") if profile else None
            # Apply the canonical mapping at write time so storage matches
            # the heatmap's render-time grouping. If Finnhub returned no
            # sector, canonical_sector still routes by asset_class (e.g.
            # ETFs → Funds & ETFs) instead of leaving "Unknown" in the DB.
            pending.append((sym, canonical_sector(raw_sector, asset_class)))
        except Exception:
            logger.exception("sector_backfill.fetch_failed symbol=%s", sym)
        await asyncio.sleep(1.1)
        if len(pending) >= _SECTOR_BACKFILL_BATCH:
            backfilled += await _flush(pending)
            pending = []
    backfilled += await _flush(pending)

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
