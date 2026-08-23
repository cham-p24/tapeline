# Meta (Facebook / Instagram) ads — decision

*Final, 2026-08-20. Answers one question: should Tapeline run Meta ads, and would that help conversion? Long-form companion to the single Meta line in `docs/PAID_MARKETING_PLAYBOOK.md` §7 ("Special Ad Category = no lookalikes, no demographic targeting; the niche on Meta is alert-room sellers with prescriptive copy. Retargeting-only if ever."). Built from six research sweeps, then an adversarial review and a ~70-claim fact-check against live Meta pages, primary papers and `origin/main` (2026-08-20); every correction from those passes is applied here. Nothing here is legal advice. Evidence grades: A controlled / replicated · B large independent dataset · V vendor telemetry · C practitioner consensus · D single case · E folklore. Older than 2020 flagged *(older)*. [unverified] = not confirmed at a primary source. USD unless marked A$.*

---

## 1. The answer

**No. Not prospecting, not now; not retargeting until the three conditions in §7 hold; and not as a "conversion" lever at all.**

- **Meta does not touch the step that is broken.** Tapeline's conversion problem is trial → paid (0 of ~5 live no-card trials; 0 checkouts ever). Meta prospecting buys visitor → signup. The only Meta product that reaches the warm funnel is retargeting, and the best randomised evidence for retargeting is a **+14.6 % lift in return visits** that decays within weeks, with no headline purchase lift (Sahni, Narayanan & Kalyanam, *JMR* 2019, A). The five trialists are reachable by email today for $0.
- **The economics fail by 4–40×, and no bid or creative optimisation closes that.** Finance CPCs of $1.22–3.77 (WordStream 2025, B; aggregators, C) against a ~$0.50 affordable click (Cohen's ARPA ÷ 25 rule, C) and a ~$30–60 affordable CAC give **$40–150 per trial** and, at the opt-in-trial median of 4–6 % trial→paid (ChartMogul 2026, n=200 B2B, B — a proxy for a B2C prosumer tool, not a measurement), **$650–2,500 per payer**. Even the most generous reading of the ChartMogul data (the 23 % of no-card products converting above 25 %) lands at ~$164 per payer — still ~4× the ceiling (§4).
- **Policy removes the levers that would normally rescue a niche product.** Since 2025-01-14 (Marketing API doc, V; Ads Manager enforcement reported from 2025-01-21, C) anything Meta reads as "investment services" falls in the Financial Products & Services (FPS) Special Ad Category: no lookalikes, no age/gender/ZIP targeting, no interest exclusions. Finance domains typically land in Meta's "core setup" data-sharing restriction (URL paths and custom parameters stripped — C). Australia has a separate verification-and-label regime since Feb 2025 that Tapeline must not enter before the Holley Nethercote consult (§3).
- **Retargeting is deliverable but tiny, unstable and unmeasurable at today's traffic.** At the playbook's ~50 visitors/week, a 180-day website audience is roughly **400–900 matched people** — above Meta's ~100 hard floor, at or under the ~1,000 practical floor (C). It would saturate in days, cost A$2–5/day, and prove nothing about payers: the 14-day trial puts any `Subscribe` event outside Meta's 7-day-click window by construction, and detecting a purchase lift needs audiences in the millions (Lewis & Rao, *QJE* 2015, A *(older)*).
- **Channel–ICP mismatch.** The Ad Library sweep (§6) shows "swing trading" on Meta is ~520 alert-room / trading-education ads. People who click those are pre-selected for prescriptive offers; a descriptive scanner is the wrong product for that audience even before price.

**Verdict:** Meta prospecting — closed (three independent blockers: economics, FPS learning floor, unmet ads gate; any one is sufficient). Meta retargeting — closed until §7; two of the three conditions are A$0 reads once a pixel exists, and a pixel is itself a gated item (§8). **The positive recommendation is in §9: run the message test organically, for A$0, which is also gate condition 4 of the standing playbook.** This is the same verdict as the Google gate in `PAID_MARKETING_PLAYBOOK.md` §4, reached from a different direction; nothing in the six sweeps, the review or the fact-check reopens it.

---

## 2. What "conversion" means here, and which step Meta touches

| Step | State on 2026-08-20 | What moves it | Does Meta move it? |
|---|---|---|---|
| Visitor → signup | ~200 visits and ~7 signups a month (`SAAS_OPTIMISATION_PLAYBOOK.md` §6, A6). Visits are the scarce input (the playbook's 15–35k-visits/month back-solve). The only engaged users came from AI-assistant referral. | Traffic + landing page + message. | **Yes — this is what prospecting buys.** The objection is not that the step is solved; it is that Meta buys it at $1.22–3.77 a click against a ~$0.50 affordable click, with colder people than the Google search clicks that already produced 0 trials from A$951, and teaches nothing about trial→paid. |
| Signup → trial | 100 % by construction (auto 14-day Premium trial, no card). | Nothing. | No. |
| Trial → activation | Was the gap; fixed in #507. | Product, onboarding, email. | No. |
| **Trial → checkout → paid** | **0 of ~5 live; 0 ever. Unmeasured.** | Product value, price, trust, in-app prompts, email (#441 / #442 / #445 shipped). | **No** — only retargeting reaches it, and retargeting lifts return visits, not purchases (§5). |
| Paid → retained 60 d | No data. | Product. | No. |

"0 of 5" is unmeasured, not bad: with zero successes in n trials the one-sided 95 % upper bound on the true rate is ≈ 3/n (rule of three) — ~60 % at n=5, 15 % at n=20. The way to measure it is more trials *of the kind that already engage* (organic / AEO) plus asking the live trialists why they have not checked out — the ≥6 interviews the SaaS playbook gates engineering behind (0 recorded). Cold Meta trials would add noise to exactly the cohort that has to be read cleanly.

Two further reasons Meta would not even add clean top-of-funnel information: paid-click returns are "a fraction of non-experimental estimates" and concentrate in new / infrequent users (Blake, Nosko & Tadelis, *Econometrica* 2015, A *(older)*); and observational / attribution-style lift estimates are unreliable even with hundreds of experiments to calibrate against — across 663 Facebook RCTs the best non-experimental methods were off by a median **115 / 107 / 62 percentage points** for upper / mid / lower-funnel outcomes, against true median lifts of 28 / 19 / 6 % (Gordon, Moakler & Zettelmeyer, *Marketing Science* 2023, arXiv 2201.07055, A/B; Gordon et al. 2019 on 15 experiments found the same several-fold overstatement, A). "3 conversions attributed" at A$450 spend would be noise dressed as signal.

---

## 3. Policy — Special Ad Category, verification, domain restrictions

**Financial Products & Services (FPS) Special Ad Category.** Required from **2025-01-14** for advertisers based in or targeting the US who run ads for financial products and services (Marketing API "Special Ad Category" doc, fetched 2026-08-20, V; practitioner pages — Lone Beacon 2025-06, Data Axle, Jon Loomer — give 2025-01-21 as the Ads Manager enforcement date, C). The Help Centre definition (paraphrased; the page body is JS-gated and could not be fetched verbatim) lists "investment services" among the covered products, and automated review means **a stock scanner should be treated as in scope** (C). Undeclared FPS ads are rejected; the cost of declaring is near zero because the levers it removes are ones Tapeline would not use.

| Lever | Under FPS (Marketing API doc, V, except where marked) |
|---|---|
| Age / gender | Fixed 18–65+; no gender. |
| Location | No exclusions; ≥15-mile / 25-km radius (US/CA); no ZIP. |
| Detailed targeting | No behaviour / demographic targeting; no interest or detailed-targeting exclusions. Interests from a previously approved list only — [unverified] whether "stock trading" survives on it (Help Centre, C). |
| Lookalikes / Special Ad Audiences | **Gone** — lookalikes unavailable; Special Ad Audiences sunset 2022-10-12 under the DOJ/HUD settlement. Any 2025–26 guide still recommending them is stale. |
| Saved audiences | Removed under `tune_for_category`. |
| Advantage detailed-targeting expansion | **Supported** (corrected from the draft, which said "removed"). |
| Custom audiences (pixel / CRM) | **Allowed** — inclusion, exclusion and expansion; account-specific, no cross-account sharing (`is_eligible_for_sac_campaigns`). |
| Advantage+ audience | Supported inside the constraints above. |

Net: broad US 18–65+, optional approved-list interests, your own custom audiences, Advantage+ audience. "Creative is the targeting" (Meta Andromeda, engineering.fb.com 2024-12-02, V). The learning-phase rule — ~50 optimisation events per ad set within 7 days (Meta Business Help, V; it predates Andromeda) — is a budget statement: at finance CPCs and ~2 % landing→trial that is **$3–9k/week**. Below it, delivery is broad reach with no manual levers to compensate.

**Meta's September 2025 sensitive-audience change** (V/C, [unverified at primary]) also blocks custom-audience segments that imply financial status. Not relevant to plain site-visitor audiences — noted so nobody "fixes" targeting later with an uploaded customer list labelled by tier.

**Verification / disclaimers.** Meta's Financial Services standard (transparency.meta.com, fetched 2026-08-20, V) says FPS advertisers "may be required" to verify identity and "demonstrate they are authorized by the relevant regulatory authorities", and that targeting some countries requires a licence. The exemptions are **specific** — brand ads for banks or insurers, news-article ads, loan-education ads, and "ads that only mention a financial service or product without the ability to obtain or connect with that product/service" — and a scanner with a signup CTA does not obviously sit in that last bucket. Whether Meta would ask a US-targeted, unregulated software tool for SEC/RIA proof is **[unverified]**. Meta imposes no risk-warning text on such ads; a voluntary "Informational only — descriptive scores, not recommendations" line is compatible and reinforces the house posture. Meta's review reads "picks / signals / win rate / beat the market / DM us" as investment promotion (the US clause prohibits "investment products or opportunities that suggest user interaction … via … direct messaging") — **descriptive copy is safer on Meta, not a handicap**; it also removes the hooks that make finance ads click.

**Australia is a separate regime.** Since Feb 2025, ads promoting financial products or services *to users in Australia* require an AFSL-or-exemption self-declaration and carry a public "Paid for by" label under the Online Scams Code; advertisers who self-declare as exempt get an **additional public label, "AFS licence: exemption claimed"**, and the ad is viewable in the Ad Library while active (Social Media Today, Mi3, AdNews, Mediaweek 2024-12, V/C). It keys on audience location, not advertiser domicile. **Therefore: US-only geo; exclude AU and every other verification-regime country (UK, TW, IN, SG, JP, IE, HK). Never include AU before the Holley Nethercote consult** — it would put a self-declared exemption claim on a public label.

**Domain-level data-sharing restrictions (since 2025-01-13, C — Twigeo 2025-04-08, Tealium, Aimerce).** Meta may categorise a *domain* as financial services. Financial domains **typically land in "core setup"**: custom parameters and URL paths stripped, which alone breaks URL-based audiences; the stricter tier that blocks Lead / CompleteRegistration / Purchase events "regardless of client- or server-side tracking" is primarily health/wellness but possible. If tapeline.io is restricted, Meta cannot optimise toward a trial or payment and the retargeting case collapses to "show ads to page-viewers, optimise for clicks". **Whether tapeline.io is flagged is [unverified]; Events Manager surfaces the status, and almost certainly only once a pixel is installed and sending events [unverified]** — so the read is not free (§8).

---

## 4. Economics — finance CPMs / CPLs vs the affordable CAC

**Benchmarks (2024–26).**

| Metric | Value | Source · grade · date |
|---|---|---|
| Finance & Insurance CPC, traffic objective | **$1.22** (CTR 0.98 %) | WordStream 2025, 554 US campaigns Apr 2024–Jun 2025 · B |
| Finance CPM | $28.44 median (range $9.59–42.05) → implied CPC ≈ $2.90 at ~1 % CTR (own arithmetic) | SuperAds aggregate Jul 2025–Jul 2026 · V [unverified] |
| Finance CPC, conversion-optimised / SAC | $2.90–3.77; practitioners quote $2–6 | ConversionStudio / Business of Apps / WOLF 2025–26 · C |
| F&I lead-objective CPL | **$38.09** (instant forms — *less* friction than a site signup) | WordStream 2024, 2,946 campaigns Feb 2023–Apr 2024 · B (F&I absent from the 2025 leads table) |
| All-industry CPL 2025 | $27.66; CVR 7.72 % (n=726 lead campaigns) | WordStream 2025 · B |
| Finance app CPI / CPA | ~$8.70 / $8–12 | Business of Apps, adaction, Splitmetrics 2025 · V [unverified] |
| Freemium install→paid; Business-category yr-1 LTV/payer | 1.5–2.7 % [unverified]; "$14.82" [unverified — not found in RevenueCat 2025, whose own summary puts Business median LTV > $25; the SaaS playbook E11 cites RevenueCat 2026 at $62.19 vs $10.69] | RevenueCat 2025 / Adapty 2026 · V |

**Affordable CAC.** Blended ARPU ~$12/mo × ~80 % gross margin [assumed — the data-licence COGS item is a P0 open question] × 10–20-month lifetime (5–10 % monthly churn) ⇒ margin LTV $96–192 ⇒ **max CAC $32–64 at LTV:CAC = 3**; $29–58 at a 3–6-month bootstrapper payback (Walling, C). Cohen's rule (affordable CPC ≈ ARPA ÷ 25 ≈ **$0.50**; mtlynch.io notes, C *(older)*) kills it a step earlier: finance CPCs are 2.5–7× that before any conversion rate is assumed. (`PAID_ADS_PATHWAY.md` and playbook A8 already carry these ceilings.)

**Cost per trial and per payer.**

| Scenario | CPC | Landing→trial (cold social) | $/trial | Trial→paid | $/payer | vs ~$40 |
|---|---|---|---|---|---|---|
| Generous (ChartMogul top band) | $1.22 | 3 % | $41 | 25 % | **$164** | ~4× |
| Best-case p75 | $1.22 | 3 % | $41 | 15 % | **$271** | ~7× |
| Central | $2.90 | 2 % | $145 | 10 % | **$1,450** | ~36× |
| ChartMogul median via CPL | CPL $38 → | lead form | $40–100 | 4–6 % | **$650–2,500** | 16–60× |
| Worst | $3.77 | 1 % | $377 | 8 % | **$4,713** | ~118× |

ChartMogul × Poyar (Jan 2026, n=200, **B2B**, growthunhinged.com/p/free-to-paid-conversion-report, B) is bimodal for no-card trials — 20 % below 2.5 %, 30 % at 2.5–7.5 %, 23 % above 25 % — so the optimistic reader gets the top row, and it still does not close. To reach $40/payer at the *best* CPC, landing→trial × trial→paid must be ≥ 3 % (e.g. 15 % × 20 %) — warm-audience / brand-search numbers, not cold social. Tapeline's own measured paid-search landing→trial is 0 / ~500 clicks at a below-benchmark CPC (`PAID_MARKETING_PLAYBOOK.md` §2). **Only a price change, a churn change or a different channel closes a 4–40× gap.** The category telemetry says the same from the app side: the products that work on Meta have 3–10× Tapeline's ARPU, are annual-prepaid, or carry a second revenue line.

The "learn on trials" budget does not work either: the playbook's A$19–20/day buys ~3–6 finance clicks/day on Meta → 0.5–1 trial/week → nothing readable in 90 days, and FPS forbids the audience narrowing that would be the only way to lift landing→trial on cold traffic.

---

## 5. Retargeting — deliverable, tiny, unmeasurable

- **Permitted under FPS:** website custom audiences and customer lists; no age/gender narrowing, no lookalike expansion, no cross-account sharing (V; C).
- **Deliverability — sized with the repo's own number.** Meta will not deliver below roughly **100 matched** people; size estimates are hidden and delivery unstable below **~1,000** (Zenweb, Stackmatix, MHI Growth 2025–26, C; exact threshold [unverified] — Meta does not publish it). Matched fraction of raw visitors is typically 30–70 % (Safari ITP, in-app browsers, ad-blockers — C). So **1,000 matched in a 180-day window needs ~1.4–3.3k uniques over six months ≈ 250–600 uniques/month**; in a 30-day window it needs ~1.4–3.3k uniques *that month*. At the playbook's ~50 visitors/week (§6 row 4): 50 × 26 ≈ 1,300 uniques × 30–70 % ≈ **~400–900 matched in a 180-day audience** — above the hard floor, at or under the practical one. The customer list (20 users + ~5 trialists) is far below the hard floor on its own. **Honest statement: deliverable but small, unstable, and unmeasurable — not "undeliverable".** (The draft's 30-day / 180-day arithmetic was inconsistent; corrected here.)
- **Causal evidence:** +14.6 % *return visits* within four weeks, a third of the week-1 effect on day 1, decaying fast, no purchase lift reported (Sahni et al. 2019, A — a home-improvement e-commerce seller); dynamic retargeting underperforms generic until the consumer has narrowed preferences (Lambrecht & Tucker, *JMR* 2013, A *(older)*); a *purchase* lift needs millions of users — median 95 % CI on ROI > 100 pp wide (Lewis & Rao 2015, A *(older)*); Uber cut ~$100M of app-install / retargeting spend found to be largely fraud-inflated and saw no change (Frisch, D).
- **Cost if run:** a several-hundred-person audience saturates in days; realistic ceiling A$2–5/day — cheap, but "cheap, tiny and unmeasurable" is noise, not a bargain. The same people get an email for $0.
- **Measurement design, if ever built:** redundant pixel + Conversions API; `StartTrial` server-sent at signup (event_id de-duplicated with the browser event; hashed email + fbp/fbc/IP/UA stored on the User row — the same pattern as the existing `signup_gclid` column used for the Google offline-conversion upload); `Subscribe` server-sent from the Stripe webhook (idempotent via `stripe_webhook_events`). **The 14-day trial puts `Subscribe` outside the 7-day-click window by construction**, so payers are only ever counted via the stored `fbclid` → User → Stripe join, never from Ads Manager.

**Retargeting verdict:** technically allowed, deliverable to a few hundred people, unmeasurable for purchases at any traffic Tapeline will have this year. Once §7 holds it is a nudge on an existing funnel (single-digit incremental payers/month) — never a growth engine.

---

## 6. Who runs on Meta in this vertical, and what happens

**Ad Library sweep (US, active, 2026-08-20 — direct observation; counts are Meta's text-match counts, not proof of spend):**

| Query | Active US ads | Who | Read |
|---|---|---|---|
| "stock screener" | ~12 | Benzinga Edge (6+ static variants), Akyla (3 static, "Low impression count" six weeks after launch), FITools, Musaffa | Near-empty category |
| trendspider / "simply wall st" / tipranks | 0 text matches | — | Scanner incumbents do not compete on paid Meta |
| "swing trading" | ~520 | T3 Live, Momentum, alert rooms, LatAm education | Education + alert rooms, heavy guru video — **the Meta audience for this phrase is pre-selected for prescriptive offers** |
| "trade ideas" | ~170 | "95.5%+ Win", "Oracle", Sykes | Prescriptive hype |
| "seeking alpha" / "motley fool" | ~25 / ~83 | Content-led static; MF testing a "Judge Us by the Scorecard" video | The one hook near Tapeline's asset — and MF is the record-marketer whose record is the standing controversy |
| "rocket money" | ~140 | 77 % video 24–60 s, creator co-brands, install CTA | The only low-ARPU finance app visibly scaling — on a negotiation revenue share, not the sub |

**Case reading (C/D):** Akyla — the direct analogue ($20/mo screener, descriptive static creative) — had not left "Low impression count" six weeks in. Benzinga Edge ("5-factor stock ranking system … $10.75/month" — names factors, no weights: the closest copy analogue) runs on blended media/data revenue. Budgeting apps that work on Meta are annual-prepaid. Trading-education funnels spend the most because AOV is 10–100× Tapeline's and copy is prescriptive. Only "around 10 %" of ~100 subscription apps one Adapty author worked with reached 2–3× ROAS on Meta (V/C). **This extends the playbook's "0 of 8 comparable tools grew on paid search early" to paid social.**

**Creative requirement vs a solo founder (V/C):** the 2025–26 playbook wants ~20 new creatives/week, full refresh every ~2 weeks (fatigue at 2–3 weeks — Adapty, Billo), UGC rising, judged on hook/hold rate. A founder with no on-camera presence can sustain 6–12 static / screen-recorded assets a week at ~8–12 h/week — enough for a learning test if the gate is ever met, not enough to scale (20+/week with UGC ≈ 20–30 h/week or $200–500/week for creators, which alone exceeds the ad budget at that stage). Founder-to-camera is a presence investment that pays more on the organic channel (YouTube / Reddit / AI-assistant citation) than on paid.

**Free substitute for spend:** a 15-minute monthly Ad Library check — which Benzinga Edge / Akyla variants survive 30+ days — is the creative intelligence a test would have bought.

---

## 7. When Meta turns on — three conditions, then prerequisites

All of these **in addition to** the five conditions of the Google ads gate (`PAID_MARKETING_PLAYBOOK.md` §4), which apply to Meta unchanged. The draft listed eight conditions, which read as "never"; three carry the decision, the rest are things to build afterwards.

1. **Organic trial→paid is a measured number** on ≥30 organic/AEO trials, with ≥10 unaffiliated payers retained ≥60 days (= Google gate condition 1; "0 of 5" does not qualify), and LTV recomputed from that cohort's churn and the settled data-licence COGS.
2. **Deliverability, read in Events Manager:** ≥1,000 *matched* website visitors in a 180-day window (≈ 250–600 uniques/month sustained six months) **and** tapeline.io confirmed *not* under the financial-services data-sharing restriction (URL audiences allowed; Lead / CompleteRegistration / Purchase accepted).
3. **A message already proven organically** — a video, comparison page, Reddit post or email subject at ≥15 % click→trial on the exact landing page the ad would use (= Google gate conditions 2 and 4). §9 is how that gets produced.

**Then build, not before:** CAPI with the fbclid→Stripe join (§5); a card-on-trial or $1-trial landing-page variant for paid traffic only (opt-out trials convert 25–35 % vs 4–6 % opt-in — ChartMogul 2026, B; the SaaS playbook already schedules this behind a flag, row D10); US-only geo with AU and all verification-regime countries excluded, FPS declared, copy + landing page passed through `scripts/lint-copy-compliance.mjs` and the house rules; a budget label that is honest — either ~50 events/ad set/week (performance marketing) or "frequency-capped retargeting at A$5–10/day, brand defence" — never the second dressed as the first.

**Prospecting** turns on only if, on top of 1–3, ARPU/LTV moves materially (annual mix, Premium mix, Trader $59 / Team $149 SKUs) *and* organic conversion is measured at ≥ ~5 % landing→trial and ≥ ~20 % trial→paid. Until then, if 1–3 are ever true, the marginal dollar still has a better-ranked use (AEO/content — the only channel that has produced engaged users).

**Relationship to the standing Google gate — stated explicitly.** Nothing here loosens `PAID_MARKETING_PLAYBOOK.md` §4; conditions 1 and 3 restate it, condition 2 adds Meta-specific mechanics. **One place this document is stricter than the standing exception** ("brand terms + retargeting, capped at A$5/day, always allowed"): on Meta that A$5/day reaches a few hundred people at best, may be structurally degraded by a domain restriction, and cannot be measured — so on Meta the two A$0 reads in condition 2 come *before* even standing-exception spend, and the standing exception is read as applying to Meta retargeting only once those reads are in hand. The playbook's one-liner ("Retargeting-only if ever") stands; this is its long form.

---

## 8. Why there is no "cheap diagnostic campaign" in this document

The draft ended with an A$150 retargeting diagnostic. It is removed, deliberately:

- The "A$0 pre-checks" are not A$0. Reading the domain-restriction status and the matched-audience size needs a Business Manager (FPS advertisers are routinely asked to verify business/domain — V/C), a Meta pixel on tapeline.io, and for anything beyond page-views a CAPI build with hashed identifiers on the User row — backend engineering, which the SaaS playbook caps behind ≥6 interviews (§2.1) — plus a privacy-policy / consent update, because a third-party advertising tracker on a finance site touches CCPA and the AU Privacy Act. Realistic: 12–20 founder-hours and ~0.5–1 engineering-day before the first ad review, and the first FPS review cycle is often a rejection (C).
- What it would have proved (domain status, audience size, CPM) is recorded instead as **gate-time facts**: the SaaS playbook's item 26 (day 61–90 ads-gate review) notes the two Events Manager reads as facts to record *if and when* a pixel exists for other reasons. Expected verdict: unchanged.
- What it could not have proved — anything about trial→paid, incremental signups or ROI — is the only thing that matters.

A "no" document should not contain a campaign. The creatives it carried are in §9, where they earn their keep.

---

## 9. The positive recommendation — run the message test organically (A$0)

Gate condition 3 above (and Google gate condition 4) is "a message proven organically". The five copy pairs below were written for Meta and lint-clean (`node scripts/lint-copy-compliance.mjs`: 0 findings on 2026-08-20), then corrected for factual overclaims the linter cannot see. They are now a **copy bank for organic placement**: Reddit and X posts, email subject lines to the existing list, comparison-page H1s, the YouTube video titles in `PAID_MARKETING_PLAYBOOK.md` §6.2. Count click→trial per message for 60 days; the winner becomes the ad copy if the gate is ever met and the hero copy regardless.

House rules: descriptive only — never buy / sell / recommend / beat / guaranteed / urgency; never the exact weights; no win-rate numbers; the published record is a **character claim** ("we publish it, including the misses"), not a benefit headline — `SAAS_PLAYBOOK_ADDENDUM_DEEP_LITERATURE.md` §6 has the evidence that audited records do not sell and that the one brand that marketed its record is the standing controversy. Tier facts checked against `tier.py` on `origin/main` 2026-08-20: Free = **top-10 rows, live** (CLAUDE.md's "top 20 / 24-hour delayed" is stale), Free watchlist = 5 tickers (the 2026-08-02 removal was reversed 2026-08-19, #525), email alerts = Pro+, anonymous/Free scorecard picks delayed 7 days with summary stats live.

1. "Most scanners hand you 500 filters and a blank stare. Tapeline scores every name in its universe on six factors — trend, relative strength, fundamentals, smart money, macro, momentum — and gives you one number and one sentence per ticker."
   Headline: "One number. One sentence."
2. "Every evening, the same question: what changed? Tapeline keeps a live 0–100 composite on its US universe and shows what moved and why. The Free tier shows the top of the ranked list, live, no card."
   Headline: "See what the scanner read — free."
3. "We publish the scorecard because a scanner should be judged on what it said before, not after — including the misses. Summary stats are public and live; per-day entries are public on a 7-day delay, live for subscribers."
   Headline: "We publish the record, misses included." *(Whether summary statistics such as hit rate may appear in acquisition copy at all is lawyer-brief item 5(e); until answered, this line names the record's existence, not a number. The draft's "Judge the scanner by its scorecard" is dropped — it was Motley Fool's headline.)*
4. "Swing trading around a day job means about twenty minutes a night. Tapeline is built for that window: a ranked list, a one-line read on each name, and a watchlist so you decide what to look at before you open the chart."
   Headline: "Built for the 20-minute trader." *(No alert promise — alerts are Pro+ and "alerts" reads as investment promotion in cold copy.)*
5. "Tapeline reads SEC Form 4 insider purchases and Congressional disclosures into one smart-money factor, alongside trend, relative strength, fundamentals, macro and momentum. Descriptive labels, not instructions, and a methodology page that explains what each factor measures."
   Headline: "Six factors. Plain-English labels. Public methodology." *(Band names are deliberately not listed in cold copy — to a stranger the band name is the hook and reads as a strength-of-recommendation scale; a lawyer-brief line, not a house-rule breach.)*

Optional footer on every asset: "Informational only. Descriptive scores, not recommendations." Re-run the linter over any edit.

---

## 10. What NOT to do

- **No Meta prospecting** at current ARPU, conversion data and traffic — three independent blockers, any one sufficient.
- **No interest / lookalike / demographic finance targeting** — structurally gone under FPS; that playbook no longer exists for anyone.
- **No ad set that includes Australia** (or UK/TW/IN/SG/JP/IE/HK) before the Holley Nethercote consult — it triggers AU verification and a public "AFS licence: exemption claimed" label.
- **No pixel / CAPI install "just to read the numbers"** — it is engineering behind the interview gate plus a privacy-policy change; do it when the product needs it, record the two reads then.
- **No lead-gen forms or creative promising picks, alerts, signals, win rates or urgency**; no DM invitations; no band names as hooks in cold copy.
- **No reading Ads Manager conversions as truth** — payers only from the fbclid→Stripe join; 7-day click only; never 1-day view.
- **No sending paid traffic to the no-card trial** — paid LPs get the card / $1-trial variant when the gate is met; organic keeps no-card.
- **No spending the "learning" budget on Meta instead of interviews** — A$300–600/month and ~8 h/week buy 0–1 payers and zero trial→paid information; the same hours on founder interviews, AEO answers and founder video cost A$0, compound, and produce the proven message a future paid test would need.
- **No reopening the Google gate via Meta** — same five conditions, plus §7.

---

## Sources (grade · date)

Meta policy: developers.facebook.com Marketing API — Special Ad Category (primary for all FPS targeting rules; the transparency.meta.com "discriminatory practices" path 404'd 2026-08-20, so it is not cited), Conversions API, event de-duplication (V, fetched 2026-08-20) · transparency.meta.com Advertising Standards → Financial Services (V, fetched) · Meta Business Help, learning phase (V) · engineering.fb.com Andromeda 2024-12-02 (V) · justice.gov DOJ–Meta settlement 2022-06 / Special Ad Audiences sunset 2022-10-12 (A) · Social Media Today, Mi3, AdNews, Mediaweek 2024-12-02 on AU verification + labels (V/C) · Lone Beacon 2025-06-11; Data Axle; Jon Loomer; WOLF Financial 2025; ROASPIG 2026-01 (C) · Twigeo 2025-04-08; Tealium; Aimerce on domain restrictions (C) · Zenweb; Stackmatix; MHI Growth on audience floors (C).
Benchmarks: WordStream 2025 wordstream.com/blog/facebook-ads-benchmarks-2025 (B) · WordStream 2024 (B) · ChartMogul × Poyar Jan 2026 growthunhinged.com/p/free-to-paid-conversion-report; Userpilot relay (B, B2B n=200) · SuperAds (V [unverified]) · RevenueCat 2025 / Adapty 2026 (V; LTV figure [unverified]) · Business of Apps, adaction, Splitmetrics (V [unverified]).
Causal literature: Sahni, Narayanan & Kalyanam *JMR* 2019 doi 10.1177/0022243718813987 (A) · Lambrecht & Tucker *JMR* 2013 (A, older) · Gordon et al. *Mktg Sci* 2019 (A); Gordon, Moakler & Zettelmeyer *Mktg Sci* 2023 arXiv 2201.07055 (A/B) · Lewis & Rao *QJE* 2015 (A, older) · Blake, Nosko & Tadelis *Econometrica* 2015 (A, older) · Frisch on Uber (D).
Creative / vertical: Meta Ad Library US active 2026-08-20 (direct observation) · Motion, Billo, Adapty, Liftoff 2025–26 (V) · Rocket Money / TINA.org (D).
Bootstrapper rules: Cohen 2013 via mtlynch.io (C) · Walling *SaaS Playbook* (C) · Skok (C).
Internal (origin/main @ e214348, 2026-08-20): `docs/PAID_MARKETING_PLAYBOOK.md` §2, §4, §6, §7 · `docs/PAID_ADS_PATHWAY.md` · `docs/SAAS_OPTIMISATION_PLAYBOOK.md` §2.1, §6, A6, A8, D10, item 26 · `docs/COMPETITOR_GAP_ANALYSIS.md` · `backend/app/services/tier.py` · `backend/app/models/user.py` (`signup_gclid`) · `scripts/lint-copy-compliance.mjs` · `docs/SAAS_PLAYBOOK_ADDENDUM_DEEP_LITERATURE.md` §6.
Still [unverified], none changing the direction: Help Centre FPS definition verbatim; approved-interest list; exact audience-size threshold; whether tapeline.io is domain-restricted (would make this stricter); US verification for an unregulated tool; 80 % gross margin; SuperAds / RevenueCat / CPI figures.

*Compliance statement: every Tapeline copy line in this document is descriptive-only (no buy / sell / recommend / beat / guaranteed / urgency, no exact scoring weights, no win-rate numbers), no money was spent, no account created and no form submitted in producing it, and nothing here is legal advice.*
