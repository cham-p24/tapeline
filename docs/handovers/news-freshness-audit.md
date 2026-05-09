# Handover: News freshness audit + fix

## Mission

Diagnose why news ingest goes stale across the Tapeline universe and
ship a fix that holds the broad sweep + per-ticker freshness within
acceptable bounds during market hours. Build observability so this
class of regression is impossible to miss in future.

## Why this matters

A scanner that shows 14-hour-old news is not a "live" scanner. The
`/app/scanner` page renders a "● Live · updated just now" pill that the
news bar undermines. Everything Tapeline sells (transparency, public
scorecard, real-time edge) breaks visually if news is stale.

## Confirmed symptom (2026-05-08)

Querying `/api/news?limit=5` against `api.tapeline.io` returns articles
**821 minutes (~13.7 hours) old**, all sourced from Benzinga. Worker
itself is healthy (`worker_last_tick.age_seconds < 60` on `/api/status`).
So the worker is ticking, but `_refresh_news` either:
- fails silently (try/except swallows it),
- runs but `fetch_latest_news` returns nothing,
- or fires but the dedupe path skips inserts that look already-seen.

## Scope

### IN scope
1. Reproduce the staleness against production and locate the root cause
2. Add structured observability (logs, /api/status counters, alert)
3. Ship a fix that holds latest-article-age < 10 min during market hours
4. Add per-watchlisted-ticker hourly refresh (Premium feature, already
   on the roadmap per [docs/handovers] discussion)
5. Write a regression test that pings the live `/api/news` and asserts
   max age < threshold (run as a Fly cron, not just CI)

### OUT of scope
- News UI changes (the news bar component is fine; it's a data problem)
- Changing the news source preference order (Benzinga → Massive →
  Finnhub is the right chain — the Finnhub fallback was just added in
  commit `e2ffb76`)
- Per-ticker page rendering (already does live fetch on cache miss)

## Concrete tasks (priority-ordered)

### 1. Reproduce + diagnose
- [ ] Read `backend/app/workers/signal_publisher.py` — find `_refresh_news`
- [ ] Tail Fly logs: `fly logs -a tapeline-backend | grep -E "news\."`
  Look for `news.refreshed`, `news.refresh_failed`, `news.benzinga_*`
- [ ] If Benzinga returns 0 articles for `fetch_latest_news()`, confirm
  the Benzinga `/api/v2/news` endpoint with no ticker filter works at
  all (the per-ticker probe returned 200 in the earlier session)
- [ ] If insert dedupe is the issue (every "new" article matches an
  existing id), check `news_feed._fetch_from_polygon` — Massive's news
  IDs may be stable but if the broad sweep keeps hitting the same N
  articles, the worker thinks "no new news"

### 2. Build the fix
Likely fixes (rank-ordered, pick what diagnosis points to):
- [ ] Increase `fetch_latest_news` limit from 40 → 100 so we pick up
  more fresh articles per cycle
- [ ] Add a "max age" log line: `news.latest_article_age_seconds=X` per
  refresh so staleness becomes a metric, not a discovery
- [ ] If broad sweep is empty, fall back to a ticker fan-out across
  the top-50 by $-volume — guarantees fresh per-ticker news even when
  the broad endpoint is dry
- [ ] Catch + structured-log inside `_refresh_news` so silent failure
  becomes loud (currently `except Exception: logger.exception` — make
  sure we're checking *which* upstream is failing)

### 3. Per-watchlisted-ticker refresh (Premium feature)
- [ ] In `signal_publisher.py`, add a new periodic task `_refresh_watchlisted_news`
- [ ] Fires hourly (already established cadence)
- [ ] Queries `WatchlistItem` for the union of all Premium-tier
  watchlist tickers (cap at 1000 unique to bound work)
- [ ] For each, calls `fetch_news_for_ticker(symbol, limit=5)` — uses
  the new Benzinga → Massive → Finnhub chain
- [ ] Inserts new (id-deduped) into `NewsItem`
- [ ] Logs counts: `watchlisted_news.refreshed unique_tickers=X
  new_articles=Y`

Quota math: 1000 tickers × hourly = 24,000/day = 16/min. Both Benzinga
(4000/min) and Finnhub (60/min — would need batching here) can absorb.
Massive doesn't bill per-call. Stays well under all limits.

### 4. Observability — add news-health to `/api/status`
- [ ] Extend `app/routers/status.py` (or wherever the status check
  lives) to surface:
  - `news.latest_article_age_seconds` (max age of newest in DB)
  - `news.articles_24h` (count of articles inserted in last 24h)
  - `news.last_refresh_age_seconds` (when did `_refresh_news` last run)
- [ ] Update `LiveCounters.tsx` and `LiveStatusPill.tsx` if the new
  fields should surface visually (probably the latest_article_age in
  the existing strip, replacing or augmenting the regime cell)
- [ ] Status page degrades to "Degraded" if news age > 30min

### 5. Regression test
- [ ] Write a small standalone Python script `backend/app/scripts/check_news_freshness.py`
- [ ] Hits `/api/news?limit=1` and asserts the latest article is < 30
  min old during market hours, < 4h off-hours
- [ ] Schedule via Fly cron (or GitHub Actions cron on a schedule)
- [ ] Output goes to support@tapeline.io if it fails for >2
  consecutive runs

## Files / surfaces to know

```
backend/app/workers/signal_publisher.py     # _refresh_news, _refresh_universe, etc.
backend/app/services/news_feed.py           # fetch_latest_news, fetch_news_for_ticker, fallback chain
backend/app/services/benzinga_feed.py       # primary news source
backend/app/services/finnhub_feed.py        # 3rd fallback (just added)
backend/app/routers/news.py                 # /api/news endpoint
backend/app/routers/status.py (or main.py)  # /api/status — extend with news health
backend/app/models/news.py (or models/__init__.py)  # NewsItem
frontend/components/BreakingNewsBar.tsx     # the "ticker tape" news strip on /app
frontend/components/LiveStatusPill.tsx      # the green operational dot
frontend/components/LiveCounters.tsx        # the "1,316 news indexed" counter
```

## Tools / integrations needed

- Fly CLI (`fly logs -a tapeline-backend`)
- Direct API access to Benzinga + Massive + Finnhub (keys already in
  `.env` and Fly secrets)
- `pytest` for regression tests
- `ruff` for backend lint compliance (CI gates on it)

## Success criteria

1. `curl https://api.tapeline.io/api/news?limit=1` returns an article
   that's <10 min old during NYSE market hours
2. `/api/status` exposes `news.latest_article_age_seconds`
3. Footer pill turns yellow (Degraded) automatically if news goes stale
4. The Fly logs show `news.refreshed count=X` every 5 min during market
   hours, every refresh
5. New regression script exits 0 when news is fresh, exits 1 + emails
   when stale

## Recommended starter prompt

> I'm picking up the news freshness audit handover at
> `docs/handovers/news-freshness-audit.md`. Tapeline's
> production `/api/news?limit=1` is currently returning articles
> ~14 hours old, even though the worker tick is healthy. Read the
> handover, then tail the production Fly logs to figure out why
> `_refresh_news` isn't producing fresh articles. Don't ship anything
> yet — I want a diagnosis first, then a proposed fix.
