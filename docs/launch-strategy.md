# Tapeline — Launch strategy (consolidated)

This document ties together every strategic discussion from the build
sessions: where Tapeline stands today, who it's competing with, what
the product surface looks like vs the field, what SEO pushes will
move the needle, and the actual order of operations to start
generating revenue. Single source of truth — replaces the various
ad-hoc analyses in chat.

**Last reviewed:** 2026-05-10

---

## 1. Where Tapeline is right now (honest)

### Built and live ✓

- Production scoring engine on Fly: 6-factor formula (Trend 25% · RS
  20% · Fundamentals 15% · Smart money 15% · Macro 15% · Momentum
  10%) running across ~2,500 actively-scored tickers
- Sub-60s tick cadence; news refresh every 5 min (Massive + Finnhub
  parallel merge, including international names)
- Public surfaces: `/`, `/pricing`, `/how-it-works`, `/scorecard`,
  `/security`, `/status`, `/changelog`, `/blog`, `/compare/{finviz,
  zacks, wallstreetzen}`, `/t/{symbol}` per-ticker pages, `/legal/*`
- Authenticated app: `/app/scanner`, `/app/ticker/{symbol}` with
  ScoreRadial + sparkline + analyst ratings (Premium-gated)
- Email pipeline: welcome + day 3/7/13 trial drip + EOD watchlist
  digest, all wired through Resend
- Trust artefacts: live `/api/status` with database/worker/news/
  integration health; encrypted-at-rest postgres; bcrypt(12)
  passwords; HSTS preload; vulnerability disclosure
- SEO foundation: structured data (Review/FAQ/Breadcrumb JSON-LD),
  canonical URLs, sitemap with 500+ ticker pages, locale-aware dates

### Not built / not yet live ✗

- **Stripe billing** — the single hardest blocker. Account exists (or
  may exist), products + webhook need to be created, 7 keys need to
  land in Fly secrets. Until then, no revenue.
- `/about`, `/press`, `/compare/tradingview`, `/compare/trade-ideas`,
  `/best-stock-scanners` — referenced in footer, don't exist
- Google Search Console + Bing Webmaster verification
- Google Business Profile
- Backlinks (currently zero referring domains)
- App Store / Play Store presence (post-launch concern)

### Brutally honest assessment

Tapeline is a **launch-ready product without a launch-ready
business**. The technical and design surfaces are at parity or
better than most $30-50/mo retail-finance competitors. What's
missing is everything that turns visitors into paying customers:
billing, distribution, brand recognition, a backlink profile,
podcast/press hits.

The next 90 days are about the BUSINESS, not the PRODUCT.

---

## 2. Positioning — make sure we're on the same page

### Who Tapeline is for

Retail traders who:
- Already self-direct (have a brokerage account, place their own trades)
- Read finance Twitter / r/investing / r/algotrading
- Have tried 1-2 scanners (Finviz, Zacks, TipRanks) and felt the
  opacity of those products
- Pay $20-100/mo for a tool if it's clearly worth it
- Are skeptical of newsletters — they want data, not narratives

### Who Tapeline is NOT for

- Day traders chasing real-time options flow (Trade Ideas, Unusual Whales)
- Long-only buy-and-hold investors (Stock Rover, Morningstar)
- Institutional buyers (Bloomberg, FactSet, Koyfin Pro)
- Beginners who need education before tools (Investopedia, Robinhood Snacks)

### The positioning statement

> "The only retail stock scanner that publishes its scoring formula
> on the homepage and back-checks every pick against SPY publicly."

That's the wedge. Every piece of marketing reinforces it. Every
feature decision is judged by whether it strengthens or dilutes it.

### Three things competitors literally cannot copy

1. **The published formula.** TipRanks/Zacks/WallStreetZen/Simply
   Wall St all hide their methodology as IP. Their incentive
   structure prevents copying — they sell opacity.
2. **The public scorecard with both wins and losses.** Newsletter
   shops have known for 30 years to hide losers. Tapeline auto-
   publishes both.
3. **`/security` + `/status` + `/changelog` together.** Nobody else
   in retail finance publishes this stack. Plausible-style trust
   posture applied to financial data.

### Three things Tapeline cannot beat competitors on (don't fight)

1. **Domain authority.** TipRanks ranks for "AAPL stock forecast"
   because they have 10 years of backlinks. Tapeline can't catch
   that on existing terms.
2. **Per-ticker data dump.** Yahoo Finance + Stock Analysis own
   "AAPL stock price" forever.
3. **Brand recognition.** Bloomberg, Morningstar, Zacks have
   30-50 years of name awareness.

The strategy is to **win on the wedge, accept the rest.**

---

## 3. Competitor landscape (consolidated)

### Direct composite-score competitors (closest competition)

| Competitor | Their score | Pricing | Public formula? | Public scorecard? | Tapeline's edge |
|---|---|---|---|---|---|
| TipRanks | Smart Score 1-10 | $30-45/mo | ✗ | ✗ | Both transparency moats |
| WallStreetZen | Letter grade A-F | $40/mo | ✗ "115 factors" | ✗ | Both moats + cleaner UX |
| Simply Wall St | Snowflake (5-axis) | $8-16/mo | ✗ ML black box | ✗ | Formula transparency + scorecard |
| Stock Rover | Multiple scores | $8-28/mo | Partial | ✗ | Modern UX + scorecard |
| Zacks | Rank 1-5 | $250/yr | ✗ | ✗ | Modern + transparent + cheaper |
| Kavout | K-Score | Custom | ✗ "AI" | ✗ | Same |

### Adjacent (data + research, no composite score)

| Competitor | What they own | Why Tapeline can't directly compete |
|---|---|---|
| Yahoo Finance | "AAPL stock" SERPs | Free, ad-supported, scale Tapeline can't match |
| Stock Analysis | Per-ticker data tables | Pure SEO play; ranks #1-3 on most ticker queries |
| Seeking Alpha | Long-form analyst commentary | Different product (essays vs scanner) |
| Morningstar | Star rating + research reports | Old-school authority; 50-yr brand |
| Finviz | Free screener + visualizations | Free + 15-year brand; Tapeline can't undercut on price |
| Koyfin | Bloomberg-style terminal | Targets advisors; different user |

### Indirect (could become channels or threats)

| Competitor | Why they matter |
|---|---|
| Trade Ideas ($170/mo) | Real-time scanner; potential acquisition partner OR channel partner |
| Atom Finance | Mobile-first; competing for the same retail audience |
| Public.com | Social investing; could acquire scoring layers |
| Robinhood Snacks | Newsletter with massive audience; potential partnership |

### Where each competitor wins and where Tapeline can attack

**TipRanks wins on:** Brand + 10-year SEO. Tapeline can't catch these queries.
**Tapeline can attack:** "TipRanks alternative", "transparent stock score", "TICKER score audit"

**WallStreetZen wins on:** Letter-grade simplicity, single-page elegance.
**Tapeline can attack:** "Zen Ratings methodology", "WallStreetZen alternative", "stock rating without paywall"

**Simply Wall St wins on:** Snowflake visual, mobile app.
**Tapeline can attack:** Once Tapeline's radial is more recognized, "transparent Snowflake" / "Simply Wall St alternative"

**Yahoo / Stock Analysis win on:** Data depth + brand authority.
**Tapeline cannot attack these head-to-head.** Don't try. Win on the wedge instead.

---

## 4. Visualization & UX — current state + improvements

### What's working (keep)

- **ScoreRadial component** — 6-axis SVG with score-tier coloring, polygon draw-in animation. **More sophisticated than any direct competitor's score viz.** Simply Wall St's Snowflake is closest but uses 5 axes and is ML-driven (no transparency). TipRanks shows just a number; WallStreetZen just a letter. Tapeline's radial is the strongest single-stock visualization in the field.
- **Live ScannerPreview** with pulsing rows + score nudges every 4s. Sells "live" claim through demonstrated behavior, not asserted text.
- **LiveCounters strip** with counting-up animation (0 → 5,757 tickers, etc.). Pulled live from `/api/status`. Concrete numbers replace vague "live" claims.
- **TransparencyStrip** cross-linking the moat artefacts (formula, scorecard, status, security, changelog).
- **Public OG images per ticker** with the radial signature in the corner — share previews self-sell.
- **Hero gradient backdrop** with soft accent glow (Linear-style depth).
- **FadeIn-on-scroll** for trust pillars + How It Works steps, with `prefers-reduced-motion` support.

### Improvements still on the radar (prioritized)

| # | Change | Effort | Impact |
|---|---|---|---|
| 1 | **Thin context strip on `/t/{symbol}`** — Sector · Market cap · Next earnings · 52-week range. ~4 cells, single row. Adds completeness without diluting the score focus. Data already available from Finnhub. | Medium (3-4h) | High — closes data-density gap that bounces SEO visitors |
| 2 | **`/stocks/{symbol}` canonical alias** — 301 redirect from `/stocks/AAPL` → `/t/AAPL`. Indexes both URL shapes for "stocks" SERPs. | Small (1h) | High — pure SEO win, no UX cost |
| 3 | **Score history sparkline expansion** — currently sparse (top-10 entries only). Add a per-day score table that captures EVERY ticker's score daily, then sparkline becomes continuous. | Medium-large (1 day) | Medium — turns sparse trace into proper time-series |
| 4 | **Build `/about`, `/press`, missing compare pages** referenced in footer. Broken footer links hurt SEO + UX. | Medium (1 day total) | High — unblocks YMYL ranking + footer integrity |
| 5 | **Mobile review** on real device — homepage, pricing, ticker page. | Small (your end, 30 min) | Medium — retail traders browse on phone |

### Improvements explicitly NOT on the list (decided against)

- **Embed full TradingView chart on `/t/{sym}`** — would dominate the page visually, dilute the score focus. Already on `/app/ticker` for paid users.
- **Full fundamentals tables** (income statement, balance sheet, cash flow) — turns Tapeline into Stock Analysis. Wrong positioning.
- **Cmd+K palette** — power-user feature; pre-launch, defer.
- **Discord/Telegram integration as primary alert channels** — Discord retired (low conversion); Telegram exists for Premium users only.

---

## 5. SEO strategy — five phases, with budget

### Phase 1 — Foundation (this week, all free)

1. Google Search Console — verify domain, submit sitemap (30 min)
2. Bing Webmaster Tools — same (30 min)
3. Google Business Profile — Tapeline as a financial-services business (45 min)
4. Schema validation — run all JSON-LD through schema.org validator (30 min)
5. PageSpeed Insights audit on /, /pricing, /t/AAPL, /scorecard (1-2h)
6. Fix broken footer links (build `/about` + others, OR remove from footer) (1-2h decision + 1 day to build)
7. Internal link graph audit (1-2h)

**Cost:** $0
**Outcome:** Foundational hygiene — without this, nothing else works.

### Phase 2 — Content (next 4 weeks)

1. **vs-competitor pages** — `/compare/tipranks`, `/compare/seekingalpha`, `/compare/yahoo`, `/compare/morningstar`, `/compare/atom-finance`, `/compare/stockrover`, `/compare/koyfin`, `/compare/simplywallst`
2. **"Best of" listicles** — `/best-stock-scanners` (already in footer), `/best-bloomberg-alternatives`, `/best-free-stock-scoring-tools`, `/best-stock-screeners-under-50`
3. **Per-ticker FAQ enrichment** — JSON-LD already wired; add visible FAQ sections to top-100 most-traded tickers
4. **Glossary** — `/glossary/relative-strength`, `/glossary/13f-filing`, `/glossary/regime-indicator`, etc.
5. **Methodology deep-dives** — one blog post per factor explaining how Tapeline computes it (6 posts total)
6. **`/about` page with founder bio** — critical for YMYL ranking

**Cost:** $0 if writing yourself; $150-300/post if outsourcing the listicles + glossary
**Outcome:** ~30 indexable pages added; long-tail keyword surface area expanded ~5x

### Phase 3 — Authority & backlinks (months 2-6)

1. **Hacker News Show HN** — single best one-shot SEO event possible (free)
2. **Reddit posts** — r/algotrading, r/stocks, r/investing, r/wallstreetbets (free)
3. **Podcast appearances** — Animal Spirits, The Compound, Excess Returns, Risk Reversal, Indie Hackers (free pitches)
4. **Guest posts** — Substacks (Daily Upside, Compound Capital, Snippet Finance) (free pitch + ~6h writing each)
5. **HARO** — Help A Reporter Out, free, daily journalist queries (30 min/day)
6. **Press release distribution** — PRNewswire / GlobeNewswire on launch + milestones ($300-1000/release)
7. **Sponsored newsletter spots** — paid placement in Daily Upside / Snacks / Compound ($200-2000 each)
8. **Tools directory submissions** — Crunchbase, ProductHunt, AlternativeTo, G2, Capterra, BetaList (all free)

**Cost:** $500-1500/month sustained
**Outcome:** Backlink profile from 0 → 30-50 referring domains in 6 months

### Phase 4 — Verifications & business listings

| Listing | Cost | Status |
|---|---|---|
| Google Search Console | Free | Phase 1 |
| Bing Webmaster | Free | Phase 1 |
| Google Business Profile | Free | Phase 1 |
| Crunchbase | Free / $29/mo Pro | Week 2 |
| ProductHunt | Free | Launch day |
| AlternativeTo | Free | Week 2 |
| G2 / Capterra | Free for basic | Week 3 |
| BetaList | Free | Pre-launch |
| LinkedIn Company Page | Free | Week 1 |
| Trustpilot | Free | Once you have 10 paying customers |
| Wikipedia | Free, hard | Year 2 play |

### Phase 5 — Tools (paid, ROI-positive)

| Tool | Cost | When |
|---|---|---|
| Ahrefs Lite | $99/mo | Month 2 onwards |
| Screaming Frog | Free up to 500 URLs / £149/yr unlimited | When sitemap > 500 URLs |
| PageSpeed Insights | Free | Week 1 onwards |

**Total realistic SEO budget:**
- Pre-launch month: $0
- Launch month: ~$1000 (1 PR, 1 sponsored newsletter, ProductHunt boost)
- Months 2-3: $99/mo Ahrefs only
- Months 4-6: $500-1500/month sustained

---

## 6. Selling — what's blocking and what to do

### THE blocker: Stripe is not connected

Confirmed via `/api/status` and `fly secrets list`: zero `STRIPE_*`
secrets exist in production. The "Upgrade to Pro" button on
`/app/billing` returns *"Checkout isn't live yet — Stripe activation
pending"*. **Until this is fixed, no money can change hands.**

### Stripe — what you must do (cannot be delegated)

1. **Create the Stripe account** at https://dashboard.stripe.com/register
   - 10 minutes
   - Verify business identity (ABN, bank account for AUD payouts)
   - Test mode keys work immediately; live mode requires ~24h KYC
2. **Create 4 products** in Stripe Dashboard → Products → New
   - Pro Monthly: $9.99 USD recurring monthly
   - Pro Annual: $99.00 USD recurring yearly (displays as $8.25/mo)
   - Premium Monthly: $19.99 USD recurring monthly
   - Premium Annual: $199.00 USD recurring yearly (displays as $16.58/mo)
   - Copy each Price ID (`price_…`)
3. **Create webhook endpoint**
   - URL: `https://api.tapeline.io/api/webhooks/stripe`
   - Events: `checkout.session.completed`,
     `customer.subscription.{created,updated,deleted}`,
     `invoice.payment_{succeeded,failed}`
   - Copy the signing secret (`whsec_…`)
4. **Get API keys** from Developers → API keys
   - Secret key (`sk_live_…` or `sk_test_…`)
   - Publishable key (`pk_live_…` or `pk_test_…`)
5. **Send the 7 values to me** in this format:
   ```
   STRIPE_SECRET_KEY=sk_…
   STRIPE_PUBLISHABLE_KEY=pk_…
   STRIPE_WEBHOOK_SECRET=whsec_…
   STRIPE_PRICE_PRO_MONTHLY=price_…
   STRIPE_PRICE_PRO_ANNUAL=price_…
   STRIPE_PRICE_PREMIUM_MONTHLY=price_…
   STRIPE_PRICE_PREMIUM_ANNUAL=price_…
   ```

I'll then run `fly secrets set` for all 7, redeploy, verify
`/api/status` flips to `'stripe': true`, and test the checkout flow
end-to-end. ~15 minutes from receiving keys.

### Once Stripe is wired — the four selling channels

In rough order of effort vs. likely first dollar:

1. **Personal network email** (50 people you actually know) — Day 0
2. **Hacker News Show HN** — Day 0
3. **Reddit posts** — Days 1, 3, 5 (different subreddits, day-spaced)
4. **ProductHunt** — Day 0.5
5. **Twitter thread + LinkedIn announcement** — Day 0
6. **Cold-pitch 5 finance podcasts** — Week 1

The full sequenced playbook is in
`docs/handovers/marketing-agent.md`.

### What's NOT selling but feels like selling

- More polish on the marketing site
- More compare pages (each has marginal SEO value but won't drive
  trial signups directly)
- Yet another visual tweak to the homepage
- Reading more competitor sites and feeling intimidated

The site is launch-ready. Everything that's not Stripe is either
incremental polish or distribution.

---

## 7. First-30-days operational plan

### Day 0 (this week)

**Your end:**
1. Stripe — create account, 4 products, webhook, send me 7 keys
2. Google Search Console + Bing Webmaster verification (30 min)
3. Google Business Profile (45 min)
4. PageSpeed Insights audit (1h)

**My end (after Stripe keys land):**
1. Set Fly secrets, redeploy, verify integration
2. Test checkout flow (test mode first, then live)
3. Build `/about` page from your bio template

### Week 1

- Build `/compare/tradingview`, `/compare/trade-ideas`,
  `/best-stock-scanners` (referenced in footer)
- Build `/press` page with logos + fact sheet
- Build `/glossary` with 5-10 entries
- LinkedIn company page + Crunchbase listing
- Set up Plausible analytics (already configured if env var is set)
- Subscribe to HARO (free)

### Week 2

- Write the launch playbook for the actual launch date
- Pitch first 5 podcasts
- Draft Hacker News Show HN post (3 revisions minimum)
- Draft Reddit posts for 4 subreddits (each unique)
- Sign up Ahrefs Lite ($99) — start tracking competitor backlinks

### Weeks 3-4

- Publish 2 methodology blog posts
- Publish 4 comparison pages (vs TipRanks, vs Yahoo, vs Stock Analysis,
  vs Morningstar)
- Publish 2 listicles (Best stock scanners under $50, Best Bloomberg
  alternatives)
- ProductHunt + BetaList submissions
- LAUNCH — Hacker News Show HN morning Eastern Time
- Reddit posts day-spaced

### Month 2

- Sustained content cadence (1-2 blog posts/week)
- 5 podcast pitches sent, 1-2 confirmed
- First sponsored newsletter slot ($200-500 trial)
- Daily HARO responses
- First press release distribution ($300-500)
- Affiliate program design (per business-leverage handover)

### Month 3

- 50+ paying users target
- First Trustpilot reviews
- API tier design + announcement (per business-leverage handover)
- White-label outreach to 50 RIAs (per business-leverage handover)
- Continued content + backlinks

---

## 8. The single biggest risk

It's not a feature gap, a competitor, or a bug. It's the **months
between launch and traction**. New SaaS in a competitive space
typically takes 6-12 months before paid signups become predictable.
Most founders quit at month 3.

Mitigations baked into the plan:
- Multiple launch channels (HN + Reddit + PH + email + podcasts)
  spreads the eggs
- Public scorecard compounds — the longer it runs, the stronger
  the trust signal
- Compare pages compound — each one adds long-tail SEO surface
- Annual plans lock in 12 months of revenue per signup, smoothing
  cash flow
- Founder's Lifetime $399 plan (first 100) gives you cash up front
  for runway

What kills similar businesses:
- Spending months on "one more feature" instead of distribution
- Paid acquisition before organic engine works
- Trying to win against Bloomberg-tier brands head-on
- Burning cash on PR before there's a launch story to tell

---

## 9. What "right page" looks like

If we're aligned, this is the strategy:

- Tapeline is the **transparent, formula-published, scorecard-audited**
  alternative to TipRanks/Zacks/WallStreetZen
- Pricing is mid-market ($29-49/mo retail; $399 lifetime; $2k+
  enterprise) — not a race to the bottom, not premium-priced
- Distribution is organic-first: HN/Reddit/podcasts/SEO compounding
  over 6-12 months
- Stripe is the only revenue blocker; everything else is incremental
- Visual moat is the radial signature + transparency stack — defended
  by NOT cluttering with generic data dump pages
- SEO moat is the published formula + scorecard pages — defended by
  consistent compare-page + content cadence

If any of the above is wrong, tell me — better to course-correct now
than after 30 days of misaligned work.

---

## Single most important next step

**Open Stripe and send me the 7 keys.** Everything else can wait
until that's done. Without it, the rest of this plan generates traffic
that can't convert.

---

*This document supersedes all earlier piecemeal strategy notes in chat.
Update on a quarterly cadence (or when something material changes
in product / pricing / positioning).*
