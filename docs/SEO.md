# SEO Strategy & Operating Plan

**Last updated:** 2026-05-10
**Owner:** Founder
**Status:** Active — foundations branch shipped, growth work in flight

---

## TL;DR

Tapeline is a pre-launch quantitative stock scanner. We have a strong product story (public formula, public scorecard), strong site IA (681 URLs in sitemap), and **zero presence in Google's index** as of the audit. The job is to land the technical foundations cleanly, ship enough programmatic surface to compound, and build authority via content + comparison pages — without wasting the first six months on link spam.

This doc is the operating plan, not a one-time deliverable. Update it when something changes.

---

## 1. Strategy in one paragraph

We win by being the **only** stock-scanner brand that publishes (a) the exact composite scoring formula and (b) a per-pick public scorecard back-checked next-day vs SPY. Every page on the site should make one of those two transparency claims credible. SEO compounds that positioning: comparison pages capture commercial-investigation traffic ("finviz alternative", "tapeline vs zacks"), per-ticker pages capture branded-data traffic ("AAPL stock score"), programmatic sector/signal pages capture browse-mode traffic ("best technology stocks 2026"), and the blog captures top-of-funnel methodology traffic that converts via the differentiated story.

---

## 2. Page architecture & priorities

| Tier | Type                               | Pages                                                                                | Priority | Why                                                                            |
| ---- | ---------------------------------- | ------------------------------------------------------------------------------------ | -------- | ------------------------------------------------------------------------------ |
| P0   | Brand / homepage                   | `/`                                                                                  | 1.0      | Brand queries land here; converts → trial                                      |
| P0   | Pricing                            | `/pricing`                                                                           | 0.9      | High commercial intent; FAQ schema for "tapeline pricing"                      |
| P0   | Methodology                        | `/how-it-works`                                                                      | 0.9      | The transparency claim made concrete; FAQ schema                               |
| P0   | Public scorecard                   | `/scorecard`                                                                         | 0.9      | The receipt; biggest trust artifact                                            |
| P1   | Comparison vs competitor           | `/compare/{finviz, zacks, wallstreetzen, tradingview, trade-ideas, koyfin}`           | 0.8      | Highest commercial intent off-brand                                            |
| P1   | "Best X" listicles                 | `/best-finviz-alternatives`, `/best-stock-scanners`                                  | 0.8      | Top-funnel commercial-investigation                                            |
| P1   | Per-ticker programmatic            | `/t/{symbol}` × 500 (top by score)                                                   | 0.7      | The 650-URL bet; long-tail "AAPL stock score"                                  |
| P1   | Sector programmatic                | `/sector/{slug}` × 11 sectors                                                        | 0.7      | Browse intent: "best technology stocks 2026"                                   |
| P1   | Signal-level programmatic          | `/signal/{slug}` × 6 labels                                                          | 0.7      | "high conviction stocks", "stocks scoring strong setup"                        |
| P1   | Blog (methodology + commentary)    | `/blog/{slug}`                                                                       | 0.6      | Top-of-funnel + topical authority                                              |
| P2   | Trust / supporting                 | `/security`, `/status`, `/changelog`, `/roadmap`, `/support`                         | 0.4–0.6  | Brand-query support + E-E-A-T                                                  |
| P2   | Auth                               | `/signin`, `/signup`                                                                 | 0.4–0.6  | Brand queries ("tapeline signin")                                              |
| P2   | Legal                              | `/legal/{terms, privacy, risk}`                                                      | 0.3      | Required + brand-query support                                                 |

**Total currently in sitemap:** ~700 URLs (homepage + ~20 statics + 11 sectors + 6 signals + 4 blog + ~500 tickers + 6 compare + 2 listicles).

---

## 3. Keyword strategy

### 3.1 Tier-A targets (rank top-3 within 6 months — high intent + winnable)

| Keyword                                 | Intent       | Target page                     | Why winnable                                       |
| --------------------------------------- | ------------ | ------------------------------- | -------------------------------------------------- |
| tapeline / tapeline io / tapeline.io    | Brand        | `/`                             | Should be #1 once indexed                          |
| tapeline pricing                        | Brand+commercial | `/pricing`                  | FAQ schema + clear pricing block                   |
| tapeline review                         | Brand+investigation | `/scorecard` or `/`      | Build via review listicles linking to scorecard    |
| tapeline vs finviz                      | Comparison   | `/compare/finviz`               | We own the brand; honest tradeoffs                 |
| tapeline vs zacks                       | Comparison   | `/compare/zacks`                | Same                                               |
| tapeline vs tradingview                 | Comparison   | `/compare/tradingview`          | Lower volume but high intent                       |
| {TICKER} stock score                    | Long-tail    | `/t/{TICKER}`                   | 500 ticker pages × the long-tail tail              |
| {TICKER} tapeline score                 | Branded long-tail | `/t/{TICKER}`              | Defensible as soon as ticker pages index           |
| stock scanner with public formula       | Niche commercial | `/how-it-works` or `/`     | Few competitors target this; we own the angle      |
| transparent stock scanner               | Niche commercial | `/`                         | Same                                               |

### 3.2 Tier-B targets (rank top-10 within 12 months — competitive but reachable)

| Keyword                                 | Intent       | Target page                     | Strategy                                           |
| --------------------------------------- | ------------ | ------------------------------- | -------------------------------------------------- |
| finviz alternative / finviz alternatives | Commercial-investigation | `/best-finviz-alternatives` | Listicle + comparison cluster; own answer        |
| best stock scanner / best stock scanners | Commercial-investigation | `/best-stock-scanners`   | Same                                               |
| best stock scanner 2026                 | Commercial-investigation | `/best-stock-scanners`  | Year-stamped freshness                            |
| zacks alternative                       | Commercial-investigation | `/compare/zacks`         | Strong because we lead with their honest tradeoffs |
| tradingview alternative                 | Commercial-investigation | `/compare/tradingview`   | Honest "use both" angle                            |
| stock scanner free trial                | Commercial   | `/signup`                       | Trial language + signup intent                     |
| best technology stocks {YEAR}           | Browse       | `/sector/technology`            | Programmatic; one URL per sector                   |
| best healthcare stocks {YEAR}           | Browse       | `/sector/healthcare`            | Same                                               |
| high conviction stocks                  | Specialised browse | `/signal/high-conviction` | Brand-defined term; we own it                    |
| congressional trades stock scanner      | Niche commercial | Premium-tier feature page (TODO) | We have the data feed; build dedicated landing |
| 13F holdings tracker                    | Niche commercial | Premium-tier feature page (TODO) | Same                                            |

### 3.3 Tier-C targets (top-20 within 12 months — broad informational, supports topical authority)

| Keyword                                 | Intent      | Target page                     |
| --------------------------------------- | ----------- | ------------------------------- |
| how to evaluate a stock scanner         | Informational | `/blog/evaluating-a-stock-scanner` ✓ shipped |
| what does HIGH CONVICTION mean stocks   | Informational | `/blog/what-signal-labels-mean` ✓ shipped |
| how to read RSI                         | Informational | TODO blog post                  |
| how to use MACD                         | Informational | TODO blog post                  |
| what is bollinger band squeeze          | Informational | TODO blog post                  |
| how do congressional stock trades work  | Informational | TODO blog post                  |
| how to read a 13F filing                | Informational | TODO blog post                  |
| best technical indicators for swing trading | Informational | TODO blog post              |
| sector rotation strategy                | Informational | TODO blog post                  |
| public formula vs proprietary score     | Informational | `/blog/the-formula-is-public` ✓ shipped |

**Volume note:** estimates omitted on purpose — green-field tracking. Once GA4 + GSC are wired (see §6), measure actual impressions/clicks per query and reprioritise based on lift, not assumed volume.

---

## 4. Content roadmap — next 10 blog posts (briefs)

Posts are ordered by ROI: each one targets a Tier-B/C keyword, internally links to a P0 or P1 surface, and uses our credibility frame (public formula, public scorecard).

### Post 1: How to read RSI (and why it's only 1 of 6 things in our score)

- **Target:** "how to read RSI", "RSI indicator", "RSI explained"
- **Angle:** Honest primer that ends with "RSI is one input — the score is the synthesis"
- **Internal links:** `/how-it-works` (factor weight callout), `/t/{TICKER}` example
- **Length:** 1,500–2,000 words
- **Schema:** Article + FAQ
- **CTA:** Trial signup

### Post 2: A trader's guide to 13F filings (and how Tapeline tracks 8 elite funds)

- **Target:** "how to read a 13F", "13F filing tracker", "what is 13F filing"
- **Angle:** Plain-English explainer + the 8 elite funds we curate
- **Internal links:** Premium pricing page, `/how-it-works` (smart money factor)
- **Length:** 1,500 words
- **Schema:** Article + FAQ
- **CTA:** Premium trial

### Post 3: Bollinger Band squeeze — the setup, the false signals, and how we score it

- **Target:** "bollinger band squeeze", "how to find squeezes"
- **Angle:** Standalone primer + how Tapeline scores it (BB compression + volume + OBV)
- **Internal links:** `/how-it-works` (momentum factor), `/signal/strong-setup` example
- **Length:** 1,800 words

### Post 4: Sector rotation in 2026 — what's leading and how to read the regime

- **Target:** "sector rotation strategy", "current sector rotation", "what sectors are leading"
- **Angle:** Updated quarterly with current regime + how the macro factor weights it
- **Internal links:** `/sector/{leading-sector}`, `/how-it-works` (macro factor)
- **Length:** 2,000 words
- **Refresh quarterly** so it stays current — date the URL `/blog/sector-rotation-2026-q2`

### Post 5: How to evaluate any stock scanner's track record

- **Target:** "stock scanner accuracy", "stock scanner backtest", "are stock scanners worth it"
- **Angle:** What "public scorecard" means + why 99% of competitors hide it
- **Internal links:** `/scorecard`, `/best-stock-scanners`
- **Length:** 1,500 words

### Post 6: Congressional stock trades — what's actually disclosed and what it means

- **Target:** "congressional stock trades", "Pelosi tracker", "house senate stock trades"
- **Angle:** STOCK Act disclosure rules + the data feed we use + ethical caveats
- **Internal links:** Premium pricing page (Congress feed), `/how-it-works` (smart money)
- **Length:** 2,000 words

### Post 7: The case against AI-powered stock scanners (from someone who built one)

- **Target:** "AI stock scanner", "best AI stock picker", "AI stock signals"
- **Angle:** Why we publish the formula instead of using a black-box ML model
- **Internal links:** `/how-it-works`, `/compare/trade-ideas`
- **Length:** 1,800 words

### Post 8: A taxonomy of stock-scanner pricing — what you're actually paying for

- **Target:** "stock scanner price comparison", "stock scanner pricing", "is finviz worth it"
- **Angle:** Honest breakdown of Finviz/Zacks/TradingView/Trade Ideas/etc. pricing tiers and what each unlocks
- **Internal links:** All 6 `/compare/*` pages, `/pricing`, `/best-stock-scanners`
- **Length:** 2,500 words

### Post 9: Why descriptive labels beat buy/sell ratings (legal + cognitive)

- **Target:** "descriptive vs prescriptive ratings", "stock rating systems"
- **Angle:** Why we label HIGH CONVICTION instead of BUY (legal + behavioural)
- **Internal links:** `/legal/risk`, `/signal/high-conviction`, all signal pages
- **Length:** 1,200 words

### Post 10: The Tapeline scorecard at 90 days — what we've learned

- **Target:** Brand + "tapeline review", "tapeline performance"
- **Angle:** Quarterly retro of the public scorecard with hit rate, miss analysis, upcoming changes
- **Internal links:** `/scorecard`, `/changelog`
- **Length:** 1,500 words
- **Cadence:** Repeat quarterly

---

## 5. Link-building / authority plan

### 5.1 Listings & directories (week 1-2, low effort)

- Product Hunt launch (own asset; drives initial referral + SEO juice)
- BetaList
- Indie Hackers product directory
- StackShare / G2 (free profiles)
- TrustPilot, Sitejabber (begin collecting reviews from early users)
- AlternativeTo.net (list as alternative to Finviz, Zacks, TradingView)
- Capterra, Software Advice (Gartner-owned listings — reach into B2B keyword sets)

### 5.2 Communities (months 1-3, sustained presence)

- r/algotrading, r/stocks, r/investing, r/quant — answer questions, link only when genuinely relevant
- StockTwits, Twitter/X — share daily picks via per-ticker share links (the OG card sells itself)
- Hacker News — post the "public formula" angle as a Show HN
- Discord servers for trading communities

### 5.3 Earned media (months 2-6)

Pitch list:
- Benzinga (covers retail trading tools regularly)
- The Tokenist (alt-investing publication)
- StockBrokers.com / TopStockResearch (review aggregators)
- Investopedia (we have a unique angle — public scorecard)
- Fintech newsletters: Net Interest, FinTech Brainfood, Money Stuff (Matt Levine — a long shot but the public-scorecard angle is genuinely interesting)

Pitch angle: "the only retail stock scanner that publishes its formula AND its track record" — concrete, novel, easy to verify.

### 5.4 Reciprocal / partnership links (month 3+)

- Cross-promote with other transparent fintech tools (Plaid Atlas, Atom Finance equivalents)
- Guest posts on adjacent newsletters (algorithmic trading, indie finance tooling)
- Podcast appearances (Trader Mike, Top Trading Performance, Animal Spirits)

### 5.5 What to avoid

- **No paid link networks, PBNs, or paid guest posts on low-authority sites.** Manual penalty risk.
- **No directory submission spam.** Capterra + AlternativeTo + Product Hunt are enough.
- **No reciprocal link schemes.** Earn links by being useful, not by trading them.

---

## 6. Technical SEO setup (do these in order)

### 6.1 Search Console (week 1)

1. Add tapeline.io as a Domain property (covers all subdomains + protocols)
2. Verify via DNS TXT record (Fly.io / Cloudflare DNS supports this)
3. Submit `https://tapeline.io/sitemap.xml` under Sitemaps
4. Use **URL Inspection** tool to manually request indexing for: `/`, `/pricing`, `/how-it-works`, `/scorecard`, all 6 `/compare/*`, `/best-finviz-alternatives`, `/best-stock-scanners`
5. Wait 2-4 weeks; check Coverage report for indexation status

### 6.2 Bing Webmaster (week 1)

1. Add tapeline.io
2. Verify (can import GSC verification automatically)
3. Submit sitemap
4. Bing also covers Yahoo + DuckDuckGo (~10-15% of US search) — don't skip

### 6.3 IndexNow (week 1)

Bing/Yandex/Naver real-time indexing protocol. Add a tiny endpoint that pings IndexNow whenever a URL is published or a major change ships.
- Implementation: Next.js API route at `/api/internal/indexnow-ping` that accepts a list of URLs and POSTs to IndexNow
- Trigger: from CI on `main` deploy, or manually for new blog posts
- Spec: https://www.indexnow.org

### 6.4 GA4 (week 1)

1. Create GA4 property for tapeline.io
2. Wire via env var `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` (already supported in layout.tsx) — but we're using Plausible, so flip GA4 on as a complement, not replacement
3. Set up conversions: trial signup, paid conversion, pricing page view
4. Link GA4 to Search Console for keyword-level conversion attribution

### 6.5 Schema.org structured data — verify

After deploying this branch, run each page type through:
- https://search.google.com/test/rich-results
- https://validator.schema.org

Pages to verify:
- `/` (Organization, WebSite, SoftwareApplication)
- `/pricing` (FAQPage)
- `/how-it-works` (FAQPage)
- `/compare/{any}` (FAQPage)
- `/t/{any}` (Review/FinancialProduct, FAQPage, BreadcrumbList)
- `/blog/{any}` (Article)
- `/best-{anything}` (ItemList, FAQPage)
- `/sector/{any}` (BreadcrumbList, FAQPage)
- `/signal/{any}` (BreadcrumbList, FAQPage)

### 6.6 Core Web Vitals

Run a Lighthouse audit after deploy. Specifically check:
- LCP < 2.5s (hero image / first paint)
- CLS < 0.1 (the LiveCounters strip on home is the most likely CLS offender — pre-allocate height)
- INP < 200ms (the live polling on /scorecard could spike this)

### 6.7 robots.txt review

Current `robots.txt` blocks `/app/*` and `/api/*` (correct). Consider adding:
```
Sitemap: https://tapeline.io/sitemap.xml
Host: tapeline.io
```

`Host:` directive is Yandex-specific but harmless elsewhere. The `Sitemap:` directive is already there.

---

## 7. Internal linking strategy

The most under-used SEO lever is internal linking. Rules:

1. **Every per-ticker page** (`/t/{TICKER}`) links to: `/how-it-works`, `/scorecard`, 2-3 `/compare/*` pages, `/blog`. Already done in the new related-pages nav.
2. **Every comparison page** links to: at least 2 sibling `/compare/*` pages (cross-pollination of compare cluster).
3. **Every blog post** links to: at least 1 P0 page (`/`, `/pricing`, `/how-it-works`, `/scorecard`) — already done.
4. **`/sector/{X}`** links to all other sectors (already done in sister-sectors nav).
5. **`/signal/{X}`** links to all other signals (already done).
6. **Listicle pages** (`/best-*`) link to relevant `/compare/*` pages (already done).
7. **Footer** should include: `/how-it-works`, `/scorecard`, `/blog`, `/pricing`, `/security`, `/legal/*`. Audit MarketingFooter component for completeness.

Anchor text rule: use the **target page's keyword** as the anchor, not "click here". E.g. link to `/scorecard` as "the public scorecard" not "click to see".

---

## 8. KPIs & cadence

### Weekly (every Monday)

- GSC Performance: total impressions, clicks, top 10 queries, top 10 pages
- GA4 Acquisition: organic sessions, organic conversions
- Indexed-page count (GSC Coverage)

### Monthly

- Position tracking on Tier-A keywords (use a free Bing Webmaster export or a tool like SerpRobot)
- New backlinks (Ahrefs free Webmaster Tools or Majestic free tier)
- New blog posts shipped (target: 2-4/month)

### Quarterly

- Reprioritise keyword targets based on actual GSC impression/click data
- Refresh `/best-stock-scanners` and `/best-finviz-alternatives` (year-stamped pages decay)
- Quarterly scorecard retro post (Post 10 in §4)

### Goals (rough)

- Month 1: 50% of submitted pages indexed; first ranking impression
- Month 3: 5,000 monthly organic impressions; 100 organic clicks; ranking on at least 3 Tier-A keywords
- Month 6: 50,000 monthly organic impressions; 1,000 organic clicks; ranking top-3 on `tapeline pricing`, `tapeline vs {finviz|zacks}`, top-10 on `finviz alternative`
- Month 12: 200,000+ monthly organic impressions; 5,000+ organic clicks; ranking on the bulk of `/sector/*` and the top-100 ticker queries

---

## 9. What's shipped in this branch (`claude/seo-foundations`)

- **Layout fixes:** title.template (was double-applying brand suffix), pricing accuracy in description + JSON-LD, added WebSite + SearchAction schema, added Twitter sameAs to Organization schema
- **Per-page metadata:** every page now has its own title, description, canonical, openGraph, and twitter tags via the new `lib/seo.ts` `pageMeta()` helper. Previously most pages inherited the homepage OG tags, breaking social shares.
- **JSON-LD structured data:** added FAQPage on /pricing, /how-it-works, /compare/*, /t/{symbol}, /best-*, /sector/*, /signal/*; Article on blog posts; Review/FinancialProduct + BreadcrumbList on ticker pages; ItemList on listicles
- **New compare pages:** /compare/tradingview, /compare/trade-ideas, /compare/koyfin (using new shared CompareLayout component)
- **New listicle pages:** /best-finviz-alternatives (8 tools), /best-stock-scanners (10 tools)
- **New programmatic routes:** /sector/{slug} × 11 sectors, /signal/{slug} × 6 signal levels — fetches live snapshots from /api/scanner cached 5 min
- **Ticker page enrichment:** added on-page FAQ block (5 Qs per ticker), related-pages nav with anchor-text-optimised internal links, fixed title to remove duplicate brand suffix
- **Sitemap:** added all new routes (3 new compare URLs, 2 listicles, 11 sectors, 6 signals)

**Not in this branch (next session):**
- Search Console / Bing / IndexNow setup (operational, not code)
- 10 new blog posts from §4
- Off-site: Product Hunt, BetaList, AlternativeTo listings
- Premium-feature dedicated landing pages (`/features/congressional-trades`, `/features/13f-holdings`)
- Backend `/api/public/scanner` endpoint so /sector and /signal pages don't depend on the auth-gated /api/scanner free-tier rows

---

## 10. Open decisions

1. **Author attribution.** Currently every blog post is "Tapeline" (org-as-author). For E-E-A-T, would benefit from a real bylined author. Decide whether to attribute to the founder (best for trust), invent a brand persona (lower trust, easier scaling), or wait until there's a writing team.
2. **Year-stamped pages.** `/best-stock-scanners` includes "2026" in the title. Decide whether to keep year-stamped + refresh quarterly, or strip the year and rely on lastmod freshness.
3. **Page-by-page noindex policy.** Currently every page is `index, follow`. Consider noindexing `/signin`, `/signup`, and the paginated app routes to focus crawl budget. Tradeoff: brand queries like "tapeline signin" stop landing on the right page if noindexed.
4. **Backend SEO endpoints.** The /sector and /signal pages currently depend on /api/scanner returning the free-tier 20 rows. A dedicated `/api/public/scanner-snapshot` endpoint would let us return larger rankings (50-100) without auth gating, which would meaningfully improve those programmatic pages.

---

## 11. References

- Schema.org: https://schema.org
- Google Search Central: https://developers.google.com/search/docs
- IndexNow spec: https://www.indexnow.org/documentation/key-location
- Next.js metadata docs: https://nextjs.org/docs/app/api-reference/functions/generate-metadata
