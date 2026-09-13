# Meta conversion-to-sales blueprint for Tapeline

**Date:** 2026-09-13.

**What this extends.** `docs/META_ADS_PLAYBOOK_2026-09-11.md`. This document does not repeat the playbook. Where the two disagree, §6 settles it.

**How it was made.**
- Six readers covered official Meta sources: the Help Centre, Meta for Developers, the Transparency Center, the Meta for Business newsroom, and Blueprint course outlines. Blueprint lesson bodies need a Facebook login and were not read (§7.3).
- An independent skeptic re-fetched every cited page: 102 claims verified, 3 refuted, 1 outdated, 1 misapplied. The refuted, outdated and misapplied claims appear here in corrected form.
- A final critic pass checked the code references.
- Two decision-changing claims were re-read by hand on 2026-09-13:
  - the 10× budget rule on H 355670007911605;
  - the US "financial securities and investments" advertiser-verification requirement on H 719892839342050, US section of the country selector.

**Evidence rules.**
- Every claim comes from an official Meta page and was checked adversarially. Corrections found in that check are applied here. Anything not confirmed is listed in §7.
- "H nnnn" means `facebook.com/business/help/nnnn`. Help Centre pages show no last-updated date unless one is stated.

**Code read, none edited.**
- Backend: `backend/app/services/meta_capi.py`; `backend/app/routers/webhooks.py`, `auth.py`, `oauth.py`, `billing.py`.
- Frontend: `frontend/app/signup/*`, `frontend/app/app/onboarding/page.tsx`, `frontend/components/MetaPixel.tsx`, `frontend/lib/metaConversions.ts`, `frontend/lib/utm.ts`, `frontend/lib/api.ts`, `frontend/next.config.js`.
- Tests and tooling: `backend/tests/test_server_side_conversions.py`, `frontend/__tests__/MetaPixel.test.tsx`, `scripts/lint-copy-compliance.mjs` (run, not edited).
- Ad build: `docs/ads/2026-09-video/build3.mjs`, `docs/ads/2026-09-video/meta-copy-2026-09.md`. The VO cuts in `docs/ads/2026-09-video/voiceover/` were measured with ffprobe.

**Trial outcomes as of 2026-09-13, read-only from Stripe:**
- The 12 Sep trial is past due (first charge declined; Stripe retries 13 Sep 23:09 UTC).
- The 14 Sep trial is still trialing ($199/yr).
- The 17 Sep trial was cancelled 4 minutes after it started.
- The fourth trial ended cancelled.
- Revenue ever collected: $9.99, from a non-Meta customer.

**Working numbers.** These come from the August burst on the playbook's basis:
- A$123.53 spent, 3 signups (about A$41 each) and 2 cards (about A$62 each).
- CPM A$103 and CTR 2.37%, so a link click costs about A$4.35.
- A$25/day buys about 243 impressions a day.

---

## 1. The blueprint in one page

Two of Meta's own rules limit everything below.

1. **Budget should be at least 10× what the performance goal costs.** A daily budget should generally be at least 10× the average cost of the performance goal ([H 355670007911605](https://www.facebook.com/business/help/355670007911605)). At A$25/day, the goal would have to cost A$2.50 or less. No goal clears that:

   | Goal | Cost now | Daily budget the 10× rule implies |
   |---|---|---|
   | Link click | ~A$4.35 | ~A$44 |
   | Signup | ~A$41 | ~A$410 |
   | Card | ~A$62 | ~A$620 |

2. **Leaving the learning phase takes about 50 results in the 7 days after the last significant edit** ([H 112167992830700](https://www.facebook.com/business/help/112167992830700)). That means about A$290/day optimising on signups, or about A$440/day on cards (the playbook's A$293/A$443, restated only for the arithmetic). The same page warns that a very small budget gives delivery an inaccurate signal.

The build below follows Meta's structural guidance. Every variant of it is still under Meta's budget floor, and nothing in this document fixes that. Whether to raise the budget is a founder decision.

| # | Setting | Build | Official basis |
|---|---|---|---|
| 1 | Objective | **Sales.** Leads fits only when free signups are the business goal. Sales can also optimise for actions other than purchase. | [H 1438417719786914](https://www.facebook.com/business/help/1438417719786914) |
| 2 | Campaign type | A Sales campaign built in Ads Manager. It opens in the Advantage+ setup by default, and all manual controls remain. It is **not** a legacy Advantage+ shopping campaign, and the API no longer creates those. | [H 1292656978738967](https://www.facebook.com/business/help/1292656978738967); [Dev blog v25.0, 2026-02-18](https://developers.facebook.com/blog/post/2026/02/18/introducing-graph-api-v25-and-marketing-api-v25/) |
| 3 | Special Ad Category | **Financial products and services.** Set the SAC country explicitly to **United States**; if left unset it defaults to the tax country. Meta's US examples include investment services and brand ads "regardless of offer". | [H 1157846251802527](https://www.facebook.com/business/help/1157846251802527); [Dev: Special Ad Categories, updated 2026-05-21](https://developers.facebook.com/docs/marketing-api/audiences/special-ad-category/) |
| 4 | Conversion location | **Website** | [H 1438417719786914](https://www.facebook.com/business/help/1438417719786914); [H 644554008179419](https://www.facebook.com/business/help/644554008179419) |
| 5 | Performance goal | **Maximise number of conversions.** Not value: Meta recommends at least 100 events with at least 5 distinct values in 14 days. Tapeline logs about 5 signups and 1–2 cards per 14 days, and has only 4 list prices (only 2 on the Premium-only trial). | [H 355670007911605](https://www.facebook.com/business/help/355670007911605); [H 571188993373447](https://www.facebook.com/business/help/571188993373447) |
| 6 | Optimisation event | **CompleteRegistration**, unchanged. Switch to StartTrial only under the conditions in §3.3. | [H 950694752295474](https://www.facebook.com/business/help/950694752295474); [H 269269737396981](https://www.facebook.com/business/help/269269737396981) |
| 7 | Bid strategy | **Highest volume.** No cost-per-result goal: the budget must be at least 5× the goal, so the goal would need to be A$5 or less. No bid cap. No value rules. | [H 272336376749096](https://www.facebook.com/business/help/272336376749096); [H 203183363050448](https://www.facebook.com/business/help/203183363050448); [H 535014515741813](https://www.facebook.com/business/help/535014515741813) |
| 8 | Budget level | **A$25/day at campaign level, one ad set.** With one ad set this delivers the same as an ad-set budget. It also keeps `advantage_budget_state` ENABLED, so an "Advantage+ off" reading can only come from audience or placements. | [H 1602924913861363](https://www.facebook.com/business/help/1602924913861363); [Dev: Advantage+ campaigns, updated 2026-06-17](https://developers.facebook.com/docs/marketing-api/advantage-campaigns/) |
| 9 | Attribution model | **Standard, not incremental.** The incremental model is locked at publish, allows no bid controls, and no official page says it is available under FPS. | [H 644554008179419](https://www.facebook.com/business/help/644554008179419); [H 2198119873776795](https://www.facebook.com/business/help/2198119873776795) |
| 10 | Attribution setting | **7-day click + 1-day view + 1-day engage-through**, if the account shows the engage-through option. Two changes drive this. Since March 2026, click-through counts link clicks only; conversions after other clicks moved into engaged-view, renamed engage-through, whose video threshold also fell from 10 to 5 seconds. And an event only counts toward learning if it falls inside the chosen setting. Leaving engage-through off may therefore drop conversions that click-through counted before the account moved to the new definition (rollout timing varied by advertiser; whether and when this account moved is unconfirmed, §7.1). *This is an inference from those two rules, not a stated Meta recommendation.* | [H 2198119873776795](https://www.facebook.com/business/help/2198119873776795); [Meta news 2026-03-03](https://www.facebook.com/business/news/click-attribution); [H 197634954160445](https://www.facebook.com/business/help/197634954160445) |
| 11 | Placements | **Advantage+ placements, no exclusions.** Account-level placement controls don't apply to FPS ads. Any ad-set exclusion turns Advantage+ placements off. For eligible advertisers it also turns on "limited spend" by default: Meta aims to spend about 5% of budget on each excluded placement when that is likely to improve performance, until it is switched off per placement. Whether this applies to SAC campaigns is unconfirmed (§7.1). | [H 1438478636941047](https://www.facebook.com/business/help/1438478636941047); [H 1462437878221374](https://www.facebook.com/business/help/1462437878221374) |
| 12 | Audience | **United States (country), ages 18–65+, all genders.** No detailed targeting, no inclusions. Use Advantage+ audience only if the UI offers it; official sources conflict on this (§5.1). The setting is identical either way. | [Dev: Special Ad Categories](https://developers.facebook.com/docs/marketing-api/audiences/special-ad-category/); [H 2220749868045706](https://www.facebook.com/business/help/2220749868045706); [H 938372127764391](https://www.facebook.com/business/help/938372127764391) |
| 13 | Exclusion (optional) | Exclude existing accounts using a neutrally named customer list, and only if the UI accepts a custom-audience exclusion under FPS. It is worth little with about 40 accounts. | [Dev: Special Ad Categories](https://developers.facebook.com/docs/marketing-api/audiences/special-ad-category/); [Custom Audience terms, eff. 2025-12-03](https://www.facebook.com/legal/terms/customaudience); [H 1452187872132363](https://www.facebook.com/business/help/1452187872132363) |
| 14 | Ads per ad set | **One per active concept, three at most.** Adding an ad is a significant edit, and more ads can mean longer learning. Meta's Instagram video guidance says to *start* with up to 10 creatives per ad set; that is a starting point, not a stated ceiling. | [H 316478108955072](https://www.facebook.com/business/help/316478108955072); [H 2177212182495139](https://www.facebook.com/business/help/2177212182495139); [H 188534925073536 (en-gb)](https://en-gb.facebook.com/business/help/188534925073536) |
| 15 | Assets per ad | **One concept per ad.** Include 9:16, 4:5 and 1:1 versions, plus the ≤15 s cut and a static frame from §4. Opt the 4:5 and 1:1 assets out of Stories and Reels, and review auto-crops before publishing. Every ad-set placement must keep at least one eligible asset, and once assets are opted out at ad level, placement editing at ad-set level is locked. Keep concepts in separate ads: the per-asset Media breakdown can't report Start trial or Subscribe. Meta lists active or paused campaigns as unsupported for multi-media ads, so a new campaign may be needed. | [H 1530327025203003](https://www.facebook.com/business/help/1530327025203003); [H 103816146375741](https://www.facebook.com/business/help/103816146375741); [H 1822387965412520](https://www.facebook.com/business/help/1822387965412520) |
| 16 | Creative automation | **Turn off every Advantage+ creative enhancement** in both the Ad creative panel and Advanced preview, since some are only visible in Advanced preview. Some are on by default. Do it before publishing: changing them on a live ad is an ad-creative edit (inference from H 316478108955072). Also untick the account setting "Test new creative features" (Advertising settings > Creating ads > Creative features). Opting in lets test enhancements apply to eligible campaigns regardless of the ad-level opt-in; only eligible advertisers see the box. | [H 1082295769403815](https://www.facebook.com/business/help/1082295769403815); [H 2084198785720343](https://www.facebook.com/business/help/2084198785720343); [H 223409425500940](https://www.facebook.com/business/help/223409425500940) |
| 17 | Recommendations | **Turn off opportunity-score auto-apply** in Account overview, and dismiss recommendations that conflict with this plan. A low score carries no penalty. | [Opportunity score (Meta for Business)](https://www.facebook.com/business/tools/opportunity-score); [H 804913634782260](https://www.facebook.com/business/help/804913634782260) |
| 18 | Edit cadence | **One batched edit a week.** Measure from the last significant edit, wait at least 7 days, and use weekly averages. The batching advice is written for Advantage+ campaign budget, and the 7-day wait and weekly averages for cost-per-result goals; applying them to a Highest volume campaign is an extension. | [H 2177212182495139](https://www.facebook.com/business/help/2177212182495139); [H 272336376749096](https://www.facebook.com/business/help/272336376749096); [H 942374239243867](https://www.facebook.com/business/help/942374239243867) |

---

## 2. The measurement ladder

### 2.1 What Meta asks for

**Every website event** should carry the following:
- `action_source=website` and `event_source_url`. Meta's CAPI best practices mark `client_user_agent` as **required for all website events** ([Dev CAPI best practices, updated 2026-06-28](https://developers.facebook.com/docs/marketing-api/conversions-api/best-practices)).
- `client_ip_address`, unhashed. It must be the IP of the browser where the event happened; Meta prefers IPv6 when the user has one ([Dev customer information parameters, updated 2026-01-09](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/customer-information-parameters)).
- `em` (hashing required) plus `external_id` (hashing recommended; same format on every channel that sends it) (same page).
- `fbc` in the form `fb.1.<ms>.<fbclid>`, carrying the **most recent** fbclid ([Dev fbp and fbc](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/fbp-and-fbc)).
- `fbp`, unhashed, from the `_fbp` cookie (Dev customer information parameters).
- An `event_id` shared with any browser copy. Deduplication works within 48 hours ([Dev dedup](https://developers.facebook.com/docs/marketing-api/conversions-api/deduplicate-pixel-and-server-events)).

**Matching priority.** Email and fbc are High. External ID and fbp are Medium. IP and user agent aren't ranked ([H 765081237991954](https://www.facebook.com/business/help/765081237991954)).

| Funnel step | Meta event | action_source | custom_data | Can it feed learning? |
|---|---|---|---|---|
| Free signup (day 0) | CompleteRegistration | website (pixel + CAPI, shared event_id) | optional | Yes |
| Card-required trial (day 0) | **StartTrial**: the start of a free trial ([H 402791146561655](https://www.facebook.com/business/help/402791146561655)) | website | value, currency and predicted_ltv are all optional ([Dev pixel reference, updated 2024-07-16](https://developers.facebook.com/docs/meta-pixel/reference)) | Yes |
| First paid charge (day 30 or later; Stripe charges automatically, no browser involved) | **Subscribe**: the start of a paid subscription (Help Centre wording). The developer reference says "applies to start", which could also describe the day-0 checkout, so reading Subscribe as the day-30 event is an interpretation. | **system_generated**. Meta's own example for this value is an auto-pay subscription renewal ([Dev server event](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/server-event)) | value = amount charged, currency | **No.** It falls outside every click window, both for optimisation ([H 197634954160445](https://www.facebook.com/business/help/197634954160445)) and for 28-day click reporting ([H 854500742637772](https://www.facebook.com/business/help/854500742637772)). Use it for reporting, audiences and the database join. |
| Direct paid checkout (no trial) | Purchase (value and currency required) | website | value = amount paid | Yes |

### 2.2 What the code sends today

| Event | Trigger | Sends today | Gap against Meta |
|---|---|---|---|
| CompleteRegistration, email signup | `auth.py:558-566` | Hashed em and external_id. fbc built from `signup_fbclid`, which is first-touch and timestamped with `created_at`. fbp from the request body; it isn't persisted (`auth.py:111-116`). event_source_url = landing path. `content_name=method`. event_id `signup.<hash(user id)>`. There is also a browser copy with the same eventID and no advanced matching (`metaConversions.ts:95-105`). | **No `client_user_agent`, no `client_ip_address`.** The server copy probably reaches Meta first, and Meta generally keeps the first arrival, so the copy it keeps may lack both. That ordering is an inference. |
| CompleteRegistration, OAuth | `oauth.py:780-784` | Server copy: same as above, without fbp (`oauth.py:776-779`). **The browser copy is inert in practice.** It is coded on `/app/onboarding` (`app/app/onboarding/page.tsx:148`), but the OAuth callback redirects straight to `/app/onboarding` (`oauth.py:838-841`), the pixel refuses to load on `/app/*` (`MetaPixel.tsx`, `EXCLUDED_PREFIXES`), and `trackMetaCompleteRegistration` returns without sending when `fbq` is undefined (`metaConversions.ts:93`). | No UA, IP or fbp, and effectively server-only. This matters: the same file's comment records that, as of 2026-09-02, every account that had put a card on Tapeline signed up with Google (`app/app/onboarding/page.tsx:112-117`). |
| StartTrial | `webhooks.py:561-580`. Fires on `customer.subscription.created/updated` when status is `trialing` and `trial_started_at` was null. | em, external_id, fbc, event_source_url `/app/billing`, `custom_data={currency: USD}`, action_source `website` (the `send_event` default, `meta_capi.py:263`), event_id `trial.<hash(user id)>` (`meta_capi.py:386`). No value. No browser copy, by design (`MetaPixel.tsx:23`; `MetaPixel.test.tsx:90`). | No UA, IP or fbp |
| **Purchase** | `webhooks.py:357-360` → `_send_purchase_conversion` (`113-237`). Fires on `checkout.session.completed` whenever `client_reference_id` and `customer` resolve to a user, trial checkouts included. | `value = amount_total/100` (`189-194`). A trial checkout carries `subscription_data.trial_end` (`billing.py:214-218, 282`), so `amount_total` is what is due at checkout: **expected to be $0. Confirm this on one real event in Stripe.** Also sends `content_name` = tier and `content_category` = billing period (`meta_capi.py:418-421`), event_source_url `/app/billing` (`webhooks.py:230`), and event_id `purchase.<hash(checkout session id)>`. It is latched once per subscription as `ga4_purchase:{subscription_id}` (`172`). The same call sends the same value to GA4's server-side purchase event. | **Confirmed defect (timing and label); the $0 value is expected, pending the Stripe check.** For trials it is a day-0 duplicate of StartTrial, and it misstates value. `track_purchase`'s docstring says the first real charge succeeded (`meta_capi.py:409`); the wiring does not do that. The only fixture, `_checkout_obj` (`test_server_side_conversions.py:193`), uses a non-trial `amount_total` of 27900 and exercises only the GA4 destination, so the $0 case is untested. No UA, IP or fbp. |
| **First paid charge** | Nothing | **No Meta event.** The code already detects the moment: the `paid_start:{sub_id}` latch fires once when a subscription first becomes active, including `trialing → past_due → active` (`webhooks.py:688-704`). But it only sends the welcome email and a founder Telegram message. `invoice.payment_succeeded` (`1321-1363`) only handles dunning recovery. | **Confirmed gap** |

Two notes on the table. First, no official Meta page read here says a $0 Purchase hurts number-of-conversions optimisation ([H 296463804090290](https://www.facebook.com/business/help/296463804090290)). The documented harm is to value signals and to reporting. Second, StartTrial's EMQ of 0.0 most likely reflects an empty window rather than a broken payload. EMQ is computed from the last 48 hours of website events ([H 765081237991954](https://www.facebook.com/business/help/765081237991954)), and StartTrial fires only a few times a month (inference). Don't use it as the go/no-go signal.

### 2.3 Proposals (code changes are proposals only; nothing was changed)

- **P1. Send UA and IP on every website event.** Capture `client_user_agent` and `client_ip_address` on the signup request, on the OAuth callback (a top-level browser navigation, so its IP and UA should be the visitor's; inference), and on `POST /api/billing/checkout`, then store them. Attach them to CompleteRegistration directly, and to StartTrial and Purchase from the stored values.
  - A Stripe webhook carries Stripe's IP and user agent, not the buyer's, so never take them from the webhook.
  - Reuse `services/rate_limit.client_ip()`, which reads `Fly-Client-IP`.
  - Confirm those requests reach the API straight from the browser and not through a Next.js server proxy. Otherwise the IP and UA are the proxy's. The risk is real in code: `next.config.js:12-16` rewrites `/api/*` to the backend, and `lib/api.ts:1` falls back to relative paths when `NEXT_PUBLIC_API_URL` is unset at build.
  - Sending IP and user agent to Meta is new data. `meta_capi.py` go-live item 5 makes the privacy-policy update a prerequisite.
- **P2. Persist fbp.** Store `_fbp` at signup; today it is forwarded once and dropped. Send it on StartTrial, Purchase and Subscribe. The OAuth path never sees it (`oauth.py:776-779`) and its browser copy doesn't fire (§2.2), so OAuth needs `_fbp` captured before the provider redirect.
- **P3. Keep the latest fbclid.** Store the last-touch fbclid, or overwrite it on each new one. Meta says to keep the latest value; `utm.ts` currently keeps first-touch for up to 30 days.
- **P4. Stop the $0 trial Purchase.** Don't send Purchase when the checkout is a trial (`amount_total == 0` and a trial is set). If a count is needed for continuity, send it with `opt_out=true` so it only feeds attribution ([Dev server event](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/server-event)). Keep Purchase for direct paid checkouts. Apply the same guard to the GA4 server purchase: the client-side `trial=1` fix at `billing.py:243-249` never reached the server path.
- **P5. Send Subscribe on the first real charge.**
  - **Trigger:** `invoice.payment_succeeded` where `amount_paid > 0`, for a subscription that carried a trial. Latch it once per subscription with a **new** key; `ga4_purchase:` is already claimed at checkout.
  - **Filter carefully:** a $0 trial-start invoice can also arrive as paid (Stripe behaviour, not verified here), so `amount_paid > 0` is required. Run it whether or not the dunning branch fires, since a first charge that recovers from dunning still counts.
  - **User lookup:** this handler resolves the user only by `stripe_customer_id` (`webhooks.py:1329-1331`), without the metadata fallback the subscription handler has (`376-386`), so a duplicate-checkout subscription would be missed.
  - **Payload:** `action_source=system_generated`, `value=amount_paid/100`, `currency`, event_id `subscribe.<hash(subscription id)>`, plus em, external_id, fbc and fbp. Meta also defines an unhashed `subscription_id` customer-information parameter ([Dev CIP](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/customer-information-parameters)); sending it would put a raw Stripe id on the wire, which `event_id_for` deliberately avoids, so it is optional.
  - **Why the invoice:** the price on the subscription is not the amount charged when a referral, win-back or save-offer coupon applies.
- **P6. Leave StartTrial value unset.** Don't set it to the plan price, which would put unearned revenue into ROAS columns. Skip `predicted_ltv`; pLTV needs 100 attributed conversions a week ([H 2519794055122336](https://www.facebook.com/business/help/2519794055122336/)).
- **P7. Verify without opening Ads Manager.**
  - Test Events via `META_CAPI_TEST_EVENT_CODE`. Under Core Setup, Test Events hides URL paths and custom parameters, so it can't be used to check `event_source_url` ([H 124742407297678](https://www.facebook.com/business/help/124742407297678)).
  - The Dataset Quality API reports match-key coverage for `user_agent` and `ip_address` ([Dev Dataset Quality API, updated 2026-06-28](https://developers.facebook.com/docs/marketing-api/conversions-api/dataset-quality-api/)). It needs a user or system user with at least partial access ("Use events dataset"), and an app with `ads_read` plus `ads_management` or `business_management`. Whether the existing token has those is unverified.
  - Check Diagnostics daily, including "Previously detected". An issue not interacted with within three days of first detection moves there and its resolution instructions are removed ([H 667164051342757](https://www.facebook.com/business/help/667164051342757)).
- **P8. Browser advanced matching (founder and privacy decision).** For restricted verticals including financial services, Meta recommends manual advanced matching ([H 930861050579797](https://www.facebook.com/business/help/930861050579797)). Repo policy forbids it (`MetaPixel.test.tsx:95`). Not required if P1–P2 ship.

**Order.** Ship P1–P3 before any flight, because the current optimisation event (CompleteRegistration) also lacks UA and IP. Ship P4–P5 before anyone reads Meta value or Purchase columns, and before any StartTrial switch.

---

## 3. When to change the optimisation event

### 3.1 Meta's thresholds

| Threshold | Meta figure | Source |
|---|---|---|
| Exit learning | ~50 results in 7 days after the last significant edit | [H 112167992830700](https://www.facebook.com/business/help/112167992830700) |
| What counts toward it | Only events inside the attribution setting | [H 197634954160445](https://www.facebook.com/business/help/197634954160445) |
| Budget vs goal cost | Daily budget at least 10× the average goal cost | [H 355670007911605](https://www.facebook.com/business/help/355670007911605) |
| Cost-per-result goal | Budget at least 5× the goal; works best at 50–100+ conversions a week | [H 203183363050448](https://www.facebook.com/business/help/203183363050448); [H 272336376749096](https://www.facebook.com/business/help/272336376749096) |
| Judging cost per result | A window holding 50–100 conversions; Highest volume for at least 2 weeks to set a baseline; wait at least 7 days after any change. This is written for cost goals, and applying it here is an extension. | [H 176339196621566](https://www.facebook.com/business/help/176339196621566); [H 272336376749096](https://www.facebook.com/business/help/272336376749096) |
| Value optimisation | Recommended: ≥100 events with ≥5 distinct values in 14 days. Test for at least 3 weeks at 50+ a week. | [H 571188993373447](https://www.facebook.com/business/help/571188993373447); [H 296463804090290](https://www.facebook.com/business/help/296463804090290) |
| pLTV | ≥100 attributed conversions a week for 4 weeks; ≥5 distinct positive values, with the top at least 3× the bottom; value sent within 7 days | [H 2519794055122336](https://www.facebook.com/business/help/2519794055122336/) |
| A/B test | 7–30 days; ≥80% estimated power before publishing; a winner needs ≥65% confidence | [H 290009911394576](https://www.facebook.com/business/help/290009911394576); [H 560857351380163](https://www.facebook.com/business/help/560857351380163); [H 239549606692303](https://www.facebook.com/business/help/239549606692303) |
| Rare event | "Learning limited" is a forecast, and one listed fix is a more frequent event. Under ~50 conversions a week, LPV optimisation could be an effective alternative. When zero conversions are predicted, choose a more common event or LPVs. | [H 269269737396981](https://www.facebook.com/business/help/269269737396981); [H 203012060587398](https://www.facebook.com/business/help/203012060587398); [H 197634954160445](https://www.facebook.com/business/help/197634954160445) |
| Significant edits | Changing the optimisation event, targeting or creative; adding an ad; pausing 7+ days; changing bid strategy. Budget changes count depending on size, with no percentage given. | [H 316478108955072](https://www.facebook.com/business/help/316478108955072) |

### 3.2 Tapeline against those thresholds (A$25/day)

| Event | Rough events per week | Budget for 50/week | Budget under the 10× rule |
|---|---|---|---|
| Link click | ~40 at best | ~A$30/day | ~A$44/day |
| CompleteRegistration (Meta-attributed) | ~1.2 | ~A$290/day | ~A$410/day |
| StartTrial | ~0.8 (2 cards from 3 signups, n=3) | ~A$440/day | ~A$620/day |
| First paid charge | 0 that can count (it lands on day 30 or later) | never | never |

### 3.3 Decision rule

- **Stay on CompleteRegistration at A$25/day.** Of the two day-0 events, it is the more frequent. Every official low-volume page points toward *more* frequent events, never rarer ones.
- **Switch to StartTrial only when all four of these hold:**
  1. P1–P3 have shipped, and StartTrial shows UA and IP in Test Events.
  2. Events Manager shows the data source category, and StartTrial isn't a restricted event ([H 1402913027039332](https://www.facebook.com/business/help/1402913027039332); [H 511197658391698](https://www.facebook.com/business/help/511197658391698)).
  3. Carded trials become revenue: a cohort from Meta clicks shows trial-to-paid above zero. Meta frames the choice as optimising for the true business goal "or the next closest proxy" ([H 950694752295474](https://www.facebook.com/business/help/950694752295474)). A card has not yet shown it is that proxy: every carded trial that has reached its end so far has cancelled or failed its first charge.
  4. It happens at a flight boundary. A pause of 7 days or more resets learning anyway.

  Record the switch as a **departure** from Meta's low-volume advice. The pLTV page's "optimise on the intended event to build volume" applies only to advertisers who are already eligible for pLTV, so it doesn't back this switch.
- **LPV or link clicks.** At this volume, Meta's own documentation points here. The playbook rejects it, but only on third-party evidence about Audience Network traffic. The only Meta-native way to settle it is an A/B test of CompleteRegistration against LPV:
  - In the LPV arm, exclude Audience Network and untick "limited spend".
  - Pause the live campaign while the test runs: Meta says a test audience shouldn't be used by any other campaign at the same time ([H 290009911394576](https://www.facebook.com/business/help/290009911394576)).
  - Publish only if the draft shows estimated power of 80% or more. At about A$12.50/day per arm that is unlikely.
  - Below 80%, don't run it; stay on CompleteRegistration.
- **Not before the §3.1 thresholds:** value optimisation, cost goals, pLTV, incremental attribution, lift tests.

### 3.4 While the ad set can't exit learning

- **Learning limited is the expected state** (playbook §1; not restated here).
- **Read in whole weeks, starting from the last significant edit.** Add the columns Last significant edit, Optimisation events and Cost per optimisation event. Never compare periods that straddle an edit ([H 942374239243867](https://www.facebook.com/business/help/942374239243867)).
- **Spend can run above A$25 on any given day.** It can reach 175% of the daily budget in a day and 7× in a Sunday–Saturday week; the 75% flexibility is still rolling out to some accounts ([H 190490051321426](https://www.facebook.com/business/help/190490051321426)). At A$43.75/day, the playbook's "A$123 with zero signups" kill rule can trip in about 3 days, inside Meta's 7-day wait. **Check kill rules only at the end of a Sunday–Saturday week.** Start flights on a Sunday, in the ad account's time zone, so week 1 isn't prorated.
- **CPM is not a performance signal under conversion optimisation.** Compare CPM only across ads with the same event and the same period ([H 1364841787225722](https://www.facebook.com/business/help/1364841787225722)).
- **A sub-100 opportunity score is expected under FPS.** Never switch a campaign off because of it ([H 804913634782260](https://www.facebook.com/business/help/804913634782260)).
- **Budget scheduling doesn't help.** It only adds spend, up to 8× the daily budget in a window, and Meta doesn't say whether that counts as a significant edit ([H 633318028866693](https://www.facebook.com/business/help/633318028866693)).
- **Budget steps.** The playbook already notes Meta gives no percentage. What the page does give: a budget change is significant "depending on the magnitude", and its only example is USD 100→101 (not significant) versus 100→1,000 (may be) ([H 316478108955072](https://www.facebook.com/business/help/316478108955072)).

---

## 4. Creative rules applied to D, E and B2

**Naming.** "B2" here means the voice-over (VO) cut of concept B built by `build3.mjs`, with the headline "$0 today. The charge date is on the page." It is **not** B2 in `docs/ads/meta-burst-2026-08/concept-b-variants.md`.

### 4.1 Measured state of the shipped VO cuts

| | D (swing traders) | E (the record) | B2 ($0 today) |
|---|---|---|---|
| Length (9:16) | 27.6 s | 26.6 s | 28.5 s |
| Frame 1 | Static text: no motion, no product | same | same |
| Brand on screen | Every frame | same | same |
| Scene 05 starts (card, $0, cancel shown on screen) | 14.3 s | 13.2 s | 15.2 s |
| Price and interval on screen (scene 06) | 22.3 s | 21.3 s | 23.2 s |
| Primary text: length / position of "$19.99" | 375 / 290 | 334 / 278 | 305 / 144 ("$0" at 47) |
| Headline / description length | 22 / 60 | 22 / 60 | **41** / 60 |
| Safe bands | 9:16: top 270 px (14.1%), bottom 770 px (40.1%), sides 84 px (7.8%). 4:5 bottom band 160 px (11.9%). 1:1 bottom band 140 px (13.0%). | same | same |

### 4.2 Meta's rules and how each concept fares

| Rule (source) | D | E | B2 | Action |
|---|---|---|---|---|
| **R1 Similarity.** Ads that share key visual and thematic attributes are grouped as one creative. Diversification means a different look, feel, storyline and message ([Meta news 2025-12-16](https://www.facebook.com/business/news/demystifying-creative-diversification)). No threshold is published. | Shared template, screenshot and voice; scenes 05–06 identical | same | same | Meta will likely treat the three as one creative (inference). That's fine for sequential solo windows. Before running any two at once, change the *visual treatment* (for example a screen recording or founder to camera), not just the hook. |
| **R2 Diversify by motivation.** Build personas around needs and purchase blockers ([2024-11-19](https://www.facebook.com/business/news/three-steps-to-optimize-your-performance-with-creative-diversification); [2025-04-22](https://www.facebook.com/business/news/the-creative-advantage-unlocking-the-power-of-diversification-with-meta-andromeda)) | Need: rank a watchlist | Blocker: can I inspect it first? | Blocker: cost and card | Keep. The set already follows Meta's framing. |
| **R3 First 3 seconds.** Brand and key message; motion or a compelling visual in frame 1; 6–15 s is more effective; Feed under 15 s, Stories under 10 s; key information early ([H 188534925073536](https://en-gb.facebook.com/business/help/188534925073536)) | 27.6 s, static opening | 26.6 s | 28.5 s | Add a ≤15 s cut per concept: hook → one product frame → money scene with price and interval → CTA with the disclosure. Open on motion or the product screenshot. The short cut must still show "$0 today", card required, price and interval, how to cancel, and the disclosure line. |
| **R4 Sound.** Design for sound off and add subtitles for all dialogue ([H 188534925073536](https://en-gb.facebook.com/business/help/188534925073536)). Reels default to sound on ([Reels ads page](https://www.facebook.com/business/ads/facebook-instagram-reels-ads)). Uploaded `.srt` captions attach to the video, named `filename.en_US.srt` ([H 1675722002698686](https://www.facebook.com/business/help/1675722002698686)). | On-screen text paraphrases the VO: "one number they can compare" vs spoken "one number to rank the watchlist by" | Scene 03 paraphrased | CTA "Not investment advice" is spoken; on screen it appears only in the disclosure line | Card and cancel terms **are** on screen in scene 05 for all three, so sound-off viewers see them. Still, the files carry no verbatim captions, whatever the playbook's "burned-in captions" says. Upload an `en_US.srt` per video, or align on-screen lines to the spoken words. |
| **R5 Safe zone.** Reels ads with a disclaimer keep the bottom 40% clear; 9:16 video in Instagram Feed follows the Reels rule ([H 980593475366490](https://www.facebook.com/business/help/980593475366490)). The Ads Guide says 14% top, 35% bottom, 6% sides ([Reels Ads Guide](https://www.facebook.com/business/ads-guide/update/video/instagram-reels)). | 9:16 passes both | same | same | 9:16 is compliant as built. The 4:5 and 1:1 cuts fail in Reels and Stories, so opt them out of those placements (R7). |
| **R6 Text length.** Primary text ≤125, headline ≤40, description ≤25 characters ([H 223409425500940](https://www.facebook.com/business/help/223409425500940)) | Price at character 290 | 278 | 144; headline 41 | Open every primary text with a line of 125 characters or fewer, e.g. *"30-day Premium trial: card required, $0 today, then $19.99/mo or $199/yr, first charge at trial end. Cancel in one click."* (121 chars; passes `lint-copy-compliance.mjs --ads`, run 2026-09-13). B2's headline is 41 characters and says "$0 today" with no card mention. Text is truncated differently by placement and device, so the headline can be read without the primary text's card line (inference), which would break the playbook's rule that "$0 today" always travels with "card required". Replace it with *"$0 today, card required. Charged day 30."* (40 chars; passes `lint-copy-compliance.mjs --ads`, run 2026-09-13). A 60-character description will be truncated, so keep the disclaimer in the video frames rather than relying on the description. |
| **R7 Placement assets.** Cropping doesn't restrict delivery; opt-outs do. Every ad-set placement must keep at least one eligible asset ([H 1530327025203003](https://www.facebook.com/business/help/1530327025203003); [H 103816146375741](https://www.facebook.com/business/help/103816146375741)) | — | — | — | One ad per concept, three ratios, with opt-outs. Check whether the existing paused campaign allows multi-media ads. |
| **R8 Asset changes.** Pausing a non-primary asset doesn't disrupt learning; adding assets may restart it for the primary media ([H 1530327025203003](https://www.facebook.com/business/help/1530327025203003)) | — | — | — | Load every asset (≤15 s cut, static frame) **before** publishing, never mid-flight. |
| **R9 Mix.** Mix video with static images; start with up to 10 creatives per ad set and test for at least 4 days ([H 188534925073536](https://en-gb.facebook.com/business/help/188534925073536)) | — | — | — | Add a static frame (scene 03 or 06 PNG) inside each concept's ad at build time. |
| **R10 Fatigue status.** Shown only in single-creative ad sets. "Limited" means cost per result is above past ads; "fatigue" means 2× or more ([H 1346816142327858](https://www.facebook.com/business/help/1346816142327858)) | Visible only during a solo window | same | same | During a solo window, a fatigue flag means cost per result is at least 2× past ads (about A$82+ per signup on the August basis). |

### 4.3 Content-policy checks per concept

- **D.** Speaks in the third person and makes no claim about the viewer's finances. Keep it free of "you/your" wording tied to trading losses or account state ([Personal attributes policy](https://transparency.meta.com/policies/ad-standards/objectionable-content/privacy-violations-personal-attributes/)).
- **E.** "We publish every day. Including the bad ones." shows no figures. Showing that the record exists is the ceiling. Adding a hit rate, alpha or a vs-SPY figure risks two rules. The past-performance prohibition is worded for offers of investment opportunities, which Tapeline isn't, so applying it is a cautious reading. The more direct rule is Meta's ban on suggesting unrealistic outcomes for economic opportunity ([Prohibited Commercial Practices](https://transparency.meta.com/policies/community-standards/prohibited-commercial-practices/); [ad policy guidance](https://www.facebook.com/business/m/small-business/ad-policy-guidance)). The disclosure frame already includes a past-performance line.
- **B2.** The shipped headline has "$0 today" with no card mention; §4.2 R6 replaces it. Card, charge date and cancel are in scene 05 and at the start of the primary text; the R6 rewrite moves price and interval there too. That keeps the playbook's card-honesty rule inside the first 125 characters and in the headline.
- **Cross-check.** The CTA frame in all three names `tapeline.io/scorecard`. If the ad destination is `/signup?from=trial`, the on-screen URL and the click destination differ. Decide which is intended.

---

## 5. FPS constraints and policy disclosures

### 5.1 Targeting (violations are hard errors at publish)

- **Age and gender.** Age is fixed at 18–65+, so the Advantage+ age floor of 25 is not available. All genders must be included ([Dev: Special Ad Categories](https://developers.facebook.com/docs/marketing-api/audiences/special-ad-category/)).
- **Location.** Country, region or city only: no postcode, and **no location exclusion**. A US city or pin gets at least a 15-mile radius ([H 2220749868045706](https://www.facebook.com/business/help/2220749868045706)).
- **Unavailable.** Lookalikes (including Advantage+ lookalike and lookalike exclusion); saved audiences; behaviour and demographic targeting; interest and detailed-targeting exclusion. Interests can only come from an approved list. New Special Ad Audiences have been blocked since 2022-08-25 ([H 364084711158390](https://www.facebook.com/business/help/364084711158390)).
- **Advantage+ audience: official sources conflict.**
  - The Help Centre says FPS campaigns won't have access ([H 938372127764391](https://www.facebook.com/business/help/938372127764391)).
  - The dev SAC doc (2026-05-21) lists it as supported ([Dev: Special Ad Categories](https://developers.facebook.com/docs/marketing-api/audiences/special-ad-category/)).
  - The dev Advantage+ doc (2026-06-17) says access is "currently being rolled out" ([Dev: Advantage+ campaigns](https://developers.facebook.com/docs/marketing-api/advantage-campaigns/)).

  The UI is the authority. A geo-only ad set may read `advantage_audience_state` ENABLED in the API regardless, so a GET doesn't settle it (same dev doc). Separately, from Marketing API v26.0 a new FPS ad set with constrained targeting must set `advantage_audience` explicitly ([v26.0 post, 2026-07-29](https://developers.facebook.com/blog/post/2026/07/29/introducing-graph-api-v26-and-marketing-api-v26/)); this affects API builds only.
- **Custom-audience exclusion.** The dev doc lists it as supported, but also exposes an `is_eligible_for_sac_campaigns` check, so a given list can still be ineligible ([Dev: Special Ad Categories](https://developers.facebook.com/docs/marketing-api/audiences/special-ad-category/)). The Help Centre says audience exclusion is limited or unavailable ([H 2220749868045706](https://www.facebook.com/business/help/2220749868045706)). Confirm in the UI.
- **Customer lists.** The previously announced US certification restrictions will **not** roll out; the page adds that advertisers remain responsible under the Business Tools Terms ([H 1452187872132363](https://www.facebook.com/business/help/1452187872132363)). Audience names and criteria must not imply financial information ([terms, eff. 2025-12-03](https://www.facebook.com/legal/terms/customaudience)), and custom audiences that suggest financial status are flagged and can't be used ([H 2455915321411996](https://www.facebook.com/business/help/2455915321411996)). Use "tapeline-accounts", not "carded" or "past-due".
- **Website custom audiences.** Wait for several hundred people before using one ([H 237515166435276](https://www.facebook.com/business/help/237515166435276)). Under Core Setup, build them on standard events, not URL rules ([H 124742407297678](https://www.facebook.com/business/help/124742407297678)).

### 5.2 Placements, bidding and creative tooling

- **Placements.** Account-level controls don't apply to FPS ([H 1438478636941047](https://www.facebook.com/business/help/1438478636941047)).
- **Bidding.** Bid multipliers are blocked ([Dev: Special Ad Categories](https://developers.facebook.com/docs/marketing-api/audiences/special-ad-category/)). Value rules still work for SAC campaigns, but age, gender and location criteria get the ad rejected ([H 535014515741813](https://www.facebook.com/business/help/535014515741813)).
- **Generative AI features.** These may not be available to financial services ([H 223409425500940](https://www.facebook.com/business/help/223409425500940)). Ignore Meta's GenAI uplift figures, and make creative diversity by hand.
- **Existing-customer budget cap.** Removed. The manual two-ad-set replacement would split learning; don't use it ([H 1142614290190459](https://www.facebook.com/business/help/1142614290190459)).

### 5.3 Data and measurement

- **Data source category.** A Meta-assigned "Financial service" category can't be changed, only reviewed. Restrictions can go as far as blocking specific mid- and lower-funnel standard events. Notice comes by email and in Events Manager ([H 1402913027039332](https://www.facebook.com/business/help/1402913027039332); [H 511197658391698](https://www.facebook.com/business/help/511197658391698)).
- **Core Setup.** Strips custom parameters and URL paths but keeps standard parameters; Meta's examples are value, currency and content_id. Tapeline's Purchase also relies on `content_name` and `content_category`, which are standard but not named in those examples (§7.1). Automatic advanced matching may be unavailable. Custom events need review ([H 124742407297678](https://www.facebook.com/business/help/124742407297678)).
- **Custom conversions.** One that suggests financial status gets flagged, and after publishing it can't be swapped ([H 2455915321411996](https://www.facebook.com/business/help/2455915321411996)).
- **Marketing API.** Use `FINANCIAL_PRODUCTS_SERVICES`; CREDIT was replaced on 2025-01-14. 7d_view and 28d_view data left the Insights API on 2026-01-12 ([Dev OCC 2025](https://developers.facebook.com/docs/marketing-api/out-of-cycle-changes/occ-2025/)). The Insights reference still lists both in its enum, next to 28d_click, 1d_ev, incrementality and custom, so a listed value is not proof the data returns ([Insights reference, updated 2026-08-06](https://developers.facebook.com/docs/marketing-api/reference/ad-account/insights/)).

### 5.4 Verification and Australia

- **The US is on Meta's list** for financial-services verification. Advertisers promoting securities and investments to US audiences must verify both advertiser and payer, and both names appear in Ad info and the Ad Library ([H 719892839342050](https://www.facebook.com/business/help/719892839342050)). Whether a scanner subscription counts as "securities and investments" is a judgement call, so get the lawyer's view. If prompted, verify before the next flight. What Meta asks for depends on whether you verify as an organisation or an individual advertiser, and the verified name is public, so decide that beforehand. (Since March 2026 the term is "advertiser", replacing "beneficiary": [H 983527276402621](https://www.facebook.com/business/help/983527276402621).) H 983527276402621 doesn't mention Business Verification, so don't assume the playbook's Business Verification step covers this.
- **Australia.** The Australian prompt fires when an FPS ad set targets **Australia as a location**. Ads aimed at a global audience must also follow Australia's Online Scams Code. An "exemption claimed" disclaimer can't be edited once live; the ad has to come down ([H 719892839342050](https://www.facebook.com/business/help/719892839342050)). **Target the US only, and set the SAC country to the US.**

### 5.5 Ad content policies

- **Subscription services.** An ad that asks for personal information fails if it lacks any one of: an unticked opt-in checkbox, clear cancellation language, or clearly shown price and billing interval. Fine print or a separate link doesn't count. There is no trial carve-out ([policy](https://transparency.meta.com/policies/ad-standards/content-specific-restrictions/subscription-services)). Review can cover the ad destination, and ads can be re-reviewed at any time ([H 204798856225114](https://www.facebook.com/business/help/204798856225114)).
- **Prohibited commercial practices.** Persistent negative feedback about deceptive subscriptions, unauthorised charges or refunds not honoured can lead to restricted or disabled accounts ([policy](https://transparency.meta.com/policies/community-standards/prohibited-commercial-practices/)). Every carded trial that has reached its end so far cancelled or failed its first charge, so the trial-end reminder email, one-click cancel and money-back promise must work and match the ad.
- **Investment claims.** No guaranteed or risk-free returns, no past performance used to set expectations, no quick-return or get-rich-quick claims (same policy). These are worded for offers of investment opportunities, so applying them to a scanner is a cautious reading; the directly applicable rule is no unrealistic outcomes for economic opportunity ([ad policy guidance](https://www.facebook.com/business/m/small-business/ad-policy-guidance)).
- **Personal attributes.** No "you/your" phrasing that asserts or implies the viewer's financial status or financial information ([policy, changelog 2024-06-26](https://transparency.meta.com/policies/ad-standards/objectionable-content/privacy-violations-personal-attributes/)).
- **Crypto.** Education or news about crypto needs no permission. Exchange or trading offers need written permission and a licence ([policy, changelog 2026-04-15](https://transparency.meta.com/policies/ad-standards/restricted-goods-services/cryptocurrency-products-and-services/)). Keep coin pages out of ads, or show them as information only.

### 5.6 The destination page `/signup`, as read in code

| Subscription-policy test | State | Where |
|---|---|---|
| Price and billing interval, clearly shown | Present: "Then $19.99/month, or $199/year … recurring until you cancel", at `text-sm text-fg` | `SignUpForm.tsx:853-881` |
| Cancellation language | Present: "Cancel in one click" from billing | same |
| Unticked opt-in checkbox | Two email-consent boxes, both unticked by default. The subscription acknowledgement box was removed on 2026-09-05. The policy is written for ads; Meta doesn't say whether a free-signup landing page needs a subscription opt-in. **Open.** | `SignUpForm.tsx:276-277, 293-311, 777-788` |
| **Page metadata** | **Stale and in review scope.** The title says "30-Day Premium Trial". The description says signing up starts the trial ("$0 today, first charge on day 30") and lists **"congressional trades"**. Signup starts no trial, and congressional trades were removed from Premium marketing (#770). Fix before the next flight; not edited here. | `frontend/app/signup/layout.tsx:7-9` |

---

## 6. Where Meta's guidance contradicts the playbook

| # | Playbook | Meta's guidance | Resolution |
|---|---|---|---|
| 1 | §1–2: accept Learning Limited as a budget fact; build at A$25/day | Budget should be ≥10× the goal cost, which A$25/day misses for every goal, link clicks included ([H 355670007911605](https://www.facebook.com/business/help/355670007911605)). Budgets should also be realistic ([H 112167992830700](https://www.facebook.com/business/help/112167992830700)). | Keep the structure. Make budget an explicit founder decision, and label every flight read as under-powered by Meta's own rule. |
| 2 | §2: says Meta pitches LPV mainly at accounts with no lower-funnel events | Meta gives the under-~50-conversions-a-week case **first**; the no-lower-funnel case is secondary ([H 203012060587398](https://www.facebook.com/business/help/203012060587398)) | Fix the paraphrase. The no-LPV rule rests only on third-party evidence. §3.3 gives the Meta-native test. |
| 3 | §2 decision, step 2: switch to StartTrial at the next flight | Low-volume pages point to *more* frequent events ([H 269269737396981](https://www.facebook.com/business/help/269269737396981); [H 197634954160445](https://www.facebook.com/business/help/197634954160445)). The pLTV "build volume" line only applies to already-eligible advertisers. A proxy has to represent the business goal ([H 950694752295474](https://www.facebook.com/business/help/950694752295474)). | Make the switch conditional (§3.3), and add the paid-conversion evidence gate. |
| 4 | §2 Audience: leave Advantage+ audience on if offered; "API docs say rolling out" (cites 906206294602874); exclusions limited | 906206294602874 doesn't say that. The Help Centre says FPS gets no access (938372127764391); the dev docs say supported or rolling out. The dev doc also lists custom-audience exclusion as supported. | The UI is the authority, and the setting is the same either way. Cite the dev Advantage+ doc instead. Test a custom-audience exclusion in the UI. |
| 5 | §2 SAC: Australia rules sourced to Mediaweek; says FPS "may not" support location exclusion | Location exclusion is definitively unsupported. Australian rules trigger on Australia as a targeted location, or on a global audience. The SAC country defaults to the tax country ([H 719892839342050](https://www.facebook.com/business/help/719892839342050); [Dev SAC](https://developers.facebook.com/docs/marketing-api/audiences/special-ad-category/)). | Same actions: US-only targeting, SAC country = US. Replace the Mediaweek citation. |
| 6 | §2 Attribution: "7-day click, 1-day view" | Standard attribution now has three parts, including 1-day engage-through, and click-through counts link clicks only (March 2026) | Use §1 row 10. |
| 7 | §2 Budget: campaign vs ad-set level doesn't matter | True for delivery. A campaign-level budget also keeps `advantage_budget_state` ENABLED ([Dev Advantage+](https://developers.facebook.com/docs/marketing-api/advantage-campaigns/)). | Set the budget at campaign level. |
| 8 | §2 Ads and §3 ratios: flexible ad with per-placement ratios (2720085414702598) | In the multi-media workflow, cropping doesn't restrict delivery and opt-outs do. Active or paused campaigns are unsupported. The Media breakdown has no Start trial or Subscribe ([H 1530327025203003](https://www.facebook.com/business/help/1530327025203003); [H 1822387965412520](https://www.facebook.com/business/help/1822387965412520)). | Opt the 4:5 and 1:1 assets out of Stories and Reels, and review crops. Expect to need a new campaign. Keep one ad per concept. This assumes the multi-media workflow is what the playbook's flexible ad format now is; no page read states that (§7.1). |
| 9 | §3: fair test via 10-day solo windows | Meta doesn't recommend informal on/off testing; use the A/B tool with equal budgets and ≥80% power ([H 1738164643098669](https://www.facebook.com/business/help/1738164643098669); [H 560857351380163](https://www.facebook.com/business/help/560857351380163)). Each new window adds an ad, which is a significant edit. | Draft an A/B test and read its estimated power. Publish at 80% or above, with no other campaign using the same audience at the same time ([H 290009911394576](https://www.facebook.com/business/help/290009911394576)). Otherwise run solo windows, labelled as informal, and rank only on attention metrics, as the playbook already does. |
| 10 | §3 fallback: Creative Test at about A$5/day, ~700 impressions per ad | If only test ads are active, they *may* receive more of the budget. No confidence level is given. Setting up a test adds ads ([H 1423851372208214](https://www.facebook.com/business/help/1423851372208214)). | If used, run the test ads alone and treat the output as an unranked read. The ~700-impression maths is a floor, not a forecast. |
| 11 | §3: VO with "burned-in captions"; no length set | Subtitles for all dialogue; 6–15 s; Feed under 15 s; motion in frame 1 ([H 188534925073536](https://en-gb.facebook.com/business/help/188534925073536)) | Add verbatim `.srt` files and a ≤15 s cut per concept (§4.2). |
| 12 | §3: D, E and B treated as three distinct concepts | Meta groups ads that look alike ([news 2025-12-16](https://www.facebook.com/business/news/demystifying-creative-diversification)) | Acceptable for sequential runs. Change the visual treatment before running any two together. |
| 13 | §4 item 2: the CAPI fix is UA and IP on StartTrial and Purchase | CompleteRegistration lacks them too, and the webhook has no browser to take them from. The OAuth signup's browser copy never fires, because the pixel doesn't load on `/app/onboarding`. fbp isn't persisted. fbclid is first-touch, but Meta asks for the latest. Purchase fires at $0 on trials, and nothing fires on the paid charge ([Dev CIP](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/customer-information-parameters); [Dev fbp/fbc](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/fbp-and-fbc); [H 402791146561655](https://www.facebook.com/business/help/402791146561655)). | Proposals P1–P6 (§2.3). |
| 14 | §4: A$123 zero-signup kill rule | Up to 175% of daily budget can spend in one day; judge on a 7-day wait and weekly averages ([H 190490051321426](https://www.facebook.com/business/help/190490051321426); [H 272336376749096](https://www.facebook.com/business/help/272336376749096)) | Check kill rules only at week end. |
| 15 | §7: retargeting only once the pool passes ~1,000. §1: value optimisation at "~100 per 14 days" (Birch) | Meta's usability floor for a website custom audience is "several hundred" ([H 237515166435276](https://www.facebook.com/business/help/237515166435276)). Value optimisation also needs ≥5 distinct values ([H 571188993373447](https://www.facebook.com/business/help/571188993373447)). | Keep 1,000 if wanted, but label it practitioner judgement and cite Meta's floor beside it. Re-source the value figure to Meta and add the distinct-values requirement; with 2 trial prices, value optimisation is out regardless of volume. |
| 16 | §8: a US verification requirement is unverified and the country list was unreadable | The US is on the list for securities and investments advertisers ([H 719892839342050](https://www.facebook.com/business/help/719892839342050)) | Close the question; see §5.4. |
| 17 | §1: "Meta's longest click window is 7 days" | Holds for optimisation. Reporting still offers 28-day click ([H 854500742637772](https://www.facebook.com/business/help/854500742637772); Insights reference updated 2026-08-06). | Reword. The day-30 charge falls outside 28 days as well. |
| 18 | §5–6 guardrails | Three rules are missing: personal attributes, feedback-driven account restriction, and crypto (§5.5). Two account toggles can also make unscheduled edits: auto-apply and "Test new creative features". | Add all three rules to the guardrails, and turn both toggles off. |
| 19 | Citation corrections | Sound-on is stated on the Reels ads page, not 980593475366490. The 48-hour EMQ window is on H 765081237991954, not the dev parameters page. The custom-conversion flag is on H 2455915321411996, not 124742407297678, and it carries no "September 2025" date. The FPS account-level placement rule is on H 1438478636941047, not 1362234537597370. | Fix the links; no substance changes. |

---

## 7. Not confirmed, and sources

### 7.1 Not confirmed: check in the UI, the account, or with Meta or the lawyer

**Availability under FPS in this account**
- Advantage+ audience
- Custom-audience exclusion
- Incremental attribution, engage-through or custom attribution
- Maximise value
- The A/B test tool, including estimated power and the duplicate flow
- Creative Test
- Multi-media ads and per-asset opt-outs, including whether the existing paused campaign supports them
- Whether the multi-media ad workflow (H 1530327025203003) is the same product as the playbook's flexible ad format (H 2720085414702598)
- Value-rule placement criteria (including Audience Network), and whether a value rule changes the Advantage+ state
- Whether "limited spend" applies to SAC campaigns

**Account state**
- Whether opportunity-score auto-apply is on
- Whether "Test new creative features" is present and ticked. The external agency has access, so check both.
- Whether the account is on the March 2026 link-click-only definition
- Whether Compare attribution settings shows 28-day click in the UI
- The dataset's data source category, and whether StartTrial, Subscribe or Purchase is restricted
- Whether value and currency survive on the restricted dataset, and whether `content_name` / `content_category` do (Core Setup names only value, currency and content_id as examples)
- Whether a Discriminatory Practices certification prompt is pending ([H 338925176776440](https://www.facebook.com/business/help/338925176776440))
- Which time zone the Sunday–Saturday budget week uses

**Measurement mechanics**
- What Meta does with a website event that lacks `client_user_agent`: reject, down-weight or flag
- Whether a `system_generated` Subscribe shows in a Website-location campaign's reporting
- Whether deduplication merges user_data or keeps the first copy ("generally" first)
- Whether the CAPI token can call the Dataset Quality API
- Whether a $0 Purchase affects number-of-conversions optimisation
- How two day-0 events for one user affect learning
- Tapeline's real `amount_total` on a trial checkout (check in Stripe)
- Whether the click URL's query string and fbclid survive under Core Setup
- Whether production signup and checkout calls go browser → `api.tapeline.io` directly or through the Next.js `/api` rewrite (decides whether P1's captured IP and UA are real)

**Policy scope**
- Whether a stock scanner is an FPS "investment service" and falls under "securities and investments" for verification
- Whether financial-services advertiser verification is a separate step from Business Verification
- Whether the unticked-checkbox test applies to a free-signup landing page
- Whether price text hidden behind "more" satisfies the subscription policy
- The FPS requirement date: the dev doc says both 14 and 21 Jan 2025

**Testing**
- Whether Creative Test ads count as a significant edit
- Whether the source ad can be paused during a Creative Test
- Which cost metrics the A/B tool allows
- Whether a budget-scheduling increase is a significant edit
- Whether the "creative insights" similarity diagnostic appears in this account
- Sound-off vs sound-on for Facebook Feed
- The Reels guide's 44-character primary text: it was shown in the Awareness view and is unconfirmed for Sales

**Behind a login.** The Blueprint lessons on objectives, data sources, CAPI, creative and testing may contain subscription-specific guidance that isn't on the Help Centre.

### 7.2 Claims corrected during verification

- **API attribution windows.** 7d_view and 28d_view were removed from the Insights API **effective 2026-01-12**. The changelog entry is dated 2025-10-13, so "13 Oct 2025" was the wrong date ([Dev OCC 2025](https://developers.facebook.com/docs/marketing-api/out-of-cycle-changes/occ-2025/)). The [Insights reference](https://developers.facebook.com/docs/marketing-api/reference/ad-account/insights/) (updated 2026-08-06; re-read 2026-09-13) still lists 28d_click, 1d_ev, incrementality and custom, and also still lists 7d_view and 28d_view.
- **ASC/AAC pause.** The v25 blog's "ASC/AAC paused in v26.0" is outdated. v26.0 shipped on 2026-07-29 and its launch post doesn't mention an ASC/AAC pause ([v26.0 post](https://developers.facebook.com/blog/post/2026/07/29/introducing-graph-api-v26-and-marketing-api-v26/)). The [Advantage+ campaigns dev doc](https://developers.facebook.com/docs/marketing-api/advantage-campaigns/) (2026-06-17) says legacy ASC/AAC campaigns are blocked from edits at v26.0, and only those using `existing_customer_budget_percentage` are paused. The v26.0 post adds that new FPS ad sets with constrained targeting must set `advantage_audience` explicitly.
- **pLTV "build volume" line.** Re-read 2026-09-13: it is addressed to advertisers who are eligible but can't yet select pLTV ([H 2519794055122336](https://www.facebook.com/business/help/2519794055122336/)). One verification note paraphrased it as advice for advertisers not yet eligible; that reading is wrong.
- **SAC "removed features" list.** The dev SAC doc removes more than saved and lookalike audiences. It also removes location exclusion, detailed-targeting exclusion, interest exclusion, certain interest inclusions and location selection.
- **`advantage_state_info` GET.** It doesn't prove FPS lacks Advantage+ audience, because a geo-only ad set can read ENABLED anyway.
- **"Meta's only numeric creative-volume guidance".** False. The Instagram video page gives up to 10 creatives per ad set, keeping the top 5 and testing for at least 4 days.
- **pLTV page.** It still uses the name "engaged-view", so it may predate the March 2026 rename. Its 1-day/7-day click advice is written for a first pLTV test.
- **Troubleshoot conversion optimisation (H 197634954160445).** Its targeting advice (lookalikes, detailed targeting, Audience Insights) is stale or unavailable under FPS. Its event-choice advice still stands.

### 7.3 Unreadable

**Blueprint (login required)**
- Paths 253165 (activities 660185, 660186) and 253163 (objectives and data signals)
- 253164 (Advantage+)
- 219713 and 211547 (CAPI)
- 766683 and 211557 (creative)
- 219764 (testing)
- 253136 (targeting)

**Pages not found or not rendering**
- Not found: learning-phase one-sheeter, bid-strategy one-sheeter, H 144240239372256, the video checklist lesson
- Redirected: the diversification campaign-guidance card
- Retired (404): 248410/251330
- Did not render: the H 298000447747885 accordion; the Apr 30 2026 changelog content on the financial-services policy page

**Research.** No official Meta Marketing Science guidance on small-budget testing was found.

### 7.4 Sources, with page dates

**Help Centre** (`facebook.com/business/help/<id>`; undated unless noted, read 2026-09-13)

*Objectives, goals and budgets*
- 1438417719786914 — objectives
- 355670007911605 — performance goals
- 950694752295474 — delivery best practices
- 197634954160445 — troubleshoot conversion optimisation (June 2024 banner; partly stale)
- 203183363050448 — minimum budgets
- 1725302974308722 — under-delivery; 75% flexibility still rolling out

*Value optimisation*
- 571188993373447 — value requirements
- 296463804090290 — about value
- 2519794055122336 — pLTV (older "engaged-view" naming)

*Attribution*
- 2198119873776795 — attribution models (reflects March 2026)
- 854500742637772 — compare attribution settings
- 644554008179419 — incremental attribution

*Advantage+*
- 1292656978738967 — Advantage+ campaign experience
- 906206294602874 — Advantage+ caveats
- 938372127764391 — Advantage+ audience controls
- 793748385630490 — create a campaign with Advantage+ audience
- 1362234537597370 — Advantage+ sales campaigns
- 1142614290190459 — existing customer budget cap
- 1602924913861363 — budget strategy
- 153514848493595 — Advantage+ campaign budget
- 2177212182495139 — campaign budget best practices
- 1212227546879178 — audience segments (may not be available)

*Placements, bidding and recommendations*
- 1438478636941047 — account-level controls (introduced gradually)
- 1462437878221374 — limited spend
- 535014515741813 — value rules
- 804913634782260 — opportunity score (in development)
- 2086509315182746 — recommendation types

*Audiences and FPS*
- 1452187872132363 — customer-list restrictions (cancelled; old timeline Oct 2024–Apr 2025)
- 1157846251802527 — FPS ads
- 2220749868045706 — FPS audiences
- 364084711158390 — Special Ad Audiences (cut-off 2022-08-25)
- 237515166435276 — website custom audience size

*Verification and review*
- 719892839342050 — financial-services verification
- 983527276402621 — verification process (March 2026 terminology; organisation vs individual; re-read 2026-09-13)
- 204798856225114 — ads in review (re-read 2026-09-13)
- 338925176776440 — Discriminatory Practices certification (cited, not read)

*Events, CAPI and data*
- 765081237991954 — event match quality
- 308855623839366 — CAPI best practices
- 402791146561655 — standard events
- 124742407297678 — core setup
- 1402913027039332 — data source categories
- 511197658391698 — data-sharing restrictions
- 930861050579797 — advanced matching
- 2455915321411996 — custom conversion restrictions (re-read 2026-09-13; no date on the page)
- 667164051342757 — diagnostics
- 823677331451951 — deduplication

*Learning phase, cost goals and testing*
- 112167992830700 — learning phase
- 269269737396981 — learning limited
- 316478108955072 — significant edits
- 203012060587398 — LPV best practices
- 272336376749096 — cost per result goal
- 176339196621566 — cost-per-result best practices
- 942374239243867 — last significant edit (pre-rename wording)
- 190490051321426 — daily budgets
- 633318028866693 — budget scheduling
- 1738164643098669 — A/B testing
- 290009911394576 — A/B best practices
- 560857351380163 — A/B by duplication (introduced gradually)
- 239549606692303 — confidence
- 1423851372208214 — creative test
- 1364841787225722 — performance fluctuations

*Creative*
- 103816146375741 — aspect ratios
- 1530327025203003 — multi-media ads
- 1822387965412520 — media breakdown
- 1675722002698686 — captions (re-read 2026-09-13)
- 980593475366490 — safe zone (notes the Sponsored→Ad label change)
- 223409425500940 — text (mentions the 6 May 2024 GenAI terms)
- 2084198785720343 — test new creative features (re-read 2026-09-13)
- 1082295769403815 — turn off enhancements (re-read 2026-09-13)
- 1346816142327858 — creative fatigue
- en-gb 188534925073536 — Instagram video (references late-2024 Feed changes)

**Meta for Business and newsroom**
- [click-attribution](https://www.facebook.com/business/news/click-attribution) — 2026-03-03
- [demystifying-creative-diversification](https://www.facebook.com/business/news/demystifying-creative-diversification) — 2025-12-16
- [Andromeda diversification](https://www.facebook.com/business/news/the-creative-advantage-unlocking-the-power-of-diversification-with-meta-andromeda) — 2025-04-22
- [three steps](https://www.facebook.com/business/news/three-steps-to-optimize-your-performance-with-creative-diversification) — 2024-11-19; ASC-specific, possibly stale
- [about.fb.com 2026 AI drives performance](https://about.fb.com/news/2026/01/2026-ai-drives-performance/) — 2026-01-28
- Undated:
  - [Reels ads](https://www.facebook.com/business/ads/facebook-instagram-reels-ads). The 34.5% figure comes from e-commerce, retail and CPG split tests.
  - [Reels Ads Guide](https://www.facebook.com/business/ads-guide/update/video/instagram-reels) (re-read 2026-09-13; the default view is the Awareness objective)
  - [opportunity score](https://www.facebook.com/business/tools/opportunity-score)
  - [A/B testing](https://www.facebook.com/business/measurement/ab-testing). Uses old ASC naming; possibly stale.
  - [ad-creative-diversity lesson](https://www.facebook.com/business/learn/video/ad-creative-diversity)
  - [ad policy guidance](https://www.facebook.com/business/m/small-business/ad-policy-guidance) (re-read 2026-09-13)
- STALE: [Advantage+ shopping campaigns page](https://www.facebook.com/business/ads/meta-advantage/advantage-plus-shopping-ads). It predates the 2025 unification; ignore its 150-creatives and existing-customer-cap guidance.

**Meta for Developers**
- [Special Ad Categories](https://developers.facebook.com/docs/marketing-api/audiences/special-ad-category/) — updated 2026-05-21
- [Advantage+ campaigns](https://developers.facebook.com/docs/marketing-api/advantage-campaigns/) — updated 2026-06-17
- [v25.0 blog](https://developers.facebook.com/blog/post/2026/02/18/introducing-graph-api-v25-and-marketing-api-v25/) — 2026-02-18; its pause schedule was superseded by v26.0 (2026-07-29)
- [OCC 2025](https://developers.facebook.com/docs/marketing-api/out-of-cycle-changes/occ-2025/) — entries 2025-01-14 and 2025-10-13 (the latter effective 2026-01-12)
- [Pixel reference](https://developers.facebook.com/docs/meta-pixel/reference) — updated 2024-07-16
- [CAPI best practices](https://developers.facebook.com/docs/marketing-api/conversions-api/best-practices) — updated 2026-06-28
- [Dataset Quality API](https://developers.facebook.com/docs/marketing-api/conversions-api/dataset-quality-api/) — updated 2026-06-28
- [customer information parameters](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/customer-information-parameters) — updated 2026-01-09 (re-read 2026-09-13)
- [Ad Account Insights reference](https://developers.facebook.com/docs/marketing-api/reference/ad-account/insights/) — updated 2026-08-06 (re-read 2026-09-13)
- [v26.0 launch post](https://developers.facebook.com/blog/post/2026/07/29/introducing-graph-api-v26-and-marketing-api-v26/) — 2026-07-29
- Undated:
  - [server event](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/server-event)
  - [fbp and fbc](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/fbp-and-fbc)
  - [deduplication](https://developers.facebook.com/docs/marketing-api/conversions-api/deduplicate-pixel-and-server-events)
- Dev docs under `/docs/...` now redirect to `/documentation/ads-commerce/...`; the old links still resolve.

**Transparency Center and legal**
- [Subscription services](https://transparency.meta.com/policies/ad-standards/content-specific-restrictions/subscription-services) — no dated changelog
- [Prohibited commercial practices](https://transparency.meta.com/policies/community-standards/prohibited-commercial-practices/) — no dated changelog. The ad-standard pointer now redirects to `/policies/ad-standards/deceptive-content/prohibited-commercial-practices/`.
- [Personal attributes](https://transparency.meta.com/policies/ad-standards/objectionable-content/privacy-violations-personal-attributes/) — changelog 2024-06-26
- [Cryptocurrency](https://transparency.meta.com/policies/ad-standards/restricted-goods-services/cryptocurrency-products-and-services/) — changelog 2026-04-15
- [Financial services](https://transparency.meta.com/policies/ad-standards/restricted-goods-services/financial-services/) — changelog 2026-04-30; what changed could not be read
- [Customer List Custom Audiences Terms](https://www.facebook.com/legal/terms/customaudience) — effective 2025-12-03
