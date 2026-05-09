# Handover: SEO agent

## Mission

Maximise organic discovery for Tapeline against the queries retail
traders actually type. The pre-launch goal is to be ranking on page 1
within 90 days for at least three of:
- "TICKER stock score" (per-ticker pages)
- "best stock scanner" / "stock scanner that shows its work"
- "Zacks alternative" / "TipRanks alternative" / "WallStreetZen
  alternative"
- "public stock scorecard"
- "transparent stock rating system"

## Why this matters

TipRanks ranks page 1 for nearly every "TICKER stock forecast" query
because they have 6,000+ structured per-ticker pages indexed.
Tapeline already has the structured per-ticker page (`/t/{symbol}`),
the public formula, and the public scorecard — three concrete moats
TipRanks doesn't have. The content exists; the SEO layer needs to
make sure Google can find, parse, and rank it.

## Scope

### IN scope
1. Audit current on-page SEO across every public surface
2. Generate ticker-specific structured-data JSON-LD blocks for each
   `/t/{symbol}` page (Schema.org `FinancialProduct` + `Review`)
3. Build a "seed posts" pipeline — generate one piece of long-form
   content per ticker for the top 50 most-traded names
4. Audit and improve internal linking between transparency pages
5. Submit sitemap + propose Google Search Console setup
6. Generate one **monthly content review** in `outputs/seo-YYYY-MM.md`
   covering: pages indexed, pages ranking, top opportunity gaps

### OUT of scope
- Paid ads (different agent / decision)
- Backlink outreach (a marketing/PR job)
- Keyword stuffing or thin per-ticker spam pages — Google penalises
  these and they break the brand
- Any change to the 6-factor formula or signal labels for "SEO reasons"

## Concrete tasks (priority-ordered)

### 1. SEO audit

For each of: `/`, `/pricing`, `/how-it-works`, `/scorecard`,
`/security`, `/blog`, `/blog/<slug>`, `/compare/finviz`, `/compare/zacks`,
`/compare/wallstreetzen`, `/t/AAPL` (representative),
`/legal/{terms,privacy,risk}`:

- [ ] Title tag — under 60 chars, primary keyword in front
- [ ] Meta description — 130-160 chars, action-oriented
- [ ] H1 — single per page, contains primary keyword
- [ ] H2 hierarchy — logical, scannable
- [ ] Open Graph + Twitter card — image, title, description present
- [ ] Canonical URL set
- [ ] Internal links — 2-5 per page minimum, descriptive anchor text
- [ ] No `noindex` accidentally on indexable pages

Output: `outputs/seo-audit-2026-MM-DD.md` with row-by-row findings.

### 2. JSON-LD structured data on `/t/{symbol}`

The `/t/{symbol}` page is Tapeline's biggest SEO surface (~500 indexed
URLs growing). Add JSON-LD structured data so Google can render rich
results:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Review",
  "itemReviewed": {
    "@type": "FinancialProduct",
    "name": "AAPL",
    "alternateName": "Apple Inc."
  },
  "reviewRating": {
    "@type": "Rating",
    "ratingValue": "56",
    "bestRating": "100",
    "worstRating": "0"
  },
  "author": {"@type": "Organization", "name": "Tapeline"},
  "reviewBody": "Tapeline Score 56/100 (CONSTRUCTIVE) — breakout from multi-month base...",
  "datePublished": "2026-05-08T07:00:00Z"
}
</script>
```

- [ ] Inject into `frontend/app/t/[symbol]/page.tsx` head
- [ ] Validate using Google's Rich Results Test
  (https://search.google.com/test/rich-results)
- [ ] Wait 2-4 weeks, check Search Console for Rich Result coverage

### 3. Long-form per-ticker content (top 50 only)

For each of the 50 most-actively-traded tickers (NVDA, AAPL, MSFT,
AMZN, META, GOOGL, TSLA, AMD, PLTR, NFLX, AVGO, COST, JPM, V, MA, LLY,
UNH, etc.):

- [ ] Generate a 600-800 word "What is the Tapeline Score for $TICKER?"
  blog post following this template:
  - Intro: what TICKER scores today + the signal
  - 6-factor breakdown — what each factor sees
  - How TICKER compares to its sector peers
  - What the public scorecard says about TICKER's recent picks
  - Honest disclaimer (descriptive, not investment advice)
- [ ] Each post links to `/t/{TICKER}`, `/scorecard`, `/how-it-works`,
  and the relevant `/compare/*` page
- [ ] Slug pattern: `/blog/tapeline-score-explained-{ticker-lower}`
- [ ] Publish 1-2/week to avoid Google penalising "content dump" patterns

### 4. Internal linking audit

- [ ] Generate a graph of every internal link in the public site
- [ ] Identify orphan pages (no incoming links beyond nav/footer)
- [ ] Identify "linkrot risk" — pages linking to deleted slugs
- [ ] Recommend specific link additions: e.g. "/scorecard should link
  to /how-it-works in the methodology section"

### 5. Sitemap + Google Search Console

- [ ] Verify `/sitemap.xml` is valid against Google's spec
- [ ] Submit sitemap via Search Console (owner action — agent
  produces the click-by-click)
- [ ] Generate weekly indexing report: how many of the submitted URLs
  are actually indexed?
- [ ] If indexing rate < 60%, identify what's blocking (thin content,
  duplicate, robots, etc.)

### 6. Monthly content review

End of each month, produce `outputs/seo-2026-MM.md` covering:
- Pages indexed (delta vs last month)
- Top 10 ranking pages (queries + positions, from Search Console)
- Pages dropped out of index (with diagnosis)
- New keyword opportunities (queries getting impressions but no clicks
  → could be answered better)
- Recommended content for next month (3-5 specific posts)

## Files / surfaces

```
frontend/app/t/[symbol]/page.tsx        # main per-ticker SEO page
frontend/app/t/[symbol]/opengraph-image.tsx  # OG card
frontend/app/sitemap.ts                 # auto-pulls top 500 tickers
frontend/app/blog/posts.ts              # blog content manifest
frontend/app/robots.txt → frontend/public/robots.txt
backend/app/routers/news.py             # could surface news as SEO content
docs/PRICING.md, docs/OPERATIONS.md    # internal — useful for agent context
```

## Tools / integrations

- WebSearch + WebFetch for SERP probes
- Read access to all Tapeline routes
- Google Search Console API (owner sets up + provides token)
- Google's Rich Results Test (manual URL submission)
- A LLM for content drafting (Claude itself; the agent IS the LLM)

## Success criteria

1. **Indexing: 90% of submitted sitemap URLs indexed within 30 days**
   of submission
2. **Ranking: at least 3 page-1 positions** for the target queries
   within 90 days of launch
3. **JSON-LD rich results showing** in Google for at least 100
   `/t/{symbol}` pages
4. **Monthly review delivered** every month-end without prompting
5. **Zero "thin content" or "doorway page" warnings** in Search Console

## Recommended starter prompt

> I'm picking up the SEO agent handover at `docs/handovers/seo-agent.md`.
> Read it, then read CLAUDE.md, then audit the current state of
> `/`, `/pricing`, `/how-it-works`, `/scorecard`, and `/t/AAPL` for
> on-page SEO. Produce `outputs/seo-audit-2026-05-08.md` with row-by-row
> findings before writing any content. After I review the audit, we'll
> prioritise.
