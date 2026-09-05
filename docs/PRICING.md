# Tapeline — Pricing

> **This document is descriptive, not authoritative.** The code is the source
> of truth and this file mirrors it:
>
> - `frontend/lib/pricing.ts` — `PRICING`, `DEFAULT_BILLING_PERIOD`,
>   `FREE_LIMITS`, `PROMO_OPEN_ACCESS_UNTIL`, `REFUND`
> - `backend/app/services/tier.py` — `FEATURES`, `TIER_LIMITS`, `TIER_PRICES`,
>   `_MRR_CONTRIBUTION`, the card gate (`CARD_GATE_START` / `must_add_card`),
>   the open-access promo (`free_open_access`)
>
> Change those files first; update this doc in the same PR. There is no build
> check tying the three together.

> **2026-07 founding reprice.** Market research put the old prices
> ($29.99/$49.99) at the ~70th–80th percentile of the market with zero brand
> assets. Stripe charges the founding prices below (price IDs swapped in
> backend env). Zero paying customers existed at switch time, so no
> grandfathering was needed. Framing everywhere: **"Founding pricing — locked
> in for early subscribers"** — truthful (subscribers keep their price); never
> a fake countdown or a fabricated "N left" counter.

## Card gate (2026-08-22 → 2026-08-30) — REMOVED

**There is no card wall.** It was added by #548 on 2026-08-22 and removed by
#683 on 2026-08-30, an eight-day life. During that window a new account met
Stripe Checkout at `/app/start` before it could use the logged-in product.
**It no longer does:** every `/app` route renders for an uncarded account with
free-tier limits applied inside it, enforced server-side in
`backend/app/services/tier.py`.

Why it went, from #683: three accounts were created under the wall — **none
added a card, none ran a single scan, two never opened the payment page.** And
it was never really a wall: `must_add_card` appeared only in session payloads
and copy, and **no backend route ever read it**, so the API and the public MCP
server always served the full product uncarded.

`CARD_GATE_START` and `must_add_card()` still exist and are still the single
predicate every surface reads — but what they answer now is *"has this account
ever put a card down?"*, driving `/app/start`, upgrade prompts, drip emails and
funnel cohorts. **Do not reintroduce a route wall on it.**

- **Grandfathering is now moot but stays.** Since #683 every account has the
  "free, no card" deal, so the `created_at` comparison no longer separates two
  cohorts. It is kept because ripping a dated cutover out of a billing
  predicate is how you accidentally re-wall real people.
- **The public surface** was never gated and still isn't: `/scorecard`,
  `/daily-picks`, the record CSV/JSON export (`/api/scorecard.csv`,
  `/api/scorecard.json`), the per-ticker pages, the marketing pages and the
  public API — no account, no card.

Copy rule, and note it has **inverted** since #548: describing a new ACCOUNT as
free and card-free is **true again** (#686 corrected 79 such claims across 42
files back). What stays permanently false is describing the **trial** as
card-free — the 30-day Premium trial genuinely requires a card.

## Tiers

Four tiers: **Free / Pro / Premium / Trader**, plus the account-free public
record. Trader, Team, Enterprise and Lifetime all map to `premium` in the DB
with per-account overrides for larger seat counts or API caps.

### Public record — free, no account
**$0**
- The daily Top 10 at `/daily-picks`, live
- The complete scorecard at `/scorecard` — every pick, back-checked vs SPY
- A page per scored ticker at `/t/{TICKER}`, all six factor sub-scores
- The raw record as CSV and JSON
- Anonymous ticker look-ups: 2 per UTC day per IP (`ANON_DAILY_LOOKUPS`)
- Purpose: the trust asset and the only card-free entry point. Not a trial and
  does not expire.

### Free — $0 (not self-serve)
The tier for accounts created before the 2026-08-22 card gate, and the tier an
account lands on after cancelling or lapsing a trial (a card or trial stamp is
already on record at that point, so `must_add_card` stays false — they are
never re-walled). A new visitor cannot sign up directly for this tier, and
marketing surfaces must not advertise it as an available plan.

Limits — enforced in `tier.py` and mirrored in `FREE_LIMITS`
(`frontend/lib/pricing.ts`); every copy surface derives from those constants:

- Scanner: **top 10 rows, live** (`FREE_SCANNER_ROWS = 10`,
  `FREE_DATA_DELAY_MINUTES = 0` — no stale-data cliff)
- Ticker-detail look-ups: **12 per UTC day** (`FREE_DAILY_LOOKUPS`); brand-new
  accounts are never metered for the first **24 h**
  (`FREE_FIRST_SESSION_GRACE_HOURS`)
- Watchlist: **5 tickers, 1 list** (`FREE_WATCHLIST_TICKERS`; the 2026-08-02
  watchlist→Pro cutover was REVERSED 2026-08-19)
- Web-push alerts: **up to 2 rules** (`FREE_WEB_PUSH_ALERTS`) — the deliberate
  free "alert taste"; email alerts 0/day, no API, no saved scans, no CSV export
- Squeeze Watch preview: **3 rows** (`FREE_SQUEEZE_PREVIEW_LIMIT`,
  `routers/squeeze.py`); Congress preview: **3 most recent disclosures**
  (`routers/congress.py`)
- Market regime: basic view

#### Open-access month — temporary, until 8 September 2026
`PROMO_OPEN_ACCESS_UNTIL = 2026-09-08` (`tier.py` + `lib/pricing.ts`, kept in
lock-step). Founder experiment started 2026-08-08; the last open day is
**2026-09-07** and the revert is date-gated — no deploy needed.

The lift is **one numeric cap, not "Free becomes Pro"**: signed-in Free
accounts get the Pro scanner row cap (1,000 rows) instead of 10. Logged-out
visitors keep the standard top-10 (the lift is authenticated-only, on
purpose). `daily_lookups`, `watchlist_tickers`, `web_push_alerts` and every
Pro/Premium **feature** stay gated. `backend/tests/test_open_access_month.py`
asserts each exclusion by name and is the authority if copy drifts.

Forward-looking copy (pricing cards, cancel intercepts, trial nudges) must
quote the steady-state Free caps, never the promo numbers — see
`freeScannerRows()` in `lib/pricing.ts`.

### Pro — "Scanner"
**$9.99/mo** or **$8.25/mo · billed annually ($99/yr · save $20)**
- Scanner: full active-universe scan, **live (sub-60s refresh)**, row cap 1,000
  (`TIER_LIMITS[PRO]["scanner_rows"]`)
- Squeeze Watch: full setup list with windows
- Market regime: full view with VIX/DXY/10Y/sector leaders · heatmap
- Full ticker detail, news, IPOs, earnings; ticker look-ups unmetered
- Watchlist: 50 tickers across 5 named lists, with smart alerts
- Email alerts: up to 10/day · browser push (effectively unlimited)
- Daily briefing email · CSV export · 10 saved scans
- No Congress feed, no API access

### Premium — "Analyst"
**$19.99/mo** or **$16.58/mo · billed annually ($199/yr · save $40)**
- Everything in Pro
- **Congressional trade feed** (`congress.feed`) at `/app/congress`.
  **Honest status:** no live disclosure source is wired in production — the
  fabricated dev generator is gated out of prod
  (`signal_publisher._mock_writes_enabled`), so the table does not accrue new
  rows until a real feed is wired. Congressional STOCK Act names DO feed the
  Smart Money sub-factor via the curated workbook tab
  (`sheet_feed.parse_smart_money_csv`). Marketing copy must not describe the
  `/app/congress` feed as live/daily until a real source ships.
- **Recent insider buys** (`holdings.elite`) — SEC Form 4 transactions,
  refreshed daily — plus per-ticker Form 4 detail (`insider.form4`)
- **Analyst ratings widget** (`ratings.analyst`) — Buy/Hold/Sell consensus
  tally only; per-firm rating events and price targets are not on the current
  data plan and must not be advertised
- **Personal watchlist track record** (`watchlist.track_record`) — each
  watchlist ticker frozen daily and back-checked vs SPY
- **API access**: 1,000 requests/day (throttled to 100/day while on trial —
  `_TRIAL_PREMIUM_REDUCTIONS`)
- Email alerts: unlimited · watchlist 200 tickers / 20 lists · 100 saved scans
- Priority support

Note: Telegram alerts were removed as a user-facing feature in 2026-08
(PR #474; the ops bot remains). The `telegram_alerts_per_day` entries in
`TIER_LIMITS` are legacy plumbing — do not resurrect Telegram in marketing
copy from them.

### Trader — concierge
**$59/mo** or **$49/mo · billed annually ($588/yr)** — early-access / concierge
high tier.
- **Not self-serve.** Sold by hand via the "Talk to us" CTA; there is no Stripe
  self-checkout, so no unbuilt feature can be billed. A manually created
  Trader subscription books via `TIER_PRICES` / `_MRR_CONTRIBUTION` in
  `tier.py` ($49/mo recognized on annual).
- The data-out differentiators (full record + attribution, higher API caps,
  bulk export/webhooks) are built WITH the early customers who buy it.
- Its job on the pricing page is the high anchor that reframes Premium as the
  value choice.

## Billing default & annual math

- **Annual is the sitewide default** (`DEFAULT_BILLING_PERIOD = "annual"`,
  founder decision 2026-07-18). Monthly is one click away.
  `BillingToggle.tsx` seeds the default so plan cards and the always-annual
  comparison table can never disagree; explicit intent (`?billing=monthly`)
  overrides.
- An annual per-month rate **never renders without** "billed annually
  ($N/yr)" attached (`billedAnnuallyNote`) — a bare "$8.25/mo" reads as a
  monthly price, which it isn't.
- Savings are floored to whole dollars so they are never overstated
  (`annualSaving`): Pro $119.88 → $99 ("save $20", not $21); Premium $239.88
  → $199 ("save $40"); Trader $708 → $588.
- Revenue accounting: annual subscriptions book MRR at the advertised
  per-month equivalent ($8.25 / $16.58 / $49), keeping the admin dashboard
  aligned with the pricing page with zero rounding drift.

## Trial / conversion

- **30-day Premium trial, card required — but chosen, not forced.** Signup is
  email + password and lands on a working Free plan. Starting the trial is a
  deliberate step that runs Stripe Checkout (`mode=subscription` +
  `subscription_data.trial_end`). Since #683 nothing routes a new account into
  that checkout before it can use the product.
- Disclosed before the card is entered: $0 charged today, the exact
  first-charge date (day 30), the amount, and one-click cancel before then.
- Declining is a normal outcome and must not be punished: the wall carries a
  link to the free public record and a sign-out. No auto-redirect into Stripe,
  nothing pre-ticked.
- At day 30 the subscription starts and the card is charged, unless cancelled
  first (one click in Billing) — in which case the account lands on Free and
  is never asked for a card again.
- During trial the API cap is throttled 1,000 → 100/day
  (`_TRIAL_PREMIUM_REDUCTIONS`) — full conversion-test value on product
  features, abuse-resistant on data extraction.
- Email drip: day 0 welcome, day 3 feature tour, day 7 trial reminder (both
  price cards), day 11 T-3, day 13 trial-ends-tomorrow; trial-ended emails
  quote BOTH options ("Keep everything — Premium" / "Keep the scanner — Pro").

## Refunds

Single-sourced from the `REFUND` object in `lib/pricing.ts`, ground truth at
`/legal/refund`:

- **Monthly plans**: full refund within 30 days of the first paid charge.
- **Annual plans**: prorated refund within 30 days (one month at the monthly
  rate is retained).

Do not write "30-day money back on every plan, in full" — the annual clause is
prorated.

## Why these prices

Founding pricing puts Tapeline at the bottom of the credible-screener category
on purpose: an unknown tool with no reviews earns trust with a low ask, a
fully public and downloadable track record that needs no account, and the
refund guarantee above — not with a mid-pack sticker. Competitor pricing
verified 2026-08: Pro at $99/yr sits well under Finviz Elite (~$299.50/yr),
Stock Rover (~$280/yr), Koyfin ($374+/yr) and Danelfin ($228+/yr). Price is
not the current conversion blocker; do not cut it. Premium is if anything
under-priced — revisit after there are paying customers, not before.

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

Per Premium subscriber marginal cost: ~$1–2/mo (mostly data-tier overage +
email sends). **Breakeven: ~11 monthly Pro users OR ~6 monthly Premium users**
at founding prices. Revenue targets from the $29.99/$49.99 era are void;
re-baseline once real conversion data exists.
