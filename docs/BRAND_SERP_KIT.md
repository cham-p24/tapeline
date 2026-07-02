# Brand SERP Kit — paste-ready off-site copy + launch pitch

**Last updated:** 2026-06-01
**Owner:** Founder (operator actions — Claude cannot create accounts or send these)
**Companion to:** [`OFFSITE.md`](./OFFSITE.md) (the *where + steps*) and
[`layout.tsx`](../frontend/app/layout.tsx) `Organization.sameAs` (the entity graph these feed).

---

## Why this doc exists

A Google search for the bare word **"tapeline"** is owned by a dictionary word
(*tapeline* = tape measure), a 40-year-old UK cassette manufacturer
(`tapeline.info`), and `tapeline.com` / `.org`. Per the 2026-05-19 Search Console
audit noted in `layout.tsx`, `tapeline.io` sits ~position 15 for its own name —
but that query draws ~13 impressions / 0 clicks per 90 days. **It is a near-zero
traffic vanity query.** The queries that convert already rank #1:

| Query | tapeline.io rank |
|---|---|
| `tapeline stock scanner` | **#1 — owns the top 4 results** |
| `tapeline.io` | #1 |
| `site:tapeline.io` | fully indexed (5+ pages) |
| bare `tapeline` | ~#15 (low-value, contested) |

On-page markup is already maxed (Organization + WebSite + SoftwareApplication
JSON-LD, `legalName`, `knowsAbout`, full `sameAs`). The **only** remaining lever
for the bare word is *off-site entity authority* — third-party profiles Google
trusts that confirm "Tapeline = US stock-scanner SaaS," plus brand backlinks.
This doc is the exact copy to paste. `OFFSITE.md` is the click-by-click steps.

**Do not chase the bare word as a priority** — it is low ROI and the cassette
company is not a competitor. Treat this kit as launch hygiene that compounds.

---

## Canonical strings — paste verbatim, never reword

> Drift fragments the entity. Every platform uses the *same* name, handle, and
> copy. If you want to change any of these, change them in `/press` first, then
> here.

- **Display name:** `Tapeline` (no qualifier, no "io")
- **Handle ladder (use first available):** `@tapeline_io` → `tapelineio` → `tapeline`
- **One sentence — short (bios, ≤90 chars):**
  ```
  Live quantitative stock scanner. Public 6-factor formula. Public scorecard. tapeline.io
  ```
- **One sentence — formal (press, taglines):**
  ```
  Tapeline is a quantitative stock scanner that publishes its 6-factor scoring formula and back-checks every top-10 daily pick against the next-day SPY-relative move.
  ```
- **One paragraph (the canonical description — verbatim from `/press`):**
  ```
  Tapeline is a quantitative stock scanner for active retail traders, built on the principle that the formula and the track record should both be public. Every US ticker in the active universe gets one 0-100 composite score blended from six published factors — Trend (25%), Relative Strength (20%), Fundamentals (15%), Smart Money (15%), Macro (15%), Momentum (10%) — updated sub-60s during market hours. Every top-10 daily pick auto-publishes to a public scorecard with the realized next-day return vs SPY, immutable and back-checked. Tapeline is bootstrapped, launched in 2026, and competes with Finviz, Zacks, WallStreetZen, TradingView, Trade Ideas, and Koyfin at the $25-40/mo price point.
  ```
- **Fact sheet (verbatim from `/press`):**
  | Field | Value |
  |---|---|
  | Company | Tapeline (tapeline.io) |
  | Founder | Christian Piyatilaka (solo founder) |
  | Founded | 2025 (engine), 2026 (public launch) |
  | Headquarters | Melbourne, Victoria, Australia |
  | Funding | Bootstrapped — no external investment |
  | Pricing | Free · Pro from $8.25/mo (annual) · Premium from $16.58/mo (annual) |
  | Free trial | 14-day Premium, no credit card required |
  | Universe | ~2,500 active US tickers (top by daily $-volume) · 5,757 tracked |
  | Update cadence | Sub-60 seconds during US market hours |
  | Press contact | press@tapeline.io |
- **Logo / social card:** `tapeline.io/favicon.svg` (export to PNG where SVG is
  rejected) and `tapeline.io/opengraph-image` (1200×630 PNG).
- **Founder identity:** always **Christian Piyatilaka** in public copy. (Never
  the private legal first name.)

---

## Part A — Profile-claim copy (the unclaimed `sameAs` platforms)

These six are the authoritative entity platforms currently **404 / unclaimed**
in `Organization.sameAs` (X, LinkedIn, GitHub, Reddit are already live). Claim in
this order — each one, once live, gets added back to `sameAs` and strengthens the
brand entity. After claiming *any* profile, do the **post-claim checklist** at the
bottom of Part A.

### A0 · Google Business Profile — `business.google.com/create`

> **Different from the six below.** GBP isn't a `sameAs` 404 — it's the single
> highest-impact entity profile *for Google specifically* (it feeds the Knowledge
> Panel + Maps). It's also the slowest: it needs **mailed-postcard verification
> (~7–14 days)**, so claim it FIRST even though copy below is faster to deploy.
> Set it up as a **service-area business** (SaaS, no storefront) so no street
> address is shown.

- **Business name:** `Tapeline`
- **Primary category:** `Software company`
- **Secondary category:** *leave blank, or use a software/data category.* ⚠️ Do
  **not** pick `Financial consultant` / `Financial planner` / `Investment service`
  — those labels imply you give financial advice, which cuts directly against the
  publisher's-exemption voice. (This overrides the older "Financial consultant"
  note in `OFFSITE.md` — your call, but the advice-implying category is a real
  legal-posture risk.)
- **Service area:** `United States` (primary market = the ticker universe); add
  `Australia` (home) and any others you actively serve. Hide the physical address.
- **Hours:** `Open 24 hours` (the product is always-on).
- **Website:** `https://tapeline.io`
- **Phone:** optional — skip it, or use a Google Voice / VoIP number (never a personal mobile).
- **Description (paste — GBP allows ≤750 chars, NO URLs / NO pricing / NO promo
  language, so this is a policy-clean variant of the canonical paragraph):**
  ```
  Tapeline is a quantitative stock scanner for active retail traders, built on the principle that the formula and the track record should both be public. Every active US ticker gets one 0-100 composite score blended from six published factors — Trend, Relative Strength, Fundamentals, Smart Money, Macro, and Momentum — updated in under 60 seconds during US market hours, each with a plain-English explanation of the reading. Every top-10 daily pick is logged to a public, back-checked scorecard showing its realized next-day return versus the S&P 500. Tapeline provides descriptive market analytics, not financial advice. Bootstrapped and built in Melbourne, Australia; launched in 2026.
  ```
  *(686 chars — under GBP's 750 limit. Note: GBP descriptions forbid URLs, phone numbers, pricing, and
  promotional/sales language — so this drops the tapeline.io / $-tiers / competitor
  list that the canonical paragraph carries. Everything else is voice-identical.)*
- **Logo:** export `tapeline.io/favicon.svg` to PNG, **min 250×250** (720×720 ideal).
- **Cover photo:** `tapeline.io/opengraph-image` (1200×630 — clears the 1080×608 min).
- **After postcard verification:** request the Knowledge Panel at
  `support.google.com/business/answer/9692654`, supplying the
  [`/about`](../frontend/app/about/page.tsx) URL as the canonical entity reference.
  Then add the public listing URL (`g.page/...` or the Maps URL) to `sameAs` per
  the post-claim checklist below.

### A1 · Product Hunt — `producthunt.com/posts/new`

- **Name:** `Tapeline`
- **Tagline (max 60 chars — use one):**
  ```
  One score, one sentence, and a public track record.
  ```
  *(51 chars. Alt: `Stock scanner that shows its work` — 33 chars.)*
- **Description (short — ~260 chars):**
  ```
  A transparent quantitative stock scanner. Every US ticker gets one 0-100 score from a public 6-factor formula, plus a plain-English "why." Every top-10 daily pick is logged to a public, back-checked scorecard vs SPY. Bootstrapped. Free tier + 14-day Premium trial, no card.
  ```
- **Topics:** `Fintech`, `Stock trading`, `Investing`, `SaaS`, `Analytics`
- **Links:** Website `https://tapeline.io` · Pricing `https://tapeline.io/pricing`
- **Pricing label:** `Freemium`
- **Maker's first comment (paste as the maker — this is the main ranking signal):**
  ```
  Maker here 👋 I'm Christian, solo founder.

  I built Tapeline because every other scanner either gives you 60 raw filter
  fields and a blank stare, or an "AI pick" with no way to check it. Tapeline
  does the opposite: one 0-100 score per US ticker from a formula I publish in
  full (Trend 25 / Relative Strength 20 / Fundamentals 15 / Smart Money 15 /
  Macro 15 / Momentum 10), plus one plain-English sentence on why.

  The part I care most about: every top-10 daily pick auto-publishes to a public
  scorecard the next day with its realized return vs SPY — winners and losers,
  unedited. The formula is copyable; the moat is the data spine and the
  receipts.

  It's descriptive, not advice — six labels, no buy/sell language. Free tier is
  the real product (delayed); 14-day Premium trial, no card. Would genuinely
  love feedback on the scoring methodology: https://tapeline.io/how-it-works
  ```
- **Launch timing:** schedule for a **Tuesday, 12:01am PT** (per `OFFSITE.md`).

### A2 · Crunchbase — `crunchbase.com/add-new`

- **Company name:** `Tapeline`
- **Permalink:** `tapeline-io` (bare `tapeline` is taken by the cassette co)
- **Short description (max ~120 chars):**
  ```
  Quantitative US-stock scanner with a public 6-factor formula and a back-checked, public daily scorecard.
  ```
  *(104 chars.)*
- **Full description:** paste the **canonical one paragraph** above.
- **Founded date:** `2025` (engine built 2025; public launch 2026 — say so in the description)
- **Operating status:** `Active`
- **Company type:** `For Profit`
- **Industries:** `Financial Services`, `FinTech`, `Software`, `Trading Platform`, `Analytics`
- **Headquarters:** `Melbourne, Victoria, Australia`
- **Founder:** `Christian Piyatilaka` — add as a Crunchbase **Person**, title `Founder`, linked to the company
- **Funding:** Bootstrapped — state **$0 raised** explicitly
- **Website:** `https://tapeline.io` · **Socials:** X `@tapeline_io`, LinkedIn `company/tapeline-io`

### A3 · G2 — `sell.g2.com`

- **Product name:** `Tapeline`
- **Categories:** `Stock Analysis Software`, `Investment Research Software`
- **Description:** paste the **canonical one paragraph**.
- **Website:** `https://tapeline.io` · **Pricing:** `https://tapeline.io/pricing`
- **Comparison set (G2 auto-builds vs-pages):** Finviz, Zacks, TradingView
- **Logo / screenshots:** `favicon.svg` + the four screens in `/press` → Screenshot kit
  (Live scanner `/`, Per-ticker `/t/AAPL`, Methodology `/how-it-works`, Scorecard `/scorecard`)
- **Recurring:** email paying users for reviews after 30 days; target 10 in 90 days.

### A4 · Capterra — `capterra.com/vendors/sign-up`

*(One submission also feeds GetApp + Software Advice — Gartner Digital Markets.)*

- **Software name:** `Tapeline`
- **Tagline:** the **formal one sentence** above.
- **Description:** paste the **canonical one paragraph**.
- **Categories:** `Stock Analysis`, `Investment Management`, `Financial Analysis`
- **Pricing model:** `Subscription` + `Free version` · starting price **$9.99/mo** (Pro, annual)
- **Deployment:** `Web-based / Cloud`
- **Tick only true features:** Watchlist, Alerts/Notifications, Technical Analysis,
  Fundamental Analysis, Performance Metrics, Customizable Reports/Export.
  *(Do NOT tick: trade execution, portfolio custody, robo-advice — Tapeline does none of these.)*

### A5 · AlternativeTo — `alternativeto.net/contribute`

- **App name:** `Tapeline`
- **Short tagline:** the **short one sentence** above.
- **Description:** paste the **canonical one paragraph**.
- **Categories:** `Stock Analyzer`, `Stock Quote`, `Stock Picker`
- **Alternative to:** Finviz, Zacks, WallStreetZen, TradingView, Trade Ideas, Koyfin
  *(same set as the `/compare/*` pages)*
- **License:** `Freemium` · **Platforms:** `Online / Web`
- **Links:** `https://tapeline.io`

### A6 · StockTwits — `stocktwits.com/signup`

- **Username:** `tapeline_io` (else `tapelineio`)
- **Name:** `Tapeline`
- **Bio:** the **short one sentence** above.
- **Website:** `https://tapeline.io`
- **Pin a post** linking to `/scorecard` with the caption: `The receipts.`
- **Recurring:** post the daily top-10 from `/scorecard` (informational only —
  never bare ticker spam, never buy/sell language).

### Post-claim checklist (do in the same session, per `OFFSITE.md`)

1. ☐ Add the live profile URL to `Organization.sameAs` in
   [`frontend/app/layout.tsx`](../frontend/app/layout.tsx).
2. ☐ Add the same URL to the `PROFILES` array in
   [`frontend/app/about/page.tsx`](../frontend/app/about/page.tsx).
3. ☐ Add `rel="me"` back to `tapeline.io` on the profile where the platform
   allows it (X, GitHub, StockTwits do; LinkedIn, Crunchbase, G2 don't).
4. ☐ Trigger the post-deploy SEO ping (GitHub Actions →
   `post-deploy-seo.yml`) so the updated `/about` re-indexes.

> A `sameAs` URL that 404s is a *negative* trust signal — only add a URL once
> the profile is live and points at Tapeline (the scanner).

---

## Part B — Launch / backlink pitch

Ordered by ROI for a bootstrapped, dev-built SaaS. **B1–B2 need no gatekeeper**
and are the fastest brand backlinks; B3+ are earned coverage.

### B1 · Show HN (highest-ROI self-serve backlink) — `news.ycombinator.com/submit`

HN culture: technical, humble, zero marketing words ("best", "revolutionary",
"game-changer" all backfire). Disclose the paid tier plainly.

- **Title (≤80 chars):**
  ```
  Show HN: Tapeline – a stock scanner that publishes its formula and scorecard
  ```
- **URL:** `https://tapeline.io`
- **First comment (post immediately after submitting):**
  ```
  I'm a solo dev + retail trader. I got tired of scanners that are either 60
  filter fields with no opinion, or an "AI pick" you can't audit. So I built the
  opposite.

  Tapeline gives every active US ticker one 0-100 score from a fixed, fully
  published 6-factor formula (Trend 25 / RS 20 / Fundamentals 15 / Smart Money
  15 / Macro 15 / Momentum 10) — weights are versioned in a public changelog and
  never edited retroactively, no ML rerank between the formula and the number.
  Each ticker also gets one plain-English sentence explaining the score.

  The accountability bit: every top-10 daily pick auto-logs to a public
  scorecard the next session with realized return vs SPY — including the losers.

  Stack: FastAPI + SQLAlchemy + Postgres, Next.js front end, a 60s scoring
  worker, SSE for live updates. Scores are descriptive, not advice (no buy/sell
  language — publisher's-exemption posture). Free tier is the real product
  (delayed data); Premium is live. Methodology: https://tapeline.io/how-it-works

  Happy to talk about the scoring design, the data spine, or the
  publish-your-track-record bet. Feedback welcome.
  ```

### B2 · Indie Hackers — `indiehackers.com` (post / milestone)

- **Title:**
  ```
  I bet a bootstrapped SaaS on radical transparency: public formula + public scorecard
  ```
- **Body angle:** solo + bootstrapped + the contrarian bet (give away the
  formula, publish every pick's result). Open with the problem, show the
  scorecard link as proof, end with a specific ask ("does the
  publish-your-losers angle build trust or scare people off?"). Link
  `tapeline.io` and `/scorecard`.

### B3 · Cold email template (newsletters & podcasts)

Personalize the bracketed slots — a generic blast gets ignored. One outlet at a
time.

- **Subject (pick one):**
  - `Tapeline: a stock scanner that publishes its formula and its track record`
  - `Bootstrapped stock scanner — public 6-factor formula, public scorecard`
- **Body:**
  ```
  Hi [NAME],

  I read [SPECIFIC PIECE / EPISODE] — [ONE GENUINE SENTENCE ON WHY IT'S RELEVANT].

  I'm Christian Piyatilaka, solo founder of Tapeline (tapeline.io), a
  quantitative stock scanner with an unusual bet: both the formula and the track
  record are public. Every US ticker gets one 0-100 score from a published
  6-factor formula, and every top-10 daily pick auto-logs to a public scorecard
  the next day with its realized return vs SPY — winners and losers, unedited.

  It's descriptive analytics, not advice (no buy/sell language). Bootstrapped,
  launched 2026, built solo.

  If it's useful for [OUTLET], I can send a custom data pull, a founder quote, or
  early access — whatever your piece needs. Full fact sheet, logos, and
  pre-cleared quotes: https://tapeline.io/press

  Either way, thanks for [the newsletter / the show].

  Christian Piyatilaka
  Founder, Tapeline · tapeline.io
  press@tapeline.io
  ```
  > **Claude cannot send this** — it's drafted for you to send from your own
  > mail client. (No outreach from the domain on the user's behalf.)

### B4 · Target list (from `OFFSITE.md` Priority 4)

- **Newsletters:** Net Interest · FinTech Brainfood · Money Stuff (Matt Levine) · The Tokenist · Benzinga
- **Podcasts:** Animal Spirits · Trader Mike · Top Trading Performance
- **Self-serve (do first):** Hacker News (B1) · Indie Hackers (B2)
- **Sequencing:** finish Part A (entity profiles) *before* B3/B4 — journalists
  Google a brand before replying, and a populated Crunchbase / LinkedIn / G2 is
  what makes the pitch look real.

### B5 · Three reusable hooks (rotate per channel)

1. **Transparency:** "The formula is public. Anyone can copy it. The moat is the
   data spine plus a public scorecard back-checking every call."
2. **Accountability:** "Newsletter shops have hidden their losers for 30 years.
   We auto-publish every top-10 pick the next day, regardless of how it moved."
3. **Anti-black-box:** "Six descriptive labels, no buy/sell language. We tell you
   what the data says — you decide what to do with it."
   *(All three are pre-cleared pull quotes on `/press`.)*

---

## Voice guardrails (legal-critical — applies to every word above)

- **Descriptive, never prescriptive.** Never "buy", "sell", "you should",
  "recommend", "best pick". Use the score, the label, the data.
- **No performance promises or return guarantees.** The scorecard shows realized
  results, framed as a record, never a forecast.
- **Bootstrapped / solo / Melbourne / Christian Piyatilaka** — keep the founder
  story identical everywhere.
- This posture is what protects the Australian publisher's exemption from AFSL.
  When in doubt, copy from `/press` rather than writing fresh.
