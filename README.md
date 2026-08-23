# Tapeline

**A live quantitative market scanner for retail traders.**

Tapeline surfaces high-conviction technical and fundamental signals across US stocks and ETFs. It scores ~2,500 tickers every minute during market hours, detects Bollinger Band squeezes and volume expansions, surfaces recent insider buys (SEC Form 4), and classifies the overall market regime. (A Congressional-trades surface is built and Premium-gated, but no disclosure feed is wired yet.)

Built on the same engine that powers a production personal trading bot.

---

## Status

**Live.** `tapeline.io` is served by the Fly.io app `tapeline-web`; the API runs at `api.tapeline.io` (Fly app `tapeline-backend`). Real market data comes from Massive, with Finnhub for fundamentals, calendars and SEC Form 4 insider transactions, and FRED for macro. Three live tiers, Stripe billing, and a public scorecard. This repo stays separate from the personal `C:\signal-system\` engine — no shared files.

## Architecture (see `docs/ARCHITECTURE.md`)

```
┌──────────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Massive SIP feed    │─────▶│  Scoring worker  │─────▶│  Postgres       │
│  (Polygon, rebranded │      │  (adapted from   │      │  (scores,       │
│   2025-10-30)        │      │   signal-system) │      │   snapshots)    │
└──────────────────────┘      └──────────────────┘      └────────┬────────┘
                                                                 │
                                                                 ▼
┌──────────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Next.js dashboard   │◀─SSE─│  FastAPI         │◀─────│  Read API       │
│  (scanner, squeeze,  │      │  (auth, billing, │      │                 │
│   regime, congress)  │      │   live stream)   │      │                 │
└──────────────────────┘      └──────────────────┘      └─────────────────┘
          │                            │
          ▼                            ▼
┌──────────────────────┐      ┌──────────────────┐
│  Cookie-JWT auth     │      │  Stripe (billing)│
└──────────────────────┘      └──────────────────┘
```

## Stack

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy + Alembic
- **Database:** Postgres (Supabase or Neon)
- **Frontend:** Next.js 16 + TypeScript + Tailwind + shadcn/ui
- **Auth:** native cookie-JWT sessions (`services/session.py`), with emailed sign-in codes as a new-device second factor; Clerk and Google/Microsoft OAuth are env-gated add-ons
- **Billing:** Stripe
- **Data feed:** Massive Stocks Starter ($29/mo) — formerly Polygon.io, rebranded 2025-10-30. Licence scope is under review; see `docs/LICENSE_AUDIT.md`
- **Macro / fundamentals / smart money:** FRED · Finnhub (fundamentals, SEC Form 4 insider transactions, earnings + IPO calendars)
- **Deployment:** Fly.io — `tapeline-backend` (API + scoring worker) and `tapeline-web` (Next.js frontend, serves tapeline.io). Vercel builds PR previews only
- **Email:** Resend

## Product tabs (v1)

1. **📡 Scanner** — ~2,500 tickers, composite score, filters, sort
2. **🔥 Squeeze Watch** — BB squeeze days, volume expansion, OBV trend, suggested window
3. **🌊 Market Regime** — current regime, VIX, DXY, 10Y, rate direction, sector leaders
4. **🏛️ Congress Trades** — recent politician buys/sells aggregated by ticker. *Surface and Premium gate are built, but no disclosure feed is wired: the table does not accrue rows in production (see `docs/DATA_SOURCES.md`).*

## Pricing

- **Free** $0 — top-10 scanner rows, live (no delay), 12 ticker look-ups per UTC day, watchlist of 5, 2 browser-push alert rules. *(Open-access promo, ends 2026-09-08: scanner rows only are lifted 10 → 1,000 for signed-in Free accounts — `tier.py:PROMO_OPEN_ACCESS_UNTIL`. Look-ups, watchlist and push caps are unchanged, no Pro feature unlocks, and anonymous visitors still see the top 10.)*
- **Pro** $9.99/mo or $8.25/mo billed annually ($99/yr) — full universe live, squeeze + regime + heatmap, watchlist 50, email alerts (10/day), CSV export, browser push.
- **Premium** $19.99/mo or $16.58/mo billed annually ($199/yr) — everything in Pro plus Congressional trades, Recent insider buys (SEC Form 4), unlimited email alerts, watchlist 200, saved scans 100, public API (1,000 req/day).

Accounts created from 2026-08-22 add a card at first sign-in, which starts a 14-day Premium trial: $0 that day, first charge on day 14, one click to cancel. Accounts created before that date are grandfathered and are never asked for a card. The public record — scorecard, daily picks, per-ticker pages, the CSV/JSON exports and the public API — needs no account and no card.

## Repo layout

```
backend/          FastAPI + scoring worker
frontend/        Next.js dashboard (initialize with `npx create-next-app@latest`)
infra/           Docker, deployment config
docs/            Architecture, legal checklist, data sources, pricing
scripts/         One-off ops scripts
```

## Getting started

See `docs/ARCHITECTURE.md` for the full technical plan and `docs/LEGAL_CHECKLIST.md` for pre-launch must-dos.

## What this is NOT

Tapeline is a **quantitative scanning and research tool**. It does not:

- Provide individualized investment advice
- Execute trades
- Make price predictions
- Manage customer funds

All output is factual data synthesis. Users make their own decisions. See `docs/LEGAL_CHECKLIST.md`.
