# Meta live campaign — addendum

> ## ⚠️ CORRECTION BLOCK — READ BEFORE §1. THE BODY BELOW IS PARTLY BUILT ON A FALSE PREMISE.
>
> This document was drafted on the belief that **Meta had received zero conversion events because
> the browser pixel fires `PageView` and nothing else**. That was checked against the repo after
> drafting and is **wrong**. Corrected 2026-09-02 by direct verification:
>
> **1. A browser-side `CompleteRegistration` HAS been firing since 2026-08-27.**
> `frontend/lib/metaConversions.ts` (PR #652, commit `99c3b32`, 2026-08-27) exports
> `trackMetaCompleteRegistration`, called at `frontend/app/signup/page.tsx:487`. It is deduped
> against the CAPI copy via an `event_id` that mirrors `meta_capi.event_id_for("signup", user_id)`.
> `NEXT_PUBLIC_META_PIXEL_ID` is set in `frontend/fly.toml` and the pixel id is present on the live
> `/signup` page. So the pixel is **not** PageView-only, and every statement in the body to that
> effect is superseded. Any recommendation below to "add a browser event" is already done —
> **do not re-add it, that would double-count.**
>
> **2. The ads DID produce registrations, and the evidence is stronger than `utm_source` alone.**
> Three accounts created since the 2026-08-27 launch carry a non-null **`signup_fbclid`** — the
> Facebook click identifier — *and* `utm_source=facebook`: `ericahelms76` (27 Aug, free),
> `llegrandconsulting` (29 Aug), `avasmom8723` (31 Aug). §1.2's caution that "an `fbclid` can come
> from an organic link" stands in general, but the **combination** of an `fbclid` with the ad's own
> `utm_source` is a far better paid-click signature than either alone. Seven accounts signed up in
> that window; three carry it.
>
> **3. So the real anomaly is the opposite of the one this document set out to explain.**
> Not "Meta is blind because nothing is wired" — the browser event is wired, deployed, and firing,
> and the ads produced ~3 registrations — yet **Ads Manager still reports zero results.** The
> likeliest explanation is that the browser event is not surviving for these particular users
> (tracker blocking is heavy in this audience — the original rationale for building CAPI at all in
> #538), with attribution-window and reporting lag as lesser candidates. **CAPI remains the correct
> top action**, but as the *redundant server-side path* for an event that is demonstrably being
> lost client-side — not because nothing is instrumented.
>
> **4. Neither Facebook account has paid yet.** Both are on card-required trials
> (`trial_ends_at` 2026-09-12 and 2026-09-14). The only payment ever collected is $9.99 from
> `yankeezz2828`, who came from **copilot.com**, not Meta. §1.2's fourth discount was right.
>
> **5. Derived costs, in the account's reported unit** (see the currency warning below — very
> probably AUD): ~49/registration (146.86 ÷ 3) and ~73/Premium-trial-start (÷ 2). **Not** cost per
> payer: no Meta-sourced payer exists yet. The Poisson caution in §1.2 applies unchanged — n=3 is
> still weak.
>
> Sections **5 through 8** (2026 product changes, the Ad Library read, what real payers unlock, the
> organic-to-paid bridge) are **unaffected** by this correction and stand as written.


*Written 2026-09-02, six days into a live flight. **This document covers only what the existing Meta docs do not.** It does not re-argue the go/no-go case (`META_ADS_DECISION.md`), the FPS policy basics (`META_ADS_DECISION.md` §3), the campaign blueprint or creative system (`META_SAAS_ADS_PLAYBOOK.md`; `PAID_ADS_METRICS_BIBLE.md` §7.2–7.3), the runbook (`META_GO_LIVE.md`), or the metrics tree (`PAID_ADS_METRICS_BIBLE.md` §2). Those stand. This addendum exists because live Ads Manager and production-DB data post-dates all four and contradicts a premise they share: that the pre-spend checklist would be completed before the first dollar. It was not — `PAID_ADS_METRICS_BIBLE.md` §7.5 item 4 (set `META_CAPI_ACCESS_TOKEN`) was skipped, and the campaign has been running a conversion objective with zero conversion events for its entire flight.*

*Evidence grades, as in the standing docs: **A** controlled / replicated · **B** large independent dataset · **V** vendor documentation or vendor telemetry · **C** practitioner consensus · **D** single case or modelled inference · **E** folklore. `[unverified]` = not confirmed at a primary source. Where this document downgrades a grade used in a source doc or a research sweep, it says so.*

> **Currency discipline — read before quoting any number below.** The account bills **A$25/day**. The flight has run since 2026-08-26/27, i.e. six to seven days, and Ads Manager reports spend of **146.86**. Six days at A$25 is A$150; the same spend in USD would imply roughly nine days at the stated budget, which is more days than the flight has existed. **The figure is therefore very probably AUD (D — arithmetic on the account's own numbers, not a confirmed setting).** Every derived figure below is given in the account's reported unit first, with the USD reading at ~0.655 in brackets. **Confirm the account currency in Ads Manager → Billing before any of these numbers leaves this file.** If it is AUD, every USD figure circulating from the research sweeps is ~35% too high — `PAID_ADS_METRICS_BIBLE.md`'s preamble already warns that the AUD-at-par error "silently flatters every reach and cost-per-registration forecast by ~35%", and this is that error arriving from the other direction.

---

## 1. The finding that reframes the file

### 1.1 What is proven

Direct observation, Ads Manager and production DB, 2026-09-02:

| Fact | Value | Grade |
|---|---|---|
| Campaign "Tapeline - message test (US, FPS)" | ACTIVE, ad account 274761096383152, pixel/dataset 28351455154543230 | A |
| Spend | 146.86 (≈US$96 if AUD) | A |
| Reach / frequency | 1,054 / 1.34 → **~1,412 impressions** | A |
| Attribution setting shown | 7-day click, 1-day view | A |
| Optimisation event | "Website completed registration" (`CompleteRegistration`) | A |
| Results reported by Meta | **"—" (zero)**, flagged "Low results" | A |
| `META_CAPI_ACCESS_TOKEN` on Fly | **never set** → `services/meta_capi.py` is a silent no-op | A (repo + Fly) |
| Browser pixel event coverage | `PageView` only, `/app` excluded (`components/MetaPixel.tsx:74`) | A (repo) |
| Accounts with `stripe_customer_id` | **4**, up from 0 in mid-August | A |
| Facebook-attributed in the DB | **2**: `llegrandconsulting@gmail.com` (`utm_source=facebook`, Premium, 2026-08-29) and `avasmom8723@gmail.com` (referrer `m.facebook.com`, `utm_source=facebook`, Premium, 2026-08-31) | A |
| The other two | organic: `yankeezz2828` (`utm=copilot.com`, Pro), `billydone` (`accounts.youtube.com`, Premium) | A |

**The mechanism behind the zero.** `CompleteRegistration`, `StartTrial` and `Purchase` are sent **server-side only**, by `services/meta_capi.py`. The browser pixel deliberately fires `PageView` and nothing else, scoped off `/app` so it cannot report which tickers a user views — a design `PAID_ADS_METRICS_BIBLE.md` §7.1 correctly calls load-bearing, and which §7 below argues is now also a compliance asset. With the token unset, every conversion helper returns `False` before it builds a payload. **Meta has therefore received zero conversion events for the entire flight and has been optimising a conversion objective blind.**

### 1.2 What is inferred, and how weakly

That the ads caused the two Facebook-attributed payers is **not proven**. Four independent reasons to hold it loosely:

1. **`fbclid` and a Facebook referrer do not mean "paid".** Unlike Google's `gclid`, Meta appends `fbclid` to organic outbound links as well as paid ones, and `m.facebook.com` / `l.facebook.com` only says "Facebook mobile web" (C — Northbeam docs and link-shim explainers, 2025–26). If the published ad URLs carry only `utm_source=facebook` with no campaign or ad token, a hand-shared link is indistinguishable from a paid click in the DB.
2. **The click volume may not support it.** ~1,412 impressions at a 1–2% link CTR implies only ~14–28 link clicks (**D — modelled, not observed**; the CTR is assumed, not measured). A cold funnel at 3% visit→signup and 20% signup→card would expect 0.08–0.17 payers from that traffic, against two observed. Either the reach and frequency figures cover a shorter window than the spend, or landing-page views are far above that CTR assumption, or the two payers reached a Facebook-referred page some other way. **One free number in Ads Manager — "Landing page views" and "Unique link clicks" for the flight — collapses this three-way disjunction.**
3. **Two events cannot separate a good campaign from a terrible one.** The exact Poisson 95% interval on an observed count of 2 is [0.242, 7.225] events, so true cost-per-payer sits anywhere in **~20 to ~607 in the account's currency** (≈US$13–397 if AUD). The point estimate of ~73 (≈US$48 if AUD) and `META_ADS_DECISION.md` §4's most-generous US$164 both sit comfortably inside that interval — and so does a number that closes the channel outright.
4. **The money may not exist yet.** CLAUDE.md's 2026-08-30 reconciliation found three Stripe customers — one `active`, two `trialing` — and exactly one paid invoice of $9.99, which maps to the Pro account (`yankeezz2828`), **not** to either Facebook-attributed Premium account. If those two are the `trialing` rows, Meta has produced $0 collected and $39.98 of contingent MRR whose first charges land around 12–14 Sep. At the card-required trial→paid rate already in `PAID_ADS_METRICS_BIBLE.md` §2.4 (ChartMogul 31.4%, V, 200 products — First Page Sage's 48.8% is a wide outer bound from a vendor page with no published methodology), expected realised value from those two is roughly half to two-thirds of one payer: **$10–20 of first-month revenue against 146.86 spent.**

**What would raise confidence, in descending order of value per hour:** the four checks in §4. Three of them are free and take under an hour combined.

### 1.3 What the standing docs got right, and stays right

- **The event architecture.** All three events are wired to the correct triggers; `fbc` is rebuilt server-side in the correct `fb.1.<ms>.<fbclid>` wire format; `fbc`/`fbp` go unhashed; `signup_fbclid` capture shipped (`frontend/lib/utm.ts`, `models/user.py:317`) — **gap G4 in `PAID_ADS_METRICS_BIBLE.md` §7.1 is closed**, which that document did not know when written.
- **The privacy scoping** of `MetaPixel.tsx`. §6.2 adds a second, independent reason to keep it.
- **"Plan to live in Learning Limited permanently"** (`PAID_ADS_METRICS_BIBLE.md` §7.2). §2 shows this was optimistic, not pessimistic.
- **"The DB is ground truth"** (§2 reading rule 1). It is the only reason anything is known about this flight at all.
- **Descriptive copy is not the constraint.** §6 finds the live US auction carries far more aggressive registers than Tapeline's, running for 90–395 days, with disclaimers attached and no visible delivery penalty. The zero is the missing conversion signal, not the copy.

### 1.4 What needs revising

| Standing claim | Where | Revision |
|---|---|---|
| "The 14-day trial puts `Subscribe` / `Purchase` outside Meta's 7-day-click window **by construction**" | `META_ADS_DECISION.md` §5; `META_GO_LIVE.md` §3; `PAID_ADS_METRICS_BIBLE.md` §2.1, §7.1, §7.4 | **Wrong about the shipped code, right about the outcome, wrong about the reason.** `_send_purchase_conversion` (`routers/webhooks.py:76`, called only from line 319) fires `Purchase` on **`checkout.session.completed` — day 0**, inside the 7-day window. Nothing fires at the day-14 charge. The real defect is the opposite: a trial checkout has `amount_total = 0`, so Meta receives a Purchase worth **$0.00**, and the first real invoice is never reported at all (`invoice.payment_succeeded`, line 1003, only handles dunning). The Purchase and ROAS columns read zero because **no value is ever sent**, not because of the attribution window. The fix is "send the subscription's contracted value, not `amount_total`", not "Purchase is unattributable". |
| "Expect EMQ ~5–6 with today's email + `external_id`-only matching" | `PAID_ADS_METRICS_BIBLE.md` §2.3, §7.1 | Predates the shipped `fbclid` capture. Meta's customer-information priority table (V) rates **email HIGH and click ID (`fbc`) HIGH**; `fbp`, `external_id`, phone and country are Medium. Tapeline sends both HIGH-priority parameters wherever `signup_fbclid` was captured, so the expected posture is **Good**, not floor. Read the real figure at +48h; if it is under 6 the cause is coverage (OAuth signup and both webhook paths carry no `fbp`), not hashing. |
| "1 ad set × 25 distinct creatives beat 5 × 5 by +17% conversions at −16% cost" | `PAID_ADS_METRICS_BIBLE.md` §7.2 (cited secondhand, C) | **No primary source exists for this test.** Neither do the widely-circulated Andromeda figures ("+22% ROAS", a 6–8 → 2–4 week creative-lifespan compression, an October 2025 global rollout). Meta's own engineering post (2024-12-02, V) publishes only **+6% retrieval recall and +8% ad quality on selected segments**, plus latency and throughput gains — and that +8% is a segment-level ad-quality metric, not advertiser ROAS. Treat the consolidation principle as sound and the numbers as unsourced. Note the practical inversion at this budget: Tapeline already has an ad publicly flagged "Low impression count / <100 impressions" (§6.1), so **more creatives here means more starvation, not more learning.** |
| The competitor benchmark set (Finviz / TradingView / Trade Ideas / Koyfin as the reference class) | `META_ADS_DECISION.md` §6; `PAID_ADS_METRICS_BIBLE.md` §8 | A 2026-09-02 Ad Library sweep found no owned US ads for any of them — **but that sweep used exact-phrase keyword search, which matches ad body text rather than advertiser identity and is not a valid coverage check** (the "tradingview" query returned ~350 matches, none of them from TradingView). **Regrade D-inference**; re-check by page (§6.3) before relying on it. The positive observations in §6 are unaffected. |
| "$650–2,500 per payer; most generous ~$164" | `META_ADS_DECISION.md` §4 | Not overturned — see §9.1. The observation sits below the range, and its confidence interval spans it. |

---

## 2. Conversion-blind delivery: what it cost, and what it did not

**Meta publishes a document for exactly this failure mode**, titled for what to do when an ad is predicted to get zero conversions (Meta Business Help, V). Three of its statements matter here:

- **The volume rule.** "When maximising the number of conversions, we recommend choosing one that happens about 50 times per week at a minimum. Our system needs that many to learn from." Its first ranked remedy is *choose a more common conversion*; its second is *optimise for landing page views*.
- **The window rule.** "In order for a conversion to count towards your 50, it has to happen within your chosen attribution setting." (Relevant to §5, not to the current zero.)
- **The bidding rule.** Meta says an uncapped highest-**value** strategy is unlikely to be the cause of zero conversions, "because our system will bid higher as needed to spend your budget." Applying that to Highest Volume is a **reasonable extension, not a Meta quote** — both are uncapped pacing strategies obligated to spend. It is the mechanism behind 146.86 spent against Results = "—": nothing throttles a signal-less conversion campaign. **The founder's A$350 kill line is the only brake in this system.**

**The budget arithmetic, taken from the robust direction.** A$25/day × 7 = A$175/week, so exiting learning on `CompleteRegistration` requires a CPA of **≤ A$3.50**. At a plausible cold FPS registration cost of US$15–60 the shortfall is roughly **5–20×**, depending on which Meta budget heuristic is applied. (A widely-quoted "daily budget ≥ 10× your performance-goal cost" rule could not be corroborated at a primary source; the multiplier that does surface in current Meta budget guidance is 5×, and it attaches to cost-per-result-goal bidding. The 50-events rule is the one to rest on.) **Setting the token fixes blindness. It does not fix this.** `PAID_ADS_METRICS_BIBLE.md` §7.2 already says to plan for permanent Learning Limited; the correction is that the account was not merely under-fed, it was **unfed**, which is a different and more expensive state.

**What blind delivery appears to have cost.** Implied CPM = 146.86 ÷ 1,412 × 1,000 ≈ **104** in the account's currency (**≈US$68 if AUD**), and ~0.14 per person reached. Published 2026 Meta benchmarks for the same measure span roughly **$11–23 all-industry** and **$18–45 finance**, across at least eight compilations that disagree with each other by a factor of four (B/C — Superads, WordStream/LocaliQ, AdManage, DigitalApplied and others; none authoritative, and one of them puts Meta finance CPC at $1.22 while another puts it at $3.77 for the same platform and period). So: **somewhere between roughly 1.5× and 6× high, depending on the compilation and on the currency answer** — a range, not a verdict. The arithmetic is A-grade; the benchmark comparison is C-grade at best. Before treating it as real, confirm that reach, frequency and spend are drawn from the same date window, and pull the CPM and impressions columns directly rather than deriving them.

**What blind delivery did *not* cost: a permanent handicap.** Meta states that "Learning limited isn't a penalty", that an ad set moves back to Active once it receives enough optimisation events since the last significant edit, and — on its ad-delivery page — that the system "uses predictions of future performance to determine where to deliver next, not each ad set's past performance" (V). **There is no accumulated demerit to escape.** The argument for burning this ad set and starting clean has no mechanism behind it. This is the single most decision-relevant finding in the whole sweep.

**Why "let the AI figure it out" is not available.** Meta's published gains from its 2025–26 ranking work are single-digit and multiplicative on the signal supplied: the Generative Ads Model reports **+5% ad conversions on Instagram and +3% on Facebook Feed** (Meta engineering, 2025-11-10, V). Its July 2026 research post concedes the underlying problem directly — deep-funnel user feedback is scarce, so Meta substitutes multimodal creative-content features to extend supervision (V; no conversion-lift numbers published). Three to five percent of zero is zero. That same post is, however, the strongest available support for the standing "creative is the targeting" doctrine: **while conversions are dark, the semantic content of the creative and the landing page is the only signal Meta has.**

---

## 3. The recovery decision

Three options were on the table: **(a)** set the token now, mid-flight, in the running ad set; **(b)** duplicate into a fresh ad set with signal from day one; **(c)** let the burst finish on 8 Sep and restart clean.

**Take (a). It dominates.**

**Why (a) is safe.** Meta's published list of significant edits that re-enter the learning phase is: any change to targeting; any change to ad creative; any change to the optimisation event; adding a new ad to the ad set; pausing the ad set for seven days or longer; changing bid strategy; and magnitude-dependent changes to budget, bid or spend cap (V). Setting a Fly secret touches no ad set field — it is a backend environment change plus a dataset that starts receiving events. **A reset is therefore unlikely, but Meta does not present that list as exhaustive, so this is an inference about Meta's internals rather than a vendor guarantee.** Say it that way to the agency.

**Why (b) is now the worst option.** Duplicating an ad set *is* a reset by construction (new ad set, no history), it abandons whatever delivery signal the original accumulated, and with one campaign and one ad set it would put two Tapeline ad sets into the same US auction bidding against each other (C — practitioner tracking, 2026-08). A duplicated *creative* also does not get a fresh start: fatigue attaches to how many times a person has seen the underlying visual and message, not to the ad ID (C).

**Why (c) preserves nothing.** "Pausing your ad set for seven days or longer" is itself on Meta's significant-edit list (V). If the burst ends 8 Sep and the next flight starts more than a week later, the ad set restarts cold regardless. Option (c) buys zero structural advantage and costs six more days of blind spend (~A$150).

**The forcing function is a deadline, not a preference.** Meta's server-event spec is explicit: *"The `event_time` can be up to 7 days before you send an event to Facebook. If any `event_time` in data is greater than 7 days in the past, we return an error for the entire request and process no events"* (V — Conversions API server-event parameters; **regraded from A-tested to V-vendor**, since it is a documentation citation, not a test). So:

- `llegrandconsulting`, signed 2026-08-29 → **last sendable 2026-09-05** (3 days left)
- `avasmom8723`, signed 2026-08-31 → **last sendable 2026-09-07** (5 days left)

After those dates Meta can never be told those registrations happened. Note the **atomic** failure mode: one event older than 7 days rejects the whole request, so any replay must filter by `created_at` before sending.

**The honest cost of (a): it contaminates the natural experiment.** §4.6 recommends treating the scheduled 8 Sep stop as a free pre/post read. Turning CAPI on mid-flight changes the treatment inside the window, so that read becomes "blind ads, then signal-fed ads, then no ads" rather than a clean on/off. That is a real loss and it belongs in writing. It is outweighed by the backfill deadline, by six days of otherwise-blind spend, and by the fact that at this budget the optimiser will not meaningfully change behaviour in six days anyway (§2).

**Order of operations, this week:**

1. **Check Events Manager → the tapeline.io dataset → Data Restrictions *first*.** Meta classifies domains into restricted categories including Financial Services, with a "core setup" tier (custom parameters and specific URL data blocked; standard-event optimisation still allowed) and an "event blocking" tier (optimisation toward specific lower-funnel events removed). Sources conflict on whether Financial Services can reach the blocking tier (C — Twigeo 2025-04-08 says core-setup only in the US and EU; other vendors disagree), which is precisely why this is a five-minute check rather than a research question. Meta states the Conversions API is not a way around a restriction. `PAID_ADS_METRICS_BIBLE.md` §7.5 item 8 recorded "Core setup: Off" on the fresh dataset **before any events flowed** — take the authoritative re-read now, dated, and screenshot it. **If `CompleteRegistration` is restricted, the token changes nothing and the plan needs a different event.** Appeals go via Request Review, take days, and can be resubmitted only every 30 days.
2. **Ship the two code fixes on `fix/meta-capi-token-and-visibility` before the token is set.** Both are small, and both are silent-failure classes:
   - **`event_source_url` is required for CAPI website events** when `action_source` is `"website"` (V). The parameter exists in `send_event` (`meta_capi.py:212`) but defaults to `None`, and **no call site passes it** — `auth.py:537`, `oauth.py:780`, `webhooks.py:187`, `webhooks.py:534`. Event Match Quality is also only computed for website-source CAPI events. One line per call site (`https://tapeline.io/signup` for registration; the billing path for trial and purchase).
   - **Bump `GRAPH_API_VERSION`.** `meta_capi.py:110` pins `v21.0`, which Meta retires **2027-01-21**; current is v26.0 (V). It works today, so this is not a blocker — but it is a dated landmine on the only conversion feed, and the file is already open on this branch.
3. **Set `META_CAPI_ACCESS_TOKEN`** (`scripts/meta-capi-golive.ps1` wraps it). Use a system-user token, which does not expire.
4. **Verify with `META_CAPI_TEST_EVENT_CODE`, then unset it** — the existing runbook step; the service already logs a warning while it is set.
5. **Replay the flight cohort inside the deadline.** A new script in `backend/app/scripts/`, modelled on `upload_google_ads_conversions.py`, sending `CompleteRegistration` (and `StartTrial` where `trial_started_at` is set) for every account created since 2026-08-26, with the true `event_time`, `action_source="website"`, `event_source_url` on a public URL, hashed email, hashed `external_id`, and the server-rebuilt `fbc` where `signup_fbclid` is populated.
   > **What the replay cannot carry, corrected against the code:** `send_event` has **no `client_ip_address` or `client_user_agent` parameter**, and the schema stores neither — there is no signup IP or user-agent column on `User`. There is also **no `Subscribe` event**; the wired names are `CompleteRegistration` / `StartTrial` / `Purchase`. Most replayed rows will therefore match on hashed email alone. **Treat the replay as dataset seeding, not as attribution.** A backfilled event that does match lands retroactively on the **27–31 Aug rows**, not on today — Meta credits a conversion to the date of the click that earned it — so do not expect the dashboard's recent zeros to move.
6. **Add a retry or outbox for CAPI sends before relying on them.** Meta's freshness table recommends web events within **1 hour** and accepts at most 7 days for Sales and Leads objectives, warning that late events "will likely lead to poor performance in the product and Meta may opt to not use your events" (V). Tapeline's sends are inline and fast, which is good — but they use a 2.0s timeout, fire-and-forget, never raising, with no queue or retry (`meta_capi.py`). A Meta 5xx or a slow Graph call drops the event with a log line. **Without this, the zero-events problem recurs intermittently and nobody notices.**
7. **Do not switch the optimisation event on the live ad set.** It is on Meta's significant-edit list, it would reset learning with six days left, and it would destroy the pre/post baseline. Pick the up-funnel event for the *next* flight (§9.3).
8. **Do not use Meta's one-click "Meta-enabled" CAPI** (April 2026). It mirrors the events and parameters the **pixel** already sends — and this pixel sends `PageView` and nothing else. It would produce a healthy green CAPI status in Events Manager and a server-side stream of PageViews, with `CompleteRegistration` still at zero. **Flag this explicitly to the agency: it is the most plausible wrong fix available, and it looks like the right one.**

---

## 4. Attribution reconciliation — did those two payers come from the ads?

Four checks, all runnable against this stack, ordered by value per hour.

### 4.1 Query the DB — the answer is probably already stored (30 minutes, free)

The forensic instinct — grep Fly logs for `fbclid` and Facebook in-app-browser user agents — **mostly will not work here, and is not needed.** The `fbclid`-decorated landing URL hits the Next.js frontend app (`tapeline-web`), not the FastAPI backend, and the signup POST carries `fbclid` in the JSON body rather than the URL; the "httpx logs full request URLs" behaviour applies to **outbound vendor calls**. The answer is in Postgres:

```sql
SELECT email, created_at, tier, stripe_customer_id, trial_started_at,
       signup_utm_source, signup_utm_medium, signup_utm_campaign,
       signup_utm_content, signup_utm_term,
       signup_fbclid, signup_referrer_host, signup_landing_path,
       referral_source
FROM users
WHERE created_at >= '2026-08-26'
ORDER BY created_at;
```

Read it like this:

| What the two rows show | What it means |
|---|---|
| `signup_fbclid` populated | They arrived from a Meta surface. Still not proof of *paid* — Meta appends `fbclid` to organic links too. |
| `signup_fbclid` populated **and** the ad's full UTM set present (`utm_campaign` / `utm_content`) | Paid, effectively proven. |
| Neither populated, only `utm_source=facebook` | The Facebook signal came from a shared link or a stale first-touch UTM. **The ads did not deliver them**, and the ~73-per-payer figure is a coincidence, not a CAC. |

Also read the **published ad destination URLs** in Ads Manager. If they carry only `utm_source=facebook`, a hand-shared link is indistinguishable from a paid click — which makes this check inconclusive by construction, and that is itself the finding.

Note the capture mechanism, because it changes what an empty column means: `lib/utm.ts` stores the raw `fbclid` in **localStorage with a 30-day TTL, first touch wins**, forwards it on the signup POST, and it is written once to `users.signup_fbclid`. Safari purges script-writable storage after roughly seven days without site interaction, so the 30-day TTL is optimistic there and an empty column on a Safari user is weaker evidence of absence than on Chrome. *(A related and frequently-cited hazard — WebKit ITP 2.2 capping JS-set cookies to 24 hours when the landing URL carries a query string — does not apply, because Tapeline never relied on the pixel's `_fbc` cookie; it captures the raw `fbclid` itself. Source regraded to **V, 2019**; a server-set HttpOnly first-party cookie would harden a working path, not fix a missing one.)*

### 4.2 Pull two Ads Manager columns (5 minutes, free)

**"Landing page views"** and **"Unique link clicks"** for the whole flight. This one number decides which of the three explanations in §1.2 is true. **If landing page views is under ~50, stop treating the observed cost per payer as a CAC** until §4.1 says otherwise. While there: add **Columns → Compare Attribution Settings** to see 1-day click / 7-day click / 1-day view side by side, and check the **placement breakdown** before concluding anything about creative (§5 explains why).

### 4.3 Check whether the money is real (10 minutes, free)

Run `backend/app/scripts/billing_audit.py` and read `subscription.status` on the two Facebook-attributed accounts. `active` and `trialing` are different worlds (§1.2 item 4). **Diarise 12–14 Sep** — that is when the answer actually arrives, and it is the only date on which the observed cost per payer becomes a realised number rather than a contingent one.

### 4.4 Ask the two customers (two emails — needs authorisation before sending)

Self-reported attribution captured close to the conversion is the highest-yield instrument available at this scale, and the direction of the bias is consistent: word-of-mouth, communities and dark social are systematically under-represented in UTM data relative to what people say when asked (C — *the specific percentage pairs circulating for this effect were killed in verification as unsourced; use the direction only*). Two actions:

1. **Wire the HDYHAU field properly.** `users.referral_source` and the API field are live, but onboarding auto-POSTs `null` (gap G2 in `PAID_ADS_METRICS_BIBLE.md` §2.8). Free-text, optional, categorised later.
2. **Email exactly two people** — one plain question, *"what were you doing when you first came across Tapeline?"*, to `llegrandconsulting` and `avasmom8723`. n=2 with a direct answer beats n=2 with a dashboard guess. **These are live paying customers; get authorisation before sending.**

### 4.5 Stamp the remaining days so this is never ambiguous again (10 minutes)

Meta substitutes `{{campaign.id}}`, `{{campaign.name}}`, `{{adset.id}}`, `{{ad.id}}`, `{{ad.name}}`, `{{placement}}` and `{{site_source_name}}` at serve time, entered in the **URL Parameters** field at ad level (C). `PAID_ADS_METRICS_BIBLE.md` §7.5 item 11 already specifies the exact string; it evidently did not make it onto the live ads. Add it now, before 8 Sep, so the last week of the burst is cleanly labelled. Two caveats: **name** tokens freeze at publish time (renaming the campaign later does not update them, so prefer ID tokens), and this only helps traffic from here on — it is not a substitute for §4.1 on the two existing payers. From that point a bare `utm_source=facebook` means organic or shared, and a stamped one means paid.

### 4.6 The 8 Sep stop is a free natural experiment — instrument it *before* it happens

The campaign auto-ends 2026-09-08. Pre/post is the method the literature recommends below roughly US$50k/month spend, because everything better is priced out: standard sizing puts detection of a 20% lift at ~392 conversions per cell and a 10% lift at ~1,568 (B); Meta's Conversion Lift is widely reported as unavailable below ~US$30k/month; and Meta's Incremental Attribution (June 2025) withholds ~15% of an already tiny audience **and removes the ability to edit attribution settings at all** — the practitioner guidance is that it suits advertisers with no trouble getting conversion volume, which is the opposite of this account (C). **Do not switch it on.**

So, today, freeze and record — dated, in `docs/WEEKLY_LEDGER.md`, per the §7.5 item 9 discipline that already exists: **signups/day, card-adds/day and Facebook-referred sessions/day for 2026-08-27 → 09-07 (ads on)**, to be compared against **09-08 → 09-19 (ads off)** on identical definitions. With ~31 accounts total this is badly underpowered and can only detect a large effect — but a clean pre/post with pre-registered metrics beats an argument in three weeks about what the baseline felt like. **Write the comparison rule down before the ads stop, or hindsight will write it.** Note the §3 caveat: turning CAPI on mid-flight already blurs this read.

---

## 5. What 2026 changed that a 2025-built campaign should adapt to

Most of these are attribution and structure changes that landed after the standing docs were written. Grades: items quoting Meta's own changelog verbatim are **V**; items where trade press adds analysis, aggregates advertiser reports or forecasts consequences are **C** — the source for most of this section is ppc.land, which is secondary trade press, not the vendor.

| Change | Date | What it means here |
|---|---|---|
| **Click-through attribution redefined** — click-through now counts **link clicks only**; likes, shares and saves moved to a new **engage-through** bucket (1-day, on by default, not extendable); the qualifying video threshold dropped from 10s to 5s | 2026-03-03, rolling out from late March (V) | The 2026 default is 7-day click / 1-day engage-through / 1-day view-through. The ad set reports "7-day click, 1-day view" — **check whether engage-through is present on it.** For a registration event, 1-day view-through is the most likely source of inflated results; on the next rebuild, run registration on 7-day click with view-through off, so the number read is a number that can be trusted. Changing the attribution setting influences delivery, not just reporting. |
| **7-day-view and 28-day-view removed** from the Ads Insights API across all versions, on eight endpoints | 2026-01-12 (V) | Retained: 1-day click, 7-day click, 28-day click, 1-day engaged view, 1-day view — so the current setting is safe. The hazard is the **silent** failure: requests for the dead windows return empty data with no error. **Any reporting the agency builds must specify windows explicitly**, or a dashboard will render zeroes that look like a performance collapse. |
| **Advantage+ unified structure mandatory** (Marketing API v25.0); legacy ASC/AAC creation blocked on all versions 19 May 2026 | 2026-02-18 (V) | A campaign now earns Advantage+ status by having budget, audience and placement automation on simultaneously, surfaced in a read-only `advantage_state_info`. Any 2025-era instruction to "choose manual placements" or "build a manual control campaign" cannot be executed as written. Editing a legacy campaign in the new interface can silently convert it. |
| **FPS ad sets created via API must set `advantage_audience` explicitly to 1 or 0** | 2026-07-29, v26.0; extends to remaining versions 2026-10-27 (V) | Applies to **new** ad set creation only — updating the running ad set does not trigger it. It matters because an external agency now has access: **any tooling that scripts ad set creation against v26.0 will hard-fail without the field.** |
| **Placement controls disappearing for some advertisers**; the documented substitute (value rules) caps bid decreases at −90%, so no placement can be fully switched off | reported from 2026-08-25 (**C** — aggregated advertiser reports of a partial rollout, not a documented platform-wide change) | Verify in the account rather than assuming. Value rules are separately documented as **unavailable in Special Ad Categories**, so an FPS advertiser may have neither lever. |
| **Threads ads global**, Threads feed placement **on by default** | 2026-01-26 (C) | A surface no 2025 playbook accounts for. Check the placement breakdown before concluding the creative underperformed — some of the spend may have gone somewhere nobody chose. |
| **AEM is gone**: the 8-event limit, event prioritisation and the AEM tab were removed | **June 2025** — the separate May 2023 announcement removed conversion-domain selection and the domain-verification requirement, and **the two are frequently conflated; this document corrects that conflation** (V) | When events still look thin after the token goes live, **do not go hunting for an event-priority screen.** Check EMQ, event coverage and Test Events instead. Some 2026 content still asserts an 8-event cap silently dropping events on iOS; that conflicts with Meta's announcement and should not drive engineering time. |
| **AI pixel enrichment** — the pixel uses AI to read page and product information at event time and attach it automatically; existing pixels got a 30-day notification window that was a **review period, not an opt-in** | announced 2026-04-15 (V for the mechanism; **the state of pixel 28351455154543230 is an untested assumption**) | Those windows have largely closed, so it may be active. It reads page content at event time — and although `/app` is excluded, public ticker pages are not. **Open Events Manager → dataset settings, confirm, and decide deliberately.** It does not reactivate after being disabled. Meta's launch note also says access "may not be available to advertisers that have certain data source categories", which likely includes financial services. |
| **Graph API deprecation** | v21.0 retires 2027-01-21 (V) | See §3 step 2. |
| **CAPI performance claim** | 2026-04-15 (V — vendor marketing) | Meta states advertisers with a web CAPI setup saw **17.8% lower cost per result** than those without. Frame the expectation correctly: 17.8% off a CPA already several times what the budget can support does not make the ad set optimisable. **The token buys measurement and a modest efficiency gain — not a learning-phase exit.** |

**Two policy items that can end the ad account rather than the flight**, which the standing docs flag only in general terms:

1. **The US messaging prohibition.** Meta's Financial and Insurance Products and Services standard carries a US-specific clause: investment-product ads must not "suggest user interaction with the advertiser via on-platform or off-platform direct messaging services" (V — transparency.meta.com; changelog entries 2026-03-11, 2026-03-20 and 2026-04-30, none of which describe what changed, so any 2025 reading of that page is three revisions stale). **The campaign is literally named "message test".** The evidence says this is fine — Ads Manager reports the optimisation event as "Website completed registration", which is a conversion objective, not a Messages objective — but **confirm that no ad, destination or CTA invites a DM**, and record that it was checked.
2. **Authorisation.** The same standard says advertisers promoting investment products "may be required to verify their business and/or individual identity and demonstrate they are authorized by the relevant regulatory authorities where this is a requirement; and any such authorization may be subject to review by Meta" (V). *(A widely-circulated claim that this expanded from 12 to 38 countries in 2026 with US = SEC or FINRA registration was **killed in verification** — one unnamed secondary source driving an account-existential conclusion. Do not repeat it. Meta's own text above is what stands, and it is already `PAID_ADS_METRICS_BIBLE.md` §7.7 criterion 1.)* Business verification and account hardening are already the §7.5 item 10 checklist; the only thing to add is **do it while the account is healthy**, because a post-restriction appeal is a bad plan.

**And one naming rule with a date.** From 2025-09-02 Meta proactively scans and disables custom conversions and custom audiences whose names or rules suggest health conditions or financial status — its cited examples are "credit score" and "high income" — including previously-approved ones, and flagged conversions cannot be used in new campaigns (V — LiveRamp announcement of the Meta change). `META_ADS_DECISION.md` §3 flags this as `[unverified at primary]`; this addendum supplies the effective date and the concrete rule. **Use flat operational names: `signup_complete`, `welcome_page`. Never `premium_payers`, `high_value_customers` or `investor_tier`.**

---

## 6. Live competitive read, and the repeatable weekly method

Direct Ad Library observation, US, active, 2026-09-02 (**A** for each specific ad ID, start date and payload field; **D** for any absence claim, per §1.4).

### 6.1 What the live auction actually contains

- **The one proven formula in this exact niche.** Page "Day Trading Strategies" (`106287404187944`, 426 likes) runs 7 active US ads; the control (`1634445887605949`) has been live since **2026-04-13 — 142 days**, and a second angle since 29 Apr (126 days). The structure is: **a free, named, usable artefact** (a Lite scanner), **a hard specificity number** in the description, and an unambiguous free-access promise that names the absence of any payment step. It is an artefact, not a trial offer. **Tapeline already has the free artefact** — the public scorecard, daily picks, per-ticker pages and top-10 live rows, none of which need an account — **and is not leading with it.**
- **An anti-hype lane is being opened by that same advertiser.** A 17 Aug 2026 ad from the 142-day control account positions explicitly against flashy AI-generated trading ads and promises fast, accurate data instead. **Tapeline's legally-required descriptive register is the strongest version of that angle available in this auction.** It is a credibility asset, not a handicap.
- **A near-identical competitor launched 27 Aug 2026.** Page "NineThirty AI" (`1264774733392666`, page_like_count = 1) runs 2 US ads at the same $19.99/month price point, with the same compliance register ("For informational and educational purposes only. Not investment advice."), `display_format` DCO with 4 headline/description pairs × 3 images, all 5 placements — and `categories: ["UNKNOWN"]`, i.e. **no special ad category declared**. This is the control group; watch the page weekly. **It is not a precedent for de-declaring FPS** — Meta's 2026 classifiers can auto-apply the category from creative regardless, mis-declaration is an account-level risk on the only ad account with a card on file, and changing the category mid-flight is a significant edit that resets learning anyway. Whether a descriptive-only market-data subscription is an FPS "financial product" is a question for the Holley Nethercote brief (§7), not one to settle by watching a five-day-old page.
- **The failure twin, and Tapeline's own version of it.** Page "Akyla" (screener.akyla.ai, ~$20/mo) has 3 ads started 6 Jul 2026, all flagged "Low impression count" with `<100` impressions and an `end_date` one day after `start_date` — good descriptive copy, no delivery. **Tapeline's own ad `2144028049479862` (started 26 Aug, the "Sunday-night spreadsheet" creative) carries the same public "Low impression count / <100 impressions" flag.** Copy quality is not the binding constraint at this budget; **delivery is.** Splitting A$25/day across ads guarantees none of them accumulate anything.
- **The niche is video-first.** Of ~35 active US ads matching "stock scanner", ~27 (77%) are video; the pure-image filter returns nothing. The observed working length band on the long-running control sets is **20–75 seconds.** A screen recording of the scanner resolving a ticker is the highest-leverage asset not yet in the creative set — **with a constraint**: show the *mechanism*, not the call. A paid US ad showing a named live ticker under a conviction label reads as a pick even though the label is descriptive, and that is exactly the shape regulators are enforcing against. Show the interface and the descriptive vocabulary, anchor it to the public record, and carry no outcome, win-rate or performance overlay.
- **Nobody in the live set leads with a card-required trial.** The observed offer ladder is: free artefact with no card (142 days), free newsletter (392 days), free dated webinar, seven days of free access, a three-day free trial then $20/mo, "start free" then $19.99/mo, and one incumbent running a deep price-led promotional entry. Tapeline's own live ad `1577663127424189` (28 Aug) opens by explaining that the 14-day Premium trial takes a card, charges $0 that day, and shows the first-charge date before you confirm. **That copy is scrupulously honest and it is also the highest-friction opening line in the category.** The card requirement binds only on the **trial** — since #683 a Tapeline account is email and password on a working Free plan. **Lead with the free artefact; let the trial appear after the click.** *(Permanent guardrail: "free account, no card" is true and safe. The claim pairing the 14-day trial with an absence of a card is never allowed to appear.)*
- **The compliance register in this vertical is far more aggressive than Tapeline's, and Meta is not stopping it.** Live right now: explicit win-percentage headlines (95 days and counting), an AI product advertising explicit directional calls (395 days), a profit-total claim (392 days), and a major publisher running a conviction hook (139 days) — alongside advertisers running full inline risk warnings and "not investment advice" lines. **The evidence is that a disclaimer does not suppress delivery.** Stop treating the descriptive constraint as the reason results are zero.
- **One thing to take from the largest advertiser, and one to refuse.** The Motley Fool runs ~53 active US ads with a 139-day control, and its ad `link_url` carries the full dynamic macro set. **Take the macros** (§4.5) — they are scale-free and let the DB attribute a signup to a specific ad with no dependence on the pixel or CAPI. **Refuse the rest**: their variant-testing method needs impression volume this account does not have (~1,412 lifetime impressions cannot separate two headlines), and their curiosity-gap register is off-limits under the copy rules however well it performs for them.
- **Bursts, not always-on, is a viable shape for a capped budget.** One incumbent scanner has exactly **one** active US ad, launched that same day, with no back catalogue — it uses Meta as a short promotional channel, not a continuous acquisition engine. **Take the concentration** (spend a capped allowance in one dense burst rather than a thin drip); **refuse the mechanism** (a dated, price-led sale is deadline-and-discount copy, which the copy rules bar, and founding pricing is framed as locked in for early subscribers). Hang a concentrated burst on a dateless free artefact instead.
- **The Special Ad Category is publicly visible per ad, and Tapeline's closest working analogues are not in one.** The Ad Library exposes a per-ad `categories` field: sampled 2026-09-02, TrendSpider, Moomoo, Momentum and a Motley Fool credit-card ad all read `["CREDIT"]` (FPS surfaces as CREDIT, since it replaced the Credit category); Motley Fool's Stock Advisor ads, NineThirty AI and Day Trading Strategies all read `["UNKNOWN"]`. Every ad sampled also carries `regional_regulation_data.finserv = {is_deemed_finserv: false}` — Meta's own classifier has not independently deemed any of them financial services. **This is a concrete, evidenced question for the lawyer brief, not a growth hack** (§7).

### 6.2 One live legal signal worth a line in the brief

A plaintiff firm is running three US ads (started 27 Aug 2026) recruiting people who watch videos on a finance publisher's site, on a pixel-privacy theory. Context: the US Supreme Court granted certiorari in **Salazar v. Paramount Global** in Jan 2026 on whether a free, non-video subscription creates a VPPA "consumer" relationship when the publisher also serves video, and SDNY held in March 2026 that Meta Pixel use did not violate the VPPA, deepening a circuit split. **Tapeline's current pixel design is already the defensible one.** The operative consequence: **do not "fix" the zero-conversion problem by widening the browser pixel to fire `CompleteRegistration`, and do not add pixel-tracked video to public pages.** Put the events through the server-side CAPI as designed. This also settles the "Meta wants a 75% CAPI-to-pixel event coverage ratio" diagnostic in the affirmative-negative: that target assumes a redundant-event advertiser, which Tapeline deliberately is not. **Accept a permanently non-redundant setup and stop measuring against the diagnostic.** Worth one line in the Holley Nethercote brief, since a free-signup-plus-video publisher is precisely the profile under review.

### 6.3 The repeatable weekly method — by hand, ten minutes, Mondays

**The most important methodological fact: US commercial ads vanish from the Ad Library the moment they stop.** Verified 2026-09-02 — setting `active_status=all` on a tracked page returned the same single result as `active_status=active`. Only social-issue, electoral and political ads are retained (7 years, with spend and reach). So the 142-day control, the 53 variants and — most valuably — **any competitor's failed test** are observable today and unrecoverable once paused. Six weekly snapshots become a survival curve; without them there is nothing to analyse in November.

**Do this by hand. An automated scraper of the Ad Library page payload was considered and rejected**: automated collection sits against Meta's terms, and enforcement here is account-level — the ad account, the pixel and the page — which is the dataset the entire CAPI plan depends on. Ten minutes a week of human-paced clicking obtains the same information at no risk. (For completeness: the Ad Library **API** is not an alternative for this — `ad_type=ALL` only returns results when `ad_reached_countries` is an EU member state or the UK, so a US-only advertiser is invisible to it.)

Three traps that make the naive method fail, all verified 2026-09-02:

1. **The date filter is "impressions by date", not launch date.** Adding `start_date[min]` / `start_date[max]` incremented the filter chip but left the result count unchanged, and still returned ads that started in April. **Read "Started running on" off the card yourself.** Very new ads also show a "Total active time" counter that ticks live.
2. **Keyword search matches ad BODY text, not advertiser identity.** Searching a competitor's brand mostly returns its affiliate ecosystem. **Use `search_type=page` with `view_all_page_id`** for a specific advertiser; never trust a brand keyword search as a coverage check. This is what regraded §1.4's absence claims to D.
3. **Exact-phrase search is still fuzzy** — a two-word phrase matched copy where the words were split across a sentence boundary.

Record per tracked page, in a dated table: ad count, each Library ID, "Started running on", format, `categories` chip, impressions bucket, and full body/headline/description text. **Tracked pages:** Day Trading Strategies (`106287404187944`), NineThirty AI (`1264774733392666`), TrendSpider (`145079722792894`), The Motley Fool (`7240312795`), Akyla, Momentum., Benzinga — and Tapeline's own page, because that is how the "<100 impressions" flag on Tapeline's own ad was found.

---

## 7. What real payers unlock — and what FPS still forbids

`META_ADS_DECISION.md` §3 and §5 answered "what does FPS remove" and "is retargeting deliverable". Those answers stand. This section answers the question that only becomes askable now that payers exist: **what does having them unlock?**

**Answer: almost nothing yet — and it is worth saying so in writing before an external agency proposes otherwise.**

| Lever | Status | The binding constraint |
|---|---|---|
| **Value-based / Maximize-Value bidding, ROAS goals** | **Impractical, not forbidden** | Meta's eligibility gate is roughly 30 attributed conversion events with **at least 5 distinct values** in a rolling 14 days for Purchase (100 events for non-Purchase standard events such as `CompleteRegistration`) (C). Tapeline has 4 lifetime payers, zero of them ever sent to Meta, and only two possible values ($9.99 / $19.99) — so even at 30× the volume it clears 2 of the 5 required distinct values. **Keep Highest Volume.** Revisit only with a third price point and more than ~30 monthly payers. |
| **Value rules** (the workaround for "tell Meta which customers are worth more") | **Forbidden** | Documented as unavailable in Special Ad Categories including financial services (C), and they require a Sales objective without a ROAS goal. Meta's own warning is that value rules can move cost per result by 20–1,000% — a budget this size cannot absorb that. Expect the control to be greyed out. |
| **Value-based lookalikes** | **Forbidden** | Meta's Marketing API reference states lookalike audiences are unavailable for housing, employment and financial products and services (V). A value-based lookalike is a lookalike seeded with a value column, so it sits inside the removed set. `META_ADS_DECISION.md` §3 has the general rule; **this is the specific variant an agency is most likely to propose.** |
| **Special Ad Audiences** | **Gone, and still being recommended** | Discontinued 2022-10-12 under the HUD settlement, with nothing replacing them (C) — yet current 2025–26 guides aimed at financial advertisers still advise building them. With an agency newly onboarded, **this is the most likely bad recommendation to arrive this week.** |
| **Customer-list Custom Audiences** | **Permitted — blocked by size, not policy** | Meta exposes a per-audience `is_eligible_for_sac_campaigns` flag, and a business admin must accept the non-discrimination policy first; since Jan 2025 US advertisers must also certify the list contains no prohibited attributes (V). But the hard floor is **100 matched people**, and delivery is unstable under ~1,000. Tapeline has ~31 accounts. **Do not spend this week building one; revisit at 150+ accounts.** |
| **— and a new trap on that lever** | | Meta's Jan-2025 rules require ad accounts in a portfolio **sharing** customer lists to have campaign managers on the same business email domain, and make shared lists unavailable for FPS ads where the domains differ or are generic (gmail, yahoo, hotmail) (C). Tapeline's owner identity is a gmail address and `Zanek@Hackd.Tech` is a third domain. **If a list is ever used, upload it directly in the ad account that runs the ads — never share it across portfolios.** |
| **Event-based website Custom Audiences from server events** | **Unlocked by the token — this is the underrated part** | Meta states server events are linked to the dataset and "processed like events sent using the Meta Pixel… may be used in measurement, reporting, or optimization in a similar way" (V). So a `CompleteRegistration` or `Purchase` sent by `meta_capi.py` builds a retargetable and suppressible audience **with no browser tag on `/app`** — preserving the privacy scoping entirely. One Fly secret turns on optimisation signal, reported results, *and* the only audience Tapeline can mechanically build under FPS. |
| **Retargeting ad set from this flight** | **Not viable** | The whole flight reached 1,054 people. A quality-filtered pool is a few hundred at best, against a ~1,000 practical floor. **Build one all-site-visitors audience now so the clock starts; do not create a retargeting ad set until the pool clears ~1,000.** (Plan against the standard 180-day retention figure; *a circulating claim that purchase-based audiences were extended to 730 days in May 2026 with a silent auto-migration was killed in verification — single vendor blog, no Meta source.*) |
| **Advantage+ Audience under FPS** | **Check the toggle, do not trust the blogs** | Meta's special-ad-category reference lists Advantage+ Audience and detailed-targeting expansion as **retained** under `tune_for_category` (V) — which matches `META_ADS_DECISION.md` §3 — while two 2026 practitioner guides assert the opposite. Both cannot be right. It changes nothing this week (seeding it needs a customer list that does not clear the 100-person floor), but **record which one the ad set actually offers**; it decides the structure for the next flight. |

**Two things the payers *do* unlock, both cheap:** the CAPI dataset finally has something real to seed (§3 step 5), and — once the account clears ~150 signups — a suppression audience, so prospecting stops paying to reach people who already have accounts.

**The compliance item this section adds to the lawyer brief.** §6.1's `categories` finding turns an abstract question into an evidenced one: *is a market-data analytics subscription with descriptive-only labels a "financial product" for Meta's Special Ad Category purposes, given that several close analogues run in the US without declaring one, and that Meta's own `finserv` classifier has not independently deemed any of them financial services?* Note the counter-risk before anyone acts on it: **Meta's 2026 classifiers can auto-apply the category from ad imagery even when the advertiser does not select it**, and an undeclared-then-caught financial ad is a rejection on the record. Add it to the Holley Nethercote list alongside §6.2's VPPA line and the existing question 14 in `META_GO_LIVE.md` §10 — whether paid, audience-targeted advertising changes the publisher-exemption analysis at all — which remains the sharpest question of the set.

---

## 8. The organic-to-paid bridge, sceptical case stated fairly

The tempting argument is: Meta under-reports upper-funnel effects, so the ads may be helping the proven channel — AI-assistant referral and organic — without ever showing up in Ads Manager. **The argument is directionally real, weaker than it sounds, and does not survive contact with what Tapeline actually has.**

**The case for it, at full strength.** Haus's report on 640 Meta incrementality experiments (advertisers averaging ~US$14M/year Meta spend, 7-day click / 1-day view, average test 18.6 days) puts average lift to the primary KPI at ~19% and reports attribution under-reporting ratios rising up-funnel — mid-funnel 1.3×, traffic 2.4×, reach and awareness 6.0× — with 81% of upper-funnel impact on new customers. Separately, Brainlabs pooled Meta conversion-lift studies measuring incremental **search** visits: +19% search visits among the exposed group, 71% of it landing in **organic** search rather than paid.

**Now the discounts, all of which apply here.**

1. **Grade both down.** Haus sells incrementality testing, so a report concluding that platform attribution is systematically wrong is vendor marketing built on real data — **regrade V, not B.** Note also an unreconciled inconsistency across the sweeps: Haus is cited for click attribution *understating* incremental impact by ~15%, for retargeting ROAS *overstating* it by 40–70%, and for 37.7% of attributed purchases being non-incremental. Those can coexist across tactics, but they are quoted without reconciliation, and a reader will take whichever supports the decision they already wanted. Brainlabs is **17 studies across 12 advertisers — regrade C, not B** — published by an agency marketing its own measurement practice.
2. **The populations are nothing like this account.** DTC ecommerce at ~US$14M/year Meta spend. Nothing in either dataset validates a A$25/day advertiser; they validate the *direction* of a measurement bias, not its magnitude at this scale.
3. **Meta cannot buy the signal that actually drives Tapeline's proven channel.** Ahrefs' 75,000-brand study of AI-assistant visibility (Spearman correlations, DR>40 filter) ranks **YouTube mentions ~0.737**, branded web mentions ~0.664, branded anchor text **0.527**, branded search volume **0.392**, backlinks 0.218 — and the authors state plainly that correlation is not causation. *(The branded-anchor and branded-search figures circulating in the sweep as 0.628 and 0.466 are wrong; the corrected numbers make the argument stronger, not weaker.)* A "YouTube mention" means the brand name in a title, transcript or description — something a creator video or podcast produces and a Meta ad never does. **The chain paid-social → branded search → AI citation is real but weak at both joints, and weakest at the second.** Tapeline's `billydone` payer arrived via `accounts.youtube.com` organically.
4. **There is no evidence, and no documented mechanism, for Meta ads lifting AI-assistant citations.** What *is* documented is the retrieval path: 87%+ of sampled SearchGPT citations matched Bing's top organic results (C), and Copilot grounds on the same index. Grade this as absence of evidence rather than evidence of absence — but the burden of proof sits with anyone claiming the ads help here. **Do not justify the burst as an AEO play.**
5. **The obvious reallocation is not available.** "Spend the same money getting a finance creator to name the brand on camera" is a compensated endorsement: it needs Meta's Partnership Ads designation if amplified, carries FTC disclosure obligations with brand liability, and is precisely the conduct **ASIC's 2026 finfluencer enforcement targets** — media release 26-081MR names warning notices to four finfluencers for suspected unlicensed advice and misleading conduct — including promotion of assured-outcome claims — plus a review of three AFS licensees supervising 15 finfluencers, following 18 warning notices in the June 2025 global action (V — ASIC primary). ASIC's stated position is that finfluencers must hold a licence or be an authorised representative to provide financial product advice. Micro-creator whitelisting also runs US$150–500/month on top of media (C), which alone exceeds the remaining A$350 allowance. **Read finding 3 as an argument for EARNED mentions and for standing up measurement — not as a budget reallocation.**
6. **There is nothing on Meta to amplify.** The "post organically, read watch-through, then whitelist the winner" playbook presumes an account with organic distribution. Finance is the worst vertical for that (Rival IQ puts Instagram finance engagement at 0.26% interactions/followers; note that Hootsuite's interactions/impressions definition gives 3.80% for the same vertical — a 14× definitional gap, so **never compare engagement rates across sources**). The Tapeline page has effectively no following, so a boosted post carries over no social proof.
7. **Boost is not a shortcut anyway.** The Boost button exposes no conversion objective at all — "lowest cost" there means cheapest engagement, not cheapest signup — with no A/B testing, no dynamic creative and no placement control. The real mechanic worth using is **post-ID reuse** ("Use existing post" in Ads Manager), so engagement accumulates on one object instead of resetting per ad. *(The circulating "dark posts get 43% higher CTR, 22% higher CVR, 15% lower CPC, 30% lower CPA" figure appears in multiple blogs with no study, sample or date behind it — **grade E, and it does not belong in a plan.**)*

**The one action this section does produce, and it is free.** Microsoft shipped an **AI Performance report in Bing Webmaster Tools** on 2026-02-10 (public preview, V): total citations, average cited pages per day, **grounding queries** (the reformulated queries Copilot generates internally to retrieve sources — a sample, not a complete log), page-level citation activity, and a visibility trend — covering Microsoft Copilot, Bing AI summaries and selected partner integrations. Tapeline's `yankeezz2828` payer arrived on `utm=copilot.com`, and right now nobody knows which pages Copilot cites or on which queries. Bing Webmaster Tools is a **separate free property from Google Search Console** — Zanek was granted Search Console, which does not report this — and it verifies by importing from Search Console in a couple of minutes. **That hour is worth more than any hour available in Ads Manager this week.**

---

## 9. Revised decision

### 9.1 Reconciliation with `META_ADS_DECISION.md`

**Its verdict stands.** That document closed Meta prospecting on three independent blockers — economics, the FPS learning floor, and the unmet ads gate — and stated that any one is sufficient. On the evidence here:

- **The learning-floor blocker is confirmed and strengthened.** §2's arithmetic says exiting learning at A$25/day requires a ≤A$3.50 registration, which is 5–20× off. The doc predicted the campaign would not reach the learning threshold; reality was worse — it received zero events.
- **The economics blocker is not overturned.** The observed ~73 per payer (≈US$48 if AUD) sits below the doc's most-generous US$164, which would be the first datum in the channel's favour — **but** n=2, the 95% interval spans ~20–607, the ads-caused link is unproven (§4), and realised revenue may currently be $0 with the first charges landing 12–14 Sep (§1.2). **A 30×-wide interval does not overturn a 4–40× argument.** Quoting "$73 CAC" without the interval is how a coin flip becomes a fact three months from now.
- **The ads-gate blocker is untouched.** Nothing here bears on ≥10 organic payers retained 60 days, click→trial ≥15%, or LTV:CAC ≥3.
- **One sub-claim is corrected**, at §1.4: the day-14 Purchase framing describes the charge, not the shipped event. The conclusion it supported — never judge this channel on Ads Manager's Purchase or ROAS column — survives with a better reason: no value is ever sent.

**And a procedural point that matters more than any number here.** `PAID_ADS_METRICS_BIBLE.md` §7.7's pre-registered criteria were never evaluable: criterion 3 requires cost per `CompleteRegistration` after 100+ clicks, and this flight has reported zero registrations against a modelled ~14–28 clicks. **The kill criteria did not fail — they never became readable.** Nothing about the message test has been proven or disproven. That, not the CPM, is the real cost of the six blind days.

### 9.2 Before 8 Sep — the ordered list

1. **Events Manager → Data Restrictions read**, dated and screenshotted. If `CompleteRegistration` is restricted, **stop** — this is `PAID_ADS_METRICS_BIBLE.md` §7.7 criterion 1, and the token changes nothing.
2. **Ship `event_source_url` on all four call sites, plus the Graph API version bump**, on `fix/meta-capi-token-and-visibility`.
3. **Set `META_CAPI_ACCESS_TOKEN`.** Verify via Test Events, then unset the test code.
4. **Replay the cohort created since 2026-08-26, by 2026-09-05** (the `llegrandconsulting` deadline). Filter by `created_at` — one stale event rejects the whole request.
5. **Run the four §4 checks.** The DB query, the two Ads Manager columns, `billing_audit.py`, and the ad-level URL macros. Total: about an hour.
6. **Freeze the pre/post baseline** in `docs/WEEKLY_LEDGER.md` **before** the ads stop.
7. **Agree, in writing, who may change campaign settings before 8 Sep.** `Zanek@Hackd.Tech` has had Meta access since 2026-09-02. A well-meant mid-flight objective switch would destroy both the learning history and the pre/post baseline. Hand them §3 step 8 and §7's table.
8. **Leave the ad set otherwise alone.** No objective change, no duplication, no new creative — all are significant edits, and there are six days left.
9. **Do not raise budget.** Six more days at A$25 is ~A$150, bringing the flight to roughly **A$297 — under the A$350 kill line.** The burst can run to its scheduled end without breaching it. That is the whole remaining allowance; there is no second flight inside this cap.

### 9.3 Revised kill and scale criteria

**The old kill lines stay** (`PAID_ADS_METRICS_BIBLE.md` §7.7): stop at the spend cap; stop on a data-sharing restriction; stop if cost per `CompleteRegistration` exceeds ~$50 after 100+ clicks. **The addition is that "Results = —" is not a kill signal, and the DB's two payers are not a scale signal.** Both failure modes are expensive:

> Killing on a zero dashboard kills a campaign the database says produced two Premium signups — a **measurement** failure read as a **performance** failure. Continuing on "the DB says 2 payers" spends against a number whose interval reaches ~607 per payer and whose realised revenue may be $0.

**Pre-commit this now, before the evidence arrives.** Continue past 8 Sep **only if all three hold**:

1. **Landing page views for the flight exceed ~150** (§4.2) — i.e. the traffic needed to cause two payers plausibly existed; **AND**
2. **§4.1 or §4.4 ties at least one payer to a paid click** — a populated `signup_fbclid` with the ad's UTM set, or the customer's own answer; **AND**
3. **The backfilled events actually register** in Ads Manager on the 27–31 Aug rows within 24–72h of sending.

**Fail any one and let the burst expire on schedule at ~A$297, well under the kill line.** Re-enter later — not sooner — with: the token live and verified; `event_source_url` shipped; URL macros stamped on every ad; an up-funnel optimisation event whose weekly volume is in the same order of magnitude as 50 (the only zero-code option is a **URL-rule custom conversion over the `PageView` the pixel already fires on an already-public path** — `/scorecard`, `/daily-picks`, a ticker page; there is no `ViewContent` anywhere in the codebase, and **any rule pointed at an `/app` URL will never fire, which must not be "fixed" by widening the pixel**); and a lead offer built on the free artefact rather than the trial (§6.1).

**Two dates to diarise, because they are when this actually resolves.** **2026-09-05** — the backfill deadline for the first payer. **2026-09-12 to 09-14** — when the two Premium trials either charge or lapse, and the observed cost per payer becomes either a real number or a rounding error.