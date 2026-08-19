# Tapeline — Reverse-Engineering "Why They Come"
**Date:** 2026-07-26 · **Analyst:** Growth · **Basis:** Live-SERP + AI-answer recon across 5 demand clusters

---

## 1. The honest frame

This document reverse-engineers demand from what is **observable right now** — SERP position, AI-answer presence/absence, and searcher intent — across five clusters (comparison/alternative, listicle "best stocks for X", per-ticker `/t/{symbol}`, transparency/brand, and generative AI-answer). That evidence tells us what **is capable of pulling** people to tapeline.io and what is **built to pull but not yet ranking**. It does **not** measure traffic. No number here is a click count, session count, or conversion rate — there was **no GSC or GA4 access this run** (the two GSC positions cited, momentum ~pos 11.3 and swing ~pos 12.4, come from the earlier strategy doc, not a live rank-tracker). The single action that converts every inference below into a measured fact is the data export spec in §6. Read every "captures / absent / emerging" as a statement about **demand-capture capability**, never realized traffic.

---

## 2. Demand map — clusters ranked by (observed capture × commercial intent)

Ranking axis = how much real visitor pull the cluster can plausibly deliver **today** × the commercial value of that intent.

| Rank | Cluster | Observed capture | Intent value | Where Tapeline stands |
|---|---|---|---|---|
| 1 | **Brand + branded-comparison** (subset of transparency & comparison clusters) | **Visible / owned** | High conversion, low incremental volume | Owns its SERPs: "tapeline stock scanner" 7/7 clean sweep, "tapeline.io" leads, "is tapeline better than finviz" / "tapeline vs finviz" = position 1, "Tapeline stock scanner review" AI answer built entirely from its own pages and on-message. |
| 2 | **Listicle / "best stocks for X"** (programmatic `/best-stocks-for/*`) | **Emerging** | High | Pages crawled, indexed, rendering fresh dated snapshots — but stranded below the fold. /momentum ~pos 11.3 and /swing-traders ~pos 12.4 sit on the page-1/2 border; zero appear in live page-1 organic. A foothold, not yet a traffic source. |
| 3 | **Transparency / verifiable-track-record wedge** (non-brand terms) | **Weak** | High | Defensible product-side, but /verify appears in NONE of nine SERPs (incl. brand). Generic terms hijacked: verify→filter, formula→formula-builder, track record→backtest, public methodology→GitHub. Stockopedia/AlphaStocks/YCharts own "transparent scoring." |
| 4 | **Comparison / "[competitor] alternative"** (non-branded switch intent) | **Absent** | High | Invisible on every non-branded alternative query. /compare/* pages rank for zero of them (indexing/authority gap, not content gap). SERPs owned by aggregators (AlternativeTo, G2, Capterra) + rival compare pages (ChartingLens, ScreenerHero, Incite AI). |
| 5 | **Generative / AI-answer** (non-brand "which scanner should I use") | **Absent** | High (fastest-growing) | Wins ~100% of branded AI answers, invisible on 100% of non-brand discovery — including word-for-word its own wedge. A citation/inclusion gap: absent from the affiliate roundups + syndicated PR that LLMs synthesize. Stock Market Guides, Danelfin, ChartingLens occupy the exact positioning. |
| — | **Per-ticker `/t/{symbol}`** | **Absent** | Medium | Fresh ~50-page rollout, unindexed — loses even its own branded query "NVDA stock score tapeline." Long tail is NOT thin (every nano-cap has 7–15 incumbents). Indexation problem first. |

**Read of the map:** exactly one cluster (brand) is pulling real visitors today. Everything with high non-branded volume is either emerging (listicles — closest to breaking through) or absent (comparison, generative, per-ticker). The binding constraints are **distribution/authority and indexation**, not positioning — Tapeline's message already matches the winners it is losing to.

---

## 3. The reverse-engineered "why they come" — who actually lands today

Three clusters plausibly pull real visitors now. Only one pulls at volume; two are built to pull and partially firing.

**A. Brand + branded-comparison — ALREADY PULLING (the only real current source).**
Job-to-be-done: *"I heard of Tapeline / saw it mentioned — is it legit and is it better than what I use?"* The person already knows the name and is validating a switch. They land because tapeline.io owns the entire branded SERP — homepage at position 1 for "tapeline vs finviz," a 7/7 sweep for "tapeline stock scanner," and an AI answer for "Tapeline review" assembled from /about, /scorecard, /sectors that accurately states the six factors, public weights, and SPY-back-checked scorecard (even the honest "currently trails SPY"). Our page answers because it is the authoritative source on our own brand and the pages index cleanly on-brand. **Caveat: this is demand Tapeline already created — capture, not discovery.** It converts well but does not grow the top of funnel.

**B. Listicle "best stocks for X" — BUILT TO PULL, PARTIALLY FIRING.**
Job-to-be-done: *"Give me an actionable, current list of names to trade this week."* Bottom-of-funnel trader intent (swing, momentum, breakouts). They *can* land because the pages are indexed and rendering fresh dated snapshots with live 6-factor scores — but today they mostly **don't**, because /momentum (~pos 11.3) and /swing-traders (~pos 12.4) sit just below page 1 where CTR is ~1%. Our page answers the intent better than the incumbents on substance (score-filtered list + next-day scorecard vs SPY, which Benzinga/AltIndex/Zacks don't offer) — it is simply out-authoritied by ~1–3 positions. This is the cluster closest to converting "built to pull" into "pulling."

**C. Transparency wedge — BUILT TO PULL, NOT YET RANKING.**
Job-to-be-done: *"I don't trust black-box scores — show me a scanner I can audit before I pay."* This skeptic is Tapeline's ideal buyer and the product genuinely answers (public formula + immutable public scorecard that keeps its losing days). But they don't land on non-brand terms: /verify is absent from all nine relevant SERPs and the generic queries are semantically hijacked toward filters/backtests/GitHub. So the wedge only fires **after** the brand is already known (i.e. it collapses into cluster A). Today it is a product strength with no independent discovery path.

**Distinction:** *Already pulling* = brand/branded-comparison. *Built to pull but not yet ranking* = listicles (closest) and the transparency wedge (blocked on indexation + intent-hijack). Comparison, generative, and per-ticker are not yet pulling at all.

---

## 4. Marketing refinement plan — amplify the winners

Descriptive positioning only; no performance/return claims (the scorecard trails SPY, so **verifiability itself is the headline, never outperformance**). Ordered by leverage.

### Priority 1 — Listicles (emerging → page 1): the cheapest click-unlock on the site
- **Message to lean into:** verifiability, not freshness. Freshness is table stakes — Benzinga/AltIndex/Zacks already run "updated daily" lists. Every title/snippet should front-load *"back-checked vs SPY the next day"* and *"named 6-factor formula,"* which none of them offer.
- **Pages to reinforce:** concentrate on the two border pages — `/best-stocks-for/momentum` (~pos 11.3) and `/best-stocks-for/swing-traders` (~pos 12.4). A 1–3 position gain crosses onto page 1 (pos 11→8 ≈ 5–10× CTR jump). Nothing else on the site is that cheap.
- **Content/internal links:** push internal links from the already-ranking directory pages (/stocks, /signals, /sectors, homepage) into these two slugs; add a handful of quality backlinks. **Deprioritize** /growth-stocks (brutal Forbes/US-News authority + buy-and-hold intent mismatch); treat /breakouts and /under-10 as second-tier until momentum/swing break through.
- **Where the audience is:** active-trader roundups and daily-list SERPs (Zacks/Yahoo momentum lists, TradeThatSwing, AltIndex) — the destinations already ranking for these terms.

### Priority 2 — Attack the citation corpus (generative + comparison, shared fix)
The generative and comparison clusters fail for the **same root cause**: Tapeline is absent from the two corpora that feed both LLM answers and alternative-SERPs — (1) affiliate review roundups and (2) syndicated PR + vendor compare pages.
- **Message:** the single un-fakeable claim — *"the only scanner that publishes its factor weights AND back-checks every top-10 pick against SPY, including its losers."* Danelfin/ChartingLens can pair transparency with a big return number; Tapeline can't, so it wins on the honesty a competitor structurally can't copy.
- **Moves:** (a) get **listed** on the properties that actually rank these SERPs — AlternativeTo, G2, SourceForge, Slashdot, Capterra. (b) get **seeded into** the affiliate listicles LLMs synthesize — Benzinga, WillKopec, LiberatedStockTrader, Deepvue, WallStreetZen, StockBrokers.com, ChartingLens roundups. (c) run **one distributed PR-wire release** (PRNewswire/Yahoo/Morningstar syndication) headlined on the verifiability claim — this is exactly the play Stock Market Guides used to capture the entire "publishes its track record" wedge with a single blast.
- **Priority target queries by fit+value:** "tradingview alternative stock screener," "seeking alpha alternative stock screener," "trade ideas alternative" (price-switchers = Tapeline's $8.25 wedge), "wallstreetzen alternative" (closest fit). Rivals ChartingLens, ScreenerHero, Incite AI are already inside these taking the exact slot.
- **Pages to reinforce:** the existing /compare/* pages are fine content — the fix is external authority + inclusion, not rewriting them.

### Priority 3 — Transparency wedge (unblock indexation + de-hijack intent)
- **Message:** weaponize the skeptic's literal words as H1/titles — *"A stock screener you can verify," "The scanner that shows its formula," "The screener that publishes its losing days."*
- **Pages to reinforce:** /verify is **technically flawless for indexing** — VERIFIED 2026-07-26: `robots: index, follow`, correct self-canonical `https://tapeline.io/verify`, present in the served sitemap.xml, and internally linked (MarketingFooter + TransparencyStrip). So its SERP absence is **NOT a config bug** — it is simply new (created 2026-07-25, #380) and low-authority, so Google hasn't ranked it yet. Lever = off-site citation + authority + time, plus sharper H1/title targeting. Disambiguate copy so "formula" reads as *published fixed weights*, not a DIY formula-builder.
- **Brand hygiene (cross-cluster):** always brand as **"Tapeline stock scanner"** (the disambiguated phrase returns a 7/7 sweep); never chase bare "tapeline" (lost to the tape-measure homonym + two incumbent Tapeline firms). Resolve the near-name **"Tapeboard"** rival diluting even the branded finviz SERPs.

### Cross-cutting — Per-ticker `/t/{symbol}` (fix the pipe before amplifying)
Not a top-3 amplification target, but the cheap enabler: submit a per-ticker XML sitemap, internal-link every `/t/{symbol}` from /stocks and /signals, ensure unique on-page copy + FAQ schema to dodge thin-content filters. Then target the "TICKER stock score" phrasing specifically (highest intent-fit) with the same verifiability differentiator.

---

## 5. Quick wins vs compounding bets

**Quick wins — this week (config/indexation/copy, no authority-building lag):**
- Add internal links from homepage + /stocks + /signals + /sectors into `/best-stocks-for/momentum` and `/best-stocks-for/swing-traders` (the two page-1-border pages).
- Rewrite momentum/swing (and other list) titles/snippets to front-load "back-checked vs SPY" + "named 6-factor formula" instead of freshness.
- `/verify` indexation is already correct (VERIFIED: index/follow + self-canonical + in sitemap + footer/TransparencyStrip links) — no config fix needed; it just needs authority + time. Sharpen its H1/title to the skeptic's literal words instead.
- Submit a per-ticker XML sitemap and internal-link `/t/{symbol}` pages from ranking directory pages; add unique copy + FAQ schema.
- Create/claim listings on AlternativeTo, G2, SourceForge, Capterra, Slashdot (submission is fast; ranking follows).
- Standardize all brand language to "Tapeline stock scanner"; audit for "Tapeboard" confusion.

**Compounding bets — slow plays (authority + third-party corpus):**
- One distributed PR-wire release on the verifiability claim (the Stock Market Guides play) — compounds as it gets syndicated and re-cited by LLMs.
- Earn placement inside the affiliate roundups (Benzinga, WillKopec, LiberatedStockTrader, Deepvue, WallStreetZen) — the corpus both SERPs and AI answers draw from.
- Build backlink authority to lift momentum/swing across page 1 and, over time, the /compare/* pages onto non-branded alternative SERPs.
- Expand the `/t/` rollout beyond the ~50-page pilot once indexation is proven, targeting "TICKER stock score" long tail.

---

## 6. Make it exact — the data export spec

The minimal operator action to convert every inference above from **inferred** to **measured**. Three exports; each sharpens specific sections.

**A. Google Search Console → Performance → Search results** (last 3 months)
- Export **Queries** and **Pages** tabs as CSV (toggle Clicks, Impressions, CTR, Position on).
- Look for: **top queries by clicks** (what actually pulls people — validates/replaces the cluster-A "brand is the only current source" claim), **pages by impressions with position 8–15** (confirms which /best-stocks-for/* and /compare/* pages are truly on the page-1 border), and **branded vs non-branded click split**.
- Sharpens: **§2 ranking** (turns "emerging/absent" into measured position + click data) and **§4 Priority 1** (confirms momentum/swing are the cheapest unlock, or redirects to whichever page is actually closest).

**B. Google Analytics 4**
- **Reports → Acquisition → Traffic acquisition** (last 90 days): export the **Session source/medium** table.
- **Reports → Engagement → Pages and screens** and **Landing page** (last 90 days): export both.
- Look for: **top landing pages by entrances / sessions** (which pages people actually arrive on — the empirical "why they come"), **organic vs direct vs referral mix** (how much is brand/navigational vs discovered), and **engagement time by landing page**.
- Sharpens: **§3** (replaces the inferred "already pulling vs built to pull" with the real landing-page distribution) and **§2 capture column**.

**C. PostHog → top events / funnels**
- Export top events and the **trial-start funnel** segmented by **landing page / entry path**.
- Look for: **trial-conversion rate by landing page** (does the transparency/scorecard content convert the skeptic better than the list pages?) and drop-off steps.
- Sharpens: **§4 prioritization** (reweights the plan toward whichever cluster's landing pages actually convert, not just which pull clicks) and validates the "verifiability converts" thesis.

**One-line ask to the operator:** *export GSC Queries + Pages (3mo CSV), GA4 Traffic-acquisition + Landing-page + Pages (90d), and PostHog top-events + trial funnel by landing page — that set turns this whole document from reverse-engineered inference into measured fact.*
