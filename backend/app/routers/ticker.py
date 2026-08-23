"""GET /api/ticker/{symbol} — detailed single-ticker view with breakdown + news.

Also: GET /api/ticker/{symbol}/ratings — analyst ratings consensus from
Finnhub's aggregate recommendations. Premium-only — mirrors holdings.elite
gating. Lazy-loaded by the frontend so the main ticker page doesn't block on
the upstream rating call.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, get_session, is_sqlite
from app.models import (
    DailyScorecardEntry,
    EarningsEvent,
    NewsItem,
    SqueezeSetup,
    Ticker,
)
from app.models.news import exclude_mock_clause, tickers_match_clause
from app.services.auth import current_user_optional, current_user_required
from app.services.finnhub_feed import (
    fetch_analyst_ratings,
    fetch_basic_financials,
    fetch_insider_transactions,
)
from app.services.news_feed import fetch_news_for_ticker
from app.services.percentile import peer_percentiles
from app.services.symbols import clean_symbol
from app.services.tier import Tier, has_feature

router = APIRouter()
logger = logging.getLogger(__name__)

# --- News freshness strategy (incident fix 2026-05-31, rev 2) --------------
# /api/ticker MUST be fast: it backs both the SSR'd public /t/{symbol} page
# and the daily SEO audit, which HEADs ~1.1k of those pages. The previous
# design live-fetched news (Massive ∥ Finnhub — parallel upstream calls)
# synchronously inside the request. Even after the earlier
# fix today stopped holding a pooled DB connection across that fetch, the
# multi-second call — multiplied by the audit's concurrency AND the
# frontend's 2x SSR retry on slow responses — let in-flight requests pile up
# on the single small API machine and drove a latency death-spiral
# (2.8s → 20s → timeout). That tripped the frontend's 7s SSR timeout, so the
# /t/{symbol} pages 500'd (by design, as a "retry later" signal to Googlebot)
# during every audit window.
#
# Fix: serve news straight from the DB — the same warm cache /api/news reads,
# kept fresh by the worker (~every 5 min) plus EDGAR 8-Ks. The request path
# now makes ZERO upstream calls; it's pure indexed DB reads, sub-second under
# any load. Freshness for cold / long-tail tickers (e.g. BUR, which Massive
# serves stale) is preserved by an OPPORTUNISTIC background refresh that is:
#   • deduped per symbol     — never two concurrent refreshes for one symbol,
#   • throttled per symbol   — re-fetch at most once / NEWS_REFRESH_MIN_INTERVAL,
#   • globally capped         — ≤ MAX_CONCURRENT_NEWS_REFRESH in flight machine-wide,
#   • hard-timeout-bounded    — a wedged upstream can't hold an in-flight slot.
# So the audit's ~1.1k cold symbols can never spawn ~1.1k concurrent fetches:
# at most a small trickle drains in the background while every request that
# touched them has already returned.
NEWS_REFRESH_TIMEOUT_S = 12.0          # hard cap on a single background refresh
NEWS_REFRESH_MIN_INTERVAL_S = 600.0    # don't re-fetch the same symbol < 10 min apart
MAX_CONCURRENT_NEWS_REFRESH = 3        # machine-wide ceiling on background fetches

# Per-ticker headline read window + hard cap (incident fix 2026-06-01) ---------
# The headline lookup is `WHERE tickers LIKE '%SYM%' ORDER BY published_at DESC
# LIMIT 8`. The leading-wildcard LIKE can't use the tickers B-tree index, so
# Postgres serves the LIMIT by walking the published_at index newest→oldest and
# filtering each row until it collects 8. For a symbol that's RARE in recent
# news (TSLA, GME, NIO, …) that walk ran to the end of the table — a 30s+ hang
# that held a pooled connection the whole time; under fan-out (the SEO audit /
# a crawl) those holds exhausted the 30-slot pool and 500'd EVERY /t page. The
# window caps how far the walk can scan; the per-statement timeout is the
# backstop that kills any still-slow scan so the page degrades to no-news
# instead of hanging. (A symbol abundant in recent news — AMD, "F" — always
# found 8 immediately, which is why only a subset of tickers ever 500'd.)
NEWS_LOOKBACK_DAYS = 90                 # only scan the last N days of headlines
NEWS_QUERY_TIMEOUT_MS = 2500           # Postgres per-statement cap on the scan

# Per-process state for the background refresh (one set of these per API worker).
_news_refresh_inflight: set[str] = set()          # symbols currently mid-refresh
_news_last_refresh_at: dict[str, datetime] = {}   # symbol -> last refresh start (UTC)
_news_bg_tasks: set[asyncio.Task] = set()         # strong refs so tasks aren't GC'd


async def _refresh_news_bg(symbol: str) -> None:
    """Background, fire-and-forget news refresh for one symbol.

    Runs OFF the request path: live-fetches the feed (hard-capped via
    wait_for so a wedged upstream releases its in-flight slot), then
    id-deduped-inserts any unseen rows in its own short-lived session and
    COMMITS (the request path only reads — this is what actually persists new
    articles). Every failure mode is swallowed: this is opportunistic
    freshness, never load-bearing.
    """
    try:
        live = await asyncio.wait_for(
            fetch_news_for_ticker(symbol, limit=8), timeout=NEWS_REFRESH_TIMEOUT_S
        )
        if not live:
            return
        async with SessionLocal() as session:
            inserted = 0
            for it in live:
                try:
                    existing = await session.execute(
                        select(NewsItem).where(NewsItem.id == it["id"])
                    )
                    if existing.scalar_one_or_none() is None:
                        session.add(NewsItem(**it))
                        inserted += 1
                except Exception:
                    pass
            if inserted:
                try:
                    await session.commit()
                except Exception:
                    try:
                        await session.rollback()
                    except Exception:
                        pass
    except Exception:
        logger.warning("ticker.news_bg_refresh_failed symbol=%s", symbol)
    finally:
        _news_refresh_inflight.discard(symbol)


def _maybe_refresh_news(symbol: str) -> None:
    """Opportunistically schedule a background news refresh for `symbol`.

    Cheap, synchronous, non-blocking guard: applies per-symbol dedup + a
    per-symbol throttle + a global concurrency ceiling, then spawns a detached
    task and returns immediately. The request never waits on the refresh, and
    under heavy fan-out (the SEO audit) the global ceiling caps machine-wide
    background work regardless of request volume.
    """
    if symbol in _news_refresh_inflight:
        return
    now = datetime.now(UTC)
    last = _news_last_refresh_at.get(symbol)
    if last is not None and (now - last).total_seconds() < NEWS_REFRESH_MIN_INTERVAL_S:
        return
    if len(_news_refresh_inflight) >= MAX_CONCURRENT_NEWS_REFRESH:
        return  # at capacity — skip; the DB news we already served stands
    _news_refresh_inflight.add(symbol)
    _news_last_refresh_at[symbol] = now
    task = asyncio.create_task(_refresh_news_bg(symbol))
    _news_bg_tasks.add(task)
    task.add_done_callback(_news_bg_tasks.discard)


async def _fetch_ticker_news(symbol: str) -> list[dict]:
    """Newest ≤8 headlines mentioning `symbol` — bounded so it can never wedge.

    Two guards added after the 2026-06-01 incident (see NEWS_LOOKBACK_DAYS):
      • a recency window caps how far the published_at-DESC index walk can scan
        when `symbol` is rare in recent news (the root cause of the 30s hangs),
      • a short per-statement timeout (Postgres only — SQLite ignores it) is the
        backstop: a still-slow scan is cancelled server-side and we serve the
        page with no news instead of 500ing it.
    Runs in its OWN short session so a slow or cancelled headline scan can never
    hold the core read's connection or corrupt the core ticker payload. Every
    failure mode degrades to [] — news is never load-bearing for the page.
    """
    try:
        async with SessionLocal() as session:
            # Bound the scan server-side first (Postgres); harmless no-op skip on
            # SQLite, which has no statement_timeout.
            if not is_sqlite():
                await session.execute(
                    text(f"SET LOCAL statement_timeout = '{NEWS_QUERY_TIMEOUT_MS}ms'")
                )
            cutoff = datetime.now(UTC) - timedelta(days=NEWS_LOOKBACK_DAYS)
            rows = (
                await session.execute(
                    select(NewsItem)
                    .where(
                        # Never surface fabricated mock headlines (LEGAL
                        # read-path invariant). See models.news.exclude_mock_clause.
                        exclude_mock_clause(),
                        # Exact comma-delimited token match: 'GM' must NOT match
                        # a 'GME'-only row. See models.news.tickers_match_clause.
                        tickers_match_clause(symbol),
                        NewsItem.published_at >= cutoff,
                    )
                    .order_by(desc(NewsItem.published_at))
                    .limit(8)
                )
            ).scalars().all()
        return [
            {
                "id": n.id,
                "title": n.title,
                "publisher": n.publisher,
                "published_at": n.published_at.isoformat() if hasattr(n.published_at, "isoformat") else str(n.published_at),
                "url": n.url,
                "sentiment": getattr(n, "sentiment", None),
            }
            for n in rows
        ]
    except Exception:
        # Slow scan (timed out), aborted txn, or any read error → no news.
        logger.warning("ticker.news_query_degraded symbol=%s", symbol)
        return []


def _next_utc_midnight() -> datetime:
    """Start of the next UTC day — when the daily look-up counter rolls over.

    services.usage keys the durable counter on the UTC date
    (lookups_reset_on), so "resets at the next UTC midnight" is exact, not an
    estimate. Derived rather than stored: there is no reset-timestamp column.
    """
    now = datetime.now(UTC)
    return (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _lookup_meter_payload(meter: dict) -> dict:
    """Shape the freemium look-up meter for the /api/ticker 200 response.

    These numbers are ALREADY computed by consume_ticker_lookup on every
    metered look-up; until now they were used only to decide 402-vs-200 and
    then discarded. That meant a free user's first contact with metering was
    the hard wall at the cap, with no warning at 9, 10 or 11 — a normal limit
    presented as a punishment. Returning the meter lets the page state the
    user's own usage calmly and factually well before the wall.

    `limit is None` is the UNLIMITED sentinel (paid tiers, active no-card
    trial, and the first-session grace window). There is no cap to report, so
    remaining and resets_at are None too — the counter that would reset isn't
    running for that caller.
    """
    cap = meter.get("limit")
    return {
        "used": meter.get("used", 0),
        "limit": cap,
        "remaining": meter.get("remaining"),
        "resets_at": None if cap is None else _next_utc_midnight().isoformat(),
    }


def _key_stats_payload(t: Ticker, next_earnings_date: date | None) -> dict:
    """The summary block a reader expects at the top of a ticker page.

    One flat, ordered group so the frontend can render it directly instead of
    reaching into the root payload for some rows and a nested object for the
    rest. The order here IS the display order (previous close → open → day
    range → 52-week range → volumes → market cap → valuation → earnings →
    dividend). price / volume / market_cap are repeated from the root rather
    than moved, so no existing consumer breaks.

    EVERY field is nullable and stays nullable end-to-end. ~72% of the universe
    has no price or volume read at all, so the bar-derived values are
    legitimately absent for most rows, and Finnhub has no fundamentals coverage
    for most ETFs and funds. Null renders as an em-dash. Substituting 0 for "we
    don't have it" would publish a fabricated statistic, which this product must
    never do — so there is no `or 0` anywhere below, deliberately.

    Three rows a reader might expect are ABSENT rather than approximated:
      • bid / ask — needs a level-1 quote feed we don't subscribe to,
      • the 1-year analyst price target — not on our Finnhub plan,
      • the forward dividend AMOUNT — we source the yield, not the declared
        rate; multiplying yield by price would be a number we invented rather
        than one we were given, so only `dividend_yield` is reported.

    `next_earnings_date` is passed in because it is the only stat here that does
    not live on the ticker row — see the earnings read in ticker_detail.
    """
    return {
        "price": t.price,
        "previous_close": t.previous_close,
        "day_open": t.day_open,
        # Day range and 52-week range stay as flat low/high pairs rather than
        # nested objects: either bound can be present without the other, and the
        # "low – high" string is the frontend's to compose.
        "day_low": t.day_low,
        "day_high": t.day_high,
        "week52_low": t.week52_low,
        "week52_high": t.week52_high,
        "volume": t.volume,
        "avg_volume_30d": t.avg_volume_30d,
        "market_cap": t.market_cap,
        "beta": t.beta,
        "pe_ttm": t.pe_ttm,
        "eps_ttm": t.eps_ttm,
        # Dates are ISO strings, matching how updated_at and news.published_at
        # are already serialised on this endpoint.
        "next_earnings_date": (
            next_earnings_date.isoformat() if next_earnings_date is not None else None
        ),
        "dividend_yield": t.dividend_yield,
        "ex_dividend_date": (
            t.ex_dividend_date.isoformat() if t.ex_dividend_date is not None else None
        ),
    }


# ── This ticker on our public record ───────────────────────────────────────
# `daily_scorecard` is the frozen record of what the algo flagged each day: one
# row per (date, symbol) for that day's top-10, plus the next session's outcome
# written afterwards by the back-check job. Competitors all converge on the
# same peer-relative grammar for the market's facts; none of them publishes
# what its OWN calls did next. This block is that, for one ticker.
#
# HORIZON — the table stores a NEXT-SESSION outcome and nothing else
# (price_next_day / change_pct_1d_after / spy_change_pct_1d / alpha_vs_spy).
# There is no 1-week, 1-month or 3-month column anywhere in the schema, so the
# payload names the horizon explicitly and never implies a longer one.
#
# LOSSES ARE NEVER FILTERED. A record that drops its losers is marketing, not a
# record: `resolved_count`, `beat_spy_count` and `median_alpha_vs_spy` are
# taken over EVERY resolved row, and every row is present in `flags`.

# Rows read per symbol. Mirrors the per-symbol scorecard endpoint's default;
# one flag per trading day is the ceiling, so a year of history fits.
_FLAG_ROWS_READ_CAP = 365
# Rows serialised inline on the ticker page. The full history lives on
# /scorecard; this block is a decision aid, not an archive. Truncation is
# disclosed (`flags_truncated`) rather than silent.
_FLAG_ROWS_SERIALISED_CAP = 60


def _flag_record_payload(
    rows: list[DailyScorecardEntry], *, can_see_live: bool
) -> dict:
    """Our own record on ONE ticker: every flag, most recent first, + a summary.

    `rows` is already ordered as_of DESC. `can_see_live` mirrors the scorecard
    router's tier gate — see the row-visibility note below.

    The never-flagged case (~8,400 of 8,879 symbols) is the COMMON one, not an
    error: it returns flag_count 0, an empty `flags` list, and a null median.
    Zero is a true count here; the median is genuinely unknown, so it is null.

    ARITHMETIC — deliberately UNFILTERED, and deliberately different from
    /api/scorecard/*. That endpoint drops rows whose 1-day move exceeds
    scorecard._OUTLIER_PCT_THRESHOLD from its averages, because raw vendor
    closes occasionally carry unadjusted-split prices that produce
    market-impossible moves. Here the summary counts every resolved row and
    takes the median over all of them — the median is already robust to a lone
    bad print, and this block's entire claim is that nothing is filtered out of
    it. The suspect rows are COUNTED and disclosed instead
    (`suspect_outlier_count`, with the shared threshold echoed alongside it) so
    a reader can see when a number leans on a print we ourselves distrust. The
    threshold is imported, not re-declared, so the two surfaces can never drift
    on what "suspect" means.

    ROW VISIBILITY — the summary is tier-invariant (it is the trust signal, and
    it is already public on /api/scorecard/symbol/{symbol}), but the row list
    reuses the scorecard router's delay for non-paying viewers. Without it this
    public, anonymous, un-metered endpoint would be a way to read today's
    top-10 by walking ticker pages, silently undoing the gate that keeps the
    live scanner the actual product. The delay is on RECENCY, never on outcome:
    a losing flag inside the window is shown exactly like a winning one. Both
    the delay and the number of rows it withholds are stated in the payload
    (`flags_delay_days`, `flags_hidden_recent`) so the page can say what is
    missing instead of looking broken.
    """
    # Imported from the scorecard router rather than re-declared so the delay
    # window, the entitlement test and the suspect-move threshold have exactly
    # one definition each across the two surfaces that publish this record.
    from app.routers.scorecard import _FREE_DELAY_DAYS, _OUTLIER_PCT_THRESHOLD

    resolved = [r for r in rows if r.alpha_vs_spy is not None]
    # Strictly greater: an alpha of exactly 0.0 matched SPY, it did not beat
    # it. Same test the scorecard summary uses.
    beat = [r for r in resolved if r.alpha_vs_spy > 0]
    suspect = [
        r
        for r in resolved
        if r.change_pct_1d_after is not None
        and abs(r.change_pct_1d_after) > _OUTLIER_PCT_THRESHOLD
    ]

    if can_see_live:
        visible = rows
    else:
        cutoff = datetime.now(UTC).date() - timedelta(days=_FREE_DELAY_DAYS)
        visible = [r for r in rows if r.as_of <= cutoff]
    shown = visible[:_FLAG_ROWS_SERIALISED_CAP]

    dates = [r.as_of for r in rows]
    return {
        # Structured + a printable label. The record covers ONE session after
        # the flag and nothing beyond it.
        "horizon": "next_session",
        "horizon_label": "next trading session",
        "flag_count": len(rows),
        "resolved_count": len(resolved),
        "beat_spy_count": len(beat),
        "median_alpha_vs_spy": (
            median([r.alpha_vs_spy for r in resolved]) if resolved else None
        ),
        "suspect_outlier_count": len(suspect),
        "suspect_outlier_threshold_pct": _OUTLIER_PCT_THRESHOLD,
        "first_flagged_on": min(dates).isoformat() if dates else None,
        "last_flagged_on": max(dates).isoformat() if dates else None,
        "flags": [
            {
                "as_of": r.as_of.isoformat(),
                "rank": r.rank,
                # Belt-and-suspenders clamp, mirroring the scorecard router:
                # corrupt legacy rows stored raw factor values > 100 here.
                "score_at_flag": (
                    min(r.score_at_flag, 100.0)
                    if r.score_at_flag is not None
                    else None
                ),
                "price_at_flag": r.price_at_flag,
                "price_next_day": r.price_next_day,
                "change_pct_1d_after": r.change_pct_1d_after,
                "spy_change_pct_1d": r.spy_change_pct_1d,
                "alpha_vs_spy": r.alpha_vs_spy,
                # None = the next session has not been back-checked yet, which
                # is NOT the same as "did not beat SPY".
                "beat_spy": None if r.alpha_vs_spy is None else r.alpha_vs_spy > 0,
            }
            for r in shown
        ],
        # 0 is a real value here (no delay applies to this caller), not a
        # stand-in for unknown.
        "flags_delay_days": 0 if can_see_live else _FREE_DELAY_DAYS,
        "flags_hidden_recent": len(rows) - len(visible),
        "flags_truncated": len(visible) > len(shown),
    }


def _client_ip(request: Request) -> str | None:
    """Real client IP behind Fly's edge proxy. Mirrors routers/auth +
    services/rate_limit: request.client.host is the proxy's internal peer (the
    SAME for every external visitor), so prefer the leftmost X-Forwarded-For
    entry (the original client). Used to key the anonymous lookup meter."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("/{symbol}")
async def ticker_detail(symbol: str, request: Request) -> dict:
    """Complete view of a single ticker — score breakdown, squeeze status, news.

    Freemium metering (added 2026-06-20): a "lookup" is one of these detailed
    views. Pro / Premium / active-trial callers are never metered. A logged-in
    FREE user gets tier.FREE_DAILY_LOOKUPS per UTC day; an anonymous (no-account)
    caller gets tier.ANON_DAILY_LOOKUPS per IP per day. Over-cap callers get a
    402 per the shared API contract (error "free_lookup_limit" for free users,
    "signup_required" for anon). The lookup is only counted AFTER the symbol is
    confirmed to resolve to a real ticker, so a 404/invalid symbol never burns
    the caller's daily budget.

    The 200 response also carries the meter as `lookups`
    (used / limit / remaining / resets_at) so the client can show the count
    approaching the cap rather than only discovering it at the 402. See
    _lookup_meter_payload.

    `key_stats` (added 2026-08-22) is the summary block a reader expects at the
    top of a ticker page — previous close, open, day range, 52-week range,
    volumes, market cap, beta, P/E, EPS, next earnings date, dividend yield,
    ex-dividend date. Every field is nullable; see _key_stats_payload. All but
    the earnings date read straight off the ticker row already loaded above, so
    the block costs no extra query; the earnings date is one indexed LIMIT 1
    against calendar_events.earnings_events inside the same short txn, which
    keeps the rev2 connection discipline intact.

    `peer_percentiles` and `flag_record` (added 2026-08-22) are what turn this
    from a grid of raw fields into a decision aid. key_stats states the
    market's facts; these two locate them.

      • `peer_percentiles` places the composite and each of the six
        sub-factors against the ticker's sector peers, and ALWAYS prints the
        denominator it used ("91st percentile of Health Care, n=763"). Where
        we cannot rank honestly — too few covered peers, or no value of our
        own — the percentile is null and carries a `reason` instead of a
        manufactured number. Tickers whose sector is null / "Uncategorized" /
        "Unknown" / "N/A" are compared against the whole covered universe and
        the label says exactly that. One aggregate query; see
        services/percentile.py for the peer rule, the MIN_PEERS floor and the
        measured cost.

      • `flag_record` is this ticker's history on our own public scorecard —
        every time we flagged it, most recent first, with the next session's
        outcome, plus a summary (how many times, how many resolved, how many
        beat SPY, median alpha). Losses are never filtered out. The record
        holds a NEXT-SESSION outcome only and says so; ~8,400 of 8,879 symbols
        return the clean never-flagged state. One indexed read; see
        _flag_record_payload for the arithmetic and the row-visibility gate.

    Connection + latency discipline (incident fix 2026-05-31, rev 2): this
    endpoint backs the SSR'd public /t/{symbol} page and the daily SEO audit
    that HEADs ~1.1k of them, so it MUST be fast and cheap. It does only
    indexed DB reads in a SINGLE short txn (connection released on exit) and
    makes NO upstream calls in the request path — news is served from the same
    warm DB cache /api/news reads (worker-refreshed ~every 5 min + EDGAR 8-Ks).
    A bounded, deduped, throttled background task (see _maybe_refresh_news)
    keeps long-tail tickers fresh without ever blocking the response or letting
    load pile up. `expire_on_commit=False` (see app.db) keeps the ORM objects
    readable after the `async with` closes, so building the payload outside the
    txn is safe.

    History: the news fetch used to run inline. First it held a pooled
    connection across the multi-second Massive→Finnhub chain →
    QueuePool exhaustion. Then, after the connection was released but the fetch
    stayed inline, the multi-second call (× audit concurrency × the frontend's
    2x SSR retry) drove a latency death-spiral that 500'd the SSR pages. Both
    failure modes are gone now that the request path touches only the DB.
    """
    # Validate the symbol SHAPE before touching the DB — junk like "🏆 IVV" (a
    # legacy ghost row may match it exactly) 404s instead of rendering a
    # fabricated page + a duplicate-content /t/🏆 IVV URL for Google.
    # clean_symbol also strips + uppercases. Mirrors the ingestion chokepoint in
    # sheet_feed. (Re-applied after a concurrent ticker.py revert dropped it.)
    cleaned = clean_symbol(symbol)
    if cleaned is None:
        raise HTTPException(404, f"Ticker {symbol!r} is not a valid symbol")
    symbol = cleaned

    # Single short read txn: core ticker + squeeze (both indexed point lookups).
    # The pooled connection is checked out only for these, then returned on
    # context exit. News is read separately afterward (its own bounded session)
    # so a slow headline scan can never hold THIS connection — no upstream call
    # ever holds it either.
    async with SessionLocal() as session:
        t = (
            await session.execute(select(Ticker).where(Ticker.symbol == symbol))
        ).scalar_one_or_none()
        if t is None:
            raise HTTPException(404, f"Ticker {symbol} not in scanner universe")
        # Corruption guard: the composite is clamped 0-100 at every write path
        # (score.py:compute_tapeline_composite), so a score > 100 can only be a
        # legacy pre-clamp ghost that dropped out of the universe and was never
        # re-scored (e.g. MCW=104). Don't serve it as a real conviction page —
        # it would show an impossible score and overstate a stale ghost. 404
        # keeps this consistent with public_top_tickers (which excludes
        # score > 100 from the sitemap), so Google is never pointed at a URL
        # that then 404s. A genuinely-current ticker can never trip this.
        if t.score is not None and t.score > 100:
            raise HTTPException(404, f"Ticker {symbol} not in scanner universe")

        # ── Freemium daily-lookup metering ──────────────────────────────────
        # Only NOW that the symbol is confirmed to be a real, servable ticker do
        # we charge a lookup against the caller's daily budget — a 404 above
        # never reaches here, so an invalid/missing symbol never burns budget.
        # Pro/Premium/active-trial callers are uncapped (consume_* returns
        # allowed=True with no increment). Over-cap free/anon callers get a 402
        # per the shared contract (the frontend renders an upgrade / sign-up
        # wall). We resolve the caller in THIS short read txn (sub-ms auth read)
        # — the connection is still released on context exit before the news
        # fetch, preserving the rev2 connection discipline above.
        from app.services.usage import consume_ticker_lookup

        user = await current_user_optional(request, session)
        # Anonymous callers are NOT metered on this endpoint. The public
        # /t/{symbol} SEO pages are server-rendered from the single frontend
        # machine, so a per-IP anon cap here counted our OWN renders and 402'd
        # every ticker page after the first couple — the whole /t/ surface 500'd.
        # That data is meant to be public for SEO anyway. Anonymous "sign up to
        # keep looking" gating, if we want it, belongs as a client-side prompt on
        # the page itself, not on this shared SSR/public endpoint. Logged-in FREE
        # users are still capped (durable per-user counter); Pro/Premium/active-
        # trial remain uncapped. (consume_anon_lookup stays in services.usage as
        # a dormant utility for that future client-side gate.)
        #
        # The meter is also RETURNED (see `lookups` in the payload) so the
        # ticker page can show the user where they stand before the wall,
        # instead of the cap arriving as a surprise 402. Anonymous callers
        # aren't metered here, so `lookups` stays None for them.
        lookups_payload: dict | None = None
        if user is not None:
            meter = await consume_ticker_lookup(session, user)
            if not meter["allowed"]:
                # Free user out of daily look-ups — the conversion wall. Log the
                # cap hit (fire-and-forget; only free tiers reach allowed=False,
                # and record_cap_hit refuses paid tiers anyway) before the 402.
                from app.services.cap_events import record_cap_hit

                await record_cap_hit(session, user.id, "daily_lookups", user.tier)
                raise HTTPException(
                    402,
                    detail={
                        "error": "free_lookup_limit",
                        "used": meter["used"],
                        "limit": meter["limit"],
                        "tier": "free",
                    },
                )
            lookups_payload = _lookup_meter_payload(meter)
            # Activation (Growth Playbook §4.2): viewing a ticker's full six-factor
            # breakdown IS the core "aha" — seeing WHY a stock scores what it does —
            # so it counts as activation, not only a watchlist add. Anonymous SSR
            # renders never reach here (user is None above), so only real logged-in
            # views stamp. Idempotent (guarded on NULL, never overwritten → measures
            # time-to-value). Own commit: consume_ticker_lookup already committed any
            # meter increment, and the main ticker fetch below doesn't commit.
            if user.activated_at is None:
                user.activated_at = datetime.now(UTC)
                await session.commit()

        sq = (
            await session.execute(
                select(SqueezeSetup).where(SqueezeSetup.symbol == symbol)
            )
        ).scalar_one_or_none()

        # Next scheduled earnings date — the one key stat that does NOT live on
        # the ticker row. calendar_events.earnings_events has been populated in
        # prod all along (the worker's _seed_calendar replaces the whole window
        # daily) and was simply never joined here, so the ticker page had no
        # earnings date at all.
        #
        # `>= today` is the whole point: the table holds a rolling window, and
        # the row a caller wants is the NEXT report, never the last one. Taking
        # the earliest remaining row is what makes it "next"; without the filter
        # a ticker that reported yesterday would show yesterday as upcoming.
        # UTC to match every other date boundary on this endpoint (the lookup
        # meter's reset, the news window) — the machines run UTC.
        #
        # Read from the events table rather than tickers.next_earnings_date:
        # that column is the denormalized mirror for bulk scanner reads, while
        # this endpoint serves one symbol and can afford the authoritative read,
        # so it can never serve a value the mirror hasn't caught up on. Indexed
        # equality on `symbol` then an ordered LIMIT 1 — cheap enough to stay
        # inside this same short txn, adding no connection and no round trip
        # beyond the two already here.
        today = datetime.now(UTC).date()
        next_earnings_date = (
            await session.execute(
                select(EarningsEvent.report_date)
                .where(
                    EarningsEvent.symbol == symbol,
                    EarningsEvent.report_date >= today,
                )
                .order_by(EarningsEvent.report_date)
                .limit(1)
            )
        ).scalar_one_or_none()

        # ── The two decision-aid blocks ─────────────────────────────────────
        # Both run LAST in this txn and both degrade to None rather than
        # raising. This endpoint backs the SSR'd public /t/{symbol} page; a
        # 500 there is the documented disaster mode (see the connection +
        # latency note above), and neither block is load-bearing for the
        # market facts the page already has in hand. In Postgres a failed
        # statement aborts the whole transaction, so nothing that matters may
        # follow these — which is why they are last.
        #
        # NOTE for the renderer: `flag_record: null` means "we could not read
        # the record", which is NOT the same as a record with flag_count 0 —
        # that one means "we have never flagged this ticker". Do not collapse
        # the two into one empty state.

        # Our own record on this ticker. Indexed read:
        # ix_daily_scorecard_symbol_as_of serves the equality on `symbol` AND
        # the as_of DESC ordering out of one B-tree, so it stays cheap as the
        # table grows. 720 rows across 408 symbols today, so the 365-row cap is
        # nowhere near binding; it is a ceiling, not a filter.
        flag_record: dict | None = None
        try:
            from app.routers.scorecard import _can_see_live_picks

            flag_rows = list(
                (
                    await session.execute(
                        select(DailyScorecardEntry)
                        .where(DailyScorecardEntry.symbol == symbol)
                        .order_by(desc(DailyScorecardEntry.as_of))
                        .limit(_FLAG_ROWS_READ_CAP)
                    )
                ).scalars().all()
            )
            flag_record = _flag_record_payload(
                flag_rows, can_see_live=_can_see_live_picks(user)
            )
        except Exception:
            logger.warning("ticker.flag_record_degraded symbol=%s", symbol)

        # Where this ticker sits among its peers. ONE aggregate pass over the
        # peer group yields the percentile AND the denominator for the
        # composite plus all six sub-factors; see services/percentile.py for
        # the peer-group rule, the MIN_PEERS floor and the measured cost. A
        # page that cannot locate its numbers must still render the numbers.
        percentiles: dict | None = None
        try:
            percentiles = await peer_percentiles(session, t)
        except Exception:
            logger.warning("ticker.percentiles_degraded symbol=%s", symbol)

        # News is fetched separately, AFTER this core read txn closes (see
        # _fetch_ticker_news) — its own bounded session so a slow/timed-out
        # headline scan can never hold THIS pooled connection or affect the
        # core payload. This is what stops the 2026-06-01 pool-exhaustion
        # death-spiral at the root.

    # Per-ticker headlines — newest ≤8 mentioning this symbol. Bounded (recency
    # window + Postgres statement timeout) and isolated, so a slow scan degrades
    # to [] instead of 500ing the page or wedging the pool (incident 2026-06-01).
    news_payload = await _fetch_ticker_news(symbol)

    # Opportunistic, non-blocking freshness top-up for cold / long-tail tickers.
    # Bounded + deduped + throttled inside the helper; returns instantly so the
    # response (built from the DB read above) is never delayed by an upstream.
    _maybe_refresh_news(symbol)

    return {
        "symbol": t.symbol,
        "name": t.name,
        "sector": t.sector,
        "asset_class": t.asset_class,
        "price": t.price,
        "score": t.score,
        "signal": t.signal,
        "confidence_pct": t.confidence_pct,
        "change_pct_1d": t.change_pct_1d,
        "change_pct_5d": t.change_pct_5d,
        "change_pct_1m": t.change_pct_1m,
        "volume": t.volume,
        "reason": t.reason,
        # The key-statistics summary block. Nullable throughout — a missing
        # value is a null here and an em-dash on the page, never a zero. See
        # _key_stats_payload for what is deliberately omitted and why.
        "key_stats": _key_stats_payload(t, next_earnings_date),
        # Where each of those readings SITS. A number is only a decision aid
        # once it is locatable, and every entry here carries the denominator it
        # was computed against plus the peer group actually used. None with a
        # `reason` where we refuse to rank — see services/percentile.py. The
        # whole block is null if the aggregate failed; the page still renders
        # the raw values.
        "peer_percentiles": percentiles,
        # What our own calls on this ticker did next — wins and losses, never
        # filtered, next-session horizon only. See _flag_record_payload. Null
        # here means the read failed, NOT "never flagged" (that is a present
        # block with flag_count 0).
        "flag_record": flag_record,
        # DISCLOSURE BOUNDARY. Each entry carries the factor's VALUE and its
        # LABEL, and deliberately no "weight". This endpoint has no auth
        # dependency — it backs the public SSR ticker pages, the badge and the
        # SEO pages, so anyone could curl it — and it used to return
        # {"weight": 25} … {"weight": 10} keyed to the factor names, i.e. the
        # exact internal weight vector PR #342 stripped from the public site.
        # The factor NAMES and their ORDERING are public; the numbers are not.
        # Do not add a weight key back here. If a signed-in surface ever needs
        # the numbers, serve them from an authenticated endpoint instead.
        "breakdown": {
            "trend": {"value": t.sub_trend, "label": "Trend"},
            "rs": {"value": t.sub_rs, "label": "Relative strength"},
            "fundamentals": {"value": t.sub_fundamentals, "label": "Fundamentals"},
            "smart_money": {"value": t.sub_smart_money, "label": "Smart money"},
            "macro": {"value": t.sub_macro, "label": "Macro"},
            "momentum": {"value": t.sub_momentum, "label": "Momentum"},
        },
        "squeeze": None if sq is None else {
            "spike_score": sq.spike_score,
            "squeeze_days": sq.squeeze_days,
            "volume_multiple": sq.volume_multiple,
            "obv_trend": sq.obv_trend,
            "breakout_type": sq.breakout_type,
            "suggested_window": sq.suggested_window,
            "reason": sq.reason,
        },
        "news": news_payload,
        # Freemium daily look-up meter for THIS caller (null for anonymous
        # callers, who aren't metered on this endpoint). limit=null means
        # unmetered — paid tier, active trial, or first-session grace.
        "lookups": lookups_payload,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@router.get("/{symbol}/ratings")
async def ticker_ratings(symbol: str, request: Request) -> dict:
    """Analyst ratings consensus + recent events for a ticker — Premium-only.

    Trial users (Premium for the duration of the 14-day card-required trial)
    and paid Premium subscribers see the widget. Free + Pro users hit the Paywall on the frontend; this
    endpoint also enforces the gate so the data can't be sniffed via direct
    API call.

    Lazy-loaded — the main ticker payload doesn't include this so the page
    paints before the upstream ratings call completes. When Finnhub has no
    coverage, the response shape stays the same with an empty events list so
    the frontend renders a clean empty state.
    """
    # Resolve + tier-gate the user in a SHORT-LIVED session that is released
    # BEFORE the upstream ratings call. Holding a pooled DB connection across
    # the multi-second upstream is what exhausted the pool and downed the API on
    # 2026-06-01 — the same anti-pattern the ticker_detail rev2 fix removed for
    # the news fetch. The auth read is sub-ms; the connection must not stay
    # pinned for the duration of the upstream request. See app/db.py.
    async with SessionLocal() as session:
        user = await current_user_required(request, session)
        allowed = has_feature(Tier(user.tier), "ratings.analyst")
    if not allowed:
        raise HTTPException(403, "Analyst consensus requires Premium tier")
    return await fetch_analyst_ratings(symbol.upper())


@router.get("/{symbol}/financials")
async def ticker_financials(symbol: str) -> dict:
    """Per-ticker financial metrics from Finnhub.

    Returns P/E, net margin, ROE, EPS growth, revenue growth, debt-to-equity.
    Public — same access surface as /{symbol} and /{symbol}/history. Cached
    7 days at the adapter layer; fundamentals don't change tick-to-tick.

    Most ETFs and funds have no Finnhub fundamentals coverage. The response
    keeps a stable shape (`available: false`, empty `metrics`) so the
    frontend can render a clean empty state instead of broken null fields.
    """
    sym = symbol.upper()
    metrics = await fetch_basic_financials(sym)
    return {
        "symbol": sym,
        "available": metrics is not None,
        "metrics": metrics or {},
    }


@router.get("/{symbol}/insider")
async def ticker_insider(
    symbol: str,
    request: Request,
    days_back: int = 90,
) -> dict:
    """Recent Form 4 insider transactions for a ticker — Premium only.

    Returns insider buys/sells from Finnhub for the last `days_back` days
    (default 90, clamped to [1, 365] to bound upstream cost). Each row
    carries filer name, transaction date, share change, transaction price,
    and the SEC transaction code (P=purchase, S=sale, A=award, M=option
    exercise, G=gift, F=tax withholding).

    Mirrors the Premium gating on /api/holdings — Form 4 is explicit
    Premium territory per the tier model. The frontend Paywall handles the
    upsell card; this endpoint also enforces the gate so the data can't be
    sniffed via direct API call from a Free or Pro session.

    Cached 24h at the adapter layer (per-symbol).
    """
    # Short-lived session, released BEFORE the upstream Finnhub call (see the
    # ticker_ratings note + app/db.py — avoids pinning a pooled connection
    # across the multi-second upstream, which exhausted the pool on 2026-06-01).
    async with SessionLocal() as session:
        user = await current_user_required(request, session)
        allowed = has_feature(Tier(user.tier), "insider.form4")
    if not allowed:
        raise HTTPException(403, "Insider transactions require Premium tier")

    sym = symbol.upper()
    days = max(1, min(days_back, 365))
    rows = await fetch_insider_transactions(sym, days_back=days)
    return {
        "symbol": sym,
        "days_back": days,
        "transactions": rows or [],
    }


@router.get("/{symbol}/history")
async def ticker_score_history(
    request: Request,
    symbol: str,
    days: int = 60,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Sparse score history for a ticker — points pulled from the daily
    scorecard.

    Only days where this ticker landed in the top-10 are present (that's
    the only per-day score snapshot the DB stores). For mega-cap regulars
    that's near-daily; for one-time fliers it's sparse. Frontend renders
    an empty sparkline when no rows exist.

    Long-term: a per-tick or per-day score-history table would give every
    ticker a full trace. Tracked in TECH_DEBT.md as a post-launch lift.
    """
    from datetime import date, timedelta

    from app.models import DailyScorecardEntry
    from app.routers.scorecard import _FREE_DELAY_DAYS, _can_see_live_picks

    sym = symbol.upper()
    cutoff = date.today() - timedelta(days=days)

    # SAME publication delay as /scorecard and the CSV/JSON export, and imported
    # from there rather than re-declared so the three surfaces cannot drift.
    #
    # This endpoint previously took no user at all and served today's flags to
    # anonymous callers, while the export's own metadata told readers that
    # "entries are published about 7 days after" they print. Both statements
    # cannot be true. On a product whose whole claim is that it does not
    # misstate things, the open door is the thing to close — not the promise.
    #
    # Paying tiers still see live, exactly as they do on the scorecard page.
    user = await current_user_optional(request, session)
    if not _can_see_live_picks(user):
        delay_cutoff = date.today() - timedelta(days=_FREE_DELAY_DAYS)
    else:
        delay_cutoff = None

    where = [
        DailyScorecardEntry.symbol == sym,
        DailyScorecardEntry.as_of >= cutoff,
    ]
    if delay_cutoff is not None:
        where.append(DailyScorecardEntry.as_of <= delay_cutoff)

    rows_r = await session.execute(
        select(
            DailyScorecardEntry.as_of,
            DailyScorecardEntry.score_at_flag,
            DailyScorecardEntry.rank,
            DailyScorecardEntry.change_pct_1d_after,
            DailyScorecardEntry.alpha_vs_spy,
        )
        .where(*where)
        .order_by(DailyScorecardEntry.as_of)
    )
    points = [
        {
            "date": r[0].isoformat(),
            "score": float(r[1]),
            "rank": int(r[2]),
            "change_pct_1d_after": float(r[3]) if r[3] is not None else None,
            "alpha_vs_spy": float(r[4]) if r[4] is not None else None,
        }
        for r in rows_r.all()
    ]
    return {
        "symbol": sym,
        "days": days,
        # Stated, not implied: an MCP client or a chart has no other way to
        # know whether it is looking at a complete series or a delayed one.
        "delay_days": 0 if delay_cutoff is None else _FREE_DELAY_DAYS,
        "points": points,
    }
