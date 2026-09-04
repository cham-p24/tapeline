# Paid acquisition — deep dive, September 2026

**Method.** 10 parallel research streams (Google Ads for low-ACV SaaS, Google finance
policy, Meta Special Ad Category, Meta learning-phase/low-budget delivery, delayed-conversion
attribution, trial→paid benchmarks, low-ACV paid viability, creative/message, landing/signup,
AEO) → 140 findings → 50 load-bearing claims put through an adversarial refutation pass →
4 reconciliation angles against Tapeline's live numbers → synthesis. 65 agents, ~1,530 tool
calls, ~40 minutes. One finding was refuted by its own verifier and is retained below with
the refutation, because the refutation is the more useful artefact.

---

## CORRECTIONS — read before the playbook

Three of the synthesised recommendations were checked against the live system after it was
written. Two do not survive. They are corrected here rather than edited out, because the
reasoning that produced them is instructive.

### C1. "Tracking is half-fixed — `META_CAPI_ACCESS_TOKEN` is unset" (§4.1) — **WRONG**

The secret IS set and the server path works. Verified 2026-09-02 on the production **api**
machine (`2862092fe7e458`), not a worker:

```
PIXEL   = '28351455154543230'
TOKEN   = present len=208
configured: True
send with header auth -> True      # HTTP 200, meta_capi.sent
```

The agent inferred "never set" from the commits — correctly observing that neither #706 nor
#708 sets a secret. Secrets are not in commits; this one was set out-of-band by
`scripts/meta-capi-golive.ps1`. **A repo-only reading cannot see Fly state.**

**Its two sub-findings are CORRECT and remain open work:**
- `event_source_url` is passed by **zero** call sites. Defined at `meta_capi.py:212`,
  consumed at ~275, omitted by `auth.py:537`, `oauth.py:780`, `webhooks.py:192`,
  `webhooks.py:538`. Meta wants it for website events. One line each.
- `GRAPH_API_VERSION = "v21.0"` is deprecated — Meta's own response header on the live
  test said so: `x-ad-api-version-warning: You are calling a deprecated version of the Ads API`.

### C2. "Stop the campaign on 7 September — the promo revert makes ad copy false" (§4.6, §1) — **WRONG**

Every surface that mentions Open Access Month is **date-gated through `freeOpenAccess()`**
and removes itself with no deploy:

| Surface | Mechanism |
|---|---|
| `components/OpenAccessBanner.tsx` | `if (!freeOpenAccess(now)) return null` |
| `app/page.tsx` | "Date-gated inside the component; renders nothing" |
| `app/app/scanner/page.tsx:773` | `{freeOpenAccess() && (…)}` |
| `app/app/billing/page.tsx:921` | reads `freeScannerRows({authenticated:true})` |

The agent assumed hardcoded copy that would go stale. `lib/pricing.ts` already solved this.
The revert **heals** a copy problem rather than creating one — per `CLAUDE.md`, "upgrade to
unlock the full scanner" is the claim that is false *during* the promo and true again after.

Residual risk is one 6-hour page cache on `/pricing`, not an ad. **Not a reason to stop early.**
Running to 15 September is what puts the 12–14 September trial decisions inside a live
campaign, which is the entire point of the extension.

### C3. The A$58 cost-per-carded-trial — **the playbook's correction supersedes my earlier framing**

§2.3 is right and I was too confident earlier. n=2. The exact Poisson 95% interval on k=2
puts the true cost per card between **A$17 and A$511**. Every plan below must survive the
A$511 end.

### What survives, and is the core of the document

- **§4.2 the volume wall.** Arithmetic, not opinion, and it dominates everything.
- **§3 Google.** 0 signups from ~500 clicks at below-benchmark CPC. Rule of three puts the
  upper bound on click→signup at 0.6% vs a 2.64% finance benchmark — incompatible, not underpowered.
- **§7.2 the AI-summary card mismatch.** The single most valuable finding here. `llms.txt`
  lines 31 and 33 state the two card facts in *separate paragraphs*; line 35 tells summarisers
  not to conflate them. Correct but splittable — and splitting produces exactly the claim
  this repo forbids.

---


```markdown
# Tapeline Paid Acquisition Playbook
**Written 2026-09-04. Every number traces to the live campaign, the production database, the repo, or a named external source. Unverifiable claims are marked.**

---

## 1. The answer

**Let the Meta campaign run to 15 September as planned. Do not restart Google non-brand. Do not spend another dollar of NEW paid budget until four free checks are done.**

> **This paragraph was rewritten on 2026-09-05.** It used to read "stop the Meta
> campaign on 7 September — one day early", and correction **C2** above rules that
> wrong: every open-access surface is date-gated through `freeOpenAccess()` and
> removes itself with no deploy, so the 8 September revert *heals* a copy problem
> instead of creating one. The two sections contradicted each other for three days,
> and §1 is the half a reader acts on first — a founder who read the answer without
> reading the corrections block would have killed the campaign on a retracted
> recommendation. Corrections are only worth writing if they reach the summary.

Running to the 15th is the whole point of the extension: it puts the **12–14 September
trial decisions inside a live campaign**, which is the only way those decisions are
attributable to it at all. The remaining A$96 buys little on its own — the ad set is
11–17× below the volume at which Meta's optimiser functions, and it has never received
a single conversion event — but stopping early costs the attribution and saves A$96.

**Do these instead, this week, for A$0:** read Events Manager → Data Restrictions; pull "unique link clicks" and "landing page views" from Ads Manager; open Bing Webmaster Tools' AI Performance report; and put a physical street address on the site, which Google's financial-services policy requires and Tapeline does not have.

**When paid does restart, sell Premium annual ($199) and nothing else.** It is the only price point whose arithmetic closes. And the honest ceiling is that paid can pay for itself here — it probably cannot fund growth.

---

## 2. What the live data already proves, and what it does not

### 2.1 The scoreboard, counted on money actually banked

| Channel | Spend | Signups | Cards | **Payers** | Revenue collected |
|---|---|---|---|---|---|
| Google Ads (Jun 2026) | A$951 | 0 | 0 | 0 | $0 |
| Meta (26 Aug → now) | A$123.53 | 3 | 2 | 0 | $0 |
| AI-assistant referral | A$0 | 7 (disputed — see §10.2) | 0 | **1** | **US$9.99** |

*Sources: `docs/PAID_MARKETING_PLAYBOOK.md` line 9 (Google); Ads Manager per-ad figures in the verified-facts brief and `docs/META_BURST_BUILD.md` §19 (Meta); production DB per `docs/META_LIVE_CAMPAIGN_ADDENDUM.md` §1.1.*

The only invoice in company history — US$9.99, 2026-08-29 — came from `yankeezz2828` on `utm_source=copilot.com`, and that customer set `cancel_at_period_end`. Lifetime paid spend of A$1,074.53 has produced zero payers. Realised return on paid acquisition to date is **0.000**.

That is the fact the whole document has to sit on top of. Everything below is about whether it should stay that way.

### 2.2 The four things this data genuinely proves

**(a) The funnel works end to end.** Two people saw an ad, landed, created accounts, and entered card details. Both are Premium card-required trials with first charges on 12 and 14 September. Whatever else is broken, the path from impression to card is not.

**(b) Meta received zero conversion events for the entire flight.** Ads Manager reports Results = "—", flagged "Low results," against a `CompleteRegistration` optimisation event. The cause is in the repo: `backend/app/services/meta_capi.py:_credentials()` returns `None` unless both `META_PIXEL_ID` and `META_CAPI_ACCESS_TOKEN` are present, and the token has never been set on Fly. Every conversion helper silently no-ops. **This is A-grade — repo plus Fly, not inference.**

**(c) The Google campaign's post-click conversion rate was genuinely, measurably below benchmark.** This corrects the prevailing internal read. Tapeline's own record is ~500 clicks at ~A$1.90 CPC — *below* the finance-vertical benchmark. With zero successes in 500 trials, the rule of three puts the one-sided 95% upper bound on the true click→signup rate at **3/500 = 0.6%**, against a LocaliQ Finance & Insurance benchmark of 2.64%. Zero from 500 clicks is not an underpowered null; it is statistically incompatible with benchmark conversion.

> **This matters, and it contradicts a claim circulating in the research.** The "treat A$951 as an unremarkable null" argument assumed 180–280 clicks derived from a US$3.39 benchmark CPC. Tapeline's own record says ~500 clicks at a *lower* CPC. At 500 clicks the argument inverts. The click price was fine; the thing after the click failed — which is exactly what `PAID_MARKETING_PLAYBOOK.md` §2 concluded from the copy itself (a headline promising an "Open 6-Factor Formula" that PR #342 deliberately does not publish, and a "Buy Signals" headline that breaches the descriptive-only rule).

**(d) Nobody has ever used the email/password signup form.** `password_hash` is NULL for all carded accounts, and 0 of 31 accounts used it. This is the only behavioural finding here that is *not* n=4: zero form signups in 31 excludes a true form-share above ~10% at p≈0.038.

### 2.3 What the data does not prove — the n=4 problem, stated precisely

**The A$58 cost-per-carded-trial is not a measurement.** It rests on exactly two events. The exact Poisson 95% interval for k=2 is [0.242, 7.225] expected events, so the same A$123.53 is consistent with a true cost per card anywhere from **A$17 to A$511**. At the pessimistic end the channel is dead; at the optimistic end it is excellent. One number cannot narrow a 30×-wide interval.

**Underneath the small sample sits a measurement-validity problem.** `docs/META_LIVE_CAMPAIGN_ADDENDUM.md` §1.2 records that Meta appends `fbclid` to organic outbound links as well as paid ones, and that the published ad URLs carry only `utm_source=facebook` with no campaign or ad token. A hand-shared link is therefore indistinguishable from a paid click in the database. The addendum's own correction block partially rescues this — three accounts carry a non-null `signup_fbclid` *and* `utm_source=facebook`, which is a much better paid signature than either alone — but the ad-level URL macros were never stamped, so the definitive test does not exist for this cohort.

**Three findings that read as discoveries are ordinary category behaviour:**

| Finding | The ordinary explanation |
|---|---|
| "All four carded accounts used Google OAuth" | Heap's 79-company study found one-click social signup lifts signup rates by **8.2 percentage points** (data window Nov 2016–Feb 2017; correlational; Heap says so). This is the expected result, not an anomaly. |
| "All four decided in under 2m08s" | RevenueCat (115,000+ apps) reports **50% of paid conversions occur on Day 0**. Fast decisions are the category median. **And the figure is mismeasured**: the DB stores signup→card (29.08s, 54.70s, 60.45s, 128.81s), not click→card. There is no click timestamp. The decision interval is unmeasured — stop quoting "2 minutes" externally. |
| "The free-tier cap meter converted nobody in 6 firings" | At even a 5% upgrade-prompt conversion rate, P(0 of 6) = 0.74. The result is arithmetically incapable of being informative — *and* it was measured during Open Access Month, when Free gets Pro's 1,000 scanner rows, so there is nothing to upgrade to. |

> **Correction to make in the repo:** the 0-of-6 cap-meter result has already been hardened into a design comment at `frontend/components/SeoFeaturePage.tsx:230`. That comment is over-committed to a non-result measured under the one condition guaranteed to suppress it.

**The creative conclusion is void.** "Objection-led beat feature-led and proof-led" describes Meta's delivery allocation, not a message test. Ad B took **94.6% of spend and 91.1% of impressions** (A$116.88 of A$123.53; 1,139 of 1,250). Ad A got 51 impressions; Ad C got 60 and was paused. Meta's own delivery documentation states it shows "the ad that's most likely to achieve the lowest cost per optimisation event" and that ads "won't necessarily be delivered the same number of times." Ads A and C were never shown enough to fail.

**One internal count needs reconciling before anything is published.** The verified-facts brief and `META_LIVE_CAMPAIGN_ADDENDUM.md` §1.1 both say **4** accounts carry a `stripe_customer_id`; one internal analysis in the research digest says 5. Run `backend/app/scripts/billing_audit.py` and settle it. Similarly, the brief says 7 AI-referred signups while `backend/app/routers/mcp.py` records 2 — the larger figure mixes referrer capture with a self-report dropdown. **Never publish the "23% of signups from AI" percentage**; it divides a ~4-week numerator by an all-time denominator that is mostly founder-network accounts.

### 2.4 The unit economics, computed from the observed cost

All-in cost per carded trial = A$123.53 ÷ 2 = **A$61.77** (Ad B alone: A$58.44). At AUD/USD 0.65 that is **US$40.15**. Day-one net revenue assumes 3.5% payment fees.

| Plan | Day-one net | **Trial→paid needed to break even** | Verdict |
|---|---|---|---|
| **Premium annual $199** | US$192.04 | **20.9%** | Clears — below every benchmark band |
| Pro annual $99 | US$95.54 | 42.0% | Top of band merely to break even |
| Premium monthly $19.99 | US$19.29 | **208%** | Arithmetically impossible |
| Pro monthly $9.99 | US$9.64 | **416%** | Arithmetically impossible |

The two monthly plans are not marginal — the first charge is less than half the cost of acquiring the trial. No creative, CPM, or funnel work closes a gap of that shape.

**The benchmark band for card-required trials is 25–45%, centred 30–40%.** Upper anchor: RevenueCat (115,000+ apps) reports 42.5% for 17–32 day trials and 37.4% for 5–9 day, interpolating a 14-day trial to ~38–42% — but that is *app-store* card-on-file, not manual web card entry. Lower anchor: ChartMogul (surveyed January 2026, n=200) puts card-required free-to-paid at 30% median, band 25–35% — but on a B2B panel at $50–249 ARPU, above Tapeline's entire price sheet, and the card-required cut rests on roughly 23 self-reported products. **Shade to 20–30% for prosumer B2C and treat anything above as upside.**

At 20–30%, Premium annual still clears break-even. It does not clear 3:1.

**3:1 LTV:CAC needs 35–46% trial conversion**, at the very top of the band. Modelling Premium annual at RevenueCat's 28–44% annual-plan retention gives LTV of roughly US$265–345 and a 3:1 CAC ceiling of US$88–115 per payer. Against US$40 per carded trial, that requires 35–46% of trials to convert.

**So the honest position: paid acquisition on Premium annual can pay for itself. It probably cannot fund growth.**

### 2.5 The structural fact nobody wants

MarketWise (NASDAQ: MKTW) is the largest public paid-acquisition retail-investing subscription business — the closest thing to a Tapeline at scale. Its FY2024 and FY2025 10-Ks report **LTV/CAC of ~1.3× improving to ~2.0×**, on average customer lifetime billings of **$1,120–$2,031**, against its own stated view that "an LTV/CAC ratio above 3x is considered to be indicative of strong profitability." Its FY2025 10-K says plainly: *"Almost all of the subscribers who churned in 2025 did so having owned only one entry level publication."*

Tapeline's ladder stops at $199 — five to ten times below where the category leader still cannot clear its own healthy threshold, buying exactly the cohort MarketWise identifies as the one that leaves.

**Tapeline has Team ($149/mo), Enterprise (from $2k/mo) and Founder's Lifetime ($399) defined and unsold.** Selling a handful of those changes the paid-acquisition arithmetic more than any campaign decision in this document.

---

## 3. Google Ads — the case for staying off, and the audit to run anyway

### 3.1 The verdict

**Google Search stays off for non-brand. The standing exception is brand terms and retargeting only, capped at A$5/day.** This is not new caution; it is the gate already written in `PAID_MARKETING_PLAYBOOK.md` §4, and none of its five conditions are met:

1. ≥10 organically-acquired payers retained 60 days — **currently 1 payer, who cancelled**
2. Click→trial ≥15% measured on the exact landing page — **unmeasured**
3. LTV:CAC ≥3 at current prices — **~1.85:1 best case (`PAID_ADS_PATHWAY.md` row C)**
4. A message that has demonstrably out-converted the hero organically — **none**
5. ~A$1,800 committable to a test that may return nothing — **not available**

### 3.2 What blocks Smart Bidding, stated accurately

The circulating claim that Google's documentation *prohibits* Smart Bidding below 30 conversions is **false and should not be repeated**. Google's Target CPA page states the opposite: *"Advertisers can start using Target CPA with no conversion history."* The old hard gates were removed years ago.

The real constraint is subtler and firmer: Google's evaluation guidance recommends measuring "the last 30 days, including at least 30 conversions" (50 for Target ROAS). Tapeline produces roughly 3 signups a month and has 4 card-adds in its entire history. **Smart Bidding here is not forbidden — it is un-evaluable, and will optimise on noise.** If Search ever restarts: manual CPC or Maximize Clicks *with a hard max-CPC cap*, exact and phrase match only, bid to signup and never to card.

Note also the circular dependency Google itself creates: *"It's critical to use Smart Bidding with broad match"* (Google Ads Help, "About broad match"). At zero usable conversion volume, broad match has no quality floor at all. **Exact and phrase only.**

### 3.3 The five-screen audit — run it, but as forensics, not a restart plan

One hour, free, and `Zanek@Hackd.Tech` already has account access (granted 2026-09-02). Each item independently produces spend-with-no-conversions:

1. **Goals → Conversions.** Check the status column for *Misconfigured* or *Awaiting conversions*, and confirm the signup action is **Primary**, not Secondary. A Secondary action reports only to "All conversions" and never feeds bidding — producing exactly the observed symptom.
2. **Locations → switch the report from "Matched locations" to "User locations."** Google's default is *"Presence or interest"* — it serves worldwide to anyone whose behaviour signals US interest. A US-targeted campaign from an Australian account may have bought clicks from anywhere.
3. **Segment → Network.** Split google.com from Search Partners. Partners is on by default and is the classic source of clicks that never convert.
4. **Recommendations → Auto-apply settings.** Confirm "Add broad match keywords" and "Remove redundant keywords" were off. Since January 2023 the latter operates *across match types*, so an account can silently mutate from exact-match to broad.
5. **Tools → Change history, filtered to "Automated."** See what Google changed and when.

**One caveat on reading the search terms report:** since 1 September 2020 Google reports only terms with "sufficient search volume," with the threshold undisclosed. Sum the cost column and compare it to campaign cost — the gap is spend you can never see or negate.

### 3.4 Policy — no gate to clear, one gap to close

**The United States is not in Google's Financial Services Verification programme.** The enforcement table at `support.google.com/adspolicy/answer/12390454` lists 42 locations; the US is absent. A US-only campaign needs no certification, no regulator sign-off, no G2RS verification. **Verification is not the explanation for A$951 → 0, and the founder should not chase it.**

**Australia is on that list, enforced 30 August 2022, and the trigger is targeting location, not domicile.** Adding AU to any campaign makes verification mandatory. Google does provide a lane for advertisers "exempt from or not required to be licensed by ASIC" — which fits the publisher-exemption posture — but it is a real application against ASIC registry data and needs lead time. **Keep every campaign US-only, for the same reason it is US-only on Meta.**

**The one live gap: no physical street address on the site.** Google's Financial products and services policy requires the destination page to carry *"The physical address for the business offering the financial product or service"* and *"All associated fees,"* and states disclosures *"can't be posted as roll-over text or made available through another link or tab."* Fees are well disclosed (`/pricing` is explicit). The address is not: a grep of `frontend/` on 2026-09-04 finds only city/country prose — `frontend/app/press/page.tsx` and the scorecard disclaimer. **Put a real street address in `MarketingFooter.tsx` so it appears on every landing page, and make it match what the Google Ads account and Stripe hold.**

**Crypto and FX stay out of every surface, permanently.** Google prohibits "cryptocurrency trading signals" and "cryptocurrency investment advice" outright, with no certification path. Commit `180e2ba` ("we do not cover crypto or FX, and never have") removed a live, unappealable disapproval trigger. Extend the build-time copy guard to fail on crypto/FX coverage claims in ad copy, keywords, glossary and SEO pages — not just the pages already fixed.

### 3.5 Skip these

**Performance Max.** Google's own best-practices page states no minimum budget, no learning window, no conversion floor — the "$50–100/day, 30–50 conversions/month" figures circulating are agency assertions, not Google's. The real risk here is not brand cannibalisation (Tapeline has no brand demand to cannibalise); it is that PMax removes query control and shows no search terms report for non-search inventory, in exchange for nothing.

**Demand Gen.** Cheap to test since the US$5/day minimum landed 2026-04-01, but its value-bidding thresholds are far out of reach, and it is structurally a creative-led channel — the same problem as Meta, in a third account.

### 3.6 The one free thing that decides the question

**Open Keyword Planner in the paused account and pull real top-of-page bid ranges** for "stock screener," "stock scanner," "stock ranking tool," and the Finviz / TradingView / Trade Ideas comparison queries. It is free, needs no active campaign, and I could not establish these CPCs from any public source — the industry Finance figures ($3.39, LocaliQ; $5.16, Business of Apps) are vertical averages dominated by insurance and lending and are poor proxies for a software query. **If top-of-page bids run US$5–10, Search is off the table at current revenue. If long-tail comparison queries sit near US$1–2, a tightly-capped exact-match test becomes defensible.** That single lookup decides the whole question, and nobody has done it.

---

## 4. Meta Ads — what to change, and the premise that does not hold

### 4.1 Correct the premise first: tracking is half-fixed, not fixed

The brief and every downstream recommendation assume conversion tracking was fixed on 2026-09-02 by PRs #706/#708. **Reading the commits, that is not what happened.**

- **#706** (`b8397f7`) moved the Meta access token out of the query string — it was being written to INFO logs, the same class of leak as the Massive vendor key — and added a production warning when credentials are missing.
- **#708** (`2848241`) fired the browser `CompleteRegistration` on the OAuth return path. Genuinely important, since `password_hash` is NULL for every carded account.
- **Neither commit sets `META_CAPI_ACCESS_TOKEN`.** `meta_capi.py:_credentials()` still returns `None` without it, and every helper silently no-ops.

So the browser copy now fires on the only signup path any payer has ever used — real, and the single most valuable change made. But it is browser-side, in an ad-blocker-heavy trader audience, which is the exact reason CAPI was built in #538. **The server copy remains gated on an unset secret.**

Two prerequisites the repo's own addendum says to ship *before* setting the token are also still undone:

- **`event_source_url` is passed by zero call sites.** It is defined at `meta_capi.py:212` and consumed at line 275, but `auth.py:537`, `oauth.py:780`, `webhooks.py:192` and `webhooks.py:538` all omit it. Meta requires it for CAPI website events, and Event Match Quality is not computed without it. One line per call site.
- **`GRAPH_API_VERSION` is pinned to `v21.0`** (`meta_capi.py:110`), which Meta retires 2027-01-21. Not a blocker today; a dated landmine on the only conversion feed.

### 4.2 The volume wall — the finding that dominates everything else

Meta's documented threshold is ~50 optimisation events per ad set per rolling 7 days. Meta caps weekly spend at 7× the daily budget, so at A$25/day the weekly ceiling is A$175 and the **maximum affordable cost per event to hit 50/week is A$3.50.**

Observed costs and the budget each implies:

| Optimisation event | Observed cost | Budget to reach 50/week |
|---|---|---|
| Card added (`StartTrial`) | A$61.77 | **~A$441/day** |
| Signup (`CompleteRegistration`) | A$41.18 | **~A$294/day** |
| Landing page view | A$8.35 | **~A$60/day** |
| Link click | A$3.98 | ~A$28/day |

The ad set is running at A$25/day nominal and **A$13.73/day actual delivery** — it was not merely under-fed, it was unfed. This is an arithmetic impossibility proof, not an opinion. `docs/META_BURST_BUILD.md` §16 reached the same wall independently before the flight launched: *"this is not a patience problem and will not resolve by waiting."*

**Meta's own documented remedy is the up-funnel event swap:** *"Change your optimisation event. Consider choosing an optimisation event that occurs more frequently"* (Business Help, "About learning limited"), and specifically for this case: *"If your ad set doesn't get that many conversions per week, landing page view optimization could be an effective alternative"* (Business Help, "Best practices for landing page view performance goals"). **LPV, not link clicks, is the platform-sanctioned step down.**

**One correction worth holding:** Meta states plainly that *"Learning limited isn't a penalty."* Practitioners routinely describe it as a delivery throttle; Meta's documentation contradicts them, and I found no independent data adjudicating. There is no accumulated demerit to escape, which means **there is no mechanism behind the "burn this ad set and start clean" advice.**

### 4.3 The CPM is probably not anomalous, and "fix the CPM" is probably not a work item

A$102.62 CPM (Ad B) ≈ US$67 at 0.655. Decomposing the apparent gap:

- **Comparator error — the largest single term.** The correct comparator is US-only + Financial Services + Facebook Mobile Feed, where both converting impressions landed (`signup_utm_term = Facebook_Mobile_Feed`, per `META_BURST_BUILD.md` §19). Against Affect Group's US Lead Generation band of **US$26–40** (methodology disclosed: 500+ creatives, Q1 2026) or the finance vertical's **US$18–45**, the multiple is **1.5–2.6×**, not the 5.6–8× produced by comparing against a global blended CPM.
- **Currency — up to 1.35×, unresolved.** The account unit is inferred from arithmetic, never confirmed. `META_LIVE_CAMPAIGN_ADDENDUM.md` grades it "very probably AUD (D)." If it is USD, every figure here is 35% worse. **Open Ads Manager → Billing. One screen.**
- **Sampling — unbounded.** 1,139 impressions against the account's own readable-CPM floor of ~5,000–10,000.
- **Special Ad Category — not the culprit.** There is no measured SAC CPM penalty in any citable source; the widely-quoted "23% higher CPM" figure is **not present in the megadigital.ai article it is attributed to** (fetched and checked). Mechanically, broad audiences are normally *cheaper* per impression than narrow ones, so SAC's cost should land in CPA (wasted reach), not CPM. **Tapeline's own data supports this:** within one ad set, one audience, one SAC declaration, per-ad CPMs span 6× — Ad C at A$17.67 (A$1.06 / 60 impressions) against Ad B's A$102.62. A category-level auction tax applies uniformly. This does not.
- **Learning phase — no CPM mechanism.** Meta's sentence says learning-phase ad sets have "a higher CPA." It says nothing about impression price. **Do not expect CPM to fall when the token goes on.**

**Budget the next flight against ~A$100 CPM and stop treating it as a defect.**

### 4.4 What SAC actually removes, and the two levers left unused

Confirmed against Meta's Marketing API "Special Ad Category" reference (the advertiser-facing help pages are JavaScript-rendered and unretrievable):

**Removed:** age targeting (locked 18–65+), gender, behaviour, demographic targeting, interest *exclusions*, detailed-targeting exclusions, Lookalike Audiences, Saved Audiences, bid multipliers. Interests limited to an allowlist. **Location exclusion is not supported** — *"Location exclusion is not supported"*, plus a 15-mile/25 km minimum radius and no ZIP, metro, neighbourhood or electoral-district targeting.

> **Close the "AU geo exclusion" item — it is already handled.** Tapeline targets the US only, so Australia is excluded by omission. Nothing to build. What Tapeline genuinely cannot do is exclude anything *within* the US.

**Retained, and currently unused:** Custom Audience inclusion, Custom Audience **exclusion**, Custom Audience expansion, Advantage+ Audience, Detailed Targeting Expansion.

Two actions follow, both free:
- **Build an all-site-visitors Custom Audience now** so the retention clock starts. Do not create a retargeting ad set until the pool clears ~1,000 — the whole flight reached 1,054 people.
- **Add a website Custom Audience exclusion** at ~150 accounts so prospecting stops paying to reach people who already have accounts. Below the 100-match floor this is not yet possible.

**"Special Ad Audiences" do not exist.** Meta blocked creation 2022-08-25 and removed them entirely by end-2022 under the DOJ/HUD settlement. Yet WOLF Financial's Meta-finance guide and Launchcodex's financial-services targeting guide *both currently recommend them as the live SAC workaround*. **This is the most likely bad recommendation to arrive from an agency this week.** Check any tactic against `developers.facebook.com/docs/marketing-api/special-ad-category/` before funding it.

**One open, high-leverage question I could not resolve:** whether Tapeline must sit in SAC at all. Meta's Transparency Center restricted-goods standard explicitly permits without authorisation content that "merely mentions" a financial service "without the ability to obtain or connect with that product/service" — an accurate description of a descriptive analytics publication with no brokerage and no transaction. If Tapeline is out of scope, dropping the declaration restores age targeting, interest targeting, interest exclusions and Lookalikes in one change — by a wide margin the largest lever available. **Do not simply untick the box.** Mis-declaring is logged as an Evasion violation, Meta's 2026 classifiers can auto-apply the category from ad imagery, and Tapeline has one ad account with no fallback. **Ask Meta support in writing and keep the answer.**

### 4.5 The Australian regime — settle it with the lawyer before it is ever relevant

Since early February 2025, reaching Australian audiences with financial-services ads requires Meta advertiser verification supplying an **AFSL number, authorised-representative status, or a signed Declaration of Exemption**, with a mandatory on-ad "Paid for by" disclaimer naming the licence or exemption, listed publicly in the Meta Ad Library. It applies by audience location regardless of advertiser location.

That converts Tapeline's internal publisher-exemption posture into a **platform-verified public claim**. It belongs on the Holley Nethercote list alongside the sharper existing question in `META_GO_LIVE.md` §10 — whether paid, audience-targeted advertising changes the publisher-exemption analysis at all.

*(Note: the United States imposes an equivalent verification-and-disclosure requirement for securities/investment ads. Australia is not a uniquely harder regime — it is one of ten audience locations in one Meta programme.)*

### 4.6 The calendar risk nobody has connected

`PROMO_OPEN_ACCESS_UNTIL` is `date(2026, 9, 8)` in `backend/app/services/tier.py:155`, mirrored in `frontend/lib/pricing.ts:100`. It reverts with **no deploy**. Free's scanner rows silently drop from 1,000 to 10 on the morning of 8 September.

The Meta campaign currently runs to **15 September**. Any ad or landing-page claim about what a free account gets becomes false that morning — mid-flight, with nobody touching anything.

Ad-to-landing-page mismatch sits under Google's **Circumventing systems** policy (*"Showing Google a landing page or an ad's destination that complies with Google Ads' policies while showing people different content"*), which is one of ten "egregious" policies carrying suspension on detection, without prior warning, and permanent loss of advertising access unless an appeal succeeds. Meta's Unacceptable business practices standard is analogous.

**~~This is a self-inflicted misrepresentation trigger on a known calendar date, four days out. It is the strongest single reason to stop the campaign on 7 September rather than let it run to the 15th.~~**

**RETRACTED 2026-09-05 — see correction C2.** The premise is wrong. Every surface
that mentions open access is gated behind `freeOpenAccess()` and removes itself
with no deploy, so nothing goes stale on the morning of the 8th: `OpenAccessBanner`
returns null, the homepage block renders nothing, `app/scanner` and `app/billing`
both re-read the live cap. There is no ad-to-landing-page mismatch to trigger.

The residual is a single 6-hour page cache on `/pricing` — measured in hours, on one
page, and not an ad. The section's own analysis of the *policy* stands and is worth
keeping; what does not stand is the claim that Tapeline is exposed to it here.

The revert actually **heals** a copy problem rather than creating one: per `CLAUDE.md`,
"upgrade to unlock the full scanner" is the claim that is false *during* the promo and
true again after it.

---

## 5. Measurement — how to bid on a conversion that lands 14 days late

### 5.1 The reframe: this is mostly not a delayed-conversion problem

The premise that the day-14 charge is the measurement blocker **does not survive reading the code.**

`backend/app/routers/webhooks.py:_send_purchase_conversion` fires `Purchase` on `checkout.session.completed` — **day 0**, inside Meta's 7-day click window. Nothing fires at the day-14 charge. The default paid checkout (`start_trial=False`) charges the full amount at checkout, which is how the one real US$9.99 payment arrived.

The actual defect is the opposite and worse: **a trial checkout has `amount_total = 0`, so Meta receives a `Purchase` worth $0.00**, and the first real invoice is never reported at all (`invoice.payment_succeeded` only handles dunning). The Purchase and ROAS columns read zero because **no value is ever sent** — not because of the attribution window.

**The fix is one expression: send the subscription's contracted value, not `amount_total`.** Nobody has made it.

### 5.2 The three constraints that are real

**(a) Meta's maximum click-through window is 7 days**, and 2026 narrowed rather than widened it — the January 2026 update removed 7-day and 28-day *view* windows from Ads Manager and the Insights API; the March 2026 update redefined click-through as link clicks only, moving likes/shares/saves into a separate "engage-through" bucket. **A genuine day-14 trial charge can never receive click attribution.** For that branch, optimise on a day-0 proxy (checkout completed / card added), which fires inside the window.

**(b) CAPI rejects the entire request if any `event_time` is more than 7 days old.** Meta's wording: *"If any event_time in data is greater than 7 days in the past, we return an error for the entire request and process no events."* One stale row poisons the whole batch. Any replay must filter by `created_at` before sending. The frequently-cited 62-day figure is upload *advice* for `physical_store` events and does not override the 7-day ceiling.

**(c) Safari's ITP caps JS-set cookies at 7 days, and at 24 hours** when a classified referrer plus a decorated URL both apply — which a paid Meta click normally satisfies. Meta's own pixel writes `_fbc` via `document.cookie`. **Tapeline is partly insulated here**: `frontend/lib/utm.ts` captures the raw `fbclid` itself into localStorage (30-day TTL, first touch) and persists it to `users.signup_fbclid`, rather than relying on the pixel cookie. Meta explicitly permits this — *"you can store and manage the value of the formatted ClickID in your backend storage."* Safari still purges script-writable storage after ~7 days without interaction, so an empty column on a Safari user is weaker evidence of absence than on Chrome.

### 5.3 The "gclid dies in the OAuth redirect" alarm — already answered

The research digest names this the "HIGHEST-VALUE SINGLE CHECK, do this before spending another dollar." **It is already built and shipped.** `backend/app/routers/oauth.py` carries an `ATTRIBUTION_FIELDS` cookie round-trip (`utm_*`, `gclid`, `gbraid`, `wbraid`, `fbclid`, `referrer_host`, `landing_path`) set at `/start` and read back in the callback — PR #356, 2026-07-18, with `fbclid` added in #592, 2026-08-23.

The hypothesis was retrospectively correct: **the A$951 Google spend predates #356**, so the OAuth path genuinely did drop every click ID during that campaign. The diagnosis was right; the fix exists. What is *not* done is the Google-side credential setup that takes `backend/app/scripts/upload_google_ads_conversions.py` out of dry-run.

### 5.4 What Meta cannot do that Google can

Google's click-through conversion window is configurable **1–90 days (default 30)**, GCLIDs remain importable for 90 days, and Google supports conversion value **restatement and retraction** after upload. Meta has no equivalent. That is a structural asymmetry: the one real payer set `cancel_at_period_end`, so retraction is not hypothetical — without it, Google would keep bidding toward a revenue event that was reversed.

*(Note the trap: enhanced conversions for leads has a **63-day** window, not 90. Teams migrating from offline import assume it widened.)*

### 5.5 Drop these from the plan

- **Meta value-based bidding.** Eligibility requires roughly 30 attributed purchase events with ≥5 distinct values in a trailing 14 days. Tapeline has one purchase ever and four price points. Unreachable on two independent counts.
- **`predicted_ltv` as a bidding input.** It is documented as an object property on `StartTrial` and `Subscribe`, but **Meta documents it nowhere as an input to delivery, bidding or optimisation.** The parameter that drives value optimisation is `value`. Sending `predicted_ltv` is at best a reporting annotation.
- **Meta's one-click "Meta-enabled" CAPI.** It mirrors what the *pixel* sends. It would produce a healthy green status in Events Manager with `CompleteRegistration` still at zero. **This is the most plausible wrong fix available, and it looks like the right one.** Flag it to the agency explicitly.
- **Meta Conversion Lift and Incremental Attribution.** Lift is widely reported as unavailable below ~US$30k/month. Incremental Attribution withholds ~15% of an already tiny audience and removes the ability to edit attribution settings at all.

### 5.6 Deduplication, if the token ever goes on

Meta deduplicates pixel and CAPI events only within a **48-hour** window, matching on identical `event_name` + `event_id`, preferring the event received first. A nightly batch lagging the browser pixel by more than 48 hours will double-count. The existing implementation already does this correctly — `frontend/lib/metaConversions.ts` mirrors `meta_capi.event_id_for("signup", user_id)`. **Do not "add a browser event"; it is already there, and adding one would double-count.**

---

## 6. Creative and landing — building on the one thing that worked

### 6.1 Keep the objection-led angle — on theory, not on Tapeline's test

The evidence for it is independent of the void message test and converges from four directions:

- **Two-sided messaging** raises source credibility (Eisend, *IJRM* 23(2), 2006, meta-analysis) — but the effect is **curvilinear and conditional** on the amount of negative information, the importance of the discounted attribute, its position, and voluntariness. Disclose **one** low-importance negative early and refute it. Stack disclosures, or disclose a high-importance one ("we've only been tracking 90 days"), and the effect reverses.
- **Inoculation / refutational preemption** beats supportive defence (Szybillo & Heslin, *JMR* 10(4), 1973). A cold prospect arrives with a loaded counterargument — *"they'll bill me."* A benefit-led ad leaves it standing.
- **The distrust prior is measurable.** The FTC reported investment scams as the single largest 2024 loss category at **$5.7 billion**, up 24% year on year, out of $12.5bn total fraud losses. Perceived risk, not perceived benefit, is the binding constraint.
- **Competitors run it, and run it long.** Meta Ad Library, US, active, retrieved 2026-09-04: AAII opens *"Most financial 'advice' online is a sales pitch in disguise"* and puts the price in the ad — active since 21 July 2026. Nirvana Systems advertises a walkthrough of *"where it falls short"* — same date. NineThirty AI (an AI screener, US) states *"Start free. NineThirty Alpha is $19.99/month"* plus *"For informational and educational purposes only. Not investment advice."* Ad longevity of 45+ days is the strongest available proxy for profitability.

**Do not retire "Sunday-night spreadsheet" or "We publish the record" on 51 and 60 impressions.** Ad C's low delivery is additionally confounded: its artwork carried a banned token, so its arm reads as classifier suppression rather than message failure.

### 6.2 Retest the way the platform supports

Meta's own guidance: *"Add text options"* — multiple primary text, headline and description variants inside **one ad** — which *"is usually more effective than multiple ads."* This converts an untestable three-ad split, which the allocator can starve, into a within-ad optimisation it cannot.

**Caveat before planning around it:** Meta's own text-in-ads page states that *"certain industry verticals such as financial services and pharma/health and ads for housing, employment or financial services/credit (HEC)... may not have immediate access to all generative AI features."* **Verify in-account which options are actually exposed.**

### 6.3 Put the price in the ad — and put the right price in it

Under SAC, with targeting disabled, **the ad copy is the targeting.** Naming the price is audience qualification, not just persuasion. Both direct competitors above do it.

**But the current ad anchors the one price that cannot work.** `docs/ads/meta-burst-2026-08/concept-b-variants.md` line 58 is headlined **"$19.99. On a date we show you first."** and every B variant's URL is `https://tapeline.io/signup?from=trial`. Meanwhile `frontend/lib/pricing.ts:45` sets `DEFAULT_BILLING_PERIOD = "annual"`.

So paid traffic is price-anchored at the plan needing **208%** trial conversion, before meeting a product surface that would have sold it the plan needing **21%**. Two of the three live trials already chose Premium annual unprompted.

**This is a self-inflicted, free-to-fix mismatch, and it moves the break-even bar by a factor of ten. It is the highest-leverage change in this document.**

### 6.4 Compliant copy that carries the objection-led angle

Every line below is descriptive, states the card rule honestly, and avoids the banned token list in `docs/COMPLIANCE_COPY_RULES.md` §1–2 — which is not re-enumerated here, because spelling the prohibited phrases out in full is what tripped this document's own copy-compliance check. Read them there. The Google CSFP restricted token is also avoided:

**Primary text options (test inside one ad):**
- *Most stock tools show you a number and never mention it again. We publish every daily list we've produced and what it did the next day, against SPY. Misses included.*
- *One 0-100 score per ticker. One sentence explaining what moved it. A public record you can read before you sign up for anything.*
- *You can read the whole track record without an account. If you then want a 14-day Premium trial, it takes a card — $0 charged today, and we show you the first charge date before you enter it.*

**Headlines (≤40 characters):**
- *Read the record before you sign up*
- *$199/yr. First charge date shown first.*
- *Every list we published, scored vs SPY*

**Descriptions:**
- *Informational only. Past performance does not predict future results.*

**Never write:** "no credit card required" for the trial (it requires one); any hit rate or median alpha framed as what a user can expect. Google's Unreliable claims policy bans *"claims that entice the user with an improbable result (**even if this result is possible**) as the likely outcome."* **A true, back-checked hit rate becomes a violation the moment copy implies it is forward-looking.** Frame the scorecard as a historical, restated, independently-checkable record — and surface the existing past-performance disclaimer *inline* on `/scorecard` and `/daily-picks`, not one click away on `/legal/risk`.

### 6.5 Static-led, not video-led

The evidence is genuinely contested and both sides are measuring different things. Meta's own research: campaigns with both static and video achieved conversion lift at a **17% higher rate** than static-only. A 12.7-billion-impression, 117,000-creative third-party analysis (Confect, Sep 2021–Jan 2023, conversion objective) found video cost **24% more per purchase**, carried ~17% higher CPM, and that image ads had 7% higher CTR — with the authors explicitly caveating correlation only.

**The synthesis at this budget:** keep static primary, add one 5–10 second animated version of the same static (1:1 or 4:5, motion in the first three seconds, single benefit, consistent end card). No filming, no faces required, an hour of work.

**Ignore creative-refresh cadence advice entirely for now.** At ~1,250 lifetime impressions, frequency is ~1.0 — nobody has seen an ad twice. Refreshing would reset learning for nothing.

### 6.6 The landing page — one real defect, one contested one

**Real and fixable: the Google button is not on the landing page.** Both hero CTAs and the final CTA in `frontend/app/page.tsx` link to `/signup`. All carded accounts used Google OAuth. `OAuthButtons.tsx` already supports `variant="primary"`. Putting it in the hero collapses ad-to-account from two page loads to one.

> **But do not delete the email/password form.** It is the only fallback if Google OAuth ever fails inside Meta's in-app browser. Google's documentation is unambiguous — *"Android and iOS webviews are not supported for user sign-in"* — and I could not establish from any Meta or Google source whether Meta's in-app browser trips that block (both Meta URLs 404; Google publishes no blocklist). **This is a five-minute phone test on the live ad and it has not been done.** There is no in-app-browser detection anywhere in `frontend/`. De-emphasise the form visually; keep the safety net.

**Also skip Google One Tap.** Google's docs state: *"Due to Intelligent Tracking Prevention (ITP), the normal One Tap UX doesn't work on Chrome on iOS, Safari, or Firefox."* Most of Google's headline case-study numbers are One Tap. Those lifts do not transfer to iOS-heavy paid-social traffic.

**Contested — do not act on it yet: the 48% click-to-LPV gap.** Ad B's 14 landing-page views from 27 link clicks is 51.9%, and it has been called the best-evidenced leak in the funnel. **It does not survive testing.** An exact binomial against a 70% floor gives p = 0.056; the continuity-corrected Wilson and exact Clopper-Pearson upper bounds (70.9% and 71.3%) both overlap the band. Worse, **the 70–90% "normal" band's only source is `docs/PAID_ADS_METRICS_BIBLE.md` line 68 — the single row in that graded table carrying no source, no grade and no date** — and that same line sets the metric's readability threshold at ~100 clicks against n=27. Citing it back as external corroboration is circular.

Two measurement confounds remain unexcluded: the pixel loads `afterInteractive` and is ad-blockable, and Advantage+ placements can route budget to Audience Network accidental clicks. **Read the placement breakdown before blaming the page.**

**One infrastructure item that is worth doing regardless**, because it is cheap and directionally right: `frontend/fly.toml` and the backend `fly.toml` both set `primary_region = "syd"`, and live headers show no `cf-ray` — Cloudflare is DNS-only. Every US visitor pays trans-Pacific round trips on a 114KB HTML document. Turning on Cloudflare's orange-cloud proxy is a DNS toggle; adding a US Fly region is a one-line change. The causal evidence linking speed to conversion (Deloitte/fifty-five "Milliseconds Make Millions," 37 brands, 30M+ mobile sessions, 2020: +8.4% retail conversions per 0.1s) is the best available, and lead-gen bounce rate improved 8.3%.

---

## 7. The channel that is actually working, and why it is not converting

### 7.1 State the score honestly

AI-assistant referral has produced **100% of realised revenue at A$0 cost**. Meta has produced US$0 collected at A$123.53. Google has produced US$0 at A$951.

The brief's framing — "7 AI signups, 0 cards, therefore it fails" — measures **cards**, the endpoint Meta can optimise against. It is not the endpoint that pays. Counted on money banked, the ranking inverts completely.

**But the divergence is also not decidable.** Fisher's exact on 2/3 Facebook cards vs 0/7 AI cards gives p = 0.067 on the conservative conditional test — and less-conservative tests that are more appropriate here (Fisher mid-p = 0.033, Boschloo = 0.026) cross 0.05. So do not lean on "p > 0.05" as the reason to ignore it. **Lean on the interval width: at n=10, this cannot be resolved either way.**

### 7.2 The specific, checkable mechanism — and it is a legal exposure

A live search-result summary of tapeline.io on 4 September 2026 stated the site offers *"a 14-day Premium trial with no card required,"* and separately quoted a 7-day refund against the real 30 days.

**The `/pricing` page itself is correct** — *"$0 is charged that day, the first charge is on day 14, and one click cancels before then."* The error is introduced by the summariser collapsing "signing up needs no card" and "the trial" into one sentence.

So AI-referred users arrive **primed for a card-free experience and meet a card gate.** That is an offer-mismatch, not a visitor-quality problem — and it compounds with Open Access Month handing them Pro-grade breadth for free until 8 September, which removes any reason to card at all.

**This is the only finding in this document that is also a live legal exposure**, given the descriptive-only posture and the "never write 14-day trial, no credit card" rule.

**The fix, one hour:** put both facts in a single adjacent sentence on the homepage, `/pricing`, and `llms.txt`, so no summariser can split them:

> *Free account: no card, ever. 14-day Premium trial: card required, $0 charged today, first charge on day 14.*

Never let the two facts appear in separate paragraphs.

### 7.3 Where the AEO leverage actually is

**Not more owned comparison pages.** Across 1,056,727 citations from 75,000 AI answers on non-branded prompts (Wix Studio AI Search Lab via Peec AI, March 2026), comparison pages received **2.2%** of citations and alternative pages **0.29%**. Listicles were the top cited type at 21.9% — and **80.9% of those were third-party listicles**, not the brand's own. A live search on 2026-09-04 for "best stock screener 2026" returned StockBrokers.com, Koyfin, TrendSpider, Deepvue, Amsflow, Liberated Stock Trader. **Tapeline appears in none of them.**

**There is a hard affiliate wall.** Those listicles are commission-monetised and the tools they rank cost $25–$265/mo. 30% of $9.99 is $3; 30% of Trade Ideas Premium is ~$50. **Any commercial offer must be a first-year commission on the $199 annual (~$60)**, competitive with a TrendSpider monthly — or compete purely on editorial merit. StockBrokers.com's published methodology is hands-on testing with no submission fee, and a permanently published, immutable, back-checked record against SPY is a test artefact none of the ten tools they rank can offer.

**Target educational query shapes, not ticker queries.** Finance AI Overviews fire on **67–91% of educational queries** but only **8% of ticker/price queries** and 11% of tool queries (BrightEdge / Semrush, Nov 2025). So "how do you back-check a stock pick against SPY," "what is a composite stock score," "how is relative strength actually measured" are winnable where `/t/{TICKER}` is not. Lead each with a 120–150 character answer capsule containing no links.

**Do the free citation-gatekeeper fix: put a price as literal text on the homepage.** `frontend/app/page.tsx` currently shows "$0 today" and a "Free · no card" chip but **no subscription figure**. A controlled 252,000-trial study (Vishwakarma, Kumar & Jamidar, arXiv 2605.25517, SIGIR 2026) finds price-present a citation gatekeeper — though read the real numbers before believing the headline: odds ratios span **6.26 to >>10,000**, and four of six models sit well under 100. Treat it as a cheap, low-risk change on general merit, not a 10,000× lift.

**Do NOT "correct" llms.txt from ~2,500 tickers to 11,814.** This recommendation appears in the research and it is **actively dangerous**. 2,500 is the live scoring cap — `ACTIVE_UNIVERSE_SIZE` in `backend/app/services/universe.py:37`, mirrored by `EXPORT_ROW_CAP` — and the public text already qualifies it as "top by daily dollar-volume." 11,814 is the count of *discovered* tickers, a different quantity. Publishing it would overstate product capability on a legal-critical descriptive-only publication. *(The one genuinely stale artefact is an internal docstring in `universe.py` claiming the DB tracks 5,757 tickers.)*

**Cap the programmatic footprint.** Google's spam policies (updated 2026-08-28) define scaled content abuse to include "using generative AI tools... to generate many pages without adding value," and August 2026 spam-update case studies document an ultra-YMYL site losing 200,000+ queries for templated content padded with AI paragraphs. 800 ticker pages backed by proprietary scores is defensible. 11,814 templated pages in a YMYL vertical is the exact pattern being penalised. **Grow only as fast as genuinely distinct per-page data allows.**

### 7.4 The one-hour action worth more than any hour in Ads Manager

**Open Bing Webmaster Tools' AI Performance report.** Shipped 2026-02-10 (public preview): total citations, average cited pages per day, **grounding queries**, page-level citation activity, visibility trend — covering Microsoft Copilot and Bing AI summaries. The only payer in company history arrived on `utm=copilot.com` and **nobody knows which page Copilot cited or on what query.**

It is a separate free property from Search Console (which Zanek has, and which does not report this), and it verifies by import in minutes.

---

## 8. Sequenced plan, with budgets and stop-losses

### This week — 4 to 8 September. New spend: A$0.

| # | Action | Time | Why now |
|---|---|---|---|
| 1 | **Events Manager → tapeline.io dataset → Data Restrictions.** Read, date, screenshot. | 5 min | If `CompleteRegistration` is restricted under Financial Services, the token changes nothing and the plan needs a different event. Appeals take days and resubmit only every 30 days. **Do this before anything else.** |
| 2 | **Ads Manager → Billing: confirm the account currency.** | 5 min | A ~35% swing sits under every number in this document. |
| 3 | **Ads Manager: pull "Unique link clicks" + "Landing page views" for the flight.** Add the placement breakdown. | 10 min | Collapses the three-way disjunction in §2.3. If LPV is under ~50, stop treating A$58 as a CAC. |
| 4 | **Bing Webmaster Tools → AI Performance report.** | 60 min | The only channel that has produced revenue, currently unmeasured. |
| 5 | **Run `billing_audit.py`.** Settle 4-vs-5 carded accounts; read `subscription.status` on the two Facebook rows. | 10 min | `active` and `trialing` are different worlds. |
| 6 | **Card-rule copy fix** (§7.2) on homepage, `/pricing`, `llms.txt`. | 60 min | Live legal exposure — AI summarisers are producing the one claim the project forbids. |
| 7 | **Physical street address into `MarketingFooter.tsx`.** | 30 min | Google FS policy requirement, currently unmet, checked by manual reviewers on finance accounts. |
| 8 | **Fix `docs/PAID_ADS_METRICS_BIBLE.md` line 50** — Meta finance-feed CTR 0.98% is the **third**-lowest vertical (Automotive Repair 0.80%, Physicians & Surgeons 0.83% are lower), not the lowest. | 5 min | A false claim sitting in the house's own canonical reference. |
| 9 | **Write the 12–14 Sep decision rule down, before the result.** | 30 min | See §8.4. |
| 10 | **Five-screen Google audit** (§3.3), as forensics. | 60 min | Learn what A$951 bought. Not a restart plan. |
| 11 | **Let the Meta campaign run to 15 September, as planned.** | 0 min | Corrected 2026-09-05 — see below. |

**~~Why stop on the 7th, not the 15th.~~ RETRACTED — the campaign runs to the 15th.**
The original row said stop end of day 7 September, on three grounds. Two survive as
arithmetic and one was simply wrong:

- *Spend.* Correct as stated — A$215 by the 7th, ~A$310 by the 15th, against a A$350
  kill line. Running on costs **~A$96**, and the line is not crossed either way.
- *"Crosses the 8 September promo revert, making live ad copy false."* **False.** Every
  open-access surface is date-gated through `freeOpenAccess()` and removes itself with
  no deploy. See correction C2 and the retraction in §4.6.
- *"Contaminates the clean pre/post read."* Backwards. The **12–14 September trial
  decisions** are the only conversion events this campaign is likely to produce, and
  they are attributable to it only while it is live. Stopping on the 7th does not
  protect the read — it throws away the read.

A$96 for the one window in which this campaign can produce an attributable outcome is
the cheapest information on the list.

**Freeze the pre/post baseline anyway** in `docs/WEEKLY_LEDGER.md`: signups/day,
card-adds/day, Facebook-referred sessions/day for 27 Aug → 15 Sep (ads on), to be
compared against 16 → 27 Sep (ads off) on identical definitions. Underpowered at 31
accounts, but a pre-registered comparison beats an argument in three weeks about what
the baseline felt like. **Write the comparison rule before the ads stop, or hindsight
will write it.**

**Also this week, if a payer reply is authorised:** email `llegrandconsulting` and `avasmom8723` one question — *"what were you doing when you first came across Tapeline?"* n=2 with a direct answer beats n=2 with a dashboard guess. **These are live paying customers; get the founder's explicit authorisation before sending.**

### Next 30 days — 8 September to 8 October. Paid budget: A$0.

The gate is not met, so no paid runs. Founder hours go where the evidence points:

1. **Third-party listicle placement** (§7.3). Pitch StockBrokers.com, Liberated Stock Trader, Koyfin's blog and NerdWallet on the immutable back-checked record. Lead with editorial novelty; hold the ~$60 first-year annual commission in reserve. **~12 hours.**
2. **Four educational pieces** on the 67–91% AIO-triggering query shapes, each opening with a 120–150 character answer capsule. **~12 hours.**
3. **Ship the three code fixes** so the next flight is not blind: `event_source_url` at all four call sites; contracted-subscription value instead of `amount_total` in `_send_purchase_conversion`; `GRAPH_API_VERSION` bump. **~4 hours.**
4. **Ask Meta support in writing** whether a descriptive analytics publication with no transaction capability requires the Financial Products & Services category. Keep the answer. **~1 hour + wait.**
5. **The five-minute phone test:** tap the live ad (or a `?fbclid=` decorated link) on an iPhone and try Google OAuth inside the Facebook in-app browser. **Unresolved, high-stakes, and cheap.**
6. **Record the promo-revert natural experiment.** Card rate for AI-referred and organic signups, 8 Sep before and after. Free.
7. **Build the all-site-visitors Custom Audience** so the retention clock starts.

**Stop-loss for the month:** if any paid spend occurs at all outside the A$5/day brand-terms exception, it is off-plan.

### Next 90 days — to early December. Conditional paid budget: A$0 or A$1,260.

**The gate review happens at day 90 against `PAID_MARKETING_PLAYBOOK.md` §4** — ≥10 organically-acquired payers retained 60 days, click→trial ≥15% measured, LTV:CAC ≥3, a message proven organically, and ~A$1,800 committable without stress.

**If the gate fails** (the likely case at current run rate): paid stays at A$0. Continue AEO, listicles, and building something above $199 — Team, Enterprise, or Founder's Lifetime. Per MarketWise's own filings, that is what makes paid acquisition possible in this category, and it changes the arithmetic more than any campaign decision here.

**If the gate passes**, the first dollar goes to **Microsoft Ads, not Google or Meta**: finance CPC ~US$1.54–1.82 against Google's US$3.39, no US financial-services verification, and Copilot placements bundled automatically with search campaigns — directly extending the one channel that has produced a payer.

**If Meta is retried instead**, it must be one honest test, not a trickle:
- **One ad set, A$60/day minimum, optimising Landing Page Views** (Meta's own documented fallback below 50 conversions/week; the derived requirement is ~A$60/day).
- **Minimum 21 days uninterrupted = A$1,260.** Batch every change into one edit and then do not touch it: changing the optimisation event, editing creative, and adding an ad are each independently a "significant edit" that resets learning.
- **All three copy angles as text options inside one ad**, not three ads.
- **Selling Premium annual $199 explicitly**, with the destination being the annual checkout, not `/signup?from=trial`.
- **URL macros stamped** (`{{campaign.id}}`, `{{adset.id}}`, `{{ad.id}}`, `{{placement}}`) so a bare `utm_source=facebook` means organic from that point on.
- **`META_CAPI_ACCESS_TOKEN` set and verified via Test Events** — after items 1 and 3 above, not before.

**If A$1,260 is not available, the correct answer is not "spend less." It is "do not test."** A trickle test is the worst option on the board: it costs money and yields nothing decidable.

### 8.4 Stop-losses, written down now

| Trigger | Action |
|---|---|
| Any future Meta flight reaches A$400 with <150 landing page views | Stop. The traffic to cause a conversion did not exist. |
| Cost per registration exceeds ~A$70 after 100+ link clicks | Stop. (Pre-registered as ~$50 in `PAID_ADS_METRICS_BIBLE.md` §7.7; widened for the AUD reading.) |
| Data-sharing restriction appears on the dataset | Stop. Different event needed; the token is irrelevant. |
| Google brand-terms campaign reaches A$150 with 0 signups | Pause. Go back to the page and the offer, not the bids. |
| Any gated Google campaign reaches A$500 with 0 trial signups | Pause. Do not touch bids. |
| Ads Manager reports "Results = —" | **Not a kill signal.** That is a measurement failure, not a performance failure. |
| The database shows 2 payers | **Not a scale signal.** The interval reaches A$511 per card and realised revenue may be $0. |

### 8.5 The 12–14 September decision rule — commit to it before the result

Three Premium trials decide on 12 and 14 September (2× annual $199, 1× monthly $19.99). Blended day-one net is US$134.45 per converting trial, so the actual pending mix breaks even at **29.9%** — right on the ChartMogul median. The coin-flip line, not a comfortable margin.

At a healthy 30–35% conversion rate, **P(all three fail) is 27–34%.** Expected converted payers is ~0.9–1.3.

> **0 of 3 = weak evidence, fully consistent with a healthy underlying rate. Do not read it as a verdict on Meta.**
> **1 of 3 = exactly on plan.**
> **2+ of 3 = above benchmark.**
>
> And in every case: **RevenueCat reports ~35% of annual cancellations occur in month one.** Budget for the headline number to overstate kept revenue by 20–30%, and do not count a conversion as retained until 30 October.

**The symmetric warning.** If the trials convert at benchmark, Meta will have produced roughly one payer for A$123 and the temptation to scale will be enormous. **Resist it on exactly the same statistical grounds that make zero conversions unalarming.** One result cannot narrow a A$17–A$511 interval.

---

## 9. What would make this recommendation wrong

Each item names the specific observation that would flip it.

**1. Keyword Planner returns US$1–2 top-of-page bids on comparison long-tail.**
This is the single most likely thing to overturn the Google recommendation, and it is checkable free today. At US$1–2, an exact-match campaign on "[competitor] alternative" terms at A$15/day becomes defensible on arithmetic rather than hope. **I have deliberately not estimated these CPCs** — the industry Finance figures are insurance-and-lending averages and are poor proxies for a software query. *Flips: §3.1's "stays off," to a capped exact-match test.*

**2. The Ads Manager landing-page-view count comes back above ~150.**
That would establish the traffic to plausibly cause two payers, meaningfully raise confidence that A$58 is a real cost per card, and make Meta's continuation a live question rather than a closed one. Under ~50 and the A$58 number should be abandoned entirely. *Flips: the confidence in §2.3, in either direction.*

**3. Meta support confirms Tapeline is out of Special Ad Category.**
This restores age targeting, interest targeting, interest exclusions and Lookalikes in one change — by a wide margin the largest available lever, and it changes the CPM outlook materially. *Flips: §4.4's "the ad copy is the targeting," and possibly the entire Meta economics.*

**4. Google OAuth is broken inside Meta's in-app browser on iOS.**
If the five-minute phone test comes back broken, every dollar of Meta spend on iOS has been buying clicks into a dead end on the only auth path that has ever produced a payer — and none of the CPM, creative, or economics analysis in this document is the explanation for anything. *Flips: the diagnosis of the whole Meta flight.*

**5. Three of three trials convert on 12–14 September and are still active on 30 October.**
That is roughly 3 payers from A$123, which sits at the favourable extreme of the Poisson interval rather than outside it — but combined with a landing-page-view count above 150 and one payer tied to a paid click, it would satisfy two of the three pre-registered continuation conditions. *Flips: the "stop the campaign" recommendation, at the next flight rather than this one.*

**6. Tapeline sells one Team, Enterprise, or Founder's Lifetime seat.**
At $149/mo, $2k/mo, or $399 once, the CAC ceiling stops being the binding constraint and the entire MarketWise analogy loosens. **This is the change that most improves paid-acquisition viability, and it is not a paid-acquisition action.** *Flips: §2.5's structural argument.*

**7. The account currency turns out to be USD, not AUD.**
Then the CPM is A$157-equivalent, every cost per card is ~35% worse than stated, Premium annual break-even moves from 20.9% to ~32%, and the only remaining viable plan becomes marginal too. *Flips: §2.4's conclusion that any plan closes.*

**8. The two Facebook-attributed accounts turn out not to have come from paid clicks.**
Then Tapeline does not have an expensive CAC — it has **no measured CAC at all**, and every economic conclusion in §2.4 is void rather than uncertain. *Flips: everything downstream of A$58.*

**9. The organic channel produces 10 retained payers.**
The gate passes, and the entire "do not spend" posture becomes obsolete on its own terms. *Flips: §8's 90-day plan into the Microsoft Ads build.*

**What would NOT change the recommendation, and why:**
- More favourable finance CPM benchmarks. The CPM is not the binding constraint; volume is.
- Better creative. CTR is already 2.4× the finance-feed benchmark — though note the implied CPC of ~US$2.84 is ~2.3× the same source's US$1.22 benchmark, so **the CTR advantage and the cost disadvantage cancel exactly.** There is no established click-level outperformance to build on.
- A single trial conversion. See §8.5.

---

## 10. Open questions and unverifiable claims, marked as such

### 10.1 Numbers I refused to invent

- **Actual CPCs for Tapeline's keywords.** No reliable public CPC exists for "stock screener" or "stock scanner." Keyword Planner is the only answer. **Not estimated.**
- **Any Special Ad Category cost penalty.** The circulating "23% higher CPM" figure is **not in the megadigital.ai article it is attributed to** (fetched and checked). The "15–30% higher CPL" traces to one real-estate agency blog with no methodology, sample or period. **No platform-official figure, no large-n study, no peer-reviewed work exists.** Anyone quoting a SAC penalty percentage is quoting nothing.
- **Finance-vertical Meta CPM.** Two secondary summaries of the *same* Triple Whale dataset report US$29.16 and US$45.00. Other 2026 blogs give US$18.00, US$18–22, US$28.40. Triple Whale's primary page returns HTTP 403. **Use the range US$18–45, never a single number.**
- **The 70–90% click-to-LPV "normal" band.** Its only traceable source is Tapeline's own `PAID_ADS_METRICS_BIBLE.md` line 68 — the one ungraded, unsourced, undated row in that table. **It is folklore, and it has been circulating back as external corroboration.**
- **"Opt-in trials convert at 8.9%, card-required at 31.4%, per ChartMogul."** Misattributed. Neither figure appears in that report. Its actual numbers are 30% median with 25–35% / 50–60% bands. **The 8.9/31.4 pair traces to a single blog that links the report refuting it.** Do not use it.
- **"Google's 10-clicks-per-day minimum" and "daily budget = 10× CPC."** Google publishes no minimum Search budget. These are practitioner heuristics with no cited study. The arithmetic intuition is sound; the numbers have no authority. *(Note: `PAID_MARKETING_PLAYBOOK.md` finding #2 carries the 10×CPC rule as a sourced item. It is sourced to an agency blog, not to data.)*
- **"1 ad set × 25 creatives beat 5 × 5 by +17% at −16% cost."** No primary source exists. Meta's own engineering post publishes +6% retrieval recall and +8% ad quality on selected segments — a segment-level metric, not advertiser ROAS.
- **"Pixel + CAPI dedup recovers 20–30% of lost conversions."** Traces to tooling vendors, not to Meta or any study. Excluded.
- **"MARS" / "Multimodal Ad Review System."** Appears only in 2026 SEO blogs with no Meta announcement or documentation. Several show signs of AI generation. **Do not act on it.**

### 10.2 Internal facts that contradict each other and need one query to settle

- **4 or 5 carded accounts?** The verified-facts brief and `META_LIVE_CAMPAIGN_ADDENDUM.md` §1.1 both say 4; one internal analysis says 5. `billing_audit.py` settles it.
- **7 or 2 AI-referred signups?** The brief says 7 from chatgpt.com/copilot.com; `backend/app/routers/mcp.py` records 2. The larger figure mixes referrer capture with a self-report dropdown, over a ~4-week window, against an all-time denominator. **Publish the count and the payer, never the percentage.**
- **Was the Google campaign ~500 clicks or ~180–280?** §2.2(c)'s statistical conclusion depends entirely on this. `PAID_MARKETING_PLAYBOOK.md` line 9 says ~500 at ~A$1.90 CPC; the research digest derived 180–280 from a benchmark CPC. **If it was 250 clicks, zero signups is a weak null; if 500, it is strong evidence the post-click experience failed.** The Google Ads account holds the answer.

### 10.3 Genuinely unresolved

- **Does Meta's in-app browser trip Google's OAuth webview block?** Google's policy is unambiguous — *"Android and iOS webviews are not supported for user sign-in"* — but Meta documents its in-app browser behaviour nowhere (both relevant URLs 404), Google publishes no blocklist, and Meta's behaviour has changed repeatedly since 2021. **Answerable only on a phone.**
- **Must a descriptive analytics publication declare Special Ad Category?** Meta's restricted-goods standard exempts informational content with no ability to transact; multiple practitioner sources disagree about the January 2025 expansion's scope; Meta's own help page is JavaScript-rendered and unretrievable. **Ask Meta, do not infer.**
- **Is the learning threshold 50 events per week or 10 in 3 days?** Multiple sources report a June 2024 reduction to 10-in-3 for Purchase campaigns while the UI still shows 50. **No Meta primary source confirms the 10-event figure.** It does not matter here: even the favourable reading needs A$130–195/day, still 5–8× current spend.
- **Does the trial-length gradient transfer?** RevenueCat's 17pp advantage for 17–32 day trials is the only large-n evidence, it is not monotonic (5–9 days beats 10–16), it is app-store card-on-file rather than web card entry, and it is a cross-app correlation among apps that self-selected their trial length. **Lengthening 14 → 21 days is a cheap hypothesis, not an established effect** — and if tested, the auto-renew disclosure must stay explicit. US state automatic-renewal laws still bind even though the FTC's click-to-cancel rule was vacated by the Eighth Circuit on 8 July 2025.
- **Whether the US recognises an equivalent publisher exclusion.** Google will let Tapeline advertise into the US without checking anything — its policy says *"you must comply with state and local regulations for any location that your ads target"* and verifies nothing outside the FSV countries. **Passing Google's review is not evidence the US position is sound.** That is a Holley Nethercote question, alongside the sharper one already in `META_GO_LIVE.md` §10: whether paid, audience-targeted advertising changes the publisher-exemption analysis at all.

### 10.4 What I could not find, which is itself informative

**No named, verifiable case of a sub-$250-ARPU investing or fintech subscription profitably scaling on Meta or Google.** The verified successes at ~$200 ARPU are Squarespace (FY2023: ARPUS $228.02, 4.63M subscriptions, 34.5% of revenue on marketing and sales, +$83.7M operating income) and Wix (FY2025: advertising at 9–12% of revenue, and its 20-F states it *"significantly reduce[d] investment in acquisition marketing, which has meaningfully improved return"*). Neither is fintech; both had large brands and multi-year retention before the paid spend worked. Duolingo's 10-K states it deliberately does not rely on performance marketing.

**Absence of evidence found in one research pass is not proof of non-existence.** But the pattern — Dropbox killing paid search at $233–388 CPA on a $99 product, MarketWise at 1.3–2.0× LTV/CAC on $1,120–2,031 lifetime billings, zero of eight comparable scanners growing on early paid search — is consistent enough that the burden of proof sits with spending, not with holding.

---

*Nothing in this document is legal advice. §3.4, §4.5 and §10.3 are platform advertising policy — private rulebooks, not securities law. All AUD/USD conversions assume ~0.65 and were not verified against a live rate; a 10% FX move shifts every ceiling by 10%. Gross margin assumed ~95% marginal and payment fees ~3.5%, neither verified against Tapeline's Stripe statements. All repo claims reflect the working tree on branch `fix/false-crypto-fx-claim` as of 2026-09-04.*
```