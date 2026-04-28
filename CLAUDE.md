# Tapeline

SaaS quantitative market scanner for retail stock pickers. Lives at `C:\Project 1\`. Built by a Melbourne-based founder. Pre-launch.

**Pitch:** "Every other scanner gives you 500 filters and a blank stare. Tapeline gives you one number, one sentence, and a public track record."

**Domain:** `tapeline.io` (NOT YET REGISTERED).

## Boundary — do not touch
The personal trading system at `C:\signal-system\` is a separate project. Tapeline reuses the *scoring approach* but does NOT share files with it. Never edit anything outside `C:\Project 1\`.

## Operational facts
- **No git repo yet.** Treat file edits as one-way — no rollback, no `git diff`. Initialising git is on the user's TODO list.
- **No Docker required for dev.** Run `.\scripts\run_nodocker.ps1` from project root. Uses SQLite, opens browser to `http://localhost:3000`.
- **Owner login** (already seeded): `owner@tapeline.io` / `TapelineOwner!2026` — premium tier, admin. Re-seed via `python -m app.scripts.seed_owner` from `backend/` (idempotent; reads `OWNER_EMAIL` / `OWNER_PASSWORD` env vars).
- **Dev auth bypass:** `Authorization: Bearer dev-bypass` returns a premium token in dev. **Strip before production.**
- **Today's date for relative refs:** see system date.

## Stack
FastAPI + SQLAlchemy + Alembic (Python 3.12) backend. Next.js 14 + TypeScript + Tailwind frontend. SQLite dev / Postgres prod (Supabase or Neon). SSE for live updates. Native cookie-JWT auth (built) + Clerk + Google/Microsoft OAuth (env-gated). Stripe billing (env-gated). Resend email (env-gated). Hosting plan: Fly.io backend + Vercel frontend.

## Worker
Single scoring worker at `backend/app/workers/signal_publisher.py`. Default tick = **60s** (`SCORE_REFRESH_SECONDS` in `.env.example`). Dev script overrides to 10s for faster iteration. Also: hourly Telegram digest, ~5min news refresh, daily scorecard back-check, on-boot universe + calendar seed.

## Tier model — canonical source: `backend/app/services/tier.py`
**Three tiers** (decided 2026-04-26, Free hardened 2026-04-27):
- **Free** $0 — **top 20 tickers, 24-hour delayed**, watchlist (5, no alerts)
- **Pro** $29/mo or $290/yr — full universe live, squeeze + regime + heatmap, watchlist (50), email alerts (10/day), CSV
- **Premium** $49/mo or $490/yr — everything in Pro + Congressional trades, Telegram unlimited, email unlimited, public API (1,000/day), elite 13F holdings, priority support

Anchor offerings (custom-sold; all map to `premium` in the DB): **Team** $149/mo for 5 seats, **Enterprise** custom from $2k/mo, **Founder's Lifetime** $399 once for first 100.

**Trial:** auto-started on signup gives **PREMIUM** for 14 days, no card. At expiry, hourly worker task `_downgrade_expired_trials` drops users with no `stripe_customer_id` straight to `free` (skip the Pro middle so loss aversion bites hardest). `TrialBanner.tsx` shows the countdown.

## Pricing source-of-truth (all kept in sync as of 2026-04-26)
- `backend/app/services/tier.py` — feature gating + caps
- `frontend/components/PricingTable.tsx` — pricing UI
- `frontend/components/ComparisonTable.tsx` — comparison table on /pricing
- `docs/PRICING.md` — narrative + unit economics

## Signal labels — do not change (legal posture)
Descriptive, NOT prescriptive — protects the publisher's exemption.
- `HIGH CONVICTION` (85–100) — was "BUY NOW"
- `STRONG SETUP` (70–84) — was "STRONG ACCUMULATE"
- `CONSTRUCTIVE` (55–69) — was "ACCUMULATE"
- `NEUTRAL` (40–54) — was "HOLD"
- `CAUTION` (25–39) — was "WATCH"
- `WEAK` (0–24) — was "AVOID"

## Scoring formula — do not change (transparency is the moat)
Documented publicly on `/how-it-works`:
```
score = 0.25*trend + 0.20*relative_strength + 0.15*fundamentals
      + 0.15*smart_money + 0.15*macro + 0.10*momentum
```

## Mock-to-real data switch
**No env flag, no auto-switch.** Currently the worker imports `app.services.mock_feed` directly. To switch to live Polygon data: add `POLYGON_API_KEY` to `.env`, then **manually edit the imports at the top of `backend/app/workers/signal_publisher.py`** (swap `mock_feed` → `polygon_feed`) and restart the worker. See `QUICKSTART.md` lines 40–49 for the exact swap.

## Universe + commodities
Mock universe is 112 tickers (80 equities + 32 commodity ETFs). Commodity ETFs added 2026-04-26 with sector="Commodities" — gold, silver, oil, gas, ag, copper, uranium, miners. Polygon Starter doesn't include futures contracts, so commodity exposure is via ETFs only. Auto-discovery of new ETFs via Polygon `/v3/reference/tickers` is on the post-launch list (not wired yet).

## Bot / abuse protection — `backend/app/services/bot_protection.py`
Three application-level layers (Cloudflare Bot Fight Mode is the recommended free baseline once domain is proxied):
1. **Honeypot field** — invisible `company` input on signup form. Bots fill it; humans don't see it. Tripped → fake-success response (no account created, no session cookie).
2. **Disposable-email block** — built-in set of ~62 throwaway providers (mailinator, guerrillamail, tempmail, etc.). Rejected with 400.
3. **Cloudflare Turnstile** — env-gated. `CLOUDFLARE_TURNSTILE_SITE_KEY` + `CLOUDFLARE_TURNSTILE_SECRET_KEY`. Pass-through when unset (dev), enforced when set.

Rate limit: `services/rate_limit.py` `limit_auth` caps `/api/auth/*` at 10 attempts per IP per minute (vs default 120 for /api/*).

## Universe + commodities
Mock universe is 112 tickers (80 equities + 32 commodity ETFs). Commodity ETFs added 2026-04-26 with sector="Commodities" — gold, silver, oil, gas, ag, copper, uranium, miners. Polygon Starter doesn't include futures contracts, so commodity exposure is via ETFs only. Auto-discovery of new ETFs via Polygon `/v3/reference/tickers` is on the post-launch list (not wired yet).

## Smart-money / 13F holdings
Wired end-to-end as of 2026-04-27. `services/quiver_feed.py` fetches 13F data for 8 elite funds (Buffett, Burry, Tepper, Ackman, Druckenmiller, Laffont, Coleman, Singer); 24h cache + multi-endpoint fallback. Worker task `_refresh_elite_13f` runs daily; falls back to `mock_elite_13f_holdings()` when no `QUIVER_API_KEY`. Endpoint `/api/holdings` (Premium-only via feature `holdings.elite`). Frontend page not yet built — use existing congress page pattern for `/app/holdings` when ready.

## Known issues / partially-built
- **`rate_direction` in regime is a placeholder** — `polygon_feed.py:fetch_regime` still returns hardcoded value. Breadth_pct + sector_leaders now computed live from the snapshot universe each tick. DXY/10Y/VIX use FRED when configured.
- **No `/v3/reference/tickers/{sym}` sector backfill** — universe auto-discovery from Polygon adds new tickers with `sector="Unknown"`. Worker should backfill sectors lazily for tickers users actually look at.
- **Web push send needs `pywebpush`** — `services/web_push.py` imports it conditionally; if not installed, the channel logs a skip and continues. Run `pip install pywebpush` in the backend venv to activate.
- **Frontend tests cover ~6 surfaces** — Paywall, PricingTable, SignupForm honeypot, ScannerPreview labels, BillingToggle, HoldingsPage. Grow with billing flow + alerts CRUD + scanner page next.
- **No E2E tests** — Playwright would land later. Unit tests catch most regressions.

## Notification channels
Five delivery channels for alerts (`backend/app/services/alerts.py:_fire`):
- **Email** (Pro+) — Resend, no extra cost. Default channel for every rule. Always on.
- **Browser push / Web Push** (Pro+) — VAPID + Service Worker (`frontend/public/sw.js`). Free. One-click enable on Chrome/Firefox/Edge desktop + Android. iOS requires PWA install.
- **Discord** (Pro+) — webhook URL the user creates in their server. Free. Posts rich embeds.
- **Telegram** (Premium) — free, hourly digest + per-rule alerts. Customer adds their chat_id at `/app/billing` (Telegram card).
- **SMS** (Premium) — Twilio (~$0.008/msg US, more elsewhere). Reserve for high-conviction rules — every send is billed.

End-of-day watchlist email digest fires daily ~21:00 UTC for every Pro+ user with watchlist items (`services/email.py:run_eod_watchlist_digest`).

## Per-ticker confidence
Each Ticker row carries a `confidence_pct` (0-100) that varies with which underlying data feeds returned data for that symbol. Mega-caps with full Quiver/Finnhub/FINRA coverage land 88-96, ETFs without traditional fundamentals land 45-70, the typical liquid stock lands 60-85. Surfaced as a column on the scanner table + as an inline pill on the ticker page. Documented on `/how-it-works`. Pattern ported from the personal signal-system. Mock value via `mock_feed._compute_mock_confidence(symbol)` (deterministic per symbol). Real polygon_feed should compute from actual data-feed presence.

## Webhook idempotency
`stripe_webhook_events` table logs every processed event id. Replay attacks and Stripe redeliveries return `{ok: true, replay: true}` instead of double-processing. Migration 0010.

## Tests
Backend: 8 smoke tests at `backend/tests/test_smoke.py`, pytest config at `backend/pytest.ini`. Run: `pytest` from `backend/`. Frontend: no tests.

## Things NOT to change without thinking
- 6-factor scoring formula and weights
- Descriptive (not prescriptive) signal labels
- Public scorecard from day 1 (the trust mechanism)
- Three-tier price points ($29 Pro / $49 Premium) — only revisit with conversion data
- Free tier shows real product (delayed) — not a feature-stripped version
- Owner login mechanism (only seeded via `seed_owner.py`, never via signup form)

## Critical file map
- `backend/app/main.py` — FastAPI entry, router mounts, CORS
- `backend/app/config.py` — every env var, Pydantic-typed
- `backend/app/services/tier.py` — **canonical** tier gating + caps
- `backend/app/services/auth.py` — native + Clerk JWT verification + dev-bypass
- `backend/app/services/mock_feed.py` — fake data generator (112 tickers incl. 32 commodity ETFs)
- `backend/app/services/polygon_feed.py` — real Polygon adapter (stubbed in places)
- `backend/app/services/quiver_feed.py` — Quiver 13F + tracked elite funds (wired end-to-end with mock fallback)
- `backend/app/services/bot_protection.py` — honeypot + disposable email + Turnstile
- `backend/app/services/fred_feed.py` — FRED macro indicators (DXY, 10Y, VIX) with 1h cache
- `backend/app/services/alerts.py` — per-rule alert evaluators (score / squeeze / regime / congress) with five-channel delivery (email / web push / Discord / Telegram / SMS)
- `backend/app/services/sms.py` — Twilio SMS (no-op when not configured)
- `backend/app/services/discord.py` — Discord webhook delivery (no-op when no webhook saved)
- `backend/app/services/web_push.py` — Web Push via VAPID + pywebpush (no-op when either is missing)
- `frontend/public/sw.js` — Service Worker for Web Push notification handling
- `frontend/lib/webPush.ts` — client-side subscribe/unsubscribe/test helpers
- `backend/app/routers/roadmap.py` — public roadmap voting (Premium-gated)
- `frontend/__tests__/` — Vitest + RTL scaffold (run `npm test` after `npm install`)
- `backend/app/workers/signal_publisher.py` — scoring tick worker
- `backend/app/scripts/seed_owner.py` — creates/updates the owner account
- `backend/alembic/versions/` — 7 migrations, run via `alembic upgrade head`
- `frontend/components/PricingTable.tsx` — **canonical** pricing UI
- `frontend/components/TrialBanner.tsx` — trial countdown UI
- `frontend/middleware.ts` — gates `/app/*` routes
- `frontend/lib/auth.ts` — session + tier check helpers
- `docs/ARCHITECTURE.md` — system overview, deployment plan
- `docs/LEGAL_CHECKLIST.md` — pre-launch legal must-dos
- `docs/DATA_SOURCES.md` — what's licensed vs not

## Pending TODOs (only the user can do these — needs accounts/cards)
Full step-by-step in `docs/OPERATIONS.md`. Short list:
1. Push the git repo to GitHub (init done, no remote yet)
2. Register `tapeline.io` at Cloudflare (~$35/yr) + Turnstile keys
3. Polygon.io Starter ($29/mo) → key in `.env` + manual import swap in `signal_publisher.py`
4. Stripe account → 4 Price IDs (Pro/Premium × monthly/annual) + webhook secret
5. Resend → API key (activates: alerts, welcome, day-3/7/13 drip, trial-ended)
6. Telegram BotFather → `@TapelineBot` (activates customer Notifications card)
7. Quiver QuantData free key (activates real 13F holdings)
8. FRED API free key (activates live DXY / 10Y / VIX in regime endpoint)
9. Google + Microsoft OAuth client IDs (buttons auto-appear when env vars set)
10. Fly.io + Vercel deploy
11. Postgres (Supabase Pro $25/mo or Neon $19/mo) for prod DB
12. Lawyer consult — Holley Nethercote Melbourne ($400-800)

## Communication style
- The user prefers tight, factual responses over long narration.
- When suggesting changes, lead with the recommendation; offer to implement rather than implementing unprompted (since there's no git rollback).
- Don't add features, abstractions, or "while I'm here" cleanups beyond what was asked.
