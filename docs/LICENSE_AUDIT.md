# Data-source license audit — 2026-05-17

Strategic doc. **Read before the Holley Nethercote consult** (already on launch-blocker list).

## TL;DR

Three of the data sources powering Tapeline are licensed for personal use only.
Continuing as-is = TOS breach on each. This is bigger than just Quiver.

Tapeline → real customer at $24.99-49.99/mo → customer sees data on screen → that data came from a personal-use-only feed.

| API | Tier | Use in Tapeline | Commercial use allowed? |
|---|---|---|---|
| Polygon / Massive | Stocks Starter $29/mo | Core: live prices, OHLC, snapshots for entire universe | ❌ Personal/non-business only |
| Finnhub | Free | Fundamentals, insider Form 4, calendars, sector backfill | ❌ Personal/non-business only |
| Quiver | Trader $30/mo | Smart-money signal via sheet | ❌ No commercial use rights |
| FRED | Free | Macro indicators | ✅ Public domain |
| SEC EDGAR direct | Free | 8-K filings | ✅ Public record |
| Resend / Stripe / Telegram / Cloudflare / Sentry | various | Infra | ✅ Service, not data |

## Quoted clauses

### Polygon / Massive — Market Data TOS, October 9, 2024

**Section 1** — *"Polygon hereby grants you a nonexclusive, nontransferable, non-sublicensable, revocable, limited license to use Market Data exclusively for your personal, non-business, and non-commercial purposes. For the avoidance of doubt, you may not use the Market Data for any business or commercial purpose, and you may not use the Market Data to build an application intended for use by end users other than you."*

**Section 3** — *"Market Data is made available to you on the basis that you represent and warrant to us that you are a Non-Professional... Any use of Market Data for business, professional, or other commercial purposes is incompatible with Non-Professional status, even if the business or commercial use is on behalf of an organization not in the securities industry."*

**Section 5(c)** — *"Absent prior express written consent... you may not: ... Redistribute, display, disseminate, duplicate, license, sublicense, publish, broadcast, transmit, distribute, redistribute, perform, display, sell, resell, rebrand, or otherwise transfer the Market Data—or any data, charts, analytics, research, or other works based on, referring to, or derived from the Market Data ("Derived Works")—to any third party or use the Market Data for business or commercial purposes."*

**Section 8** — *"To the maximum extent permitted by law, you will indemnify and hold harmless Polygon... against all liabilities, costs, damages, and expenses arising out of or relating to your use of Market Data."*

The Derived-Works clause explicitly closes the "Google Sheet in the middle" loophole.

### Finnhub — Terms of Service

*"All plan listed on Finnhub website is strictly for personal use unless explicitly stated otherwise. Personal plan can't be used by any business even internally without a written approval."*

*"You hereby agree to not redistribute or share access to data or derived results from the data obtained from Finnhub with anyone or any 3rd party without written approval from Finnhub."*

### Quiver — Pricing Page

| Tier | Price | Commercial use? |
|---|---|---|
| Hobbyist | $30/mo (or $25 annual) | No |
| Trader | $75/mo (or $62.50 annual) | No |
| Commercial | "Contact for pricing" | Yes |

User is on Trader at $30/mo (price shown is the actual Stripe receipt, may be a promotional rate).

## Realistic paths forward

### Option 1 — Stay quiet, address before scale ⭐ what 90% of solo fintech founders do
- **Cost**: $0
- **Risk**: Real but small at <100 users
- **Timing**: Crystallises when (a) you scale, (b) you get a takedown letter, (c) a competitor screenshots data + reports
- **Why it works in practice**: Vendors don't actively police small-volume infringers
- **Why it fails**: As soon as Tapeline shows up on a TechCrunch list or hits a HN front page, somebody at Polygon's compliance team notices

### Option 2 — Switch to commercial-tier vendors
- **Polygon Business**: $5,000-15,000/mo + exchange fees. Out of reach pre-revenue.
- **Tiingo Business**: $200-500/mo, lower-volume data, may need to drop some features. **Realistic cheapest path.**
- **EOD Historical Data**: $30-100/mo, commercial tiers available, mostly EOD not real-time
- **IEX Cloud Business**: ~$200/mo for low volume, US-equities focused
- **Finnhub Enterprise**: contact for pricing, typically $500+/mo

### Option 3 — Personal use only, no commerce
- Tapeline as a free personal tool — keep building, no charging, no liability
- Use this as a portfolio piece + free brand awareness
- Monetise via newsletter, consulting, or build a separate IP-clean product later

### Option 4 — Public-only data + delayed quotes
- Drop Polygon/Massive entirely
- Use SEC EDGAR (filings, fundamentals from 10-K/Q parsing), FRED (macro), Yahoo unofficial / Alpaca free / IEX 15-min delayed (prices)
- Worse data, slower, but legally clean
- Tapeline becomes a "stock research" tool not a "live scanner" — different positioning

## Recommendation

1. **Before launching paid subs**: 30-min call with Holley Nethercote (already on launch list, $400-800). Their fintech specialist will tell you exactly:
   - How aggressively each vendor enforces
   - Australian-specific consumer protection on what you advertise vs what you deliver
   - Whether a "data analyst → product" interpretation is defensible
   - Whether you need to upgrade Polygon now or can defer

2. **Tonight's safe move**: ship the "Elite 13F → Insider Form 4" copy strip (this PR). That removes the single most directly-actionable false advertising claim.

3. **Build a `/data-sources` page** that's honest about every feed and what tier it lives on. Doubles as SEO content (Google likes transparent pages).

4. **Set a personal "$X MRR before I worry" threshold.** Many founders pick $1k or $5k MRR. Below that, the cost of upgrading vendor licenses kills the business; above that, you can afford to do it right.

## What this PR ships

- Strips "Elite 13F holdings" from: PricingTable component, JSON-LD, llms.txt, Pricing OG image, simply-wall-st compare page, ticker share pages (`/t/[symbol]`), blog ticker pages, Smart Money blog post (heavy edit), how-it-works confidence FAQ, layout SEO keywords, roadmap (relabelled "Recent insider buys"), signup page metadata, ScannerPreview demo row
- Adds a new v0.1.12 changelog entry explaining the change as "honest about what powers Premium"
- Smart Money blog post adds a paragraph explicitly noting Tapeline doesn't fold 13F into the sub-score (turning it into a positive design choice rather than a missing feature)

## What this PR does NOT ship

- The bigger Polygon/Finnhub license question is unresolved
- No `/data-sources` page yet
- No vendor switch
- No legal opinion in writing

Those are conversations for the Holley Nethercote call.
