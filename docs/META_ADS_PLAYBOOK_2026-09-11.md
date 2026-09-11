# Tapeline Meta Ads: Operating Playbook (2026-09-11)

Scope: the US-only Financial Products & Services (FPS) campaign at A$25/day. This builds on `docs/META_SAAS_ADS_PLAYBOOK.md`, `docs/META_ADS_DECISION.md` and `docs/PAID_ACQUISITION_DEEP_DIVE_2026-09.md`. Where this document disagrees with them, it says so.

**Working numbers.**
- A$25/day at A$103 CPM buys about 243 impressions a day, or about 1,700 a week.
- If delivery were perfect, the weekly ceiling would be about 40 clicks, 21 landing-page views (LPVs), 4 signups and 2.8 cards ([Meta](https://www.facebook.com/business/ads/performance-marketing)).
- What actually happens is about 1.2 optimisation events a week. Meta needs about 50 a week for an ad set to leave the learning phase.

---

## 1. The short version

- **Tapeline can't buy its way out of the learning phase.** Big accounts set each ad set's budget high enough to get about 50 events a week ([Meta](https://www.facebook.com/business/help/112167992830700)). For Tapeline that means about A$293/day optimising on signups, or about A$443/day on cards. Meta says Learning Limited "isn't a penalty", but it also says the budget isn't being spent effectively ([Meta](https://www.facebook.com/business/help/269269737396981)). Accept it as a budget fact. Don't restructure the account to get rid of the label.
- **Fewer ads, with more variety inside each ad, does transfer.** Meta recommends fewer ads per ad set, up to ten assets per ad, and multiple text options ([Meta](https://www.facebook.com/business/help/2720085414702598)).
- **Optimising on a day-0 event and reading revenue from your own database also transfers.** Meta's longest click window is 7 days ([Meta](https://www.facebook.com/business/help/2198119873776795)). A 30-day trial's first charge will never show up in Ads Manager.
- **Creative volume and the statistical tools don't transfer.**
  - Enterprise accounts launch 18.8 creatives a week ([Motion](https://motionapp.com/library/research/creative-benchmarks-2026/testing-volume-by-tier)).
  - Conversion Lift needs US$5,000 of spend and 500 conversions ([Meta](https://www.facebook.com/business/help/221353413010930)).
  - Value optimisation needs about 100 events per 14 days ([Birch / Meta](https://bir.ch/blog/meta-value-optimization)).
  - Tapeline is 40–100× short on each.
- **A creative test only works if the ads are isolated.** The August burst failed as a test because ad B took 91.1% of impressions and 94.6% of spend (`PAID_ACQUISITION_DEEP_DIVE_2026-09.md:156`). At this volume, compare ads on attention metrics (hook rate, hold rate, CTR), not on cards.

---

## 2. Account structure to build now

| Setting | Do this | Evidence |
|---|---|---|
| Objective | Sales, website destination (as already built: `META_BURST_BUILD.md:73,154`) | The flexible ad format needs Sales with a Website destination ([Meta](https://www.facebook.com/business/help/2720085414702598)) |
| Special Ad Category | FPS. Set the SAC **Countries** field to United States and **uncheck Australia in both places it appears** | FPS has been required for US audiences since 21 Jan 2025 ([Meta](https://www.facebook.com/business/help/2220749868045706)). The field pre-fills Australia from the ad account, which puts the ads under Australia's rules: an AFSL number or an on-ad "exemption claimed" label ([Mediaweek](https://www.mediaweek.com.au/meta-rolls-out-verification-requirements-for-financial-ads/); `META_BURST_BUILD.md` §4b). FPS may not support location exclusion, so excluding Australia in the ad-set geo is not a substitute. |
| Audience | United States only, nothing else | Under FPS, age, gender, ZIP, exclusions, lookalikes and saved audiences are limited or unavailable ([Meta](https://www.facebook.com/business/help/2220749868045706)). If Advantage+ audience is offered, leave it on. Meta's API docs say FPS access to it is still rolling out ([Meta](https://www.facebook.com/business/help/906206294602874)). |
| Ad sets | 1 | Combining ad sets combines their learning ([Meta](https://www.facebook.com/business/help/269269737396981)) |
| Ads | At most 2–3, one per concept. Each should be a flexible or multi-asset ad with per-placement ratios | Too many ads means each one delivers less often ([Meta](https://www.facebook.com/business/help/2720085414702598)). This is tighter than the playbook's 3–5; treat 3 as the ceiling. |
| Budget | A$25/day. Campaign budget vs ad-set budget doesn't matter with one ad set | ([Meta](https://www.facebook.com/business/help/1388266028979935)) |
| Budget changes | Steps of 20% or less, at least 72 hours apart, or up to the headroom figure Ads Manager shows | This is practitioner practice. Meta's docs don't back a specific step size ([Meta](https://www.facebook.com/business/help/316478108955072)) |
| Bid strategy | Highest volume. No cost-per-result goal and no bid cap | A cost goal works best at 50–100+ conversions a week ([Meta](https://www.facebook.com/business/help/272336376749096)) |
| Placements | Advantage+ placements | Account-level placement controls don't apply to FPS ads. Excluding Audience Network therefore has to be done inside the campaign, and that switches Advantage+ placements off ([Meta](https://www.facebook.com/business/help/1362234537597370)). Accept that while optimising on a conversion event. If you ever optimise on LPVs or clicks, excluding Audience Network becomes mandatory (see below). |
| Advantage+ creative | Turn all 31 enhancements off. Include the non-AI ones that add content: "Add standard label", "Add details to ad layout" and "Profile end card". Turn off AI video subtitles and burn in your own captions | Meta may adjust the uploaded media and text ([Meta](https://www.facebook.com/business/help/297506218282224)) |
| Attribution | Standard: 7-day click, 1-day view. Not incremental | The incremental model can't be changed after publishing, allows no bid controls, and may not be available under FPS ([Meta](https://www.facebook.com/business/help/644554008179419)) |
| Advantage+ status | Check the indicator in Ads Manager. Don't plan around Meta's 9% or 20% improvement claims | Meta says Special Ad Category campaigns may not get every Advantage+ feature ([Meta](https://www.facebook.com/business/help/906206294602874); [Meta](https://www.facebook.com/business/help/1362234537597370)) |

### The optimisation event: the rare-conversion problem

No event reaches 50 a week at A$25/day except link clicks (about A$29/day needed). LPVs would need about A$60/day ([Meta](https://www.facebook.com/business/help/112167992830700)). Meta's documented fix is to switch to a more frequent event ([Meta](https://www.facebook.com/business/help/269269737396981)). But Meta pitches LPV optimisation mainly at accounts that have no lower-funnel events set up ([Meta](https://www.facebook.com/business/help/203012060587398)), and Tapeline has them. In one practitioner test, 96% of LPVs and 99% of link clicks came from Audience Network ([Loomer, 2023, possibly stale](https://www.jonloomer.com/split-test-which-optimization-leads-to-the-most-high-quality-traffic/)). Subscription consultants pick the event that best predicts revenue and don't move up the funnel just to hit the threshold. As Marcus Burke puts it: "I would rather feed 20 relevant events a week than 100 irrelevant ones" ([Burke](https://marcuscnslt.substack.com/p/revenuecat-meta-ads-masterclass)).

**Decision:**
1. **Keep CompleteRegistration for the current flight.** Changing the optimisation event is a significant edit that resets learning ([Meta](https://www.facebook.com/business/help/316478108955072)).
2. **At the next flight boundary, switch to StartTrial, but only if both of these are done first:**
   - (a) The CAPI fix in §4 has shipped. StartTrial currently goes out missing `client_user_agent`, which Meta requires for website events.
   - (b) Events Manager shows StartTrial isn't restricted under the dataset's data category.

   Every card so far was put down within about 2 minutes of signup, so both events happen on day 0 and StartTrial is closer to money. The volume cost ("67% of signups add a card") rests on n=3. A pause of 7 days or more resets learning anyway, so switching between flights costs little extra ([Meta](https://www.facebook.com/business/help/269269737396981)).
3. **Never optimise on LPVs or link clicks.**
4. **Don't build a custom "EngagedVisit" event yet.** Custom events are blocked until Meta reviews them when the data source is restricted ([Meta](https://www.facebook.com/business/help/511197658391698)).

This resolves a repo conflict: the docstring at `meta_capi.py:50-53` says StartTrial, while the live campaign docs say CompleteRegistration.

---

## 3. Creative: what to launch and how to test it

**Concept order: D, then E, then B.**
- **D (swing traders).** Search Console's only non-brand organic clicks are swing-trading queries, so D has an audience signal behind it. Hooks don't transfer across verticals, Finance included ([Motion](https://motionapp.com/library/research/creative-benchmarks-2026/testing-volume-by-tier)), so D is unproven on Meta.
- **E (published record).** This is the concept with the most compliance risk (§6). Show that a public, dated record exists. Never quote its numbers.
- **B (the money question).** It is the only concept with cards, but 2 cards from 3 signups is not evidence of anything. Motion's data puts offer hooks at the top for spend concentration. Motion defines a "winner" by spend, not conversions, so that is only weak support ([Motion](https://motionapp.com/library/research/creative-benchmarks-2026/testing-volume-by-tier)). **Before B runs again, confirm the live copy says 30 days** (memory records that it still said 14).

**Fair test: solo windows, not a shared budget.**
- Run each concept as the only active ad for about 10 days. That is about 2,400 impressions and A$250 per concept.
- At 2,400 impressions, a hook rate around 20% has a standard error of about 0.82 points. A 5-point gap between two ads is therefore about 4.3 standard errors, which is clearly real. CTR gaps under about 0.9 points are noise ([Peachblue](https://peachblue.io/blog/hook-rate-hold-rate-thumbstop)).
- Each window will produce only a handful of signups. Record them, but don't rank concepts on them.
- **Caveat:** running concepts one after another mixes the creative effect with timing (market news, day of week).

**Fallback: Meta's Creative Test tool.** Use B as the source ad, with copies carrying the D and E creative. B stays in normal delivery. The tool needs Highest volume bidding, and Meta suggests spending no more than 20% of budget on the test: about A$5/day, or about 48 impressions a day. That gives about 700 impressions per ad over 30 days. Only hook-rate gaps of about 4.3 points or more are readable, and CTR is unreadable ([Meta](https://www.facebook.com/business/help/1423851372208214)). Use it only if Ads Manager offers it under FPS.

After the windows, keep the best 1–2 concepts running and let cards accumulate for at least 30 days before reading cost per card.

**Ratios and safe zones.** Use placement asset customisation ([Meta](https://www.facebook.com/business/help/2720085414702598)): 9:16 for Stories and Reels, 4:5 for Feeds, 1:1 for the rest.

For Reels ads that carry a disclaimer, Meta says to keep the bottom 40% free of text, logos and key elements ([Meta](https://www.facebook.com/business/help/980593475366490)). The committed verticals break this rule:
- `make_verticals.ps1` draws the disclaimers at y=1360 and y=1392, and tapeline.io at y=1444. All three are below the 40% line at y=1152.
- B's "Cancel in one click." straddles that line.
- The 2026-09-06 re-render lives in a scratchpad zip, not the repo, and its footer is still inside the band.

**Re-render every 9:16 file before it goes live.** The 4:5 and 1:1 cuts also need clear space at the bottom and sides.

**Silent vs voice-over.** Reels play with sound on by default ([Meta](https://www.facebook.com/business/help/980593475366490)). Meta's figure that music plus voice-over scores 15 points better is 2023 data, so possibly stale. Use the voice-over version with burned-in captions as the single audio treatment per concept, unless a flexible ad can hold both versions (check in the UI). No verified evidence covers sound in Feed placements.

---

## 4. Measurement

**One-time fixes before the next flight:**
1. **Check the dataset's data category.** In Events Manager, open the dataset's data source category and Diagnostics. If it is "Financial service", Meta may apply Core Setup, block specific events, or block all events ([Meta](https://www.facebook.com/business/help/511197658391698)). Meta notifies by email, so check tapeline.inbox@gmail.com; Claude can't read that mailbox.
2. **Fix the CAPI payload.** Add `client_user_agent` and an unhashed `client_ip_address` to the StartTrial and Purchase server events ([Meta](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/customer-information-parameters)). Neither field is sent anywhere in `backend/app`.
3. **Plan for Core Setup.** If it applies, URL paths are cut to the domain, but tier and billing period survive because they are sent as standard parameters. Any "qualified signup" proxy must be a neutrally named standard event sent from the server. No custom conversion may suggest financial status; Meta has flagged these since September 2025, and a flagged conversion can't be changed after publishing ([Meta](https://www.facebook.com/business/help/124742407297678)).
4. **Keep events on time.** Send them within an hour. A request containing any event older than 7 days is rejected in full ([Meta](https://www.facebook.com/business/help/801591810609156)). This only matters if a retry or backfill job is ever added.

**Daily (5 minutes, no decisions):** delivery and rejection status; spend pacing; every database signup or card has a matching Meta event (the pre-2026-09-02 outage was silent); Events Manager diagnostics. Don't act on data less than 48–72 hours old ([admanage](https://admanage.ai/blog/when-to-kill-a-facebook-ad)).

**Weekly (one sitting, one batched edit):**
- Per ad: impressions, CPM, hook rate (3-second plays ÷ impressions), hold rate (ThruPlays ÷ 3-second plays), CTR, LPVs, signups and cards from the database, cost per signup and per card ([Peachblue](https://peachblue.io/blog/hook-rate-hold-rate-thumbstop)).
- Event Match Quality: scored 0–10 on the last 48 hours, noisy at this volume ([Meta](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/customer-information-parameters)).

**30-day cohort (database and Stripe, never Ads Manager):** trial-to-paid, scans run, cancellations. The two live trials are 14-day trials that charge on 12 and 14 Sep. Those charges fall outside the 7-day click window ([Meta](https://www.facebook.com/business/help/2198119873776795)).

**Thresholds:**

| Call | Rule |
|---|---|
| **Kill** | After at least 2,400 impressions: hook rate 5+ points below the best sibling, or CTR 0.9+ points below. Or: zero signups after about A$123 of spend, which is 3× the August cost per signup (A$123.53 ÷ 3) ([admanage](https://admanage.ai/blog/when-to-kill-a-facebook-ad)). |
| **Hold** | The default state. Anything within those gaps. |
| **Scale** | Never on Meta-reported conversions. Scale only when a 30-day database cohort shows cards turning into paid customers at a cost under Tapeline's CAC ceiling (that ceiling is not in this brief). Then use steps of 20% or less. |

Meta's "Creative fatigue" status is unavailable when an ad set has more than one ad ([Meta](https://www.facebook.com/business/help/1346816142327858)). Drop the 18–28% hook-rate floor and the "<18% = first-frame failure" rule in `PAID_ADS_METRICS_BIBLE.md`; compare Tapeline's ads with each other instead.

---

## 5. What to pause and why

- **Ads A and C.** They got 51 and 60 impressions, so they were never really tested. They only dilute delivery ([Meta](https://www.facebook.com/business/help/2720085414702598)).
- **Any live ad B creative that says "14-day".** New trials are 30 days, so that copy is now false. Replacing it is a significant edit; accept the reset. Otherwise, keep a proven ad running when you add new ones ([Meta](https://www.facebook.com/business/help/1346816142327858)).
- **Every committed 9:16 file**, until it is re-rendered to clear the bottom 40%.
- **Advantage+ creative enhancements** (§2).
- **Mid-week edits.** Make one batched change a week. Meta's docs say adding an ad resets learning; practitioners say it often doesn't. Plan as if it will ([Meta](https://www.facebook.com/business/help/316478108955072)).

---

## 6. Compliance guardrails

- **Descriptive only.** Never buy, sell, should or recommend. No performance statistics, no vs-SPY figures in headlines, and no claims about the reader's finances. This applies to every text × media pairing inside a flexible ad.
- **No live named ticker shown landing on HIGH CONVICTION** in screen recordings. Show the mechanism, not a pick (`META_LIVE_CAMPAIGN_ADDENDUM.md`).
- **Subscription policy.** Ads must disclose pricing and recurring billing. Any page that collects personal details must clearly show the price and billing interval, say how to cancel, and use an unticked opt-in checkbox. Fine print or a separate link does not count ([Meta](https://transparency.meta.com/policies/ad-standards/content-specific-restrictions/subscription-services)). /signup collects an email, so it is in scope. Stripe's terms-of-service tickbox comes after signup and may not satisfy the rule there. The safe reading is to put the after-trial price and interval in the ad itself: "$19.99/mo from day 30, or $199/yr, charged at trial end."
- **Card honesty.** "$0 today" must always come with "card required, first charge at trial end". Never write "30-day trial, no credit card".
- **No message destinations and no "DM us"** ([Meta](https://transparency.meta.com/policies/ad-standards/restricted-goods-services/financial-services/)).
- **One standing disclaimer line.** Reuse an existing one ("Informational only. Descriptive scores, not recommendations."). A disclaimer doesn't fix copy that is otherwise non-compliant (`COMPLIANCE_COPY_RULES.md` §9). Put "as of <date>" on any comparison ([Public/Yahoo](https://finance.yahoo.com/news/public-launches-brand-campaign-130000976.html)).
- **Complete Meta Business Verification.** Meta is expanding verification, with emphasis on financial-investment ads ([Meta](https://about.fb.com/news/2026/03/meta-launches-new-anti-scam-tools-deploys-ai-technology-to-fight-scammers-and-protect-people/)). It verifies identity only; it is not regulator authorisation.
- **No creator or partnership ads.** Meta's branded-content rules restrict financial products. FINRA fined M1 Finance US$850K for paid influencer posts it didn't review or keep ([FINRA](https://www.finra.org/media-center/newsreleases/2024/finra-fines-m1-finance-850000-violations-regarding-use-social-media); [Marketing Dive](https://www.marketingdive.com/news/meta-streamlines-brands-creator-partnerships-with-ai-powered-updates/807629/)). A founder-to-camera ad from Tapeline's own Page is not branded content, so it is fine.

---

## 7. What big advertisers do that Tapeline should not copy

| Practice | Why not |
|---|---|
| Budgeting each ad set out of learning | Needs A$293–443/day ([Meta](https://www.facebook.com/business/help/112167992830700)) |
| Large test budgets (Foxwell: US$10–15K over two weeks) | 44–66× Tapeline's budget ([Meta](https://www.facebook.com/business/help/1388266028979935)) |
| High creative volume: 18.8 new ads a week, 15–50 new ads a month | A$750/month is below Motion's US$500 winner floor ([Motion](https://motionapp.com/library/research/creative-benchmarks-2026/testing-volume-by-tier)). Andromeda and GEM are built for that scale ([Meta Eng](https://engineering.fb.com/2024/12/02/production-engineering/meta-andromeda-advantage-automation-next-gen-personalized-ads-retrieval-engine/)) |
| Chasing Advantage+ uplift | 58% of brands did better on manual campaigns in Haus's 640 tests ([Haus](https://www.haus.io/blog/the-meta-report-lessons-from-640-haus-incrementality-experiments)). FPS may get a partial Advantage+ experience ([Meta](https://www.facebook.com/business/help/906206294602874)) |
| Cost caps, bid caps, value optimisation | 40–80× below Meta's floors ([Meta](https://www.facebook.com/business/help/272336376749096); [Birch](https://bir.ch/blog/meta-value-optimization)) |
| Lift tests or geo holdouts | About 100× short on conversions ([Meta](https://www.facebook.com/business/help/221353413010930)) |
| Retargeting with exclusions and lookalikes | Limited under FPS ([Meta](https://www.facebook.com/business/help/2220749868045706)). Don't build a retargeting ad set until the audience pool passes about 1,000 |
| Deposit-style incentives (SoFi: "Get $50 or $400") | The transferable part is one concrete offer with its condition stated, which B already is ([moomoo](https://www.moomoo.com/us/newsroom/moomoolaunchestakechargeofyourtrading)) |
| Brokers' 75–250 live ads; TV and podcasts creating demand | Irrelevant at this spend. The idea that missing TV demand explains the CPM is speculation ([Motion](https://motionapp.com/library/robinhood); [Robinhood](https://robinhood.com/us/en/newsroom/a-new-visual-identity/)) |

---

## 8. Open questions and unverified assumptions

- Under FPS, are these available: the flexible ad format, multiple text optimisation, the Creative Test tool, Advantage+ audience, and incremental attribution? Check each in Ads Manager.
- Which data category is on the dataset, and is StartTrial restricted?
- Does the live ad B say 14 or 30 days? Which asset is it actually using?
- Can one flexible ad hold both per-placement ratios and both audio versions?
- Is Tapeline an "investment product" under Meta's financial-services policy? The "cannot obtain" exemption probably doesn't fit ([Meta](https://transparency.meta.com/policies/ad-standards/restricted-goods-services/financial-services/)). Get Meta support's and the lawyer's view in writing.
- Is a US SEC/FINRA verification requirement coming? It's unverified, and Meta's country list couldn't be read ([Meta](https://about.fb.com/news/2026/03/meta-launches-new-anti-scam-tools-deploys-ai-technology-to-fight-scammers-and-protect-people/)).
- Are ad-set-level placement exclusions being removed? Only secondary sources say so.
- Vendor claims that the learning threshold fell to 10–25 events have no Meta source ([Meta](https://www.facebook.com/business/help/112167992830700)).
- Budget-step rule: this document uses 20% or less, at least 72 hours apart. Another proposal is one step, then hold 7 days. Meta backs neither.
- Should paid traffic see a no-trial direct-purchase offer ([Adapty](https://adapty.io/blog/first-10k-meta-ads-subscription-apps/)), or one default offer ([RevenueCat](https://www.revenuecat.com/blog/growth/web-to-app-funnel-examples))? The two conflict; decide before shipping either. The annual plan is preselected (`pricing.ts:45`), so annual picks aren't unprompted.
- Is a card revenue? Both live trials have run zero scans, and the 12 and 14 Sep charges are the first real read.
- Stale sources: the Loomer Audience Network test (2023), the Reels sound data (2023), Performance 5 (2022). The methodology behind Meta's 68%-in-learning figure couldn't be retrieved.
- Why is CPM A$103? Unknown.