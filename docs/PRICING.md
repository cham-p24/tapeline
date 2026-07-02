# Tapeline — Pricing

> **2026-07 founding reprice.** Market research put the old prices ($29.99/$49.99)
> at the ~70th-80th percentile of the market with zero brand assets; the accepted
> band for an unknown tool is $8-15. Stripe now charges the founding prices below
> (price IDs swapped in backend env). Zero paying customers existed at switch
> time, so no grandfathering was needed. Framing everywhere: **"Founding pricing —
> locked in for early subscribers"** — truthful (subscribers keep their price);
> never a fake countdown or a fabricated "N left" counter.

## Tiers

### Free — "Browser"
**$0/mo**
- Scanner: top 20 tickers only, **24-hour delayed**
- Market regime: basic view (bull/neutral/bear label only)
- Watchlist: 5 tickers, no alerts
- Public scorecard access
- Purpose: lead magnet + landing-page demo + loss-aversion lever at trial expiry

### Pro — "Scanner"
**$9.99/mo** or **$8.25/mo billed annually** ($99/yr · save $20)
- Scanner: full ~2,500-ticker universe, **live (sub-60s refresh)**
- Squeeze Watch: full setup list with windows
- Market regime: full view with VIX/DXY/10Y/sector leaders
- Watchlist (50) with smart alerts
- Email alerts: up to 10 per day
- Daily briefing email · CSV export
- Browser push alerts
- No Congress data, no Telegram, no API

### Premium — "Analyst"
**$19.99/mo** or **$16.58/mo billed annually** ($199/yr · save $40)
- Everything in Pro
- **Congressional trade feed** (daily updates, ticker aggregation)
- **Recent insider buys** — live SEC Form 4 transactions across the active universe, refreshed daily
- **Telegram alerts** (unlimited)
- **API access** (1,000 requests/day)
- Email alerts: unlimited
- Watchlist (200) · saved scans (100)
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

Founding pricing puts Tapeline at the bottom of the live-scanner category on
purpose: an unknown tool with no reviews earns trust with a low ask, a real
free tier, and a 30-day money-back guarantee — not with a mid-pack sticker.
Pro at $9.99 is an impulse-priced entry; Premium at $19.99 undercuts Unusual
Whales (~$48/mo) and Trade Ideas (~$170/mo) by a wide margin while covering a
different primary use case (quant scanner vs. options flow).

## Trial / conversion strategy

- **14-day Premium trial, no credit card** — every new signup starts in Premium for 14 days
- At day 14, prompts to add card OR drops to Free
- **Monthly is the default billing toggle** on /pricing and /app/billing (smaller
  first yes); annual is one click away with its saving shown
- **30-day money back** on every paid plan (was 7-day; extended 2026-07 —
  costless at zero customers, neutralizes the no-reviews trust gap)
- Pro carries the **"Best value"** badge (factual framing); no popularity
  claims anywhere until there are customers to back them
- Email drip: day 0 welcome, day 3 feature tour, day 7 trial reminder (both
  price cards), day 11 T-3, day 13 trial-ends-tomorrow + trial-expired emails
  quote BOTH options ("Keep everything — Premium $19.99/mo" / "Keep the
  scanner — Pro $9.99/mo")

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

**Breakeven: ~11 paying Pro users OR ~6 Premium users** (at founding prices).

## Revenue targets (year 1)

Old targets were set against $29.99/$49.99 stickers; scale expectations to
roughly one-third revenue per subscriber, offset by (hopefully) materially
higher conversion at the credible price point. Re-baseline once real
conversion data exists — do not steer by the old table.

## Annual plan pricing math

Monthly → Annual discount is **~17%** (close to 2 months free), with the exact
per-month equivalent advertised (never overstated):
- Pro: $9.99 × 12 = $119.88 → **$99 annual** ($8.25/mo · save $20/yr)
- Premium: $19.99 × 12 = $239.88 → **$199 annual** ($16.58/mo · save $40/yr)

Annual plans should be **≥40% of paid revenue** by month 6 — they dramatically reduce churn.
