# Handover: Business leverage + scale strategy

## Mission

Identify and prioritise the highest-ROI ways to expand Tapeline beyond
the core retail-trader subscription product. Owner is launching solo;
the goal is to find revenue surfaces that compound without proportional
operational cost. Three time horizons:

- **0-90 days post-launch:** what unlocks growth without distracting
  from product
- **90-365 days:** what to build / partner on once paid revenue is
  predictable
- **Year 2+:** structural plays (acquisition, vertical expansion,
  enterprise tier)

## Why this matters

A retail SaaS at $29-$49/mo per user has a clear ceiling: even at
10,000 paying users (very ambitious for a solo founder pre-launch),
that's ~$5M ARR. Real generational outcomes come from leverage
multipliers — partnerships, API revenue, white-label, enterprise tiers,
acquisition. This agent's job is to find those without building
features that don't pay.

## Scope

### IN scope
1. **Affiliate program design** — referral economics + technical
   implementation outline
2. **API monetization** — already on Premium ($49/mo includes
   1k/day); design a higher API-only tier
3. **White-label evaluation** — could financial advisors / RIAs buy
   Tapeline-branded-as-theirs? Cost vs. revenue?
4. **Education / course product** — "How to read a stock scanner"
   evergreen course at $49 one-time
5. **Newsletter integration** — does Tapeline data become a paid
   feature inside larger finance newsletters? (The Daily Upside,
   Compound Capital, etc.)
6. **Acquihire targets** — small failing fintech tools whose users
   could roll into Tapeline for cheap CAC
7. **Acquisition partners** — fintechs that might want to buy Tapeline
   in 18-36 months (Public.com, eToro, Trade Republic, Robinhood)
8. **Quarterly strategy memo** — `outputs/leverage-2026-Q3.md` and
   onward, summarising opportunities + recommendations

### OUT of scope
- Core product features (different agents)
- Day-to-day marketing (different agent)
- Going public or fundraising (founder decision; agent provides
  inputs not actions)

## Concrete tasks (priority-ordered)

### 1. Affiliate program design

Most retail SaaS gets meaningful growth from creator/community
affiliates (50%+ of HoneyBook's growth came via Pinterest creators;
Notion via student ambassadors).

Deliver `outputs/affiliate-program-design.md` covering:
- [ ] Commission structure: recommended 30% lifetime on Pro, 25%
  lifetime on Premium (annual locked subscribers). Modelled against
  CAC + churn assumptions.
- [ ] Cookie window: 60 days (industry standard for SaaS)
- [ ] Disqualifications: paid search affiliates banned (creates brand
  bidding war + trademark abuse)
- [ ] Tooling: Rewardful or Tolt vs. building in-house
  (recommendation: Rewardful at $49/mo for first 6 months; in-house
  once volume justifies)
- [ ] Recruitment: target list of 50 finance-Twitter creators + 10
  finance YouTubers + 5 substack writers
- [ ] Tracking: per-affiliate dashboard, monthly payouts via Wise/Stripe

Estimated impact: 15-30% of paid signups within 6 months if executed
well. Real cost: $49/mo Rewardful + 25-30% of MRR from affiliate
signups, but offset by zero direct CAC on those signups.

### 2. Public API tier

Tapeline already has API access at Premium ($49/mo, 1,000 req/day).
That's a feature, not a product line. There's a market for an
API-first tier targeted at:
- Quant hobbyists building their own dashboards
- Discord/Telegram trading communities embedding scores
- Other fintech products wanting a "scoring data spine"

Deliver `outputs/api-tier-design.md` covering:
- [ ] Pricing tiers:
  - **Hobbyist** $99/mo · 50k req/day · all endpoints · 90-day history
  - **Community** $499/mo · 500k req/day · webhooks · 1-year history
  - **Embed** $2,499/mo · 5M req/day · custom fields · SLA
- [ ] Endpoint scope: `/api/scanner`, `/api/ticker/{sym}`,
  `/api/scorecard`, `/api/regime`, `/api/news`. Hidden:
  `/api/holdings` (Quiver licensing), `/api/congress` (Quiver)
- [ ] Implementation: separate `api_token` table, per-tier rate limit
  middleware, usage dashboard. ~2 weeks engineering
- [ ] Marketing: Show HN, dev.to write-up, post on r/algotrading
- [ ] Compliance: API customers redistributing scores must include
  "Powered by Tapeline" + a link to /how-it-works

Estimated TAM: 50-200 active API customers Year 1 = $10-50k MRR.
Higher LTV than retail; lower churn.

### 3. White-label for RIAs / financial advisors

Independent financial advisors are a real underserved B2B market.
Many can't afford Bloomberg ($31k/yr) or YCharts ($4k+/yr) but want
quantitative data for client reports.

Deliver `outputs/whitelabel-rfa.md`:
- [ ] Product: "Tapeline for Advisors" — same scanner, RIA's logo,
  "Powered by Tapeline" footer (small but required), client-facing
  scorecard PDF generator
- [ ] Pricing: $199/mo for first 5 client logins, $399/mo unlimited
- [ ] Feature: per-RIA branded scorecard PDFs (one-pager any RIA can
  hand to a client)
- [ ] Compliance: each RIA is responsible for their own
  recommendations; Tapeline never crosses into advisory. Disclosure
  language explicit on every PDF.
- [ ] Sales: cold outreach to 200 fee-only RIAs (NAPFA member
  directory is public). Conversion estimate: 5-10% in first 90 days
  of outreach.
- [ ] Engineering: ~3 weeks (mostly white-label theming + PDF gen)

Estimated revenue: 50 RIAs × $199 average = $9,950 MRR by month 12 of
the workstream. Higher LTV than retail. Lower churn.

### 4. Education / course product

A self-paced course "How to read a stock scanner without losing your
shirt" priced at $49 one-time. Three benefits:
- Pure-margin revenue (no recurring infra cost)
- Builds an audience of warm leads who'll convert to subscriptions
- Creates SEO tail (course landing pages rank for "how to use a
  stock scanner")

Deliver `outputs/course-product-design.md`:
- [ ] Curriculum: 8 lessons, each 5-10 min video + 1-page transcript
  - L1: What a composite score actually means
  - L2: The 6 factors and what each measures
  - L3: How to read signal labels without taking them as buy/sell
  - L4: When to trust your scanner and when to override it
  - L5: Reading the public scorecard (winning + losing weeks)
  - L6: Building a watchlist that doesn't suffocate you
  - L7: Avoiding common scanner mistakes (over-trading, narrative
    chasing, etc.)
  - L8: A 30-day routine for using Tapeline
- [ ] Platform: Gumroad initially (lower barrier than Teachable or
  Kajabi); migrate if revenue > $5k/mo
- [ ] Pricing: $49 launch, $79 standard
- [ ] Bundling: every paid Tapeline subscriber gets the course free
  (retention + upsell vector)
- [ ] Marketing: SEO landing page, email drip mention, weekly digest

Estimated: 100-300 sales in Year 1 at $49 = $5-15k. Real value is the
warm-audience build.

### 5. Newsletter integration / partnerships

Established finance newsletters (Daily Upside, Compound Capital,
Snacks by Robinhood, Morning Brew Money) reach 100k-500k subscribers
each. A licensing deal — "Tapeline data inside the newsletter, with
attribution" — is a one-shot brand boost + revenue stream.

Deliver `outputs/newsletter-partnerships.md`:
- [ ] Target list: 5 newsletters with paying-customer overlap
- [ ] Offer structure: $X/mo flat fee + 20% rev share on Tapeline
  subscribers attributed to that newsletter
- [ ] Content surface: a "Tapeline weekly score recap" 200-word
  block in the newsletter, dynamically generated
- [ ] Engineering: ~2 weeks (RSS endpoint exposing the scorecard +
  attribution pixel)

### 6. Acquihire targets

Look for retail-finance tools with:
- Active product (not abandoned)
- 1-3 founders considering shutdown
- A paying customer base of 200-2,000 in a tangential vertical
- No acquirer interest from larger fintechs yet

Quarterly: produce a list of 5-10 candidate targets with notes on
why each could fold into Tapeline. Targets may be open-source or
indie SaaS that ran out of runway.

### 7. Acquisition partners (Year 2+)

Companies that might want to buy Tapeline in 18-36 months:
- **Public.com** — building "social investing" — Tapeline's scoring
  layer fills a gap
- **eToro** — owns the social side, lacks a quant overlay
- **Trade Republic** (EU) — same logic, pre-IPO
- **Robinhood** — has scoring via "Robinhood Snacks" but it's
  thin; could buy depth
- **Charles Schwab** — historically buys boutique research
- **Morningstar** — has the brand but their retail product is dated

Quarterly: produce a memo on these companies' recent moves +
inferred strategic gaps. NOT for outreach; for the founder's
optionality awareness.

### 8. Quarterly strategy memo

End of each quarter: `outputs/leverage-2026-Q{n}.md`:
- Status of each workstream (started / in-progress / shipped /
  deferred)
- New opportunities surfaced
- Recommendations for next quarter's focus

## Tools / integrations

- WebSearch for competitive intel + market sizing
- Read access to Tapeline metrics (paid users, churn, LTV) once
  available
- Output: memos to `outputs/leverage-*.md`. NEVER ship code or
  partnerships without owner approval.

## Success criteria

1. **Affiliate program live** within 90 days of Tapeline launch,
   driving 10%+ of paid signups by month 6
2. **API tier launched** within 12 months, $5k+ MRR by month 18
3. **White-label** signed first 5 RIA customers within 12 months
4. **Course** shipped + 100+ sales within 6 months
5. **Quarterly memos** delivered every quarter with at least one
   actionable recommendation each

## Recommended starter prompt

> I'm picking up the business-leverage handover at
> `docs/handovers/business-leverage.md`. Read it, then read CLAUDE.md
> for context on Tapeline's positioning + boundaries. Your first
> deliverable is the affiliate program design at
> `outputs/affiliate-program-design.md` — full economic model + tooling
> recommendation. Don't write code; this is strategy. Owner reviews
> before any implementation work.
