# Tapeline — Data Sources

Every data source used in production must be documented here with license terms, cost, renewal cadence, and the tables it populates.

## Production-approved sources

### Massive (formerly Polygon.io) — Primary market data
- **Tier:** Stocks Starter ($29/mo) minimum; Developer ($79/mo) or Advanced ($199/mo) for more features
- **License:** ❌ **Personal / non-business only** on Stocks Starter. The Market Data TOS (9 Oct 2024) §1 and §5(c) forbid business use and forbid redistributing Market Data *or Derived Works* to any third party. This is an open launch blocker — see `docs/LICENSE_AUDIT.md` for the quoted clauses and the Holley Nethercote brief.
- **URL:** https://massive.com/pricing
- **Note:** Polygon.io rebranded to Massive on 2025-10-30. Same API, same auth, same endpoint shapes — adapter `polygon_feed.py` only needed a hostname change to `api.massive.com`. Legacy `api.polygon.io` still resolves during grace period.
- **Feeds used:**
  - Snapshot API (`/v2/snapshot/locale/us/markets/stocks/tickers`) — real-time prices
  - Aggregates API (`/v2/aggs/ticker/{symbol}/range/...`) — historical bars for scoring
  - Reference data — ticker lists, splits, dividends
- **Populates:** `tickers`, `snapshots`, `scores` (via aggregates)
- **Rate limit:** Starter 5 calls/min, Developer unlimited
- **Renewal:** Monthly auto-renew via card

### Finnhub — Fundamentals, insider Form 4, calendars, sector backfill
- **Tier:** Free
- **License:** ❌ **Personal use only.** Finnhub's ToS: personal plans cannot be used by a business, even internally, without written approval, and derived results may not be redistributed. Open launch blocker — see `docs/LICENSE_AUDIT.md`.
- **URL:** https://finnhub.io/pricing
- **Feeds used:** `/stock/metric` (basic financials), `/stock/insider-transactions` (SEC Form 4), `/calendar/earnings`, `/calendar/ipo`, `/stock/profile2` (sector backfill), `/stock/recommendation` (analyst consensus)
- **Populates:** `insider_transactions`, ticker sectors, calendar tables, `sub_fundamentals` inputs
- **Renewal:** n/a (free tier)

### FRED — Macro indicators
- **Tier:** Free API key
- **License:** ✅ Public domain (US federal data)
- **URL:** https://fred.stlouisfed.org/docs/api/fred/
- **Feeds used:** DXY, 10Y Treasury yield, VIX — 1h cache in `services/fred_feed.py`
- **Populates:** regime inputs, `rate_direction`
- **Renewal:** n/a

### SEC EDGAR — 8-K filings
- **Tier:** Free, direct
- **License:** ✅ Public record
- **URL:** https://www.sec.gov/edgar
- **Populates:** `news` (8-Ks folded into the combined news feed by the worker)
- **Renewal:** n/a

### Congressional trades — ⚠️ NO SOURCE WIRED
- **Status:** Not a production source. `polygon_feed.fetch_congress_trades()` returns an empty list, and `mock_feed`'s generator (which invents trades attributed to real, named politicians) is only persisted outside production — see `signal_publisher._mock_writes_enabled()`. The `congress_trades` table therefore stops accruing rows in prod.
- **Would-be source:** official House/Senate STOCK Act disclosures are public record, but nothing reads them — there is no `congress_ingestor.py`. Wiring one is unstarted work, not a documented feed.
- **Note:** QuiverQuant was **removed** (subscription cancelled). Its Trader tier carried "No Commercial Use Rights"; the adapter, worker task, model and config key are deleted, and the feed only ever served mock data.
- **Caveat:** the SMART MONEY & CONGRESS sheet tab is ingested, but it only boosts each ticker's `sub_smart_money` by appearance count — it does not store individual trades.

### Clerk — Authentication (env-gated, not the live path)
- **Tier:** Free up to 10k MAU; paid tiers from $25/mo
- **License:** Standard SaaS terms, commercial use permitted
- **URL:** https://clerk.com/pricing
- **Stores:** User auth credentials + email/name metadata (never in our DB)
- **Syncs to:** `users` table via webhook on signup/update/delete — only when `CLERK_WEBHOOK_SECRET` is set. The live auth path is native cookie-JWT (`services/session.py`).

### Stripe — Billing
- **Tier:** Pay-as-you-go (2.9% + 30¢ per transaction)
- **License:** Standard Stripe terms
- **URL:** https://stripe.com
- **Stores:** Payment methods, subscription state (source of truth)
- **Syncs to:** `subscriptions` table via webhook

### Resend — Email delivery
- **Tier:** Free up to 3k emails/mo; Pro $20/mo up to 50k
- **License:** Standard SaaS terms
- **URL:** https://resend.com/pricing
- **Used for:** Alert emails, transactional (welcome, native password reset, new-device sign-in codes), digests

---

## ❌ Prohibited sources (do NOT use in production)

### Yahoo Finance / yfinance
- **Why prohibited:** Yahoo's ToS explicitly prohibit commercial use of their data feed. Using in a paid product = license violation and potential cease-and-desist.
- **Removed from:** all production paths
- **Replacement:** Polygon

### Alpaca Market Data (free tier IEX / SIP personal)
- **Why prohibited:** The user's personal Alpaca data subscription is licensed to the end user only. Redistribution to paying customers violates terms.
- **Allowed use:** Personal `C:\signal-system\` and `C:\Wealth\` — not this project
- **Replacement:** Polygon

### Scraping any other paywalled site
- **Why prohibited:** CFAA and site-specific ToS
- **Replacement:** pay for an API, or drop the feature

---

## Data freshness targets

| Source | Production refresh cadence |
|---|---|
| Polygon snapshot | 30–60 seconds during market hours |
| Polygon aggregates (scoring) | Every 5 minutes during market hours |
| Regime inputs (VIX, DXY, 10Y) | Every 5 minutes |
| Congress disclosures | ⚠️ n/a — no feed wired; the table does not accrue rows in production |
| Fundamentals (P/E, margins, etc.) | Weekly refresh |

---

## Renewal tracking

| Vendor | Next renewal | Card on file |
|---|---|---|
| Massive (formerly Polygon.io) | Monthly auto-renew | ✅ live |
| Finnhub | n/a (free tier) | — |
| FRED | n/a (free API key) | — |
| Clerk | n/a (env-gated, not in the live auth path) | — |
| Stripe | n/a (PAYG) | ✅ live, all 6 `STRIPE_*` secrets set |
| Resend | n/a (free tier) | ✅ live |
| Fly.io | Monthly | ✅ live (`tapeline-backend` + `tapeline-web`) |
| Neon Postgres | Monthly | ✅ live (`DATABASE_URL`) |
| Vercel | n/a (PR previews only since the 2026-06-14 migration) | — |
| Domain (tapeline.io) | Annual (Cloudflare) | ✅ live |

Update this table at every signup. Set calendar reminders 30 days before each renewal.
