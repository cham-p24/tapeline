# Tapeline — Architecture

## System overview

Tapeline is a multi-tenant SaaS that delivers live quantitative market signals to retail traders via a web dashboard. It reuses the scoring engine from the personal `C:\signal-system\` tool, but wraps it in a commercial-grade pipeline: licensed data in, multi-tenant web app out.

## Component map

### 1. Scoring worker (`backend/app/workers/signal_publisher.py`)
- Runs on a fixed schedule (every 60s during market hours, 15min off-hours)
- Pulls live snapshots from **Polygon.io** (NOT yfinance or Alpaca — licensing)
- Calls the adapted scoring functions (composite score, spike detection, regime classification)
- Writes results to Postgres
- Publishes change events to an in-memory Redis pub/sub for SSE push

### 2. Database (Postgres)
Core tables:
- `tickers` — master list (symbol, name, sector, asset_class)
- `scores` — latest composite score + sub-scores per ticker, per minute
- `snapshots` — intraday OHLCV + derived fields
- `squeeze_setups` — BB squeeze detections
- `regime_state` — current market regime snapshot
- `congress_trades` — politician STOCK Act disclosures. **No production source is wired**: `fetch_congress_trades()` returns an empty list, QuiverQuant was cancelled and its adapter deleted, and mock rows are only persisted outside production. The table stops accruing rows in prod until a real disclosure feed is added.
- `users` — written by native signup (`routers/auth.py`); the Clerk webhook syncs into the same table only when `CLERK_WEBHOOK_SECRET` is set
- `subscriptions` — Stripe subscription state
- `alert_rules` — per-user alert config
- `alert_events` — delivered alerts log

### 3. API (`backend/app/main.py` — FastAPI)
- `GET /api/scanner` — paginated ticker list with filters
- `GET /api/squeeze` — current squeeze setups
- `GET /api/regime` — market regime snapshot
- `GET /api/congress` — recent congressional trades
- `GET /api/ticker/{symbol}` — single-ticker deep view
- `GET /api/stream/live` — SSE endpoint, pushes updates to connected clients
- `POST /api/webhooks/clerk` — auth user sync
- `POST /api/webhooks/stripe` — subscription state sync
- `GET /api/me` — current user + subscription tier
- `POST /api/alerts/rules` — create alert rule
- All reads gated by `require_tier(free|pro|premium)` dependency

### 4. Frontend (`frontend/` — Next.js 16 App Router)
- `/` — landing page (pricing, sample data screenshot, signup)
- `/signin`, `/signup` — native cookie-JWT forms (Clerk and Google/Microsoft OAuth are env-gated add-ons)
- `/app/scanner` — live filterable table
- `/app/squeeze` — squeeze watchlist
- `/app/regime` — regime dashboard with VIX/DXY/10Y widgets
- `/app/congress` — congressional trade feed
- `/app/alerts` — alert rule configuration
- `/app/billing` — Stripe customer portal link

### 5. Real-time delivery
- Server-Sent Events (SSE), not WebSockets — simpler, fine for 30-60s cadence
- Browser opens `/api/stream/live`, receives JSON patches as scores change
- Dashboard applies patches to React state, no full reload

## Data flow per minute (market hours)

```
t=0    Worker fires
t=0.1  Polygon snapshot API call (batched, 1000 symbols / call)
t=2.0  Snapshot batch parsed, pandas dataframe assembled
t=3.0  Composite score computed (trend, RS, fundamentals, smart money, macro, momentum)
t=3.5  Spike detection (BB squeeze, volume expansion, breakout classification)
t=4.0  Regime classification (VIX, breadth, yield curve)
t=4.2  Postgres upsert (scores, snapshots, squeeze_setups)
t=4.3  Redis publish "update" event
t=4.4  SSE stream pushes patch to all connected clients
t=4.5  Alert rules evaluated; matched rules trigger email/web-push delivery
```

## Tier gating

| Feature | Free | Pro ($9.99/mo · $8.25/mo annual) | Premium ($19.99/mo · $16.58/mo annual) |
|---|---|---|---|
| Scanner | top 10, live (lifted to 1,000 rows for authenticated Free until 2026-09-08, `PROMO_OPEN_ACCESS_UNTIL`) | All ~2,500, live | All ~2,500, live |
| Squeeze Watch | — | ✅ | ✅ |
| Market Regime | ✅ basic | ✅ full | ✅ full |
| Congress Trades | — | — | ✅ |
| Email alerts | — | 10/day | unlimited |
| Browser push alerts | 2 rules | effectively uncapped | effectively uncapped |
| CSV export | — | ✅ | ✅ |
| API access | — | — | ✅ (1000 req/day) |

Email and browser push are the **only** alert channels. Telegram was retired as a
customer channel on 2026-08-11 (Discord + SMS on 2026-05-04); `routers/alerts.py`
accepts `channel` values `email` and `web_push` only.

## Reuse from `signal-system`

Only the **pure scoring functions** cross over. Everything else is rebuilt:
- ✅ Composite score formula (trend, RS, fundamentals, macro, momentum, smart money)
- ✅ BB squeeze + volume expansion detection
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
