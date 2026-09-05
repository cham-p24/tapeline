# Brand SERP Kit — paste-ready off-site copy + launch pitch

> **WHERE THE CARD SITS — updated 2026-08-30. Check every claim below against `docs/PRICING.md` before posting.**
>
> **Signing up takes an email and a password.** The account it makes lands on
> the Free plan and opens the live scanner — the top ten scored rows of any
> scan, one saved screen. **A card is what starts the 30-day Premium trial**
> (Stripe Checkout, $0 charged that day, first charge on day 30, one click to
> cancel before then), and the trial is what turns on every matching row rather
> than the first ten, plus alerts, CSV export and the Congressional and insider
> feeds.
>
> The **published record is free with no account at all**: the daily Top 10, the
> complete scorecard, a page per scored ticker, and the raw CSV/JSON export.
>
> So: **no line in this file may attach the card to the ACCOUNT or to SIGNING
> IN.** Attach it to the TRIAL, which genuinely requires one. Three layers, in
> this order: the record needs no account; signing up takes an email and a
> password; a card starts the trial.
>
> _History, because this block said the opposite for eight days: #548
> (2026-08-22) put a card wall in front of the logged-in product, and #683
> (2026-08-30) removed
> it. #686 corrected 79 claims across 42 files — but not this file, because
> `docs/**` was outside the copy linter's include globs, so the four paste-ready
> copy banks kept regenerating the false claim from this very instruction. They
> are named in `scripts/copy-compliance.allow.json` now, and rule
> `card-required-signup` fails the build on it._
>
> **DISCLOSURE BOUNDARY — never publish the exact factor weights or the scoring
> equation.** `/how-it-works` names the six factors and their weight *ordering*
> ("weighted most toward Trend and Relative Strength, least toward Momentum") and
> nothing more. No line here may say Tapeline publishes "the formula" or "the
> exact weights". Nor may it publish a factor's inputs at parameter level —
> named lookback windows, thresholds, indicator recipes or sub-weights are all
> out of bounds. Describe what a factor measures and stop.
>
> **OPEN-ACCESS MONTH — reverts 2026-09-08.** While it runs, a **signed-in**
> Free account sees the full 1,000-row scanner rather than the standard top 10.
> Nothing else lifts — look-ups, watchlist and push-rule caps are unchanged and
> no Pro feature unlocks — and logged-out visitors still see the top 10. Lines
> below that describe the Free row cap are the **post-promo** steady state, so
> re-check them against `tier.py` before posting them as today's product.
>
> Some drafts here are stale on product facts as well (a "top 20, 24-hour
> delayed" free tier is long gone; the per-rule Telegram alert channel was
> retired and `AlertRuleCreate` now accepts only email|web_push). Treat unmarked
> copy as a draft to re-check, not as approved copy.

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
  Live quantitative stock scanner. Six named factors. Public scorecard. tapeline.io
  ```
- **One sentence — formal (press, taglines):**
  ```
  Tapeline is a quantitative stock scanner that names the six factors behind its score and back-checks every top-10 daily pick against the next-day SPY-relative move.
  ```
- **One paragraph (the canonical description — verbatim from `/press`):**
  ```
  Tapeline is a quantitative stock scanner for active retail traders, built on the principle that the methodology and the track record should both be public. Every US ticker in the active universe gets one 0-100 composite score blended from six named factors — Trend, Relative Strength, Fundamentals, Smart Money, Macro, and Momentum, weighted most toward Trend and Relative Strength and least toward Momentum — updated sub-60s during market hours. Every top-10 daily pick auto-publishes to a public scorecard with the realized next-day return vs SPY, immutable and back-checked. Tapeline is bootstrapped, launched in 2026, and competes with Finviz, Zacks, WallStreetZen, TradingView, Trade Ideas, and Koyfin at the $10-20/mo price point (Pro $9.99/mo or $99/yr; Premium $19.99/mo or $199/yr).
  ```
- **Fact sheet (same facts as the `/press` table; the Pricing and Free-trial rows are spelled out at greater length here so the card gate can't be misread — quote `/press` itself if you need it byte-exact):**
  | Field | Value |
  |---|---|
  | Company | Tapeline (tapeline.io) |
  | Founder | Christian Piyatilaka (solo founder) |
  | Founded | 2025 (engine), 2026 (public launch) |
  | Headquarters | Melbourne, Victoria, Australia |
  | Funding | Bootstrapped — no external investment |
  | Pricing | Public record free, no account required · Pro from $8.25/mo (annual) · Premium from $16.58/mo (annual) |
  | Free trial | 14-day Premium — a card starts it, $0 charged that day, first charge on day 30, one-click cancel. Signing up itself takes only an email and a password and opens the free plan. The published record (daily Top 10, full scorecard, raw CSV/JSON) needs no account at all |
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
  Tapeline is a quantitative stock scanner for active retail traders, built on the principle that the methodology and the track record should both be public. Every active US ticker gets one 0-100 composite score from six named factors — Trend, Relative Strength, Fundamentals, Smart Money, Macro, and Momentum, weighted most toward Trend and Relative Strength, least toward Momentum — updated in under 60 seconds during market hours, each with a plain-English explanation of the reading. Every top-10 daily pick is logged to a public, back-checked scorecard showing its realized next-day return versus the S&P 500. Tapeline provides descriptive market analytics, not financial advice. Bootstrapped and built in Melbourne, Australia; launched in 2026.
  ```
  *(748 chars — under GBP's 750 limit. Note: GBP descriptions forbid URLs, phone numbers, pricing, and
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
  A transparent quantitative stock scanner. Every US ticker gets one 0-100 score from six named factors, plus a plain-English "why." Every top-10 daily pick is logged to a public scorecard vs SPY. Bootstrapped. Record free to read, no account; trial takes a card.
  ```
- **Topics:** `Fintech`, `Stock trading`, `Investing`, `SaaS`, `Analytics`
- **Links:** Website `https://tapeline.io` · Pricing `https://tapeline.io/pricing`
- **Pricing label:** `Freemium`
- **Maker's first comment (paste as the maker — this is the main ranking signal):**
  ```
  Maker here 👋 I'm Christian, solo founder.

  I built Tapeline because every other scanner either gives you 60 raw filter
  fields and a blank stare, or an "AI pick" with no way to check it. Tapeline
  does the opposite: one 0-100 score per US ticker from six named factors I
  publish — Trend, Relative Strength, Fundamentals, Smart Money, Macro,
  Momentum, weighted most toward Trend and Relative Strength and least toward
  Momentum — plus one plain-English sentence on why.

  The part I care most about: every top-10 daily pick auto-publishes to a public
  scorecard the next day with its realized return vs SPY — winners and losers,
  unedited. The factor set is out in the open; the moat is the data spine and
  the receipts.

  It's descriptive, not advice — six labels, no buy/sell language. The public
  record is the real product and is readable with no account and no card; the
  signed-in product opens on the free plan with an email and a password; a card starts the 30-day Premium
  trial — $0 today, first charge at day 30, one click to cancel.
  Would genuinely
  love feedback on the scoring methodology: https://tapeline.io/how-it-works
  ```
- **Launch timing:** schedule for a **Tuesday, 12:01am PT** (per `OFFSITE.md`).

### A2 · Crunchbase — `crunchbase.com/add-new`

- **Company name:** `Tapeline`
- **Permalink:** `tapeline-io` (bare `tapeline` is taken by the cassette co)
- **Short description (max ~120 chars):**
  ```
  Quantitative US-stock scanner with a public 6-factor methodology and a back-checked, public daily scorecard.
  ```
  *(108 chars.)*
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
- **Pricing model:** `Subscription` · starting price **$8.25/mo** (Pro, billed annually at
  $99/yr) or **$9.99/mo** billed monthly. The published record is free with no account required.
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
  Show HN: Tapeline – a stock scanner that publishes its methodology and scorecard
  ```
- **URL:** `https://tapeline.io`
- **First comment (post immediately after submitting):**
  ```
  I'm a solo dev + retail trader. I got tired of scanners that are either 60
  filter fields with no opinion, or an "AI pick" you can't audit. So I built the
  opposite.

  Tapeline gives every active US ticker one 0-100 score from a fixed, fully
  published six-factor set (Trend, Relative Strength, Fundamentals, Smart Money,
  Macro, Momentum) — weighted most toward Trend and Relative Strength, least
  toward Momentum. The ordering is published and never changes without a
  changelog entry, and there's no ML rerank between the factors and the number.
  Each ticker also gets one plain-English sentence explaining the score.

  The accountability bit: every top-10 daily pick auto-logs to a public
  scorecard the next session with realized return vs SPY — including the losers.

  Stack: FastAPI + SQLAlchemy + Postgres, Next.js front end, a 60s scoring
  worker, SSE for live updates. Scores are descriptive, not advice (no buy/sell
  language — publisher's-exemption posture). The public record is live and needs
  no account; the full ~2,500-ticker scanner is paid.
  Methodology: https://tapeline.io/how-it-works

  Happy to talk about the scoring design, the data spine, or the
  publish-your-track-record bet. Feedback welcome.
  ```

### B2 · Indie Hackers — `indiehackers.com` (post / milestone)

- **Title:**
  ```
  I bet a bootstrapped SaaS on radical transparency: public methodology + public scorecard
  ```
- **Body angle:** solo + bootstrapped + the contrarian bet (name every factor
  and publish every pick's result). Open with the problem, show the
  scorecard link as proof, end with a specific ask ("does the
  publish-your-losers angle build trust or scare people off?"). Link
  `tapeline.io` and `/scorecard`.

### B3 · Cold email template (newsletters & podcasts)

Personalize the bracketed slots — a generic blast gets ignored. One outlet at a
time.

- **Subject (pick one):**
  - `Tapeline: a stock scanner that publishes its methodology and its track record`
  - `Bootstrapped stock scanner — public 6-factor methodology, public scorecard`
- **Body:**
  ```
  Hi [NAME],

  I read [SPECIFIC PIECE / EPISODE] — [ONE GENUINE SENTENCE ON WHY IT'S RELEVANT].

  I'm Christian Piyatilaka, solo founder of Tapeline (tapeline.io), a
  quantitative stock scanner with an unusual bet: both the methodology and the
  track record are public. Every US ticker gets one 0-100 score from six named
  factors, and every top-10 daily pick auto-logs to a public scorecard
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

1. **Transparency:** "We name the six factors and publish a per-pick scorecard —
   it's not a mystery black box. The moat is the data spine plus that public
   scorecard back-checking every call we make."
2. **Accountability:** "Newsletter shops have hidden their losers for 30 years.
   We auto-publish every top-10 pick the next day, regardless of how it moved."
3. **Anti-black-box:** "Six descriptive labels, no buy/sell language. We tell you
   what the data says — you decide what to do with it."
   *(All three are pre-cleared pull quotes on `/press`.)*

---

## Voice guardrails (legal-critical — applies to every word above)

- **Descriptive, never prescriptive.** Never "buy", "sell", "you should",
<!-- copy-compliance-allow performance-claim -- this line IS the prohibition list; it quotes the banned phrases in order to ban them -->
  "recommend", "best pick". Use the score, the label, the data.
- **No performance promises or return guarantees.** The scorecard shows realized
  results, framed as a record, never a forecast.
- **Bootstrapped / solo / Melbourne / Christian Piyatilaka** — keep the founder
  story identical everywhere.
- This posture is what protects the Australian publisher's exemption from AFSL.
  When in doubt, copy from `/press` rather than writing fresh.
