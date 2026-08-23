# Meta ads — go-live runbook

*Operational companion to `META_ADS_DECISION.md`. That document is the **analysis** and it recommends **not** running Meta. The founder has decided to run it anyway (2026-08-21, after three explicit requests). This document does not re-argue that; it is the how, written so the test is measurable, compliant, and cheap to stop.*

*Nothing here is legal or financial advice. The items marked 🔴 are hard gates, not suggestions.*

---

## 0. One honest paragraph before you spend

`META_ADS_DECISION.md` §4 priced Meta at **$650–2,500 per payer** on the old no-card trial. The card-required trial (#536) materially improves that — a card-gated trial converts far better than an opt-in one — but the doc's own most-generous figure, **~$164 per payer, is still ~4× the affordable CAC** it derives (~$30–60). I previously told you #536 "fixed the economics"; that was too generous, and this is the correction. #536 makes Meta *measurable and less bad*, not *profitable on paper*.

So run this as a **message test with a hard stop**, not as a growth channel. The thing you are buying is an answer to "does any of this copy make a stranger sign up?" — which is gate condition 3 of the standing playbook and useful to every other channel regardless of what Meta costs. Budget it as tuition.

---

## 1. What is already built

| Piece | State | Where |
|---|---|---|
| Server-side Conversions API | ✅ shipped (#538) | `backend/app/services/meta_capi.py` |
| Browser pixel (PageView) | ✅ shipped (#538), **scoped to marketing pages** | `frontend/components/MetaPixel.tsx` |
| `Purchase` event | ✅ wired | `routers/webhooks.py` — behind the GA4 latch |
| `StartTrial` event | ✅ wired | `routers/webhooks.py` — on write-once `trial_started_at` |
| `CompleteRegistration` event | ✅ wired | `routers/auth.py` (email) + `routers/oauth.py` (Google) |
| CSP allows Meta origins | ✅ shipped | `frontend/next.config.js` |
| Ad copy, lint-clean | ✅ 5 variants | `META_ADS_DECISION.md` §9 |
| Landing message-match | ✅ exists | `?from=` on `/signup` |

**Verified inert today** — on live tapeline.io in a real browser: `window.fbq` is `undefined`, zero network requests to any facebook host, and no `_fb*` cookies. The CSP permits Meta, but nothing loads because `NEXT_PUBLIC_META_PIXEL_ID` is unset.

> ⚠️ **Do not verify this with `curl | grep connect.facebook.net`.** I used that check first and it was wrong. The pixel loads with `strategy="afterInteractive"`, so Next injects it **client-side after hydration** — it never appears in server HTML whether the pixel is on or off. That grep returns `0` in both states and proves nothing.
>
> Valid checks, after you enable it:
> ```bash
> # the pixel id DOES appear in the RSC payload when set
> curl -s https://tapeline.io | grep -c "<your-pixel-id>"
> ```
> or, definitively, open the site and run in the browser console:
> ```js
> typeof window.fbq          // "function" once live
> document.cookie.match(/_fbp/)
> ```

---

## 2. 🔴 Blockers — all three must be true before `META_PIXEL_ID` is ever set

1. **🔴 Privacy policy updated** to name Meta and describe exactly what is sent. `META_ADS_DECISION.md` §8 calls this out: a third-party advertising tracker on a finance site touches CCPA and the AU Privacy Act. Tracked separately — do not set the secret before it ships.
2. **🔴 Geo excludes Australia and every other verification-regime country.** See §4. This is the one mistake that is genuinely hard to undo.
3. **🔴 FPS Special Ad Category declared** on the campaign. Undeclared financial ads get rejected, and a rejection history is not free.

---

## 2b. 🔴 Two settings that can undo all of this from a dashboard

**Leave Automatic Advanced Matching OFF.** It is a per-pixel toggle in Events Manager. Switching it on makes `fbevents.js` scrape visible form fields — email, phone, name — off the page and send hashed values to Meta, **with no change to this repo and no deploy**. We deliberately pass no advanced-matching object to `fbq('init', …)`, but the dashboard toggle overrides that intent. If you enable it, the privacy policy becomes inaccurate the moment you click save.

**The pixel is scoped to marketing pages and must stay that way.** `components/MetaPixel.tsx` refuses to render on `/app/*`. This is not cosmetic. Meta's beacon reports the full current URL as its `dl` parameter — a payload field, so `Referrer-Policy` does not trim it — and the request goes to facebook.com, so the browser may attach Facebook cookies it already holds. An unscoped pixel would therefore tell Meta **which specific tickers a user researches, linkable to their real Facebook account**. Nothing is lost by scoping: every conversion is sent server-side by `meta_capi`, which needs no browser.

*Honest limit:* scoping prevents the script from ever being inserted on an `/app/*` page, which covers hard loads and bookmarks — the normal case for a logged-in user. It does not unload a script already inserted if someone client-side-navigates from a marketing page into `/app` in the same tab. No new PageView is sent in that case, but the script is present.

---

## 3. Which event to optimise toward

**Start with `CompleteRegistration`. Not `StartTrial`, not `Purchase`.**

This reverses the recommendation in #538's PR description, for a reason that only became clear on wiring it up:

- Meta's smart bidding wants **~50 optimisation events per ad set per week** to leave the learning phase.
- Since #536 the trial is card-required, so `StartTrial` is now *genuinely scarce* — it is a strong intent signal precisely because few people do it. At Tapeline's volume it will not come close to 50/week.
- `Purchase` is scarcer still, and arrives 14 days late — outside Meta's 7-day click window by construction (`META_ADS_DECISION.md` §7).
- `CompleteRegistration` (email + password only — the `/app/start` card wall follows at first sign-in, per #548) is the only event with any chance of volume, and since #536 decoupled it from the trial it is a clean, honest signal on its own.

**Send all three regardless** — they are all wired, and the funnel view is what makes the test readable. *Which one you optimise toward is a campaign setting, not a code change.*

Be aware of the trade-off you are accepting: optimising for free signups will find people who sign up and never pay. That is the classic "optimise for the cheap event" trap. It is still strictly better than the Google campaign's failure mode, which was optimising for **clicks** with no conversion import at all (`PAID_MARKETING_PLAYBOOK.md` §2).

---

## 4. 🔴 Geo — exclude Australia

**Target: United States only.**

**Exclude: Australia, UK, Taiwan, India, Singapore, Japan, Ireland, Hong Kong.**

Australia is not a preference, it is a gate. Since Feb 2025, ads promoting financial products *to users in Australia* require an AFSL-or-exemption **self-declaration** and carry a public "Paid for by" label; advertisers self-declaring as exempt get an **additional public label reading "AFS licence: exemption claimed"**, visible in the Ad Library while the ad runs (`META_ADS_DECISION.md` §3).

Tapeline's entire legal posture is an unlitigated publisher exemption. Putting a public, Meta-hosted, permanently-archived exemption claim on the record **before** the Holley Nethercote consult is the single worst available move. It keys on **audience location, not advertiser domicile** — being a Melbourne founder does not trigger it; showing an ad to a Melbourne user does.

---

## 5. Campaign setup

- **Objective:** Sales → conversions, optimising for `CompleteRegistration`. (Not Traffic. Traffic is what produced A$951 of nothing.)
- **Special Ad Category:** Financial Products & Services. Accept what it removes — no lookalikes, no age/gender/ZIP, no interest exclusions. You would not have used them.
- **Audience:** broad US 18–65+. Under FPS, "creative is the targeting."
- **Placements:** Advantage+ placements. Do not hand-pick at this volume.
- **Budget:** whatever you are willing to lose. Label it honestly — this is a message test, **not** performance marketing, because you will not reach the learning threshold. Do not let a dashboard convince you otherwise.

---

## 6. Creative

Use the five lint-clean variants in `META_ADS_DECISION.md` §9. **Re-verified against the current linter on 2026-08-22: 0 blocking findings.**

⚠️ **That check was manual, and it has to be.** CI runs `scripts/lint-copy-compliance.mjs` with no path arguments, so it falls through to the `include` globs in `copy-compliance.allow.json` — which cover `frontend/app/**`, `frontend/components/**`, `frontend/lib/**` and a few backend template modules, but **not `docs/**`**. The ad copy bank has therefore never been checked by CI, and any edit to it won't be either. Re-run the linter by hand over any copy you change:

```bash
node scripts/lint-copy-compliance.mjs docs/META_ADS_DECISION.md
```

Point each at `/signup?from=<key>` so the landing H1 restates the ad's promise (message-match is the highest-confidence funnel lever there is, and the mechanism already exists):

| Ad headline | Landing URL |
|---|---|
| "One number. One sentence." | `/signup?from=screener` |
| "We publish the record, misses included." | `/signup?from=scorecard` |
| "See what the scanner read — no account needed." *(corrected 2026-08-22: the "— free." form predated the #548 card gate; the public pages are the true no-account surface)* | `/scorecard` |
| "Built for the 20-minute trader." | `/signup` |
| "Six factors. Plain-English labels. Public methodology." | `/signup` |

**Copy rules — these are the AFSL posture, not style preferences.** Never *buy / sell / should / recommend / beat / guaranteed / urgency*; never the exact scoring weights; no win-rate numbers in acquisition copy. Re-run `node scripts/lint-copy-compliance.mjs` over any edit. Optional footer: *"Informational only. Descriptive scores, not recommendations."*

Counter-intuitive but true: **descriptive copy is safer on Meta, not a handicap.** Meta's review treats prescriptive trading language — picks, signals, win rates, market-outperformance claims, "DM us" — as investment promotion and rejects it (`META_ADS_DECISION.md` §3). The house rules and Meta's rules point the same direction here.

---

## 7. Founder steps, in order

1. Create/confirm a Meta Business account and Business Manager. Expect a business-verification request — FPS advertisers routinely get one.
2. Create a pixel. Copy its numeric ID.
3. Events Manager → Conversions API → generate an access token.
4. **Ship the privacy policy update first.** 🔴
5. Set the backend secrets:
   ```bash
   fly secrets set META_PIXEL_ID=<id> META_CAPI_ACCESS_TOKEN=<token> -a tapeline-backend
   ```
6. Set the **frontend** pixel id. ⚠️ `NEXT_PUBLIC_*` is inlined at **build** time — a Fly secret does nothing. It must go in `frontend/fly.toml` under `[build.args]` and be redeployed. The build-arg guard suite exists to catch exactly this mistake.
7. **Verify before spending.** Set `META_CAPI_TEST_EVENT_CODE` to the code from Events Manager → Test Events, create a throwaway account, and watch `CompleteRegistration` arrive. Then **unset it** — test events are excluded from optimisation, and the service logs a warning while it is set.
8. While you are in Events Manager, record two free facts that `META_ADS_DECISION.md` §7 wants: whether **tapeline.io is under the financial-services data-sharing restriction**, and the **matched-audience size**. If the domain is restricted, Meta cannot optimise toward a registration at all and you should stop here.
9. Build the campaign per §5. Declare FPS. Set geo per §4.
10. Launch.

---

## 8. Kill criteria — decide these now, not at 2am

Write these down before spending, because the failure mode of a message test is letting it run "just a bit longer".

- **Stop immediately** if the domain shows as data-sharing restricted (step 8) — the test cannot answer its question.
- **Stop** at your pre-set spend cap, whatever happens.
- **Stop** if cost-per-`CompleteRegistration` exceeds ~$50 after 100+ clicks. The affordable click is ~$0.50 and finance CPCs run $1.22–3.77; if you are far past that, the answer is in.
- **The test succeeded** if one variant produces a materially better click→signup rate than the others — *even if every one of them is unprofitable*. That ranking is the deliverable, and it transfers to AEO, email subject lines, and comparison-page H1s, which are the channels that have actually produced engaged users.

---

## 9. What this test cannot tell you

Trial→paid. That is the broken step (`META_ADS_DECISION.md` §2), 0 conversions ever, and no amount of Meta spend measures it. The instrument for that remains the ≥6 customer interviews that `OPERATING_RULES.md` gates engineering behind — still 0 recorded — and the 17 emails already sitting unread in `christian@tapeline.io`.

---

## 10. Questions for the Holley Nethercote consult

Enabling Meta turns several open questions into live ones. These are written so counsel can answer them quickly; they are **not** things to guess at, and the privacy policy deliberately does not assert an answer to any of them.

1. Article 3(2) GDPR: does buying Meta ads that reach EU or UK users bring Tapeline within scope as "offering goods or services to data subjects in the Union"? Several of the questions below collapse or harden on this answer, so please take it first.

2. If Article 3(2) applies, is an Article 27 representative required in the EU and the UK, or does the 27(2)(a) exemption survive? Note that GA4 and a live Google Ads conversion tag already run continuously on the site alongside an ongoing subscription service, so please assess "occasional" against the current stack, not against Meta alone — and note that appointing representatives takes weeks and a fee, so this is on the pre-launch path.

3. Privacy Act 1988 (Cth) s 6D: is Tapeline an APP entity? Turnover is well under A$3M, but s 6D(4)(c) removes the small-business exemption from an operator that discloses personal information about an individual to anyone else for a benefit, service or advantage. Does sending hashed customer emails to Meta in exchange for ad optimisation fall inside that provision?

4. CCPA/CPRA s 1798.140(d): does Tapeline meet the "business" threshold? Specifically, does the 100,000-consumer limb count every visitor whose PI is shared via a pixel, or only account holders? I can supply California visitor counts from GA4 — tell me which number you need.

5. Is hashed-email conversion measurement a "sale" or a "sharing" under CPRA, or neither? If it is sharing, must we ship a "Do Not Sell or Share My Personal Information" link AND Global Privacy Control handling before the pixel goes live, or does honouring GPC alone satisfy s 1798.135(b)? Please also say whether Regs s 7026(f)(2) obliges us to notify Google/Meta downstream on an opt-out.

6. Controller status: are Google Ads and Meta joint controllers with us for the collection-and-transmission step (Wirtschaftsakademie / Fashion ID), or separate controllers only? If joint, do we need an executed Article 26 arrangement, and must its essence be published in the policy? We currently accept their standard business-tools terms rather than negotiating anything.

7. Legal basis: is consent required for the server-side Conversions API half, which sets nothing on the user's device, or is legitimate interests available for that half while the browser pixel needs consent under ePrivacy Art 5(3)? Is running two different bases across the two halves of one measurement system defensible in practice?

8. Article 21(2)-(3): does server-side advertising measurement count as processing for direct marketing, attracting the absolute right to object? If yes, we need a per-user suppression flag in code before the policy promises an opt-out — please confirm so I build it before, not after.

9. APP 7: under OAIC guidance, is matching customer identifiers so a specific individual is shown ads "direct marketing" rather than analytics? If so, does APP 7.3(c) require a prominent opt-out statement in the ad-facing surfaces as well as the policy?

10. APP 8 and s 16C: what counts as "reasonable steps" when the recipient will not contract to APP-equivalent terms — the large ad platforms do not offer them. Is accepting their published business-tools terms sufficient, or should we not make the disclosure at all?

11. Is our own 14-day material-change notice promise contractually binding as drafted, and does enabling a new sub-processor trigger it? Separately: can the notice clause itself be narrowed without first serving 14 days' notice, or would doing that be a bad-faith pattern we should avoid regardless?

12. Australian Consumer Law s 18: the live policy currently says "We do not sell data, so the opt-out of sale right is moot but still respected" while a Google Ads tag has been running and no opt-out mechanism exists. Is there misleading-conduct exposure for the period that wording was live, and does correcting it prospectively suffice, or should we do anything more?

13. Which written arrangements should we have on file with each ad platform, and under which terms — Google Ads Controller-Controller Data Protection Terms vs the Ads Data Processing Terms for GA4, and Meta's Business Tools Terms / Controller Addendum? Is there anything we must actively accept rather than passively rely on?

14. Publisher exemption: Tapeline's AFSL posture rests on being a publisher of descriptive general information. Does paid, audience-targeted advertising change that analysis — i.e. does targeting a communication to a selected audience move it from general publication toward a communication capable of being financial product advice? If so, what constraints on targeting (not just copy) should we adopt?

15. Should the "not yet reviewed by qualified counsel" banner come down once you have reviewed it, and is there anything in the revised policy you would not want published as drafted — particularly the passages where we state plainly that we are not currently meeting an EU/UK cookie-consent standard?

**The sharpest one is #14.** Tapeline's entire AFSL posture rests on being a publisher of descriptive general information. If paid, audience-targeted advertising changes that analysis, it affects far more than Meta.
