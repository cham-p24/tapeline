# Tapeline — Pricing

## Tiers

### Free — "Browser"
**$0/mo**
- Scanner: top 10 tickers only, **15-min delayed**
- Market regime: basic view (bull/neutral/bear label only)
- No alerts, no historical data, no exports
- Purpose: lead magnet + landing-page demo

### Pro — "Scanner"
**$29/mo** or $290/yr (save 2 months)
- Scanner: full ~870-ticker universe, **live (30s refresh)**
- Squeeze Watch: full setup list with windows
- Market regime: full view with VIX/DXY/10Y/sector leaders
- Email alerts: up to 10 per day
- CSV export
- No Congress data, no Telegram, no API

### Premium — "Analyst"
**$49/mo** or $490/yr (save 2 months)
- Everything in Pro
- **Congressional trade feed** (daily updates, ticker aggregation)
- **Telegram alerts** (unlimited)
- **API access** (1,000 requests/day)
- Email alerts: unlimited
- Priority support

---

## Why these prices

Competitive set:
- Motley Fool Stock Advisor: $200/yr — monthly picks, no scanner
- Seeking Alpha Premium: $240/yr — ratings + screeners, no live data
- Trade Ideas: $170/mo — real-time scanner, no congress/squeeze
- Unusual Whales: $48/mo — options flow + congress
- BlackBoxStocks: $100/mo — squeeze + dark pool alerts
- Zacks Premium: $250/yr — rankings, no scanner

Tapeline Pro at $29 undercuts everyone in the live-scanner category. Premium at $49 matches Unusual Whales and beats Trade Ideas by 3x while covering different primary use cases (quant scanner vs. options flow).

## Trial / conversion strategy

- **14-day Pro trial, no credit card** — every new signup starts in Pro for 14 days
- At day 14, prompts to add card OR drops to Free
- Annual plans shown prominently on pricing page ("save $58")
- Email drip: day 0 welcome, day 3 feature tour, day 7 trial reminder, day 13 trial ends tomorrow

## Unit economics (rough)

| Item | Monthly cost |
|---|---|
| Polygon Starter | $29 |
| Supabase Pro | $25 |
| Fly.io (api + worker) | $15 |
| Vercel Pro (if needed) | $20 |
| Clerk (under 10k MAU) | $0 |
| Resend | $20 |
| Sentry (free tier) | $0 |
| Domain amortized | $1 |
| **Fixed ops** | **~$110/mo** |

Per Premium subscriber marginal cost: ~$1–2/mo (mostly Polygon at-tier overage + email sends).

**Breakeven: 4 paying Pro users OR 3 Premium users.**

## Revenue targets (year 1)

| Month | Pro subs | Premium subs | MRR |
|---|---|---|---|
| 1 (beta) | 5 | 2 | $245 |
| 3 | 25 | 10 | $1,215 |
| 6 | 75 | 25 | $3,400 |
| 12 | 200 | 60 | $8,740 |

$105k ARR by month 12 is the stretch goal. Even 25% of that is a validated side business.

## Annual plan pricing math

Monthly → Annual discount is **~16.7%** (2 months free):
- Pro: $29 × 12 = $348 → $290 annual
- Premium: $49 × 12 = $588 → $490 annual

Annual plans should be **≥40% of paid revenue** by month 6 — they dramatically reduce churn.
