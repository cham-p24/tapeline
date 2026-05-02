# Tapeline — Data Sources

Every data source used in production must be documented here with license terms, cost, renewal cadence, and the tables it populates.

## Production-approved sources

### Massive (formerly Polygon.io) — Primary market data
- **Tier:** Stocks Starter ($29/mo) minimum; Developer ($79/mo) or Advanced ($199/mo) for more features
- **License:** Commercial redistribution rights included on paid tiers (verify at signup)
- **URL:** https://massive.com/pricing
- **Note:** Polygon.io rebranded to Massive on 2025-10-30. Same API, same auth, same endpoint shapes — adapter `polygon_feed.py` only needed a hostname change to `api.massive.com`. Legacy `api.polygon.io` still resolves during grace period.
- **Feeds used:**
  - Snapshot API (`/v2/snapshot/locale/us/markets/stocks/tickers`) — real-time prices
  - Aggregates API (`/v2/aggs/ticker/{symbol}/range/...`) — historical bars for scoring
  - Reference data — ticker lists, splits, dividends
- **Populates:** `tickers`, `snapshots`, `scores` (via aggregates)
- **Rate limit:** Starter 5 calls/min, Developer unlimited
- **Renewal:** Monthly auto-renew via card

### QuiverQuant — Congressional trading data (Premium tier only)
- **Tier:** Developer API ($50/mo)
- **License:** Commercial use permitted under standard API terms
- **URL:** https://www.quiverquant.com/ (check docs.quiverquant.com for commercial terms before signup)
- **Alternative (free):** Scrape House/Senate STOCK Act disclosures directly (public domain, but messy format)
- **Populates:** `congress_trades`
- **Renewal:** Monthly

### Clerk — Authentication
- **Tier:** Free up to 10k MAU; paid tiers from $25/mo
- **License:** Standard SaaS terms, commercial use permitted
- **URL:** https://clerk.com/pricing
- **Stores:** User auth credentials + email/name metadata (never in our DB)
- **Syncs to:** `users` table via webhook on signup/update/delete

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
- **Used for:** Alert emails, transactional (welcome, password reset via Clerk)

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
| Congress disclosures | Daily, 6am ET |
| Fundamentals (P/E, margins, etc.) | Weekly refresh |

---

## Renewal tracking

| Vendor | Next renewal | Card on file |
|---|---|---|
| Polygon.io | — (not yet subscribed) | — |
| QuiverQuant | — (Premium tier launch) | — |
| Clerk | — (free tier to start) | — |
| Stripe | — (PAYG) | — |
| Resend | — (free tier to start) | — |
| Fly.io | — | — |
| Vercel | — (free Hobby to start) | — |
| Domain (tapeline.io) | — | — |

Update this table at every signup. Set calendar reminders 30 days before each renewal.
