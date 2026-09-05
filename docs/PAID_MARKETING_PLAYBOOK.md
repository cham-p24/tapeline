# Tapeline — Paid & Organic Marketing Playbook

*Assembled 2026-08-17. Built from four research sweeps of the free layer of paid Google Ads coaching (Solutions 8 / StarterPPC, Define Digital Academy, KlientBoost, Powered by Search, WordStream, Google Help), free SaaS marketing education (MicroConf / Rob Walling, YC Startup School, April Dunford, Eli Schwartz, Kevin Indig, Ahrefs, Semrush), Google's live financial-ads policy pages, the Google Ads Transparency Center + Meta Ad Library, and the documented growth histories of eight tools in this exact vertical. Every external claim below carries its source. Companion to `PAID_ADS_PATHWAY.md` (June 2026 economics — still correct) and `GROWTH_RESEARCH_DOSSIER.md`. Nothing here is legal advice; §8 is a lawyer brief.*

---

## The one-paragraph answer

**Do not turn Google Ads back on for anything except brand terms and retargeting, and do not expect either to produce customers yet.** Four independent lines of evidence say the same thing. (1) Tapeline's own experiment: **A$951 → ~500 clicks → 0 signups**, at a CPC (~A$1.90) that was *below* the finance-vertical benchmark — so the failure was conversion, not click price. (2) The paid-ads coaches' own published floors: you need ~15 conversions/campaign/month for the account to learn anything, and a daily budget of ~10× CPC; at Tapeline's numbers that is ~A$19/day *just to learn on trial signups* and ~A$4–6k/month to learn on paid conversions — neither is sane at 18 users. (3) The unit economics: at $9.99/$19.99 the best-tuned funnel lands ~1.85:1 LTV:CAC, under the 3:1 gate every source uses. (4) The vertical's own history: **zero of eight comparable tools grew on paid search early** — TradingView hit 1M users "without an advertising budget", TrendSpider's marketer-founder spent "$4,000 in ads" in a quarter at 5k users, and Finviz (the price-comparable incumbent) runs essentially no Google Ads today. Paid search in this category is a scale-stage *defence* layer, never the ignition. What ignites is a free artifact that travels without the user, amplified by community and founder-taught content — and for Tapeline specifically, the channel that already works is AI-assistant referral. So: the Google Ads build in §5 is complete and execution-ready, and it stays **behind a gate** until §4's conditions are met. The campaign that runs *now* is §6, and it costs founder-hours, not dollars.

---

## 1. What the research actually says — 15 things worth knowing

Each is one finding from the free layer of what people pay for, with its source, translated to Tapeline in a sentence.

| # | Finding | Source | For Tapeline |
|---|---|---|---|
| 1 | **The learning floor is ~15 conversions/campaign/month absolute; 30 in 30 days is Google's own tCPA line; 50 is agency comfort.** Below 15, Solutions 8's small-budget lead says the budget "is too small… would not want to waste time wondering if optimization will ever take off." | Google Help tCPA (support.google.com/google-ads/answer/6268632); Solutions 8 (sol8.com/small-budget-google-ads/) | At any plausible click→trial rate this needs A$570–950/month on trial signups, and A$4–6k/month on *paid* conversions. Neither is defensible pre-revenue. |
| 2 | **Daily budget rule = 10 × average CPC.** "$5/day? Yes, but only if your CPC is very low (e.g. $0.50)." Expect a 60–90-day ramp. | Aaron Young, Define Digital (definedigitalacademy.com/blog/google-ads-small-budget-strategy) | At A$1.90 CPC the learning budget is ~A$19/day. The A$5/day cap buys brand defence and retargeting only — which is exactly what it should buy. |
| 3 | **A 0% click→signup rate is a landing-page/offer failure, not a bidding one.** The testing hierarchy every agency publishes is offer → message match → headline → CTA → form friction, *before* anything else. | KlientBoost (klientboost.com/landing-pages/landing-page-message-match/) | The June ads sent "Open 6-Factor Formula" and "Plain-English Buy Signals" to pages that don't publish the formula and never say "buy". Message match was broken before the first click landed. |
| 4 | **Nobody credible still teaches SKAGs, and nobody teaches Performance Max for a low-budget trial funnel.** Search-only, 2–4 campaigns, themed ad groups. Search beats PMax 84% head-to-head for lead-gen. | Aaron Young "Outdated strategies"; Solutions 8 on PMax; NAV43 2026 | If ads ever run: Search only, Search Partners off, Display Expansion off, auto-apply off. Never PMax. |
| 5 | **Track trial→paid via offline conversion import (gclid stored at signup, uploaded on first payment, ≤63 days from click) — but treat it as measurement, not a bidding signal, until volume exists.** | Pete Bowen (pete-bowen.com/google-ads-conversion-tracking-for-saas) | Already built: `backend/app/scripts/upload_google_ads_conversions.py`. Keep it; don't bid to it. |
| 6 | **Rob Walling's price-point rule: at ~$20/mo ARPA you get about five viable channels, and PPC and cold outreach are generally not among them.** | Walling, *The SaaS Playbook* (public summaries); MicroConf talk | This is the structural explanation for A$951 → 0. It was never going to work at this price. |
| 7 | **The stage-appropriate order at <100 users is: positioning thesis → founder 1:1s with the users you have → one repeatable low-touch channel → paid last.** Every stage-fit source agrees. | Dunford (SaaS Club ep. 252); Alströmer, YC Startup School; Walling; Schwartz | Tapeline has done the 1:1 outreach (17 users emailed 2026-08-11). Positioning thesis is drafted in §6.1. The one channel is AEO + comparison pages. |
| 8 | **Small brands win mid-funnel, "where users seek various options" — not head terms.** | Eli Schwartz (Lenny's Newsletter) | The 19 existing `/compare/*` pages *are* the mid-funnel play. The gap is placement and citations, not more pages. |
| 9 | **YouTube mentions are the strongest single correlate of AI-assistant visibility (r≈0.74); third-party branded mentions next (r≈0.66–0.71); backlinks and domain rating are near zero.** | Ahrefs 75k-brand study (ahrefs.com/blog/ai-brand-visibility-correlations) | For the one channel that works, a founder screen-recording is worth more than any backlink campaign. |
| 10 | **80% of AI-cited Reddit posts have <20 upvotes; Q&A threads are >50% of citations; median cited post ~80 words.** But Reddit citations barely travel between engines (~0.1%) — this is ChatGPT/Copilot-specific. | Semrush 248k-URL study; Kevin Indig "Consensus Gap" | Substantive answers in r/swingtrading etc. feed ChatGPT and Copilot directly — the two assistants that have already sent Tapeline users. Founder-written, disclosed, tool-agnostic. |
| 11 | **Schema markup and llms.txt are folklore as citation levers.** Google: "no special schema.org structured data that you need to add." | Google Search Central AI features doc | Keep the existing JSON-LD for hygiene; don't invest more here. |
| 12 | **61.7% of AI citations link a domain without naming it ("ghost citations").** Put the brand name in the sentence that carries the fact. | Semrush write-up of Indig's study | The scorecard's citable sentence must read "Tapeline's scorecard shows…", not just the numbers. |
| 13 | **A US-targeted stock scanner does NOT need Google's Financial Services verification — the US is not on the enforcement list.** What does apply: physical address + all fees immediately visible on the landing page, and the "Unreliable claims" rule. Australia *is* on the list, but only if you target AU. | support.google.com/adspolicy/answer/12390454, /2464998, /6020955 | No certification step blocks a US-only campaign. Do NOT apply for the complex-speculative-products certification — you'd fail it and flag the account. |
| 14 | **The word "signals" is a policy landmine.** The CFD/forex policy prohibits "trading signals, tips, or speculative trading information" — equities aren't in scope legally, but automated review keys on the token. | support.google.com/adspolicy/answer/15188218 | Say "score" / "composite score" / "rank" in every ad and ad-facing page. Never "signal(s)". |
| 15 | **Retargeting site visitors is allowed for an investing tool** — trading isn't a sensitive category. The real blocker is list size: Search remarketing needs ~1,000 active users in 30 days; Display ~100. | support.google.com/adspolicy/answer/143465, /2472738 | "Retargeting budget" has had nothing to spend on because there is no list. The fix is traffic, not policy. Never layer age/gender/ZIP targeting on US campaigns. |

**The one every coach implies but few write down:** no published playbook contains a "run ads anyway" case for a product whose max-affordable CPA is below its cost-per-trial. The uniform advice for that situation is fix funnel/price/LTV, use organic/referral, keep only brand defence.

---

## 2. Why the June campaign failed — the post-mortem, precisely

Reconstructed from `docs/launch/google-ads/tapeline-rsa-improved.csv` (what actually ran), the DB (no signup carries a gclid), and the research above.

| Cause | Evidence | Fix (already in §5) |
|---|---|---|
| **Compliance breach in the copy** | Headline "Plain-English Buy Signals" — "buy" violates the descriptive-only rule; "signals" is the CSFP-policy token | Removed. Every §5 headline is descriptive; "signal" never appears. |
| **Message-match failure** | Headline "Open 6-Factor Formula" — the public site deliberately does *not* publish the formula (PR #342 disclosure boundary). Anyone who clicked found the promise unkept | Copy promises only what the landing page shows. |
| **Wrong keywords for the price point** | Ad group "Best Stock Screener 2026" bid a $19.99 product on the same head term as $118 incumbents. Finance non-brand CVR is 2.55% — the lowest of any vertical — into *leads* for advertisers with $80+ CPLs | Non-brand head terms are gated off entirely. Only brand + "[competitor] alternative" long-tail. |
| **Landing pages didn't carry required disclosures** | Google FS policy requires a physical address + all fees "clearly and immediately visible" on the ad destination — not in a footer or on another tab | §5.5 landing checklist. |
| **Optimising toward the wrong event** | No offline import was live, so the account could only see clicks | Import script exists; §5.4 wires it as measurement. |
| **Sub-floor budget with no realistic path to learning** | ~A$1.90 CPC × 10 = A$19/day floor; campaign ran below it and expected optimisation | Gate in §4. |

Net: **the click price was fine (below benchmark). Everything after the click was broken.** That is a fixable problem — but fixing it and then re-buying clicks is still uneconomic at current LTV, which is why the gate exists.

---

## 3. Positioning — the thesis everything else hangs off

Drafted with April Dunford's five components, in her mandatory order (alternatives first, category last). This is a *thesis* to validate against what the 17 emailed users say, not a final answer.

**Competitive alternatives** (what the ICP would use if Tapeline didn't exist): free screeners they already have (Finviz free, TradingView screener, broker-built) — *the real competitor for a $0-budget founder*; paid scanners they're comparison-shopping (Trade Ideas ~$118–127/mo, Benzinga Pro, TrendSpider ~$107/mo) — filter/alert-heavy, day-trader-leaning; guru/alert rooms (Discord, YouTube pick lists) — prescriptive, unverifiable; DIY (spreadsheets, "ask ChatGPT for a watchlist"); do nothing.

**Unique attributes** (honest): one composite 0–100 score + one descriptive sentence per ticker instead of a filter builder; a **public, back-checked track record** (hit rate, median alpha vs SPY, days tracked) — no free screener or alert room publishes this, and paid scanners publish feature lists, not outcomes; smart-money inputs (SEC Form 4 insider buys, Congressional disclosures) alongside price/trend; descriptive labels, never buy/sell — a *feature* for the compliance-aware and for AI assistants that refuse to relay prescriptive advice; ~10× cheaper; the public record is the real product — live, and readable with no account or card; machine-readable surface (public API, SSR scorecard) — built to be quoted by assistants.

**Value**: an evening review becomes "open the daily top 10, read six sentences"; every score is checkable against what happened next so the user doesn't have to trust marketing; sub-$20/mo fits a $10–50k account where $118/mo is 1.4–7% of capital a year; one number + one sentence is quotable — to a journal, a spouse, or an AI assistant.

**Who cares most**: part-time US swing traders (hold days–weeks), $10–50k, review after work, already paying or about to pay for a scanner, skeptical of alert-room gurus, want a shortlist not a terminal. Increasingly: people who research tools by *asking* an assistant. **Explicitly not** (say so): intraday scalpers needing L2 + tick alerts (Trade Ideas fits them), options-first traders, quants wanting raw feeds.

**Market category — recommended: a sub-segment of "stock scanner"**: *the scored, track-recorded stock scanner for part-time swing traders.* Anchors on a term the ICP already searches, then reframes the buying criterion from "how many filters" to "does it publish what its scores did next, and can I read it in five minutes." (New-category positioning is legally risky and unaffordable to educate; head-to-head on "scanner" loses on filter count.)

**Compliant one-liners:**
- "Tapeline scores every US stock 0–100 on six factors and publishes the record of what those scores did next."
- "One number, one sentence, and a public track record — a stock scanner for part-time swing traders who don't have time for 500 filters."
- Comparison frame: "Trade Ideas is built for intraday scanning with real-time alerts. Tapeline is built for the evening review: a scored daily top 10 with a published back-check. Pick by workflow, not by feature count."

---

## 4. The ads gate — exact conditions for turning Google Ads back on

**Standing exception, always allowed:** brand terms + retargeting, capped at **A$5/day**, with the kill criteria in §5.6. Nothing else.

**Non-brand search turns on only when ALL of these are true:**

1. **≥10 paying customers acquired organically**, with ≥60-day retention observed on that cohort. (Alströmer: "if most people are just churning… wait until you have some people that care.")
2. **Measured landing→trial and trial→paid rates from organic/AEO traffic**, so a CPC can be turned into a CAC arithmetically rather than hoped for. Specifically: click→trial ≥15% on the exact landing page the ad would use.
3. **LTV:CAC ≥ 3 computed on that organic cohort at current prices, payback <12 months.** (Currently ~1.85:1 in the best case.)
4. **A message that has demonstrably out-converted the generic hero organically** — from a comparison page, a Reddit thread, or the AI-referral cohort. That exact message becomes the ad. (Demand Curve: ads amplify a message already proven; they don't find one.)
5. **Budget of at least A$19–20/day available for 90 days without stress** (the 10×CPC learning floor and the 60–90-day ramp) — i.e. ~A$1,800 committed to a test that may return nothing.

Until then, non-brand ads are off. This is not caution — it is what the paid-ads coaches themselves prescribe below their own floors.

**Founder action that costs nothing and sharpens the gate:** open Keyword Planner inside the paused account (free, no campaign needed) and pull real CPC ranges for the §5.2 keyword list. Every ungated CPC source is behind a paywall; the account already has the tool.

---

## 5. The Google Ads build — execution-ready, DO NOT ENABLE UNTIL §4 PASSES

Everything below is written so it can be created in the account today and left paused. Account: 271-638-2397 (currently paused, stays paused).

### 5.1 Account architecture

| Campaign | Purpose | Match / bid | Budget | Status |
|---|---|---|---|---|
| **TL — Brand** | Defend "tapeline", "tapeline scanner", "tapeline.io", "tapeline review/pricing" | Exact; Max Clicks with a A$1.50 max CPC cap | A$3/day | **Standing exception — may enable** |
| **TL — Retarget (Display/YouTube)** | Visitors who did not sign up; trialists who did not activate | Audience; Max Conv once list is eligible | A$2/day | **Standing exception — enable when the list reaches eligibility (~100 users/30d)** |
| **TL — Competitor Alternative** | "[competitor] alternative / vs / pricing / review" — Trade Ideas, TrendSpider, Benzinga Pro, Finviz Elite | Exact + phrase on modifiers only; never bare competitor names | A$12/day | **GATED (§4)** |
| **TL — Swing Scanner Intent** | Long-tail: "stock scanner for swing trading", "swing trade screener", "scanner with track record" | Exact; Max Clicks → Max Conv at first conversions | A$8/day | **GATED (§4)** |

Settings on every campaign: **Search network only. Search Partners OFF. Display Expansion OFF. Auto-apply recommendations OFF. Location = Presence in United States (not "interest"). Language English. No age/gender/ZIP layering** (consumer-finance personalisation hedge). Never Performance Max.

Bid ladder: Max Clicks (capped) while conversions = 0 → Max Conversions once trial signups exist → tCPA only at ≥30 conversions in 30 days. Value bidding: not at this scale.

### 5.2 Keywords

**Brand (exact):** `[tapeline]`, `[tapeline scanner]`, `[tapeline stock scanner]`, `[tapeline.io]`, `[tapeline pricing]`, `[tapeline review]`, `[tapeline vs finviz]`.

**Competitor alternative (exact + phrase on the modifier — GATED):**
`[trade ideas alternative]`, `"trade ideas alternative"`, `[trade ideas pricing]`, `[trade ideas vs]`, `[cheaper than trade ideas]`, `[trendspider alternative]`, `"trendspider alternative"`, `[trendspider pricing]`, `[benzinga pro alternative]`, `[benzinga pro pricing]`, `[finviz elite alternative]`, `[finviz elite worth it]`, `[stock rover alternative]`, `[tipranks alternative]`. Land each on its existing `/compare/<competitor>` page.

**Swing-scanner intent (exact — GATED):**
`[stock scanner for swing trading]`, `[swing trading stock screener]`, `[swing trade scanner]`, `[stock screener with track record]`, `[stock scanner that shows results]`, `[best stock scanner for part time traders]`, `[stock scanner one score]`.

**Negatives, campaign-level, day one** (small accounts keep tight negatives — the "fewer negatives" doctrine assumes Smart Bidding has data to learn from):
`free`, `crack`, `torrent`, `jobs`, `salary`, `career`, `course`, `tutorial`, `how to build`, `python`, `github`, `api docs`, `excel`, `spreadsheet`, `template`, `reddit`, `forex`, `crypto`, `bitcoin`, `options flow`, `signals`, `signal service`, `alerts room`, `discord`, `robot`, `bot`, `auto trade`, `autotrading`, `mt4`, `mt5`, `penny stock`, `otc`, `pink sheets`, `login`, `customer service`. Plus every competitor's bare name as an *exact* negative in the Intent campaign (so bare "trade ideas" doesn't leak from Intent — it belongs in Alternative with a modifier or nowhere).

Search Terms report mined weekly; harvest converters into exact, push junk to negatives.

### 5.3 Responsive Search Ad copy — compliance-checked

Every line below was checked against: descriptive-only (no buy/sell/should/recommend), no "beat the market"/outperform/guaranteed, no urgency/countdown, no exact factor weights, no "signal(s)", no vs-SPY figure in a headline, no regulator names or logos, no implied edge ("before it moves"). All headlines ≤30 chars, descriptions ≤90.

**Ad group: Brand**
Headlines: `Tapeline · Stock Scanner` · `One Score Per US Stock` · `Public Track Record` · `Public Record, No Account` · `Pro From $9.99/mo` · `30-Day Trial, $0 Today` · `Six-Factor Composite Score` · `Read The Tape In Minutes` · `Scores, Not 500 Filters` · `Insider Buys (Form 4)` · `Built For Swing Traders` · `See What Scores Did Next` · `Descriptive, Not Advice` · `Cancel Anytime` · `tapeline.io`
Descriptions: `A composite 0–100 score for US stocks with one plain sentence each. The record of what those scores did next is public.` · `The daily Top 10 and the full record are public and live, no account. Pro $9.99/mo, Premium $19.99/mo.` · `Recent insider buys, congressional trades and squeeze setups on one screen. Descriptive scores, not personal advice.` · `Every daily top-10 is checked against SPY the next session and published, wins and losses alike.`
Final URL: `https://tapeline.io/` (exact-match brand is the one case where homepage is acceptable).

**Ad group: Trade Ideas alternative** (GATED)
Headlines: `Trade Ideas Alternative` · `One Score, Not 500 Filters` · `Trade Ideas Is ~$127/mo` · `Tapeline Pro Is $9.99/mo` · `Built For The Evening Review` · `Not For Intraday Scalping` · `Public Track Record Daily` · `Compare Feature By Feature` · `Six-Factor Composite Score` · `30-Day Trial, $0 Today` · `Public Record, No Account` · `Pick By Workflow` · `Insider Buys + Congress` · `See The Side-By-Side` · `Descriptive, Not Advice`
Descriptions: `Trade Ideas is built for intraday scanning with real-time alerts. Tapeline is a scored daily top 10 for the evening review.` · `Trade Ideas from ~$127/mo. Tapeline Pro $9.99/mo. Same job: find setups fast. Different workflow. Compare honestly.` · `A composite 0–100 score and one sentence per stock, with the record of what those scores did next published daily.` · `If you need Level 2 and tick-level alerts, Trade Ideas fits. If you review after work, see the comparison.`
Final URL: `https://tapeline.io/compare/trade-ideas`

**Ad group: TrendSpider alternative** (GATED) — same structure; swap price line to `TrendSpider Is ~$107/mo`, URL `/compare/trendspider`.

**Ad group: Swing scanner intent** (GATED)
Headlines: `Stock Scanner For Swing Trades` · `One Score Per Stock, 0–100` · `Public Track Record` · `Read Six Sentences, Not Filters` · `Public Record, No Account` · `Pro From $9.99/mo` · `30-Day Trial, $0 Today` · `See What Scores Did Next` · `Six-Factor Composite Score` · `Insider Buys (Form 4)` · `Built For Part-Time Traders` · `Descriptive, Not Advice` · `Scores Refresh Every Minute` · `Wins And Losses Published` · `Cancel Anytime`
Descriptions: `A scored daily top 10 for part-time swing traders. One composite number and one plain sentence per stock.` · `Every daily top-10 is checked against SPY the next session and published, wins and losses alike. Judge the record.` · `The record is public and live — no account needed. Pro $9.99/mo. Premium adds insider buys and congressional trades.` · `Descriptive scores, not personal advice. See how a score is built and what it did next.`
Final URL: a dedicated `/lp/swing-scanner` (does not exist yet — build before enabling; homepage is not acceptable for non-brand).

Sitelinks (all campaigns): Scorecard → `/scorecard` · How It Works → `/how-it-works` · Pricing → `/pricing` · Compare → `/compare`. Callouts: `Public track record` · `Record free, no account` · `Cancel anytime` · `Descriptive, not advice`.

**Retargeting creative:** the scorecard with a losing week visible (proof, not promise); a 15-second live-scanner clip; "your trial ends on [date]" stated as a fact, no countdown.

### 5.4 Conversion wiring

- **Primary conversion (bid to):** `sign_up` (trial start). Already carries the Ads label per `lib/gtag.ts`.
- **Secondary (observe):** `subscribe` (first paid charge). Fires server-side from the Stripe webhook; already carries the Ads label.
- **Offline import:** `backend/app/scripts/upload_google_ads_conversions.py` uploads gclid → paid conversions with value. Needs the seven `GOOGLE_ADS_*` secrets set on the backend (see `docs/launch/google-ads/OFFLINE-CONVERSION-IMPORT.md`). Runs daily; the 30-day trial keeps first charge well inside Google's 63-day window. **Treat as measurement, not bidding signal, until ≥30 paid/30d.**
- **Enhanced conversions:** hashed email on both events. Improves match rate; adds no volume.
- **Static values for reporting:** trial = 1, paid Pro = 99, paid Premium = 199 — value-aware reporting while bidding stays count-based.
- **Do not fire `sign_up` conversions from any event other than the real signup** (see the analytics-stack notes — recovered events must never carry the Ads label).

### 5.5 Landing-page checklist (before any campaign is enabled)

Google's FS disclosure rule requires these "clearly and immediately visible" on the ad destination — not roll-over, not another tab:
- [ ] Physical business address on the landing page itself (registered office; confirm with the lawyer whether a PO box is acceptable — §8)
- [ ] All fees visible: monthly, annual, and that the trial converts to a paid plan (or lapses to free) and when
- [ ] No regulator names/logos, no implied accreditation
- [ ] "Descriptive scores, not personal advice" line above the fold
- [ ] The word "signal" absent from the page and its title/meta
- [ ] Message match: the page's H1 echoes the ad's promise (compare pages already do this for their competitor; the intent LP must be built)
- [ ] Track-record numbers presented as a record (days tracked, hit rate, median alpha) — never as a promise, never in the H1

### 5.6 Weekly checklist + kill criteria (for whatever is running)

Weekly (15 min): Search Terms report → negatives/harvest; impression share on brand (should be >90%); any disapprovals; conversion count vs floor.

Kill criteria — pause immediately if any of these fire:
- Brand campaign: any disapproval for financial-products policy → fix copy before re-enabling; spend >A$25 in a week with 0 clicks → keywords are wrong or brand has no search volume yet (likely) → pause, don't "give it time".
- Retargeting: list below eligibility for 30 days → pause the campaign, it can't serve.
- Any gated campaign, once enabled: **A$500 spent with 0 trial signups → pause and go back to §2 (page/offer), do not touch bids.** 90 days with <15 trials/month → the floor isn't reachable at this budget; pause.

---

## 6. The $0-budget campaign — what actually runs now

Ranked by evidence-from-the-vertical. Each: what, first steps, founder-hour cost, the signal it produces, and how it feeds the AI-assistant channel that already works.

### 6.1 Positioning first (Dunford) — 2 hours, once
Adopt the §3 thesis. Rewrite the hero and pricing copy to Harry Dry's three rules (visualise, falsifiable, unique). Test the thesis against the 17 users' replies to the 2026-08-11 email — tighten "who cares most" around whoever names Trade Ideas / Finviz Elite / TrendSpider as their alternative. **Signal:** whether the alternatives you assumed are the ones users actually name.

### 6.2 Founder-taught content on YouTube — 2–3 hours per video, one every two weeks
The strongest single correlate of AI-assistant visibility, and what TrendSpider (300+ videos), Benzinga (daily show) and TradingView (Wizards) all did. Five- to ten-minute screen recordings, no production: "reading a Tapeline score in 60 seconds"; "how the public track record is computed"; "Tapeline vs Finviz for an evening watchlist"; a weekly "what the scanner said vs what happened" from the scorecard. Titles carry the brand name and the comparison term (Ahrefs measures mentions in titles/descriptions/transcripts). Also publish your own "best stock screener for swing traders" video — Deepvue and Wisesheets got into that query exactly this way. Descriptive only. **Signal:** views, and whether Tapeline starts appearing in assistant answers to the video's title query.

### 6.3 Comparison pages — placement, not more pages — 3 hours, once, then 30 min/month
The 19 `/compare/*` pages are the mid-funnel play and they exist. What's missing per Indig's citation data: the one-sentence answer and the price/track-record fact in the **first 10–20% of the page**; the brand name in the sentence that carries the fact (ghost-citation defence); a "when the competitor is the better pick" section (which is what makes a comparison credible enough to cite); a dated "prices/features checked on" line. Then get the pages *cited*: submit to ScreenerMatch (lists 27 tools, low bar), and to any long-tail listicle that doesn't require an affiliate link. **Signal:** `signup_landing_path` hits on `/compare/*`; per-engine presence for "[competitor] alternative" prompts.

### 6.4 Reddit Q&A, founder-written — 1 hour/week
Answer real "which scanner for swing trading under $X" / "is Trade Ideas worth it" / "how do you build an evening watchlist" threads in r/swingtrading, r/stocks, r/Daytrading, r/investing. Substantive, tool-agnostic, disclosed founder, Tapeline mentioned only where it answers the question. Low-upvote Q&A is what ChatGPT cites — this is not about karma. **Constraint:** the founder's Reddit account is new; finance subs nuke self-promo. Answer for two weeks with zero mentions of Tapeline first. This is a human writing, not the inbox bot. **Signal:** chatgpt.com/copilot.com referrer + utm arrivals.

### 6.5 The artifact that travels — 4 hours, once
Six of eight tools in the vertical ignited on a free artifact that left the product: TradingView's embed widget on publisher sites, Finviz's heatmap image, TrendSpider's chart screenshots, Unusual Whales' data tweets. Tapeline's equivalents are **already built** — the score badge, the embed, the OG cards, the SSR scorecard. The gap is placement. Make every ticker page and scorecard row a clean, watermarked, screenshot-able image; post one striking, true, descriptive data point per day from the scorecard or the insider-buys feed to X (the Unusual Whales loop, kept descriptive). **Signal:** embed impressions (already instrumented, PR #459), X referrals.

### 6.6 Repeated launches — 2 hours each
Launch is something you keep doing (Mañalac). Re-launch on each material scorecard milestone ("365 days tracked", "1,000 picks logged") — Show HN, r/algotrading "I built…", Product Hunt update. One-third of AI citations come from zero-volume long-tail threads; launch posts are exactly that. **Signal:** referrer hosts on the launch day.

### 6.7 Monthly AI-visibility panel — 30 min/month, start now
Fix a 20-prompt set ("best stock scanner for swing traders under $20/month", "Trade Ideas alternative for part-time traders", "stock scanner with a public track record", "what is Tapeline", "Finviz vs Tapeline"…). Run monthly in ChatGPT, Copilot, Perplexity, Google AI Mode by hand. Log presence / named-vs-ghost / competitors shown, per engine (only 2.4% of cited URLs appear in all three engines — one "AI visibility score" is misleading). Diffable markdown in `docs/`. Pair with the chatgpt.com/copilot.com referrer counts, which are the outcome KPI. Start with ChatGPT — Ahrefs shows it is least gated by brand authority. **Signal:** this *is* the signal for the only channel that works.

### 6.8 Design the affiliate program now; recruit later — 2 hours design, 0 until trial→paid is measurable
Every mature tool runs 20–30% recurring with long cookies and coupon codes; none used it 0→1. At Tapeline ARPU, 30% is $3–6/mo per referral — below what coupon channels earn on Trade Ideas ($30–40/mo). So the design needs a higher % (40–50%) or a flat $20–30 bounty, a 365-day cookie, coupon-code attribution, and a creator-specific extended trial (Screener.co's 60-day pattern). **Compliance is the binding constraint:** ASIC's finfluencer enforcement (INFO 269; 26-081MR) makes the *affiliate's* copy the risk — bind creators contractually to descriptive language, ban performance claims, require disclosure, keep termination rights, supply pre-approved copy blocks. Rewardful is the wiring; blocked on the founder connecting live Stripe. **Recruit only once trial→paid is a number.**

### 30 / 60 / 90 days — a solo founder alongside product work

| Window | Do | Hours |
|---|---|---|
| **Days 1–30** | 6.1 positioning + hero rewrite · first two YouTube videos · comparison-page fact placement on the top 4 (`trade-ideas`, `finviz`, `trendspider`, `benzinga-pro`) · Reddit answering, no mentions · first AI panel run · Keyword Planner pull (no spend) · lawyer brief §8 sent | ~14 |
| **Days 31–60** | video every 2 weeks · daily descriptive data point on X · ScreenerMatch + listicle submissions · Reddit answering, mentions where relevant · second AI panel · brand campaign enabled (standing exception, A$3/day) with §5.6 kill criteria · landing-page disclosures added | ~16 |
| **Days 61–90** | keep the cadence · one milestone re-launch · third AI panel and first month-over-month comparison · affiliate program *designed* · **gate review (§4)** with real numbers | ~14 |

If, at day 90, the AI panel shows zero presence and the referrer counts haven't moved, the problem is content and citations — not ads — and the fix is more of 6.2–6.4, not spend.

---

## 7. What NOT to do — so it isn't relitigated

| Don't | Because |
|---|---|
| Re-run non-brand Google Search "to see if it works this time" | It was tested at below-benchmark CPC and produced 0/500. The floors say the budget can't learn. The vertical says 0/8 tools grew this way. Gate in §4 or nothing. |
| Performance Max, Search Partners, Display Expansion, broad match, auto-apply | Every small-account practitioner turns these off; they spend the budget on inventory Google monetises. |
| Meta prospecting | Special Ad Category = no lookalikes, no demographic targeting; the niche on Meta is alert-room sellers with prescriptive copy. Retargeting-only if ever. |
| Paid finfluencer sponsorships | $2k+ per micro-creator vs $10–20 ARPU needs ~17 annual Premium subs to break even, pre-PMF. Affiliates (pay-on-conversion) or organic inclusion only. |
| A generic affiliate program at 20–30% now | Below creators' opportunity cost at this ARPU, and no trial→paid baseline to attribute against. Design now, recruit later (6.8). |
| Investing in schema markup or llms.txt as citation levers | Google says explicitly none is needed; the causal evidence is nil. Keep for hygiene only. |
| Backlink campaigns | Near-zero correlation with AI visibility (Ahrefs r≈0.22). |
| Ad copy with "signals", "buy", "beat", "outperform", "guaranteed", win-rate-as-headline, countdowns, exact weights, regulator names | Each trips a specific Google policy or the house compliance rule (§5.3). The June campaign contained two of these. |
| Targeting Australia with any ad | Triggers Google's AU FS verification (mandatory even for "regulation-exempt" advertisers) and the ASIC advice analysis. Lawyer first (§8). |
| Reddit posting as promotion | Account is new; finance subs ban it; the citation value is in *answers*, not posts. |
| Layering age/gender/ZIP on US campaigns | Consumer-finance personalisation ambiguity; unnecessary anyway. |
| Optimising the in-account "Optimization Score" | Dismiss every recommendation and it can still read 100%. It's personalised to Google's revenue, not yours. |

---

## 8. Questions for the lawyer (Holley Nethercote) — before any AU exposure or scaled paid

1. If Tapeline ever targets Australia, Google requires FS verification even for "regulation-exempt" advertisers, with entity details matching ASIC/ABN records — which entity verifies, and does declaring "regulation-exempt" to Google create any representation risk?
2. Does paid advertising change the general-advice analysis? Does a headline like "See today's highest-ranked stocks" shift anything toward *general advice* even for a US-only audience, given AU domicile? Are AU residents who see/click the ads (geo-leak) a live issue?
3. Google's FS policy definition includes "personalized advice." Tapeline's per-user watchlist track record and user-configured alerts are user-selected, not adviser-selected — is that framing robust, and should ad copy avoid "personal(ised)" entirely?
4. US side: confirm Tapeline is neither a broker-dealer nor an investment adviser (impersonal publisher, *Lowe v. SEC* line), so FINRA 2210 and the SEC Marketing Rule don't apply.
5. `LICENSE_AUDIT.md` flagged Polygon/Massive Starter + Finnhub Free as personal/non-business tiers. Sequence the vendor-tier upgrade before scaling any paid channel?
6. Google wants a physical address on ad landing pages. Registered office vs principal place of business for a solo founder; is a PO box acceptable for Google *and* AU disclosure obligations?
7. Affiliate program: ASIC INFO 269 exposure via affiliates' copy — what contractual language and disclosure regime makes a descriptive-only affiliate program defensible?

---

## 9. Sources

**Ads coaching (free layer):** Solutions 8 small-budget floor — sol8.com/small-budget-google-ads/ · Solutions 8 on PMax — sol8.com/when-to-avoid-running-performance-max-campaigns/ · Define Digital / Aaron Young small budgets — definedigitalacademy.com/blog/google-ads-small-budget-strategy · outdated strategies — definedigitalacademy.com/blog/outdated-google-ads-strategies · KlientBoost structure — klientboost.com/kitchen/google-ads-strategy/ · message match — klientboost.com/landing-pages/landing-page-message-match/ · Powered by Search SaaS blueprint — poweredbysearch.com/blog/b2b-saas-google-ads-blueprint/ · Pete Bowen offline conversions — pete-bowen.com/google-ads-conversion-tracking-for-saas · WordStream query-matching update — wordstream.com/blog/google-ads-query-matching-updates · Google Help tCPA — support.google.com/google-ads/answer/6268632 · NAV43 Search vs PMax — nav43.com/blog/search-vs-performance-max-for-lead-gen-scale-guide-2026/

**SaaS marketing (free layer):** Rob Walling SaaS Playbook summaries — howtoes.blog/2025/06/12/the-saas-playbook-complete-book-summary-all-key-ideas/ · MicroConf talk — youtube.com/watch?v=BgC-yiNYsR4 · YC Startup School recap — ycombinator.com/blog/startup-school-week-4-recap-kat-manalac-and-gustaf-alstromer/ · April Dunford SaaS Club ep. 252 — saasclub.io/podcast/5-steps-saas-product-positioning-with-april-dunford-252/ · Eli Schwartz on Lenny's — lennysnewsletter.com/p/rethinking-seo-in-the-age-of-ai-eli-schwartz · Kevin Indig Consensus Gap — growth-memo.com/p/the-consensus-gap · Indig ChatGPT citations via SEL — searchengineland.com/chatgpt-citations-domains-study-472349 · Ahrefs AI visibility correlations — ahrefs.com/blog/ai-brand-visibility-correlations · Semrush Reddit study — semrush.com/blog/reddit-ai-search-visibility-study/ · Semrush ghost citations — semrush.com/blog/the-ghost-citations-study/ · Google AI features doc — developers.google.com/search/docs/appearance/ai-features · Harry Dry — marketingexamples.com · Demand Curve — demandcurve.com/growth/intro · Backstage SEO comparison pages — backstageseo.com/blog/b2b-comparison-pages/

**Policy:** Financial products & services — support.google.com/adspolicy/answer/2464998 · FS verification by location — /15332527 · regulators + dates — /12390454 · certifications hub — /7645254 · complex speculative products — /15188218 · unreliable claims — /6020955 · personalised advertising restrictions — /143465 · negative financial status — /16700443 · consumer finance — /16700846 · remarketing list eligibility — support.google.com/google-ads/answer/2472738

**Benchmarks:** WordStream 2025 — wordstream.com/blog/2025-google-ads-benchmarks · Google Ads Transparency Center (trade-ideas.com / trendspider.com / benzinga.com / finviz.com, US, viewed 2026-08-17) · Meta Ad Library ("stock scanner", US, active, viewed 2026-08-17)

**Vertical cases:** TradingView 2013 — builtinchicago.org/articles/investors-tradingview-addictive-facebook · TradingView 1M MAU — inc.com/shazir-mucklai/tradingview-is-taking-social-investing-to-the-next-level.html · TrendSpider founder — tradingreviewers.com/trendspider-dan-ushman-interview/ · TrendSpider affiliates — trendspider.com/affiliates/ · Trade Ideas — businessviewmagazine.com/trade-ideas-scanning-opportunities-markets-winning-financial-portfolio/ · Trade Ideas affiliates — trade-ideas.com/affiliate-program/ · Benzinga Pro affiliates — benzinga.com/pro/affiliate-program · Koyfin seed — alleywatch.com/2019/09/koyfin-invest-financial-data-analytics-rob-koyfman/ · Unusual Whales — tracxn.com/d/companies/unusualwhales/ · Finviz traffic — similarweb.com/website/finviz.com/ · ASIC finfluencer 26-081MR — asic.gov.au/about-asic/news-centre/find-a-media-release/2026-releases/26-081mr-asic-continues-finfluencer-crackdown-alongside-global-regulators/ · finance CPMs — sponsorradar.com/insights/youtube-sponsorship-rates-what-brands-should-pay

*Research working files (full sweeps with source-quality tiers and gaps): scratchpad `ads-research/1-4*.md`, 2026-08-17. Gated sources not read and not cited as read: Indig "Ghost citations" full body, Schwartz "Product-Led AEO playbook", Walling's SaaS Playbook itself, Rudansky's course transcripts.*
