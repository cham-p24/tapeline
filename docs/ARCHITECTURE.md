# Tapeline — Architecture

## System overview

Tapeline is a multi-tenant SaaS that delivers quantitative market scores to retail traders via a web dashboard.

> **Updated 15 September 2026.** Corrected against production measurements taken on 14 September 2026 (see `docs/COPY_FACTS.md`): prices are delayed about 15 minutes by the data plan; a worker pass lands about every 60 seconds (a fixed-rate loop since #843); the in-app pages that auto-refresh get one update event per pass from the API's live bridge (#840) during the US session; congressional trades and squeeze detection have no real data source. It reuses the scoring engine from the personal `C:\signal-system\` tool, but wraps it in a commercial-grade pipeline: licensed data in, multi-tenant web app out.

## Component map

### 1. Scoring worker (`backend/app/workers/signal_publisher.py`)
- Runs a fixed-rate loop (#843): a pass starts about every 60 seconds during market hours (22 gaps of 59.99 to 60.02 seconds measured on 14 September 2026, 18:45 to 19:12 UTC; longer around a deploy or restart). Before #843 the loop was a tick then a 60-second sleep, and passes landed 69.7 to 74.3 seconds apart
- Pulls snapshots from **Massive (formerly Polygon.io)** (NOT yfinance or Alpaca — licensing). On the Stocks Starter plan these prices are delayed about 15 minutes (measured 14 September 2026: AAPL snapshot 899 seconds old)
- Calls the adapted scoring functions (composite score, spike detection, regime classification)
- Writes results to Postgres
- Publishes change events to `services/pubsub.py`'s in-process `InMemoryBroker` (not Redis). The worker runs in its own process on its own Fly machine, so these events cannot reach the API process that serves SSE; the API's live bridge reads the database instead — see §5

### 2. Database (Postgres)
Core tables:
- `tickers` — master list (symbol, name, sector, asset_class)
- `scores` — latest composite score + sub-scores per ticker, rewritten each pass (most inputs are daily, so most scores change about once a day)
- `snapshots` — intraday OHLCV + derived fields
- `squeeze_setups` — BB squeeze detections. **No real writer is configured in production**; the 15 rows present were written by a mock tick on 2026-07-18 and are suppressed by `squeeze_integrity` (#818)
- `regime_state` — current market regime snapshot
- `congress_trades` — politician STOCK Act disclosures. **No production source is wired, and none is shown or sold** (#770, #820): `fetch_congress_trades()` returns an empty list, QuiverQuant was cancelled and its adapter deleted, and mock rows are only persisted outside production. The table stops accruing rows in prod until a real disclosure feed is added.
- `users` — written by native signup (`routers/auth.py`); the Clerk webhook syncs into the same table only when `CLERK_WEBHOOK_SECRET` is set
- `subscriptions` — Stripe subscription state
- `alert_rules` — per-user alert config
- `alert_events` — delivered alerts log

### 3. API (`backend/app/main.py` — FastAPI)
- `GET /api/scanner` — paginated ticker list with filters
- `GET /api/squeeze` — squeeze setups (returns only publishable rows; empty in production, #818)
- `GET /api/regime` — market regime snapshot
- `GET /api/congress` — congressional trades (no real source; filtered by `congress_integrity`, empty in production)
- `GET /api/ticker/{symbol}` — single-ticker deep view
- `GET /api/stream/live` — SSE endpoint. Sends `hello` and a 25-second `ping`; `update` events cannot arrive today (see §5)
- `POST /api/webhooks/clerk` — auth user sync
- `POST /api/webhooks/stripe` — subscription state sync
- `GET /api/me` — current user + subscription tier
- `POST /api/alerts/rules` — create alert rule
- All reads gated by `require_tier(free|pro|premium)` dependency

### 4. Frontend (`frontend/` — Next.js 16 App Router)
- `/` — landing page (pricing, sample data screenshot, signup)
- `/signin`, `/signup` — native cookie-JWT forms (Clerk and Google/Microsoft OAuth are env-gated add-ons)
- `/app/scanner` — filterable table (loads on open or filter change)
- `/app/squeeze` — squeeze page (empty state; no real data source)
- `/app/regime` — regime dashboard with VIX/DXY/10Y widgets
- `/app/congress` — says congressional trade data is not available
- `/app/alerts` — alert rule configuration
- `/app/billing` — Stripe customer portal link

### 5. Push delivery (SSE)
- Server-Sent Events (SSE), not WebSockets
- Browser opens `/api/stream/live` and refetches when an `update` event arrives
- **Since #840:** each API process runs `services/live_bridge.py`, which polls the lower-quartile `tickers.updated_at` and publishes one `scores_updated` event per worker pass once the writes settle (roughly 10 to 30 seconds after the pass ends), during the US session (04:00 to 20:00 ET on trading days). The in-app badge reads "Auto-refreshing" only while those events arrive
- **Before #840, measured 14 September 2026 14:02:11–14:07:11 UTC:** a 300-second capture received 1 `hello`, 11 `ping` and **0 `update`** events while the database was rewritten 4 times. The worker publishes to an in-process broker on the worker machine; the API subscribes to its own, separate in-process broker. `frontend/lib/useLiveStream.ts` also marked the stream as updating on `ping`, so the old badge said it was updating while nothing did. LISTEN/NOTIFY was ruled out because the production database URL is transaction-pooled

## Data flow per pass (market hours, about every 60 seconds)

```
t=0    Worker fires
t=0.1  Massive /v3/snapshot calls (250 symbols per call, 6 at a time; prices ~15 min delayed)
t=2.0  Snapshot batch parsed, pandas dataframe assembled
t=3.0  Composite score computed (trend, RS, fundamentals, smart money, macro, momentum)
t=3.5  Spike detection (no real squeeze writer in production)
t=4.0  Regime classification (VIX, breadth, yield curve)
t=4.2  Postgres upsert (scores, snapshots, squeeze_setups)
t=4.3  In-process publish "update" event (worker process only; nothing outside it listens)
t=4.5  Alert rules evaluated; matched rules trigger email/web-push delivery
t=15-35 API live bridge sees the pass settle and pushes one SSE update to clients, see §5
```

## Tier gating

| Feature | Free | Pro ($9.99/mo · $8.25/mo annual) | Premium ($19.99/mo · $16.58/mo annual) |
|---|---|---|---|
| Scanner (prices ~15 min delayed on every tier) | top 10 (the 1,000-row open-access promo ended 2026-09-08) | up to 1,000 rows of ~11,500 | up to 1,000 rows of ~11,500 |
| Squeeze Watch | — (no real data) | — (no real data, #818) | — (no real data, #818) |
| Market Regime | ✅ basic | ✅ full | ✅ full |
| Congress Trades | — | — | — (no real source, #820) |
| Email alerts | — | 10/day | 50/day |
| Browser push alerts | 0 rules (since #683) | 50/day | 50/day |
| CSV export | — | ✅ | ✅ |
| API access | — | — | ✅ (1000 req/day) |

Alert caps are DELIVERIES per UTC day, per channel, counted across every rule
plus the watchlist smart alert. Premium email was 10,000/day and browser push
had no cap at all until 2026-09-18; `services/alerts.ALERT_DAILY_CEILING` now
puts 50 under every plan, and a plan's own lower cap (Pro email: 10) still
applies first. Free receives none on either channel: its email cap is 0 and
`_channel_entitled` refuses its web push.

Email and browser push are the **only** alert channels. Telegram was retired as a
customer channel on 2026-08-11 (Discord + SMS on 2026-05-04); `routers/alerts.py`
accepts `channel` values `email` and `web_push` only.

## Reuse from `signal-system`

Only the **pure scoring functions** cross over. Everything else is rebuilt:
- ✅ Composite score formula (trend, RS, fundamentals, macro, momentum, smart money)
- ✅ BB squeeze + volume expansion detection (code only; no production squeeze data source, #818)
- ✅ Regime classification logic
- ❌ Excel writer (not needed; DB replaces)
- ❌ Google Sheets sync (not needed)
- ❌ Yahoo Finance calls (license violation; use Polygon)
- ❌ Alpaca calls (personal data license; use Polygon)
- ❌ Telegram single-bot (customer Telegram alerts were retired 2026-08-11; Tapeline's bot is founder-facing only — signup/subscription pings, weekly SEO digest, inbox approvals)

Adapter lives in `backend/app/workers/signal_publisher.py` and imports the pure scoring module.

## Deployment

- **Backend + worker:** single Fly.io app, two processes (api + worker)
- **Frontend:** Fly.io app `tapeline-web`, auto-deployed from `frontend/` on push to main (since the 2026-06-14 migration; Vercel builds PR previews only)
- **Database:** Neon Postgres (`DATABASE_URL`)
- **Redis:** not wired — rate-limit counters and caches are in-process today (`services/rate_limit.py`); Upstash remains the plan for scaling past one Fly machine

## Observability

- Logs → Fly.io log tail + Axiom for retention
- Errors → Sentry (backend + frontend)
- Uptime → BetterStack ping on `/api/health` every 30s
- User analytics → PostHog self-hosted or cloud

## Timeline

| Week | Milestone |
|---|---|
| 1 | Postgres schema + Polygon adapter + worker stub writing to DB |
| 2 | FastAPI endpoints + SSE stream + basic Next.js dashboard |
| 3 | Clerk auth + Stripe checkout + tier gating |
| 4 | Email alerts + landing page + legal pages |
| 5 | Beta with 5–10 friendly users |
| 6 | Public launch |
