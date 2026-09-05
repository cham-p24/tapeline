# Tapeline — The Paid-Ads → Paid-Subscriber Pathway

*Assembled 2026-06-28. The question answered: "the exact, clear pathway to make people subscribe and pay for Tapeline through ads." Fact-checked against current (2026) Google/Meta financial-ad policy, trial-conversion benchmarks, finance CPCs, and consumer-fintech churn. Economics are worked, not asserted. This is decision-grade, not legal/tax advice.*

---

## THE ONE-PARAGRAPH ANSWER

There is no "turn on ads → people pay" button for a $30–50/mo stock scanner. Cold ad traffic to a $30 product is **structurally marginal** because a $4–5 finance click run through a real trial funnel costs **$300–450 to produce one paying customer**, while a Tapeline subscriber is worth **~$370–530** in lifetime gross profit. At that ratio you lose money or barely tread water. The pathway that **works** is a sequence, not a switch: **(0)** *Stripe is already wired* — the real near-term gate is passing **Google Ads identity verification (~2026-07-04)**, **(1)** install conversion tracking that counts *paid subscriptions*, not signups, **(2)** point every ad at a dedicated landing page with a card-on-trial offer and a fast "aha", **(3)** start on Google **Search** (intent, no certification needed for a scanner) plus **finance-newsletter sponsorships**, **(4)** bid toward the *paid* event via offline-conversion import, **(5)** retarget abandoners cheaply, and **(6)** only scale while LTV:CAC ≥ 3 and payback < 12 months. Done in that order the math flips from −$450 to +$104 CAC. Done out of order (ads → homepage → no-card trial → optimize-to-signups) it bleeds. **Ads are the amplifier you bolt on after the funnel converts — not the engine you start with.** And for a finance product at this CAC, your *cheapest* paid-style channel is **affiliates** (pay-on-conversion creators, zero CAC risk) — see `TAPELINE_GROWTH_STRATEGY_10X.md` §6. **⚠️ 2026-07 reprice note:** at the new **$9.99–19.99** tiers even the best-tuned funnel lands only **~1.85:1 LTV:CAC — below the 3:1 scale gate** (see the pricing-update callout in Part 1). So treat paid Search as **branded + retargeting only**, and lead with **affiliates + organic** — the funnel levers below now buy *breakeven*, not profit.

---

## PART 1 — THE BRUTAL ECONOMICS (read this first; it governs everything)

Every downstream decision is justified by this table. Planning inputs (grounded in sources at the bottom):

> ⚠️ **PRICING UPDATE — 2026-07-29 (founding reprice).** Tiers dropped to **Pro $9.99/mo ($99/yr) · Premium $19.99/mo ($199/yr)** (was $29.99 / $49.99). The numbers below are **recomputed at the new prices**, and the conclusion *hardened*: lower price → lower LTV → paid Search now sits **below the 3:1 scale gate even in the best-tuned case (row C ≈ 1.85:1)**. So the funnel levers (card-trial, dedicated LP, annual mix, retargeting) are **mandatory just to reach breakeven**, and paid Search moves from "surgical" toward "branded + retargeting only." Affiliates + organic are the growth path.

- **Contribution/customer/mo** = ARPU × gross margin. Blended ARPU ≈ **$12/mo** (mostly Pro $9.99, some Premium $19.99, some annual — Pro annual $8.25/mo, Premium annual $16.58/mo), GM 80% → **≈ $9.6/mo gross profit per subscriber** (was ~$26).
- **LTV** = contribution ÷ monthly churn. Consumer-fintech churn is **5–10%/mo** (high — low switching cost, free alternatives like Finviz).
  - 9% churn → 11 mo → **LTV ≈ $106**
  - 7% churn → 14 mo → **LTV ≈ $134**
  - 5% churn (annual-plan heavy) → 20 mo → **LTV ≈ $192**
- **CPC** ≈ **$4** blended (finance avg $3.44–5.16; cheaper on "scanner/alternative software" terms, pricier on hot-money terms). Unchanged by the reprice.
- **CAC per paying customer** = CPC ÷ (click→trial × trial→paid). This compounding fraction is where businesses live or die.

| Scenario | click→trial | trial→paid | CPC | **CAC** | LTV (churn) | **LTV:CAC** | Payback | Verdict |
|---|---|---|---|---|---|---|---|---|
| **A. No-card trial, ads→homepage** (the default trap) | 10% | 8.9% | $4.00 | **$449** | $134 (7%) | **0.30** | ~47 mo | ❌ Bankrupt |
| **B. Card-required, decent landing page** | 4% | 31% | $4.00 | **$323** | $134 (7%) | **0.42** | ~34 mo | ❌ Underwater |
| **C. Tuned LP + card trial + annual push + retargeting blend** | 6% | 40% | $2.50* | **$104** | $192 (5%) | **1.85** | ~11 mo | ⚠️ ~Breakeven, still < 3:1 gate |

\*Blended CPC drops to ~$2.50 once cheap retargeting clicks ($0.50–1) and low-cost competitor-alternative keywords dilute the expensive head terms.

**The entire game is moving from row A to row C — but at the repriced tiers even row C lands ~1.85:1, under the 3:1 scale gate (§Step 6).** Notice what does NOT change between rows: the ad account, the bids, the keywords. What changes is **landing-page conversion, the trial offer, annual mix (LTV), and retargeting.** That is why ads are step 3, not step 1 — and why you must tune the funnel on cheap organic traffic *before* you pour paid clicks into it. **You cannot afford to learn CRO with $4 clicks — and at $9.99–19.99 even a great funnel barely clears breakeven, so keep paid Search tiny (branded + retargeting), and put the real energy into affiliates + organic.**

> **Honest verdict:** at Tapeline's price point, paid ads are viable but *tight* — a precision channel that returns ~3–5:1 only when the funnel is already excellent. It will never be a "faucet." Your cheapest, highest-ROI customers will keep coming from organic (HN/Reddit/SEO/scorecard) — ads are how you *add predictable volume on top* once each visitor is worth more than the click costs.

---

## PART 2 — THE PATHWAY (sequenced; do not reorder)

### STEP 0 — Confirm money can move + clear the ad-account gate (mostly done)
**Correction (per the 2026-06-26 audit): Stripe billing is already fully wired — it's the most mature subsystem.** The mid-May "Stripe is THE blocker" note is stale. So Step 0 is now *verify*, not *build*:
1. Run a real live-mode checkout end-to-end once (Pro monthly) to confirm webhook → subscription → access all fire. Confirm `/api/status` shows `stripe: true`.
2. **The actual near-term clock is Google Ads advertiser identity verification, reportedly due ~2026-07-04** (operator-only, this week). Miss it and the one demand channel you'd be funding gets throttled. Do this before spending.
3. Confirm the site is indexed (`site:tapeline.io`) and the Vercel crawl-cap/HTTP_0 throttle is fixed — paid clicks to a non-indexed, slow site waste Quality Score.
**Verify these three first-hand; they came from agents reading docs, not a live check.**

### STEP 1 — Install paid-grade conversion tracking (this is where most advertisers fail)
The #1 paid-ads mistake is optimizing toward **free trials** — you train Google to find people who love free things and never pay. Fix the architecture *before* spending:
1. **GA4 + Google tag** on the Next.js site; **Google Ads ↔ GA4 linked**.
2. **Two distinct conversion actions**: `trial_signup` (low/secondary value) and **`paid_subscription` (PRIMARY, high value)**. Fire `paid_subscription` from the Stripe `invoice.payment_succeeded` / `checkout.session.completed` webhook — server-side, not a thank-you-page pixel (paid conversion happens after the 30-day trial, off-session).
3. **Enhanced Conversions** — send hashed email (you have it via Clerk) so Google recovers cross-device/cookie-lost conversions.
4. **GCLID capture-on-click → offline conversion import.** Store the GCLID with each signup; when the trial converts to **paid**, upload that GCLID back to Google **with the dollar value** (first-month MRR, or predicted LTV). This is what lets Smart Bidding chase *payers*, not tire-kickers. Daily upload.
5. If you ever run Meta: install the **Conversions API (CAPI)** server-side for the same paid event.
**Without Step 1, you are flying blind and will optimize to the wrong outcome.**

### STEP 2 — Build the conversion funnel (the part that decides profit)
**a) Dedicated landing pages — never the homepage.** One ad theme → one page → one promise → one CTA. Message-match (the page's headline echoes the ad) converts 2.5–3× better *and* raises Quality Score (cheaper clicks). Build one LP per keyword theme (e.g. `/lp/finviz-alternative`, `/lp/transparent-stock-score`, `/lp/congress-tracker`).

**b) The trial decision — change the default for PAID traffic.** ⚠️ **Superseded 2026-08-21/22 by #536/#548** — the card-required trial shipped universally, and signup no longer grants a trial at all. The organic/paid split recommended in the rest of this sub-section no longer exists; read it as the reasoning that led to the change, not as a live recommendation. *As written in June 2026:* the 30-day **no-card** Premium trial is correct for *organic* traffic (more signups, more total payers). For **paid** traffic it bleeds: you pay $4/click to acquire trialists who convert at ~8.9%. For ads, move to one of:
   - **Card-required free trial** (~31% trial→paid, ~3.5× higher) — the single biggest CAC lever, *with* clear auto-charge disclosure, a day-13 pre-charge email, and one-click cancel; **or**
   - **A $1 / 30-day paid trial** — a strong intent filter that screens out tire-kickers entirely (best for cold paid clicks).
   ~~Keep no-card for organic; **A/B the card requirement specifically on the paid segment.**~~ **Decided and shipped 2026-08-22 (#548) — universally, not as a paid-only A/B.** The remaining open question is $1-paid-trial vs $0-card-required.

**c) Engineer the "aha" inside 15 minutes.** Trial→paid is decided by activation, not signup. For Tapeline the aha = *"the live scanner surfaced a real setup I'd act on"* + *"the public scorecard proves it isn't hype."* Onboarding must drop the user straight into a live scan with their watchlist seeded and the scorecard one click away. Instrument the activation event in GA4 and treat it as a leading indicator of the paid conversion.

**d) The wedge converts — but ONLY under the corrected pitch.** ⚠️ **Critical:** the live public scorecard currently shows *underperformance* (~42% hit-rate, −0.58% median alpha vs SPY per the 2026-06-26 audit). So you must NOT sell "our scores beat the market" — that's false, non-compliant, *and* a skeptical FinTwit/Reddit audience will check. Reframe the wedge to the only true and compliant claim: **process, honesty, and time-savings** — *"Most gurus show you the wins. We show you the entire record, graded vs SPY, losses included."* Under that framing the transparency moat (six named factors with their weight ordering published — never the numbers, which PR #342 stripped; public scorecard; live scanner preview) is still your highest-converting asset for a previously-burned audience — feature it above the fold. (And ship the scoring "Fix-3" + Finnhub cache backfill so the record improves.) See `TAPELINE_GROWTH_STRATEGY_10X.md` §1 — this is a positioning decision the founder must consciously own.

### STEP 3 — Pick channels in this order
| Rank | Channel | Why it's first/later for Tapeline | Start? |
|---|---|---|---|
| **1** | **Google Search** | Captures existing intent ("stock scanner", "Finviz alternative"). **A scanner needs NO Google certification** (it's not a CFD/forex/broker). Most control on a small budget. | **START HERE** |
| **2** | **Finance newsletter / podcast / fintwit-creator sponsorships** | Audience is pre-qualified retail traders; **not policy-gated**; often flat-fee so CAC is predictable; trust transfers from the host. Often the *best CAC* for a niche skeptical audience. Start with $200–500 test slots (Daily Upside, Snacks, Compound, niche fintwit). | **START (parallel)** |
| **3** | **Reddit Ads** | Directly targets r/stocks, r/investing, r/algotrading — your literal ICP. Cheaper clicks than Google; lower intent, so send to a strong LP + retargeting. | Week 3–4 |
| **4** | **Google Display / YouTube retargeting** | Cheap re-engagement of trial-abandoners (see Step 5). Not for cold prospecting yet. | As soon as you have traffic |
| **5** | **Meta (FB/IG)** | **Handicapped for you**: a stock scanner is forced into Meta's **Special Ad Category** (Jan 2025) → **no lookalike audiences, no age/gender targeting**, plus mandatory standardized risk warnings. Hard to reach a niche without lookalikes. | Later, retargeting-first only |
| — | **TikTok** | Only if you can make native short video and accept a younger, lower-intent audience. | Optional |

**First move: Google Search + 1–2 newsletter sponsorships, run simultaneously, ~$1.5–3k/mo test budget concentrated (don't spread thin).**

### STEP 4 — Google Search campaign structure
- **One Search campaign**, 3–6 **Single-Theme Ad Groups** (STAGs), each → its matched LP. Starting themes (cheapest, highest-intent first):
  1. **Competitor-alternative** (cheapest intent, warmest): `finviz alternative`, `trade ideas alternative`, `tipranks alternative`, `zacks alternative`, `trendspider alternative`, `stock rover alternative`.
  2. **Category tool**: `stock scanner`, `stock screener`, `real-time stock scanner`, `best stock screener`.
  3. **Use-case**: `swing trading scanner`, `momentum stock scanner`, `squeeze scanner`, `stock screener for swing trading`.
  4. **Differentiator angle** (cheap, on-brand): `transparent stock score`, `congress stock tracker`, `insider buying tracker`. (Not `13f tracker` — Quiver was cancelled and there is no 13F surface to send the click to.)
- **Match types**: start **Phrase + Exact** (control at zero data); graduate to Broad + Smart Bidding once you have ~30 conversions.
- **Negatives day one**: `free`, `crack`, `jobs`, `salary`, `course`, `reddit`, `excel`, `how to`, `forex`, `signals`, `robot`, `auto trade` (the last three also keep you clear of restricted-product intent).
- **RSAs**: 2 per ad group, 8–10 headlines, all 4 descriptions, keyword in ≥1 headline; sitelinks + callouts ("Published methodology", "Public scorecard", "Cancel anytime", "30-day trial"). **Never "Published formula" / "Open 6-Factor Formula"** — PR #342 withdrew the weights and the equation, so that copy fails message-match on arrival.
- **Settings that quietly waste money**: opt **OUT** of Search Partners + Display on Search campaigns; **auto-apply recommendations OFF**; location = **Presence** (US, + any English markets you'll support); Search Terms Report mined **weekly** (add negatives, harvest converters).
- **Bidding ladder**: Maximize Clicks (capped) → Maximize Conversions (once the paid event fires) → **Target CPA / tROAS** at ~30 paid conversions/30 days, optimizing on the **paid** action with values from Step 1.

### STEP 5 — Retargeting (the cheap conversion multiplier)
Most trial-abandoners and LP-bouncers won't convert on first touch. Stand up a **retargeting campaign** (Google Display/YouTube; Reddit later) the moment you have traffic:
- Audiences: visited LP-but-no-signup; signed up-but-not-activated; activated-but-trial-expiring.
- Creative: the scorecard (a *losing* week included — proof), a 15-sec live-scanner clip, "your trial ends in 2 days."
- Retargeting clicks are $0.50–1 and convert far higher — this is what pulls blended CPC down to the ~$2.50 in Scenario C.

### STEP 6 — The scale gate (when to add fuel, when to stop)
Run the weekly growth loop. Scale spend **only while**:
- **LTV:CAC ≥ 3** (on fully-loaded CAC, measured on *paid* subscribers via offline import), and
- **CAC payback < 12 months** (< 6 = pour it in), and
- you're shifting ≥ 40% of new subs onto **annual** (this is what lifts LTV from $377 → $528 and flips the math).
If a channel can't clear that after the learning period + 3–4 weeks, **cut it** — don't "give it more time" at $4/click. Keep no single channel > ~70% of acquisition.

---

## PART 3 — COMPLIANCE: stay inside policy, keep your account alive

A suspended ad account erases the pathway. The good news: **Tapeline's no-advice, descriptive-label, transparency posture is almost perfectly built for financial-ad approval.** The rules:

**Google (a scanner is NOT certification-gated, but financial-products rules still apply):**
- ✅ A research/screening tool with no trading, no brokerage, no advice, no "signals" is **outside** the complex-speculative-products certification regime (that's CFDs/forex/spread-betting/broker affiliates).
- ❌ **Never** in ad copy or LP: guaranteed/specific returns, "get rich", "beat the market", "winning picks", "profit", price predictions, or anything that reads as a **trading signal/tip**. That's the fastest path to disapproval *and* the one thing that could reclassify you as a restricted product.
- ✅ **Safe framing**: "scanner", "screener", "research", "data", "scores", "transparent methodology", "back-tested vs SPY (shown publicly)". Descriptive, never prescriptive.
- ✅ Add an "informational purposes only — not investment advice" disclosure on every LP; you already have `/legal/*`.

**Meta (if/when used):** stock scanner = **Special Ad Category (Financial Products & Services)** → expect business/identity verification, **no lookalikes / no demographic targeting**, and if you ever mention a number that looks like a return/yield you must use Meta's **standardized risk-warning template** (custom warning text = auto-reject). Plan Meta as retargeting-first, not prospecting.

**The single biggest account-killer:** implying performance/returns. Your scorecard *shows* outcomes factually (wins and losses) — keep it descriptive ("here's how picks moved vs SPY"), never promissory ("our picks beat the market"). This is doubly true because the live record currently *trails* SPY — a "beat the market" claim is both a policy/FTC violation and demonstrably false. The wedge, the policy, and the truth all want the same pitch: **process + honesty + time-savings.**

**Australia (you're Melbourne-based):** a tool that scores/ranks securities can edge toward "financial product advice" under ASIC. Add a clear AU disclaimer ("general information only, not personal advice, doesn't consider your objectives") and **get an AU AFSL/ASIC opinion from a financial-services lawyer before taking Australian subscribers.** This is the highest-variance legal risk in the whole plan — don't run AU-targeted ads until it's cleared.

---

## PART 4 — THE 30-60-90 EXECUTION PLAN

**Days 0–14 — Make money measurable + clear the gates (no spend yet)**
- Verify a live checkout (Stripe is already wired); **pass Google Ads identity verification before ~07-04**; confirm indexation + crawl-cap fix (Step 0).
- Install GA4 + Google tag, the two conversion actions, Enhanced Conversions, GCLID capture, offline-import job (Step 1).
- Build 3 dedicated LPs (finviz-alternative, "show-you-the-record"/transparent-process, congress-tracker) with the scorecard above the fold under the *process+honesty* reframe — not a performance claim. (The card-on-trial "variant" is moot: #548 shipped the card gate universally on 2026-08-22.)
- Confirm `/legal` disclosure + "informational only, not investment advice" line on each LP; **add the AU disclaimer block and book the AU financial-services (AFSL/ASIC) lawyer before taking AU subscribers.**

**Days 15–45 — Light the first paid traffic, tuned, small**
- Google Search: 1 campaign, 3–5 STAGs, Phrase+Exact, negatives, RSAs, Search Partners/Display OFF, Max Clicks. Budget concentrated (~$50–100/day).
- Launch 1–2 newsletter sponsorships ($200–500 each) → same LPs with a tracked UTM/promo.
- Stand up retargeting.
- ~~**A/B the card-vs-no-card trial on paid traffic.**~~ **Superseded by #548 (2026-08-22)** — the card requirement shipped universally, so there is no no-card arm left to test. The live open question is $1-paid-trial vs $0-card-required. Mine Search Terms weekly. Watch *paid* conversions, not trials.

**Days 45–90 — Bid toward payers, then decide**
- Offline conversion import live → switch to Maximize Conversions, then Target CPA on the **paid** event once ≥30 paid conversions/30 days.
- Push annual hard on the pricing page (target ≥40% of new subs annual).
- **Gate check:** is fully-loaded LTV:CAC ≥ 3 and payback < 12 mo? If yes → scale the winners. If no → fix the funnel (LP CVR, activation, annual mix) before adding budget; do **not** scale a leaky funnel.

---

## Sources
- Google Ads — Financial products & services policy: https://support.google.com/adspolicy/answer/2464998
- Google Ads — Complex speculative financial products (scanner is *excluded*; CFD/forex only): https://support.google.com/adspolicy/answer/15188218
- Google Ads — Restricted financial products certification: https://support.google.com/adspolicy/answer/7645254
- Meta — Ads for financial products & services / Special Ad Category: https://www.facebook.com/business/help/1157846251802527 · https://getelevar.com/news/meta-financial-products-services-ads-category/
- Trial-to-paid (no-card 8.9% vs card 31.4%, 2026 ChartMogul; volume deltas): https://www.chargebee.com/blog/saas-free-trial-credit-card-verdict/ · https://userpilot.com/blog/credit-card-vs-no-credit-card/
- Finance CPC benchmarks ($3.44–5.16): https://www.wordstream.com/blog/2025-google-ads-benchmarks · https://www.get-ryze.ai/blog/google-ads-cost-benchmarks-by-industry-2026
- Consumer-fintech churn (5–10%/mo): https://www.revenuecat.com/state-of-subscription-apps-2025/ · https://www.subjolt.com/guides/churn-rate-benchmarks/

*Pairs with `docs/launch-strategy.md` (organic-first plan) and `docs/PRICING.md` (trial config). Paid ads sit on top of the organic engine — they don't replace it. Revisit the economics table whenever price, churn, or CPC moves materially.*
