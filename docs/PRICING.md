# Tapeline — Pricing

> **2026-07 founding reprice.** Market research put the old prices ($29.99/$49.99)
> at the ~70th-80th percentile of the market with zero brand assets; the accepted
> band for an unknown tool is $8-15. Stripe now charges the founding prices below
> (price IDs swapped in backend env). Zero paying customers existed at switch
> time, so no grandfathering was needed. Framing everywhere: **"Founding pricing —
> locked in for early subscribers"** — truthful (subscribers keep their price);
> never a fake countdown or a fabricated "N left" counter.

## Card gate (2026-08-22)

**A new account must put a card on file at first sign-in before it can use the
logged-in product.** Single source of truth: `CARD_GATE_START = date(2026, 8, 22)`
and `must_add_card()` in `backend/app/services/tier.py`; `/api/me` exposes the
flag and the `/app` layout routes off it. The wall is Stripe Checkout — $0 today,
14-day Premium trial, first charge at trial end, one click to cancel before then.

Two things this does **not** touch, deliberately:

- **Grandfathered accounts.** Every account created BEFORE 2026-08-22 signed up
  under "free account, no card" and keeps that deal forever. They never see the
  wall. Admins and lifetime accounts are exempt too, as is anyone who already has
  a card on file or has already trialled — the ask is made once per account.
- **The public surface.** `/scorecard`, `/daily-picks`, the record CSV/JSON
  export (`/api/scorecard.csv`, `/api/scorecard.json`), the per-ticker pages, the
  marketing pages and the public API stay open with no account and no card.

Copy rule that falls out of this: **do not describe an account as free or
card-free anywhere.** Descriptions of the PUBLIC record as free and account-free
stay true and should stay.

## Tiers

### Public record — free, no account
**$0**
- The daily Top 10 at `/daily-picks`, live
- The complete scorecard at `/scorecard` — every pick, back-checked vs SPY
- A page per scored ticker at `/t/{TICKER}`, all six factor sub-scores
- The raw record as CSV and JSON
- Purpose: the trust asset and the only card-free entry point. Not a trial and
  does not expire.

### Free — "Browser" (grandfathered accounts only)
**$0/mo**
- Scanner: **top 10 tickers, live** (`FREE_DATA_DELAY_MINUTES = 0`,
  `FREE_SCANNER_ROWS = 10` in `services/tier.py`)
- Market regime: basic view (bull/neutral/bear label only)
- Watchlist: 5 tickers, no alerts
- Public scorecard access
- **No longer self-serve.** From 2026-08-22 a new visitor cannot sign up for
  this tier. It remains the tier for accounts created before the cutover, and
  the tier an account lands on after cancelling a trial (a card is already on
  file at that point, so `must_add_card` stays false and they are never
  re-walled). Marketing surfaces must not advertise it as an available plan.

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
purpose: an unknown tool with no reviews earns trust with a low ask, a fully
public and downloadable track record that needs no account, and a 30-day
money-back guarantee — not with a mid-pack sticker.
Pro at $9.99 is an impulse-priced entry; Premium at $19.99 undercuts Unusual
Whales (~$48/mo) and Trade Ideas (~$170/mo) by a wide margin while covering a
different primary use case (quant scanner vs. options flow).

## Trial / conversion strategy

- **14-day Premium trial, card required at first sign-in** — signup is email +
  password, and the first sign-in puts the account in front of the card wall
  (`/app/start`). Adding a card there runs Stripe Checkout
  (`mode=subscription` + `subscription_data.trial_end`) and starts the trial.
  Grandfathered accounts skip the wall entirely.
- Disclosed before the card is entered: $0 charged today, the exact first-charge
  date (day 14), the amount, and one-click cancel before then
- Declining is a normal outcome and must not be punished: the wall carries a
  link to the free public record and a sign-out. No auto-redirect into Stripe,
  nothing pre-ticked.
- At day 14, the subscription starts and the card is charged, unless cancelled
  first (one click in Billing) — in which case the account lands on Free and is
  never asked for a card again
- **Annual is the default billing toggle** on /pricing and /app/billing (`BillingToggle.tsx` seeds the sitewide annual default so the plan cards and the always-annual comparison table can never disagree); monthly is one click away
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
