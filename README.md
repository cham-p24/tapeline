# Tapeline

**A quantitative market scanner for retail traders.**

Tapeline scores about 11,500 US stocks and ETFs on six named factors, shows SEC Form 4 insider filings per ticker, and classifies the overall market regime. About 100 crypto pairs are scored separately, once a day.

Prices are delayed about 15 minutes (the data plan is Massive Stocks Starter). During US market hours the scoring worker re-reads them for every covered stock and ETF about every 60 seconds. Scores are recalculated on each pass, but most of their inputs are daily readings, so a score usually changes about once a day. See `docs/COPY_FACTS.md` for the measurements (14 September 2026) and for what copy may say.

Not available today: congressional trade data (no real source; the pages say so) and squeeze detection (no real data source is configured, so the squeeze pages are empty and squeeze alerts cannot fire).

Built on the same engine that powers a production personal trading bot.

---

## Status

**Live.** `tapeline.io` is served by the Fly.io app `tapeline-web`; the API runs at `api.tapeline.io` (Fly app `tapeline-backend`). Market data comes from Massive (prices delayed about 15 minutes), with Finnhub for fundamentals and calendars, SEC EDGAR for Form 4 insider filings (#835), and FRED for macro. Three live tiers, Stripe billing, and a public scorecard. This repo stays separate from the personal `C:\signal-system\` engine — no shared files.

## Architecture (see `docs/ARCHITECTURE.md`)

```
┌──────────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Massive snapshots   │─────▶│  Scoring worker  │─────▶│  Postgres       │
│  (Polygon rebrand;   │      │  (adapted from   │      │  (scores,       │
│   ~15 min delayed)   │      │   signal-system) │      │   snapshots)    │
└──────────────────────┘      └──────────────────┘      └────────┬────────┘
                                                                 │
                                                                 ▼
┌──────────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Next.js dashboard   │◀─SSE─│  FastAPI         │◀─────│  Read API       │
│  (scanner, regime,   │      │  (auth, billing, │      │                 │
│   ticker pages)      │      │   event stream)  │      │                 │
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
- **Data feed:** Massive Stocks Starter ($29/mo), a 15-minute delayed plan — formerly Polygon.io, rebranded 2025-10-30. Licence scope is under review; see `docs/LICENSE_AUDIT.md`
- **Macro / fundamentals / smart money:** FRED · Finnhub (fundamentals, earnings + IPO calendars) · SEC EDGAR (Form 4 insider filings, since #835)
- **Deployment:** Fly.io — `tapeline-backend` (API + scoring worker) and `tapeline-web` (Next.js frontend, serves tapeline.io). Vercel builds PR previews only
- **Email:** Resend

## Product tabs (v1)

1. **📡 Scanner** — about 11,500 US stocks and ETFs, composite score, filters, sort. Prices delayed about 15 minutes.
2. **🔥 Squeeze Watch** — *not working today.* No real squeeze data source is configured, so the page shows an empty state and squeeze alerts cannot fire (#818, 14 September 2026).
3. **🌊 Market Regime** — current regime, VIX, DXY, 10Y, rate direction, sector leaders
4. **🏛️ Congress Trades** — *not available.* There is no real source of congressional trade disclosures, so none are shown and none feed the score (#820, 14 September 2026). The page says so.

## Pricing

Prices and limits mirror `frontend/lib/pricing.ts` and `backend/app/services/tier.py`; check those before quoting.

- **Free** $0, no card — top-10 scanner rows, 12 ticker look-ups per UTC day, watchlist of 5, 1 saved screen, no alert rules. Anonymous look-ups are not metered.
- **Pro** $9.99/mo or $8.25/mo billed annually ($99/yr) — every matching scanner row (1,000 per request; paging reaches the rest), regime + heatmap, watchlist 50, email alerts (10/day), browser push alerts, CSV export.
- **Premium** $19.99/mo or $16.58/mo billed annually ($199/yr) — everything in Pro plus per-ticker SEC Form 4 insider filings, unlimited email alerts, watchlist 200, saved scans 100, public API (1,000 req/day).

Signing up is free and needs no card. Adding a card starts a 30-day Premium trial: $0 that day, first charge on day 30, one click to cancel, and an email about 7 days before the first charge. (A card wall on new accounts ran from 22 to 30 August 2026; #683 removed it.) The public record — scorecard, daily picks, per-ticker pages, the CSV/JSON exports and the public API — needs no account and no card. Without Pro or Premium the scorecard's per-day entries are on a 7-day delay, and the CSV/JSON export stops 7 days back for every caller; the summary figures are current.

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
