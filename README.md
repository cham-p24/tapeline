# Tapeline

**A live quantitative market scanner for retail traders.**

Tapeline surfaces high-conviction technical and fundamental signals across US equities, ETFs, and crypto. It scores ~870 tickers every minute during market hours, detects Bollinger Band squeezes and volume expansions, tracks Congressional trades and institutional flows, and classifies the overall market regime.

Built on the same engine that powers a production personal trading bot.

---

## Status

**Pre-launch scaffold.** This repo is a fresh clone separate from the personal `C:\signal-system\` engine. Nothing here is wired to live data yet; that's the first build milestone.

## Architecture (see `docs/ARCHITECTURE.md`)

```
┌──────────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Polygon.io SIP feed │─────▶│  Scoring worker  │─────▶│  Postgres       │
│  (commercial data)   │      │  (adapted from   │      │  (scores,       │
└──────────────────────┘      │   signal-system) │      │   snapshots)    │
                              └──────────────────┘      └────────┬────────┘
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
│  Clerk (auth)        │      │  Stripe (billing)│
└──────────────────────┘      └──────────────────┘
```

## Stack

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy + Alembic
- **Database:** Postgres (Supabase or Neon)
- **Frontend:** Next.js 14 + TypeScript + Tailwind + shadcn/ui
- **Auth:** Clerk
- **Billing:** Stripe
- **Data feed:** Polygon.io Starter ($29/mo, commercial redistribution)
- **Deployment:** Fly.io (backend + worker) + Vercel (frontend)
- **Email:** Resend

## Product tabs (v1)

1. **📡 Scanner** — ~870 tickers, composite score, filters, sort
2. **🔥 Squeeze Watch** — BB squeeze days, volume expansion, OBV trend, suggested window
3. **🌊 Market Regime** — current regime, VIX, DXY, 10Y, rate direction, sector leaders
4. **🏛️ Congress Trades** — recent politician buys/sells aggregated by ticker

## Pricing (planned)

- **Free:** daily delayed snapshot, 10-ticker scanner
- **Pro ($29/mo):** live updates, full scanner, squeeze + regime, email alerts
- **Premium ($49/mo):** + Congress, Telegram alerts, CSV export, API access

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
