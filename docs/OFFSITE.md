# Off-Site Presence Checklist

**Last updated:** 2026-05-10
**Owner:** Founder
**Status:** Active — work through this list in priority order; everything is one-time setup unless noted

---

## Why this matters

The on-site SEO work (the `claude/seo-foundations` branch) only goes so far. To rank for anything competitive, Google needs corroborating signals from authoritative third-party sites that confirm Tapeline is a real entity. This is what the `Organization.sameAs` graph in [layout.tsx](../frontend/app/layout.tsx) is for, and what the `/about` and `/press` pages reinforce.

This doc is the operational checklist for creating each of those off-site profiles. Work through it in the priority order below — each one is one-time setup that compounds for years.

**Naming consistency rule:** every profile uses **"Tapeline"** as the display name and **`@tapeline_io`** as the handle where available. If a handle is taken, fall back to **`tapelineio`** (no underscore). Bio: same one-liner everywhere — *"Live quantitative stock scanner. Public 6-factor formula. Public scorecard. tapeline.io"*

> **Paste-ready copy:** this doc says *where* to create each profile. For the exact field-by-field text to paste (taglines, descriptions, char-counted bios for Product Hunt / Crunchbase / G2 / Capterra / AlternativeTo / StockTwits) plus the launch press + backlink pitch (Show HN, Indie Hackers, cold-email template), see **[BRAND_SERP_KIT.md](./BRAND_SERP_KIT.md)**. All strings there are pulled verbatim from [/press](../frontend/app/press/page.tsx) so the entity stays consistent across every platform.

---

## Priority 1 — week 1 (foundational, ~3 hours total)

### ☐ Google Business Profile

- **URL:** https://business.google.com/create
- **Why:** Even though Tapeline is a SaaS, not a local business, a Business Profile unlocks Google Maps presence and feeds Knowledge Panel data. For a SaaS, register as a "service-area business" with no public address.
- **Time:** ~30 min, plus mailed-postcard verification (~7 days)
- **Setup:**
  1. Sign in to Google Business Profile with the same Google account you'll use for GA4 + Search Console
  2. Business name: **Tapeline**
  3. Category: *Software company* (primary), *Financial consultant* (secondary)
  4. Service area: list the country/region where most users are; "all of [country]" is fine
  5. Hours: 24/7 (the product is always-on)
  6. Description: paste the one-liner from the rule above
  7. Logo + cover photo: upload from `/favicon.svg` and `/opengraph-image`
  8. Verify via mailed postcard (or video call if offered)
- **After verification:** request the Knowledge Panel — at https://support.google.com/business/answer/9692654 — supplying the [/about](../frontend/app/about/page.tsx) URL as the canonical entity reference

### ☐ X / Twitter (@tapeline_io)

- **URL:** https://x.com/signup
- **Why:** `twitter:site` and `Organization.sameAs` already reference this. If the account doesn't exist, the schema link 404s.
- **Time:** ~15 min
- **Setup:**
  1. Handle: `@tapeline_io`
  2. Display name: **Tapeline**
  3. Bio: one-liner from the rule above
  4. Website: `https://tapeline.io`
  5. Header image: upload `/opengraph-image`
  6. Profile pic: upload `/favicon.svg` (export as PNG first; X doesn't accept SVG)
  7. Pin a tweet linking to `/scorecard` with the line *"The receipts."*

### ☐ LinkedIn Company Page

- **URL:** https://www.linkedin.com/company/setup/new/
- **Why:** Highest-authority B2B profile. Knowledge Panel pulls from here. Also where journalists check legitimacy.
- **Time:** ~20 min
- **Setup:**
  1. Type: *Small business*
  2. Company name: **Tapeline**
  3. LinkedIn public URL: `linkedin.com/company/tapeline`
  4. Website: `https://tapeline.io`
  5. Industry: *Financial Services* (primary), *Software Development* (secondary)
  6. Company size: 1-10 employees
  7. Tagline: one-liner from the rule above
  8. About section: paste the one-paragraph from [/press](../frontend/app/press/page.tsx)
  9. Add the founder as a "Team member" (creates the company → person link Google watches for)
- **Recurring:** post once a week (any cadence Google sees as alive — even just a link to the latest blog post)

### ☐ GitHub Organization (cham-p24/tapeline → org)

- **URL:** https://github.com/organizations/new
- **Why:** A real org account (vs personal) is a stronger E-E-A-T signal. Already linked from `Organization.sameAs`.
- **Time:** ~10 min
- **Setup:**
  1. Org name: `tapeline` if available, else `tapeline-io`
  2. Bio: one-liner
  3. Website: `https://tapeline.io`
  4. Migrate the `cham-p24/tapeline` repo into the org (or leave it where it is and add a `tapeline/.github` profile org)
  5. Pin one or two repos that are interesting to read (the methodology, an open-source helper, etc.)
- **If migrating breaks too much:** create a `tapeline-io` org as a profile-only org with a single `.github` repo containing a README, no migration needed.

### ☐ Plausible / GA4 / Search Console / Bing Webmaster

These aren't "profile" pages but they belong on the week-1 list because everything else needs them for measurement:

- Search Console: https://search.google.com/search-console — verify domain via DNS
- Bing Webmaster: https://www.bing.com/webmasters — import GSC verification
- Plausible: already wired via `NEXT_PUBLIC_PLAUSIBLE_DOMAIN` env var; just flip the env var on
- GA4: https://analytics.google.com — set up `tapeline.io` property; link to GSC

---

## Priority 2 — week 2 (commercial-investigation listings, ~2 hours total)

### ☐ Product Hunt

- **URL:** https://www.producthunt.com/posts/new
- **Why:** Drives initial referral traffic + a one-time backlink burst that helps Google notice the site exists
- **Time:** ~45 min for the launch post itself; need a maker bio + screenshots ready
- **Setup:**
  1. Maker account first (sign in with X)
  2. Submit Tapeline as a product
  3. Tagline (max 60 chars): *"Stock scanner that shows its work — public formula, public scorecard"*
  4. Description: 2-3 paragraphs from [/press](../frontend/app/press/page.tsx)
  5. Screenshots from `/screenshot kit` section of /press
  6. Pricing: link to `/pricing`
  7. **Schedule the launch for a Tuesday at 12:01am PT** — the algorithm window is Pacific midnight; weekday days >> weekends
- **Recurring (one-time):** ask 5-10 active users to upvote in the first 4 hours; the comment thread is the primary ranking signal

### ☐ AlternativeTo.net

- **URL:** https://alternativeto.net/contribute/
- **Why:** Listed as alternative to Finviz / Zacks / TradingView / Trade Ideas → captures search queries like "finviz alternative reddit" via AlternativeTo's own SEO power
- **Time:** ~30 min
- **Setup:**
  1. Add Tapeline as a new application
  2. Categories: *Stock Analyzer*, *Stock Quote*, *Stock Picker*
  3. Mark as alternative to: Finviz, Zacks, WallStreetZen, TradingView, Trade Ideas, Koyfin (the same set as our `/compare/*` pages — no coincidence)
  4. Pricing: Free / Freemium
  5. Platforms: Web
  6. Description: one-paragraph from [/press](../frontend/app/press/page.tsx)
  7. Add the same screenshots as Product Hunt

### ☐ G2

- **URL:** https://sell.g2.com/
- **Why:** The biggest B2B software directory. Even with zero reviews initially, the profile creates a brand-query landing page Google trusts highly.
- **Time:** ~30 min
- **Setup:**
  1. Create vendor account
  2. Submit product: **Tapeline**
  3. Category: *Stock Analysis Software* / *Investment Research Software*
  4. Use the same one-paragraph + screenshots as everywhere else
  5. Add comparison set: Finviz, Zacks, TradingView (G2 builds comparison pages automatically)
- **Recurring:** ask paying users for reviews via email after 30 days. Aim for 10 reviews in the first 90 days.

### ☐ Capterra

- **URL:** https://www.capterra.com/vendors/sign-up
- **Why:** Same playbook as G2 (Gartner-owned, parallel directory). Capterra also feeds Software Advice and GetApp from the same listing.
- **Time:** ~20 min (one form covers G2's sister network too)

---

## Priority 3 — week 3+ (community + content distribution, ongoing)

### ☐ Reddit (u/tapeline_io)

- **URL:** https://www.reddit.com/register
- **Why:** Reddit threads now rank in Google for almost every product comparison query. Having a verified account in the relevant subreddits builds long-term presence.
- **Setup:**
  1. Create the account
  2. Spend 2 weeks lurking + commenting in r/algotrading, r/stocks, r/investing, r/quant, r/wallstreetbets — build karma BEFORE posting anything promotional
  3. After 2 weeks, contribute substantively to threads where Tapeline solves the asker's problem (rule: link only if it answers the question better than not linking)
- **Recurring:** weekly substantive comment in at least one subreddit. NEVER paste the same link twice in a week — Reddit shadow-bans this fast.

### ☐ Substack newsletter

- **URL:** https://substack.com/sign-up
- **Why:** Owned distribution. Email list compounds independent of Google's algorithm. Also a backlinkable source — every issue links back to tapeline.io.
- **Setup:**
  1. Publication name: **Tapeline Notes** (or whatever the founder prefers)
  2. URL: `tapeline.substack.com`
  3. About: link back to `/about`
  4. First post: cross-post one of the existing `/blog` posts
- **Recurring:** weekly recap (the [generate-weekly-recap.mjs](../frontend/scripts/generate-weekly-recap.mjs) script outputs material)

### ☐ YouTube channel

- **URL:** https://www.youtube.com/create_channel
- **Why:** YouTube is the second-largest search engine; ranks via Google's algorithm directly
- **Setup:**
  1. Channel name: **Tapeline**
  2. Handle: `@tapeline`
  3. Banner: same brand asset as the X header
  4. About: one-paragraph + link to tapeline.io
  5. First video: 3-min screencast of the scanner, uploaded once
- **Recurring:** monthly walkthrough video (signal-of-the-week, methodology deep-dive). Lower priority than text content.

### ☐ Crunchbase

- **URL:** https://www.crunchbase.com/add-new
- **Why:** Knowledge Panel cross-reference. Journalists check Crunchbase to verify a company is real before covering.
- **Setup:**
  1. Add Tapeline as a company
  2. Founded date: 2025
  3. Founders: link the founder's Crunchbase person page (create one if not existing)
  4. Operating status: Active
  5. Description: one-paragraph
  6. Funding: Bootstrapped ($0 raised — explicitly say so)
  7. Categories: *Software*, *Financial Services*, *Stock Trading*

### ☐ StockTwits

- **URL:** https://stocktwits.com/signup
- **Why:** Niche-but-relevant — StockTwits users are exactly Tapeline's ICP, and the platform ranks well for ticker queries
- **Setup:**
  1. Handle: `@tapeline`
  2. Bio: one-liner
  3. Pin a post linking to `/scorecard`
- **Recurring:** post the daily top-10 from `/scorecard` (or the weekly recap) — DO NOT just spam tickers; stay informational

---

## Priority 4 — month 2-3 (earned coverage, push when ready)

These are PR/outreach moves that need a finished off-site graph (priorities 1-3) before they're worth attempting — journalists Google a brand before responding.

- **Hacker News** — Show HN with the angle "Stock scanner that publishes its formula and its scorecard"
- **Indie Hackers** — bootstrapped-SaaS post (Tapeline is bootstrapped, that's a qualifier)
- **Newsletter pitches:** Net Interest, FinTech Brainfood, Money Stuff (Matt Levine), The Tokenist, Benzinga
- **Podcasts:** Trader Mike, Top Trading Performance, Animal Spirits
- **Industry directories:** Wikipedia (only if eligible — needs independent coverage first), DBpedia, Wikidata (anyone can edit; create the entity once Wikipedia exists)

---

## Synchronisation rules

- **Display name** is always **Tapeline** (no qualifier, no "io")
- **Handle** is `@tapeline_io` first, `tapelineio` second, `tapeline` third (depending on availability per platform)
- **One-liner** is identical everywhere: *"Live quantitative stock scanner. Public 6-factor formula. Public scorecard. tapeline.io"*
- **One-paragraph** lives in [/press](../frontend/app/press/page.tsx); copy from there, never write a fresh one (drift = fragmented entity in Google's eyes)
- **Logo and brand assets** all come from `/favicon.svg` and `/opengraph-image`
- **Founder bio** stays consistent across every personal LinkedIn / Crunchbase Person / About page byline

---

## When you create a profile

After creating each profile, do this in the same session:

1. ✅ Tick the checkbox above
2. ✅ Confirm the URL in [layout.tsx](../frontend/app/layout.tsx) `Organization.sameAs` matches the actual profile URL — adjust if needed
3. ✅ Confirm the URL in [/about](../frontend/app/about/page.tsx) `PROFILES` array matches
4. ✅ Add `rel="me"` linking back to tapeline.io from the profile (where the platform allows — X, GitHub, Substack do; LinkedIn, Crunchbase don't)
5. ✅ Trigger the post-deploy SEO ping via the [Actions tab](https://github.com/cham-p24/tapeline/actions/workflows/post-deploy-seo.yml) so the updated /about page (with new sameAs entries) gets re-indexed

Steps 2-4 are what binds the off-site profile back to tapeline.io as the canonical entity — if you skip them, Google sees the new profile as a separate entity that *happens* to mention Tapeline, not as part of the Tapeline graph.
