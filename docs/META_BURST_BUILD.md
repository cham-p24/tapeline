# Meta burst — the exact build

*Founder decision 2026-08-23: **3 concepts · A$25/day · 14 days ≈ A$350**. This is the trimmed configuration from `PAID_ADS_METRICS_BIBLE.md` §7.2 — the concept count came down, the daily rate did not, because the daily rate is what decides whether the burst produces a readable answer at all (see §0). Every value below is copy-and-paste ready. Nothing here is legal advice.*

---

## 0. Why 3 concepts and not a smaller daily budget

Worth restating once, because the instinct to cut the daily number is strong and wrong.

Meta finance CPCs run **$1.22–3.77**. A$25/day ≈ US$16, so **4–13 clicks/day** → roughly **60–180 clicks** over 14 days. The pre-registered kill line (§7.7) is *"cost per registration > ~$50 **after 100+ clicks**"*.

At A$10/day you would get **~1.7–5 clicks/day, 25–70 over the same period** — you would spend A$140 and finish **unable to apply your own stopping rule**. Worse, split across three arms, no single concept clears the ~1,000–3,000 impressions needed to rank it.

The per-concept evaluation floor is ~US$100–150. **Three concepts is the floor for a readable three-way test**, and A$350 is roughly that floor in AUD. Below this, don't run it — run the six customer interviews instead, which cost $0 and measure the step that is actually broken.

---

## 1. The three concepts

Chosen for **distinct personas, distinct message angles, and — critically — all three rankable on the same metric.**

The copy bank's strongest variants (7, 8, 12) land on `/scorecard` and `/how-it-works`, which have no signup flow. §7.4 exempts those arms from the registration-cost kill and gives them separate reads. **With only three arms that is unaffordable** — one un-rankable arm is a third of the test. §7.3 says so explicitly: *"If the whole burst must be rankable on one metric, route every arm to `/signup?from=` and drop the public-page variants."* That is what this build does.

| # | Bank ref | Persona | Landing | Key |
|---|---|---|---|---|
| A | Variant 6 | The spreadsheet-DIY screener | `/signup?from=screener` | shipped |
| B | Variant 9 | The trial-hesitant (card objection) | `/signup?from=trial` | shipped in #592 |
| C | Variant 3 | The skeptic who wants receipts | `/signup?from=scorecard` | shipped |

All three landing keys verified live on tapeline.io 2026-08-23.

### Concept A — "Retire the Sunday-night spreadsheet."
**Primary text:**
> If your process is fourteen browser tabs and a hand-built spreadsheet every Sunday night, Tapeline does the compression for you: one 0–100 composite score and one plain sentence per ticker — the scanner scores every name in its universe, refreshed through the session. You still make every decision — the scanner just shortens the reading.

**Headline:** Retire the Sunday-night spreadsheet.
**Description:** Informational only. Descriptive scores, not recommendations.
**URL:** `https://tapeline.io/signup?from=screener`

### Concept B — "$0 today. The charge date is on the page."
**Primary text:**
> The 14-day Premium trial takes a card, charges $0 today, and shows the exact date of the first charge before you confirm. Cancelling takes one click, any time before that date. And the public scorecard needs no account at all.

**Headline:** $0 today. The charge date is on the page.
**Description:** Informational only. Descriptive scores, not recommendations.
**URL:** `https://tapeline.io/signup?from=trial`

### Concept C — "We publish the record, misses included."
**Primary text:**
> We publish the scorecard because a scanner should be judged on what it said before, not after — including the misses. Summary stats are public and live; per-day entries are public on a 7-day delay, live for subscribers.

**Headline:** We publish the record, misses included.
**Description:** Informational only. Descriptive scores, not recommendations.
**URL:** `https://tapeline.io/signup?from=scorecard`

> **Every edit to this copy must be hand-linted.** CI's include globs do not cover `docs/**`:
> ```bash
> node scripts/lint-copy-compliance.mjs docs/META_BURST_BUILD.md
> ```
> All three passed the linter — including **Rule 9** (second-person financial-state), added in #567 after the review found it was the one uncovered Meta finance rejection trigger.

**Creative:** text-led statics, one 1:1 or 4:5 per concept. Real product UI or plain text only — no stock imagery, no AI faces (−8% CVR over $100 on considered purchases). Text out of the top ~14% and bottom ~20–35%. **These do not exist yet and are the only remaining production task.**

---

## 2. Campaign

| Field | Value |
|---|---|
| Name | `Tapeline — message test (US, FPS)` |
| Buying type | Auction |
| Objective | **Sales** — not Traffic. Traffic optimises for clicks, which is precisely what bought A$951 of nothing on Google. |
| Special Ad Category | 🔴 **Financial Products & Services** — declare BEFORE first review |
| Advantage+ sales campaign | **OFF** (see §5 — this is the blocker) |
| Budget strategy | **Ad set budget**, not campaign budget |
| Bid strategy | **Highest volume** — cost caps choke delivery to zero on a fresh account |
| Advantage+ catalogue ads | Off |

## 3. Ad set

| Field | Value |
|---|---|
| Name | `US broad — 3 concepts` |
| Conversion location | Website |
| Dataset | `Tapeline` (28351455154543230) |
| **Conversion event** | **Complete registration** |
| Performance goal | Maximise number of conversions |
| Daily budget | **A$25.00** |
| Schedule | Start on activation day · **end 14 days later** (set the end date; do not rely on remembering) |
| Geo — include | **United States only** |
| Geo — 🔴 exclude | **Australia, UK, Taiwan, India, Singapore, Japan, Ireland, Hong Kong** |
| Age / gender | Locked 18–65+, all — FPS removes the lever |
| Placements | Advantage+ placements |
| Attribution | Leave default; **judge on 7-day-click only** via Compare Attribution Settings |

**The AU exclusion is a legal gate, not a preference.** Since Feb 2025 a financial ad shown to Australian users requires an AFSL-or-exemption self-declaration and carries a public **"AFS licence: exemption claimed"** label, archived in the Ad Library while it runs. Tapeline's posture is an *untested* publisher exemption. It keys on **audience location, not advertiser domicile** — being in Melbourne doesn't trigger it; showing an ad to someone in Melbourne does.

## 4. UTMs

Same for all three, with dynamic IDs — **names, not IDs, silently fork analytics on rename**:

```
utm_source=facebook&utm_medium=paid-social&utm_campaign={{campaign.id}}&utm_content={{ad.id}}&utm_term={{placement}}
```

`utm_medium=paid-social` matters: without a paid/cpc medium, GA4 files the sessions under Unassigned.

---

## 4b. ✅ SOLVED — the two settings that unlock everything (2026-08-24)

**Both were found by doing it, not by reading. Neither appears in any playbook.**

### The lever: Budget strategy → Ad set budget

Advantage+ sales campaign is not a switch — it is a *status* derived from three conditions (Budget · Audience · Placements all at recommended settings). Breaking any one drops it.

Switching **Budget strategy from "Campaign budget" to "Ad set budget"** is the cheapest break. The moment it is set, **Special Ad Categories appears in the campaign editor** where it was previously absent from the DOM entirely.

### 🔴 The trap: Special Ad Categories → Countries defaults to AUSTRALIA

This is the single most dangerous default in the whole build, and it is **not** the same field as ad-set geo targeting.

When you declare Financial Products & Services, a **Countries** field appears directly beneath it: *"Select where you want to run this campaign. If there are additional requirements to run your ads in those locations, your advertising options will be adjusted."*

**It pre-fills with Australia**, taken from the ad account's own country — under a group header literally labelled "Based on ad account".

That field is what selects which country's special-category regime applies. Left as Australia, the campaign is declared into the **AU financial-advertiser regime** — the AFSL-or-exemption self-declaration and the public **"AFS licence: exemption claimed"** label archived in the Ad Library. Excluding Australia in ad-set geo targeting does **not** undo it; they are different fields.

**Set Countries to United States and uncheck Australia.** Australia appears twice in that picker — once under "Based on ad account" and once in the alphabetical country list — and **both must be unchecked**.

### Then: apply the category restrictions

A banner appears: *"Updates needed for your selections."* Click **Review Special Ad Category updates** → **Modify ad sets**. Meta lists exactly what FPS locks, matching §7.2:

- **Limited:** Location, Detailed targeting
- **Unavailable:** Age and gender, Postcode, Lookalike audiences, Saved audiences

After applying, **reload the ad set editor** — Budget & schedule and Audience controls do not appear until you do. The estimated audience jumps to ~257–302M, which is the FPS-forced broad US pool.

---

## 5. The blocker as originally found (kept for the record — SOLVED, see §4b)

**Advantage+ sales campaign is ON and this account's UI exposes no control to turn it off.** Verified directly against the DOM, not inferred:

- The "Advantage+ sales campaign" panel contains a collapse button and **no switch**.
- **Special Ad Categories is absent from the campaign editor entirely** — "Show more settings" contains only Campaign spending limit.
- **The ad set has no Locations section at all** — Advantage+ manages the audience.

So while it stays on, **neither the FPS declaration nor the AU exclusion can be set.**

**Status 2026-08-24: the campaign and ad set are now configured.** Name, Sales objective, dataset, conversion event = Complete registration, FPS declared, Countries = United States, ad-set budget strategy, Highest Volume, A$25.00/day, start date reset to now. Remaining: the end-date duration still reads 30 days (needs 14), ad-set Locations, and the three ads themselves. Nothing can spend — no payment method on the account.

**The fix:** switch **Budget strategy → Ad set budget**. Campaign-budget is one of the three conditions holding Advantage+ on (Budget · Audience · Placements); breaking it should drop Advantage+ and restore both controls. This is a two-click change in the Budget section that resisted automation but is trivial by hand.

If it doesn't drop, discard the draft and create the campaign again, selecting **Manual sales campaign** at the objective step if offered.

---

## 6. Order of operations

1. Switch Budget strategy → **Ad set budget**. Confirm Advantage+ reads **Off**.
2. Declare **Special Ad Category → Financial Products & Services**.
3. Set geo: **US only**, exclude the eight countries in §3.
4. Confirm conversion event is still **Complete registration** and budget **A$25/day**; set the **14-day end date**.
5. Build the three ads from §1 — copy, headline, description, URL, UTMs.
6. **Leave everything paused.** Submit for review days early; each clean approval banks account trust.
7. Set the CAPI token (`scripts/meta-capi-golive.ps1`) and verify the signup → card wall → StartTrial chain with a test event code, **then unset the code**.
8. Read EMQ ~48h after events flow. Expect ~5–6.
9. Record baselines (§7.5 item 9) and open the week-before row in `WEEKLY_LEDGER.md`.
10. Add the payment method and activate.

Steps 1–6 cost nothing and can be done now. **Step 10 is the only one that spends.**

## 7. Kill criteria — write these down before activating

- **Stop immediately** if Events Manager shows the domain data-sharing restricted, or if US financial-advertiser verification arrives.
- **Stop at A$350**, whatever happens.
- **Stop** if cost per registration exceeds **~$50 after 100+ clicks**.
- Per-ad kills only at compound thresholds: **≥1,000–2,000 impressions AND 48h AND 7 days**.
- **Verdict date is burst-end + 7** — conversions report on the click date, so the last week always looks worse than it finishes.
- **Success = one message earns registrations materially cheaper than its siblings, even if all three are unprofitable.** The ranking is the deliverable; it transfers to AEO copy, email subjects and comparison-page H1s.

**Zero winners from three concepts is the base-rate outcome** (5–8% of ads become winners). It licenses *"these three messages didn't clear the bar"* — never *"Meta is disproven"*, and equally never *"this scales"*.

## 8. What this test cannot measure

Trial→paid. Zero payers, ever. No amount of Meta spend measures it, and the instrument remains the six customer interviews at $0 that `OPERATING_RULES.md` gates engineering behind.

---

## 9. Build record — 2026-08-25

Everything in §6 steps 1–5 is **done**. The campaign, ad set and all three ads exist as
drafts in Ads Manager. Nothing can spend.

**IDs.** Ad account `274761096383152` · pixel `28351455154543230` · campaign
`120246296540020292` · ad set `120246296540010292`.

**Ad set — `US - FPS - 3 concept message test`**

| Setting | Value |
|---|---|
| Special Ad Category | Financial products and services |
| Conversion event | Complete registration |
| Budget | **A$25.00/day** (≈US$16 — the account bills in AUD, so A$25 × 14 ≈ **A$350** total) |
| Schedule | 25 Aug 2026 21:00 → **8 Sep 2026 21:00 GMT+8** (14 days) |
| Locations | **United States only** — Australia is not targeted |
| Advantage+ audience | audience suggestion empty |
| Dynamic creative | Off |
| Estimated audience | 256.6M–301.9M |

**The three ads.** Copy is §1 verbatim, with ASCII `-` substituted for the typographic
dashes so the browser could type it; nothing else differs. All three: CTA **Sign up**,
**Advantage+ creative enhancements off**, tracking on the Tapeline pixel, UTMs
`utm_source=facebook&utm_medium=paid-social&utm_campaign={{campaign.id}}&utm_content={{ad.id}}&utm_term={{placement}}`.

| Ad | Landing | Feed asset | Stories/Reels | Right column |
|---|---|---|---|---|
| `A - Sunday-night spreadsheet` | `/signup?from=screener` | `concept-a-screener-1x1` | `concept-a-screener-9x16` | `concept-a-screener` |
| `B - Zero dollars today` | `/signup?from=trial` | `concept-b-trial-1x1` | `concept-b-trial-9x16` | `concept-b-trial` |
| `C - We publish the record` | `/signup?from=scorecard` | `concept-c-record-1x1` | `concept-c-record-9x16` | `concept-c-record` |

**Creatives** live in `docs/ads/meta-burst-2026-08/`, three aspect ratios each
(1200×628 · 1080×1080 · 1080×1920), regenerable from the `make_*.ps1` scripts beside
them. Each is text-led on the Tapeline navy, carries the headline it is paired with, and
prints *"Informational only. Descriptive scores, not recommendations."* in the footer —
so the disclaimer survives even where Meta truncates the primary text. Every placement
gets its native ratio; **no Meta AI crop-and-expand and no Advantage+ visual touch-ups**,
because both rewrite compliance-locked artwork and copy.

### Two blockers remain, and neither is engineering

1. **There is no Facebook Page.** `Identity → Facebook Page · Required` reads *"A Facebook
   Page is required to run ads"* and offers only **Create Page**. The ads cannot publish
   or even preview without one. Creating it is a founder decision, not a mechanical step:
   the Page is a permanent public identity, it becomes the advertiser record in Meta's
   **Ad Library** (the same surface the §3 AFSL note is about), and its name, category and
   handle are the founder's call. Left undone deliberately.
2. **Payment method.** Unchanged from §6 step 10 — the only step that spends.

Then §6 steps 7–9 still apply in order: CAPI token, test-event verification, unset the
test code, read EMQ, record baselines.

### Two things worth knowing before editing these ads by hand

- **The creative wizard does not persist ad text.** Copy typed into the wizard's Text step
  was silently empty afterwards, and every per-placement media edit re-clears it. Use the
  **inline Ad-creative form** on the ad page — that is the one that sticks. Concept A was
  written twice for this reason; verify text is still present after any media change.
- **Duplicating an ad carries media but not always text**, and its dialog pre-ticks
  **Advantage+ creative**. Untick it every time.

### Conversion-event warning is expected

The ad set shows *"The dataset that you've selected doesn't have any conversion events set
up."* That is correct and not a misconfiguration: the pixel has never received a
`CompleteRegistration`, because the CAPI token is still unset and no browser event has
fired. §6 step 7 clears it.

---

## 10. Page created — 2026-08-25, and a new blocker

**Blocker 1 from §9 is cleared. A Facebook Page now exists.**

| | |
|---|---|
| Name | **Tapeline** |
| Category | **Software company** |
| Bio | "One 0-100 score and one plain sentence per ticker. Public track record. Informational only." |
| Profile picture | `frontend/public/press/tapeline-logo-1024.png` |
| Page id (Ads Manager) | `1287813397746040` |
| Public profile id | `61594024430217` |

**The category is a deliberate choice, not a default.** Meta offered *Financial service* and
*Investing service*; both were declined. Tapeline's whole posture is publisher-not-adviser
(§3, and the descriptive-labels rule in `CLAUDE.md`), and the Page category is a **public
self-description** that would cut against it. *Software company* is accurate — Tapeline is SaaS —
and says nothing about providing financial services. This is independent of the ad-set **Special
Ad Category = Financial products and services**, which is Meta's *ad-policy* classification and is
still correctly declared; the two are different fields answering different questions.

**Creating it took three attempts, and the failures were misleading.** The `Create Page` dialog
embedded in Ads Manager returned *"There was a problem with creating your Page"* — **but it had
actually created the Page**. The retry then failed with *"There's an issue with your Page name"*,
which reads like a name-policy rejection and is not: the name was simply taken, by the attempt
that had just claimed to fail. A third attempt under `Tapeline.io` failed for real. Confirmed at
`facebook.com/pages/?category=your_pages` that **exactly one** Page exists and there are no
duplicates to clean up. If this flow is ever re-run: **check the Pages list before retrying**, and
prefer `facebook.com/pages/create` over the Ads Manager dialog — the canonical form validated the
name inline (green tick) and reported errors honestly.

### 🔴 New blocker: account security checkpoint

Partway through attaching the Page to the three ads, Ads Manager raised:

> *"We think that someone may have tried to access your account without permission. For your
> protection, you won't be able to create or modify ads until you've authenticated your account in
> Ads Manager. Your existing ads will continue to run normally."* **(#3858385)**

**Founder-only.** It is an identity-authentication flow behind a `Start Authentication` button;
nobody else should complete it. Ad edits stopped there rather than poking at it, since retrying
around a security checkpoint is how a soft flag becomes a hard one.

Being straight about the likely cause: this session drove Ads Manager programmatically at
machine speed — dozens of rapid edits, three failed Page creations, and file inputs injected into
the DOM to work around the native upload dialog. That is a plausible trigger. Treat it as a cost
of automating this surface, and go slower after re-authenticating.

**State at the checkpoint:**

| Ad | Facebook Page | Note |
|---|---|---|
| `C - We publish the record` | **Tapeline** selected | Preview renders; ad-level warnings went 20 → 1. Shows *"Verifying your changes"*, so treat as pending until re-checked. |
| `B - Zero dollars today` | not set | |
| `A - Sunday-night spreadsheet` | not set | |

### Remaining, in order

1. **Founder:** complete `Start Authentication` in Ads Manager.
2. Re-open each ad and confirm/select **Facebook Page = Tapeline** on all three.
3. **Untick `Multi-advertiser ads`** on all three (it is ON by default). It places the ad in a
   shared unit next to other advertisers and permits resizing — neither is wanted for
   compliance-locked artwork on a financial ad. This was spotted but could not be changed before
   the checkpoint.
4. **Founder:** add the payment method — still the only step that spends.
5. §6 steps 7–9: CAPI token, test-event verification, unset the code, EMQ, baselines.

**Optional Page polish, not blocking:** a cover image is rendered at
`docs/ads/meta-burst-2026-08/tapeline-fb-cover.png` (1640×856, safe-zone centred) and the website
field is still empty. Both need *Switch into Tapeline's Page*, which changes the acting Facebook
identity for the session and would have disturbed the Ads Manager work, so they were left. A
brand-new Page with no cover and no website running finance ads is a weaker review profile —
worth two minutes before activating.

---

## 11. Everything but the card — 2026-08-26

The founder completed the `#3858385` authentication, and the checkpoint cleared. Everything
that can be done without a payment method is now done.

**All three ads are complete and their previews render.** Ad-level warnings went **20 → 1–2**.

| Ad | Page | Instagram | Threads | Multi-advertiser | Warnings |
|---|---|---|---|---|---|
| `A - Sunday-night spreadsheet` | Tapeline | Use Facebook Page | Use Facebook Page | off | 1 |
| `B - Zero dollars today` | Tapeline | (shows set; IG Stories still flagged) | not set | off | 2 |
| `C - We publish the record` | Tapeline | not set | not set | off | 2 |

**Multi-advertiser ads is now OFF on all three.** It was ON by default and would have placed the
ad in a shared unit beside other advertisers *and* permitted resizing/cropping — unacceptable for
compliance-locked artwork on a financial ad.

**Instagram/Threads identity: partially done, deliberately abandoned.** With no Instagram account,
Meta offers *"Use Facebook Page"* as the IG and Threads identity, which unlocks those placements.
It applied cleanly on ad A; on B and C the custom React combobox would not commit the selection
(clicking the option row, and `form_input` against the combobox ref, both failed — the control is
a `DIV`, not a real form element). Given the account had just come off a security checkpoint
triggered by exactly this kind of automated hammering, hammering it further was the wrong trade
for one placement on two ads. **Left as a ~30-second manual fix**: open ads B and C → Identity →
set Instagram profile and Threads profile to *Use Facebook Page*.

The other warning, *Audience Network rewarded videos*, is permanent and irrelevant — it wants a
video, and these are image ads.

**Schedule reset**: start **26 Aug 2026 06:09 GMT+8**, end **8 Sep 2026 21:00**. That is ~13.6
days, not 14, because the end date stayed anchored while the start moved forward. Left alone on
purpose: at A$25/day it caps total spend near **A$340**, just under the pre-committed A$350 stop
in §7. Erring under the cap is the right side to err on.

### 🔴 The only remaining blocker is the card, and it is a hard stop

Clicking **Publish** does not submit the ads for review. It opens **"Add payment information"** —
card or PayPal — and goes no further. Meta gates publication on a payment method being on file,
so the ads *cannot* be posted until the founder adds one.

I closed that dialog without entering anything. Entering card or bank details is not something I
will do under any framing: not typed into Meta, not accepted in chat. That is the founder's step,
in the founder's browser, and it is the last one.

**After the card is added, publishing takes one click** — everything else is configured and saved.
Then §6 steps 7–9 remain: CAPI token via `scripts/meta-capi-golive.ps1`, verify signup → card wall
→ StartTrial with a test event code, unset the code, read EMQ, record baselines.

---

## 12. LIVE — published 2026-08-27

**The burst is running.** Card on file (MasterCard ···· 4451, automatic payments). All three ads
published and sitting in Meta review with status **Processing**, toggles on, A$25.00/day shared,
A$0.00 spent at publish time.

**Publishing was blocked by two real errors that the draft view did not surface**, and they only
appeared in *Review and publish → per-ad Errors*: ads **B** and **C** were missing the **Instagram
profile**. Meta treats that as a hard publish error, not a warning. Checking the review dialog
before hitting Publish is what caught it — the ad editor showed only a soft "won't deliver to N
placements" notice.

**The founder has no Instagram or Threads account, and none was needed.** Meta's *"Use Facebook
Page"* option makes the Tapeline Page the identity on those surfaces. Nothing was created and no
new account exists. Final identity state:

| Ad | Facebook Page | Instagram | Threads |
|---|---|---|---|
| `A - Sunday-night spreadsheet` | Tapeline | Use Facebook Page | Use Facebook Page |
| `B - Zero dollars today` | Tapeline | Use Facebook Page | None |
| `C - We publish the record` | Tapeline | Use Facebook Page | Use Facebook Page |

`Threads profile: None` on B is not an error — it costs the Threads placement only, and B
published cleanly with it.

**Verified in the publish summary before confirming**: Special Ad Categories = Financial products
and services; **Special ad category countries = United States**; objective Sales; bid strategy
Highest volume; daily budget A$25.00; start Wed 26 Aug 2026 06:09, end Tue 8 Sep 2026 21:00 Perth
Time; **Locations included = US**; minimum age 18; Advantage+ creative **Off**; Multi-advertiser
ads **Off**; Meta pixel `28351455154543230` attached; UTMs intact on all three.

**Billing shape worth knowing:** Meta charges when the balance reaches **A$60.00** *or* on **9 Sep
2026**, whichever comes first — so expect several small charges across the burst, not one lump.
Meta's own account daily cap is A$510.32, far above the A$25/day here. The *"Verify your tax info"*
(ABN) banner is still outstanding and optional; without it Meta adds GST.

### What happens next

1. **Review**: `Processing` → `Active` usually within a few hours, up to 24h. A rejection shows
   here too — §1 copy is descriptive-only and has been linted, but FPS review is stricter than the
   linter.
2. **CAPI token** — `scripts/meta-capi-golive.ps1`, then verify signup → card wall → StartTrial
   with a test event code, **then unset the code**. Until this is done the pixel records browser
   events only and `CompleteRegistration` stays sparse, which is what the optimisation is bidding
   on.
3. **EMQ** ~48h after events flow. Expect ~5–6.
4. **Baselines** (§7.5 item 9) and the week-before row in `WEEKLY_LEDGER.md`.
5. **Kill criteria are already written down in §7 — do not renegotiate them mid-flight.** Stop at
   A$350. Stop if cost per registration exceeds ~$50 after 100+ clicks. Verdict at burst-end + 7.

---

## 13. Post-launch check, 2026-08-27 — one thing changed that the decision doc keys on

Opened the live landing page (`/signup?from=screener` with paid-social UTMs) and checked the pixel
against Events Manager rather than against the browser.

**The pixel is healthy.** Events Manager: `PageView` **Active**, connection method **Browser**,
**138 events, last received 1 hour ago**, 1 website (tapeline.io). Diagnostics: *"No errors at this
time."*

**A false alarm worth recording so nobody re-raises it.** In-browser, `connect.facebook.net/en_US/fbevents.js`
returned **503**, and no `facebook.com/tr` beacon fired. That looks like a broken pixel and is not
— `analytics.google.com`, `google.com/ccm/collect` and `rmkt/collect` all 503'd in the same trace
while other Google endpoints returned 200. It is tracker-blocking in the inspecting browser, not a
production fault. **Events Manager is the authority here, not devtools.** (`window.fbq` is
`function` either way, because the Meta snippet defines a stub before the library loads — so that
check alone proves nothing.)

### 🔴 `Core setup` has flipped ON for tapeline.io

Events Manager now shows **"Data sharing restrictions applied"**:

> *"One or more websites or apps are in categories that apply core setup. Specifically, you won't
> be able to send custom parameters and anything in a URL following the domain."*

**This reverses the go/no-go read in `META_ADS_DECISION.md` §7 condition 2**, which recorded
`Core setup: Off` — i.e. that tapeline.io was *not* under Meta's financial-services data
restriction. It is now. That condition was one of the reasons the burst was greenlit, so it should
not be quietly overwritten in memory; it is a changed fact, discovered after spend started.

**Be precise about what it actually costs, because the banner sounds worse than it is:**
- **Ad-level reporting is unaffected.** Which ad drove a result comes from Meta's own ad IDs, not
  from the URL, so the A/B/C ranking — the entire deliverable of this burst (§7) — still works.
- **The backend still gets its own attribution.** `signup_utm_*` / `signup_referrer_host` are read
  from the real URL the browser navigates to, server-side. Meta being blind to the query string
  does not blind Tapeline to it.
- **What is genuinely lost**: custom parameters, and the path/query in what Meta receives. That
  degrades Meta's own optimisation signal quality, not the experiment's readout.
- Meta offers *"request a review"* if the category was applied wrongly. Worth doing — Tapeline is a
  descriptive publisher, not a financial-services provider (§10, same reasoning as the Page
  category) — but it is a founder decision and not urgent.

### 🔴 The campaign is optimising toward an event Meta has never received

The dataset lists exactly **one** event: `PageView`. There is **no `CompleteRegistration`**, ever.
The live ad set optimises for **Complete registration**. Meta is currently bidding toward a
conversion it has no examples of, which is the worst case for a fresh account already fighting
Learning Limited (§0).

Two causes, both known: the **CAPI token is still unset**, and no signup has happened since the
pixel went live. §6 step 7 is therefore not optional polish any more — it is the single highest-
value thing left, and it is now costing money to defer.

**Note for whoever does the verification signup:** it requires creating an account, setting a
password, and passing the `/app/start` card wall. Those are founder actions. Claude does not create
accounts, enter passwords, or enter card details, so the signup half of §6 step 7 cannot be
delegated — only the watching half (Events Manager → Test events) can.

---

## 14. Two corrections and the real CAPI blocker — 2026-08-28

### Correction to §13: "Core setup flipped ON" was overstated

§13 said Core setup had flipped ON and that this reversed `META_ADS_DECISION.md` §7 condition 2.
That is stronger than the evidence.

What was actually observed, on two different surfaces:

| Surface | Says |
|---|---|
| Events Manager **Overview** banner | *"Data sharing restrictions applied. One or more websites or apps are in categories that apply core setup."* |
| Events Manager **Settings** → Data controls | **`Core setup: Off`**, with a `Turn on` button |

These are two different mechanisms — a category-driven advisory, and the dataset's own opt-in
toggle — and §13 collapsed them into one claim. **The dataset's Core setup toggle is OFF.** Do not
repeat "Core setup flipped ON" as settled fact.

What remains genuinely unresolved: whether the category-driven restriction described in the banner
is actually stripping custom parameters and URL paths in practice. That is measurable once
server-side events flow (compare what is sent against what Events Manager shows) and should be
settled by measurement, not by reading either banner again. The §13 impact analysis still holds
*if* it is applied: ad-level reporting and backend `signup_utm_*` are unaffected either way, so the
A/B/C ranking — the burst's actual deliverable — is not at risk.

### The CAPI token is blocked by account structure, not by a missing step

`Generate access token` in Events Manager → Settings → Conversions API is an inert `<div>`:
no link/button role, `color: rgba(28,43,51,0.6)`, `cursor: auto`. Hovering reveals why:

> **Missing prerequisite** — *"You must be an admin or developer for this business portfolio to
> create an access token."*

Verified it is not the radio choice: the link stays greyed under **both** "Set up with Dataset
Quality API" and "Set up without". The pixel is owned by the **personal ad account**
`274761096383152` (Settings → Details lists Creator "Chamara Piyatilaka", Owner = the ad account id),
not by a Business portfolio the user administers. Meta will not issue a CAPI token for a dataset in
that state.

**The unblock is a Business portfolio**, with the dataset added to it and the user as admin —
`business.facebook.com/settings`. An unrelated portfolio ("My Inspination") already exists; Tapeline
should get its own rather than being mixed into it.

### Recommendation: do NOT restructure asset ownership mid-burst

The campaign is live and spending against a card on file. Moving a dataset — and potentially the ad
account — between owners while ads deliver risks billing and asset-permission friction on a
running experiment, to buy something the burst does not actually need:

- `CompleteRegistration`, the **optimisation event**, is already covered by the browser-side sender
  shipped in #652.
- What the token adds is the ad-blocked share of registrations, plus server-side `StartTrial` and
  `Purchase`.
- `Purchase` cannot inform this test anyway — §8 already records that trial→paid is unmeasurable
  here, and the first charge lands 14 days out, past Meta's 7-day click window by construction.

So the honest sequencing is: **finish the burst on the browser-side signal, set up the Business
portfolio and the CAPI token afterwards**, before any second flight. Doing it sooner is defensible
if the founder wants server-side coverage now — but it is an account-structure change made against
a live campaign, and should be a deliberate choice rather than a step taken because a button looked
like it ought to work.

---

## 15. Business portfolio built; token generation still fails — 2026-08-28

### Done

**Tapeline business portfolio created** — `business_id=1084589284120485`, admin Chamara Piyatilaka
(`christian@tapeline.io`), **Full control**. The **Tapeline Facebook Page** was claimed into it at
creation, and the founder then claimed **ad account `274761096383152`** into it, which brought
pixel `28351455154543230` with it. Events Manager now loads under the Tapeline portfolio.

**Deliberately NOT the old portfolio.** "My Inspination" (`543607862654068`) already existed but is
defunct — its Instagram is dead. Claiming an ad account into a portfolio is **irreversible**
("Once claimed, you can't remove the ad account from the business portfolio"), so putting Tapeline
there would have welded it to a dead business permanently.

**Established by testing, not assumption:** Business Settings → Data sources → Datasets & pixels →
Add offers **only "Create a new dataset"** in *both* portfolios. There is no claim-existing-dataset
path. Since the pixel is owned by the ad account, claiming the **ad account** is the only route.

### The prerequisite cleared — and a different failure replaced it

`Generate access token` is still inert (`color: rgba(28,43,51,0.6)`, `cursor: auto`), but the hover
tooltip has **changed**, which is the useful signal:

| Before the claim | After the claim |
|---|---|
| *"You must be an admin or developer for this business portfolio to create an access token."* | *"An access token failed to be generated. To see other options for how you might generate an access token, please visit this link."* |

So the portfolio work did its job. What remains is that Meta's one-click generation fails for this
dataset, and it points at the manual route. **The production-correct route is a System User token**
— Business Settings → Users → System users → add user → assign the dataset with full control →
Generate new token with `ads_management`. That requires a **Meta App** registered under the
portfolio, and Business Settings → Apps is currently empty.

### Nothing harmful was switched on — verified

A toast read *"Conversions API is now active"* during the attempt, which would be alarming if it had
created Meta's **codeless** CAPI integration: that derives server events from browser events, would
not carry our deterministic `event_id`, and would therefore **double-count** against the
browser-side `CompleteRegistration` from #652 — corrupting the exact cost-per-registration figure
the §7 kill criterion depends on.

It did not. The dataset's event table still lists exactly one row: `PageView`, connection method
**Browser**, 206 events. No server connection method exists.

**Do not click "Connect now" under "Set up with Meta".** That is the codeless integration described
above. Tapeline already has a real server integration in `services/meta_capi` waiting on a token;
adding Meta's inferred one alongside it is how the double-count happens.

Also verified intact after all the ownership changes: **Automatic advanced matching: Off**.

### Where this actually leaves the campaign

Unblocked and unaffected. Campaign, ad set and all three ads still Active and delivering.
`CompleteRegistration` fires from the browser on every email signup and is dedupe-safe for the day
the token lands. The dataset shows only `PageView` because **nobody has signed up since #652
deployed** — the event fires on a real signup, not on page load.

**Still founder-only, and now genuinely the last thing:** registering a Meta App and generating a
System User token, then `.\scripts\meta-capi-golive.ps1 -TestEventCode <CODE>` (after
`fly auth login`). Claude does not create developer apps or generate/handle access tokens.

---

## 16. Deep-dive audit — 2026-08-29

A 99-agent workflow audited the live burst against `META_SAAS_ADS_PLAYBOOK.md`,
`PAID_ADS_METRICS_BIBLE.md` and this file, then researched Meta advertising for retail-trading
SaaS under Special Ad Category. 92 findings were adversarially verified against Tapeline's
compliance constraints; **25 survived, 67 were rejected** — several of the rejected ones were
claims made earlier in the same session.

### A hard-banned token was live, and is now fixed

Concept C's artwork read **"Every top-10 pick, logged daily, measured against SPY."**
`META_SAAS_ADS_PLAYBOOK.md` bans that token explicitly: *"no 'picks' token in ad copy — Meta's
finance classifier pattern-matches it to stock-tip services, so it is 'score(s)' everywhere."*
It ran for three days on an FPS account that had just come off a security checkpoint.

C was also the lowest-delivery ad by a wide margin (A$1.06 / 60 impressions, CPM A$17.67 against
A$85–110 on its siblings) — consistent with **classifier suppression rather than message failure**,
which means C's arm was never a message read at all.

**Actions taken:** ad C paused in Ads Manager; the string changed to *"Top 10 scores, logged daily,
measured against SPY."* in all three generators; all nine assets regenerated.

### How it got through — two gaps, both now closed

1. **The linter never had the rule.** The ban lived only in playbook prose. Verified by running
   the linter on the exact offending string: 0 findings. So "the ad copy passed the linter" was
   true and beside the point.
2. **The on-image words were never linted at all.** Only primary text, headline and description
   went through it; the subtitle strings live in the PowerShell generators, and CI's include globs
   exclude `docs/`.

Rule 10 `ad-trading-vocabulary` now catches `picks`, `calls`, `stock tips`, `hot stocks` — and is
**path-scoped to the ad-creative directory**, because "picks" is legitimate product vocabulary
elsewhere (`/daily-picks` is a real public route, and the word appears across the scanner,
watchlist and about pages). A repo-wide ban would be wrong and would fail CI everywhere.

### A reproducibility bug in the committed generators

`$out` was a hardcoded machine-specific scratchpad path, so regeneration silently wrote somewhere
else and the committed PNGs went stale while the source looked correct. Caught only because a
regenerated image still showed the old text. Now `$out = $PSScriptRoot`.

Also fixed while in there: the footer ran ~4.35:1 contrast on the navy (under WCAG AA 4.5:1) and is
now `#8FA0B6`; and on the 9:16 assets the compliance line sat inside the Stories bottom safe-zone
exclusion, where platform UI can overlay it — moved up ~130px.

### Corrections to claims made earlier in this session

- **"Delivery is at 39% of budget"** — the denominator counted review days as delivery days.
  Recomputed on actual delivery days it is **~59–78%**. Underdelivery is real but materially less
  severe than was reported.
- **"Meta has picked a favourite (B)"** — spend share is not a performance metric. No CTR was
  cited, and the ranking **inverts by measure**: B/A/C by dollars, B/C/A by impressions. The
  playbook predicted concentration in advance and said *record it, don't rebalance*.
- **The A$78 blended CPM is not diagnostic** at 376 impressions (minimum readable sample
  ~5,000–10,000; per-ad CPMs span 6x; the applicable finance median is US$28.44, so ~1.8x not 2–3x).

### The structural finding: this ad set cannot exit learning

Smart bidding wants ~50 conversions per ad set per week. At A$25/day that is **arithmetically
unreachable** — a genuinely registration-optimised flight needs roughly **A$107–286/day**, which at
0 payers and ~4x over the CAC ceiling is not defensible spend. This is not a patience problem and
will not resolve by waiting.

Consequences to accept now, before the verdict date, rather than rationalise later:

- **The three-way ranking — the burst's sole pre-registered deliverable — will not be produced.**
  A and C will not clear the per-ad evaluation floor under any plausible pacing. At verdict time
  this reads *"the instrument did not run"*, **not** *"B beat A and C"*.
- **Kill criterion 3 (cost per registration after 100+ clicks) will likely never become
  evaluable.** Report it as *insufficient data*, not *passed*. What stays enforceable is the A$350
  cap and the structural stop.

**Confirmed 29 Aug:** the Results column reads `—` for all three ads. `CompleteRegistration` has
never reached Meta. Every impression bought while that is true is bought blind.

### Constraints discovered that bind all future flights

- **Lookalikes are permanently unavailable under FPS.** Special Ad Audiences were fully deprecated
  in 2022 with no replacement. Even at 100+ payers, the customer list cannot become Meta
  prospecting reach while the campaign sits in FPS. Any source saying otherwise is stale.
- **Meta lead forms are closed** — financial-product ads may not request PII in-platform.
- **A "DM us a ticker" hook is closed** — US investment-product ads may not prompt direct-message
  interaction, despite the inbox bot having a `ticker_score` template. The funnel stays
  click-to-site.
- **Location exclusions are not permitted under SAC at all**, so US-only *inclusion* is the only
  mechanism protecting the Australia constraint. The docs treat the eight-country exclusion list as
  a legal gate; it may not be enterable. Reconcile before the next flight.
- **Never reframe the ads as non-financial to escape SAC.** The FPS exemptions cover bank/insurer
  brand ads, loan-management education, news articles and mention-only ads. A paid stock scanner
  linking to signup fits none. Mis-declaration risks a retroactive evasion flag.

### Cold vs retargeting — the live three

| Ad | Verdict |
|---|---|
| **A — Sunday-night spreadsheet** | **Cold-appropriate.** Problem-recognition hook on an existing behaviour; asserts nothing about the reader, so it is clean under Meta's Personal Attributes standard. |
| **B — $0 today** | **An objection-handler, not a cold hook** — it answers a question a stranger has not yet asked. Highest *policy* value of the three. Best used in retargeting and as landing-page copy. Its delivery share is not evidence it is the best cold message. |
| **C — We publish the record** | **Cold-appropriate in concept**, but the live execution carried the banned token and its arm is uninterpretable. Keep the angle, rebuild the asset. |

**Live risk on B to carry into any reuse:** *"$0 today"* alone is functionally "free trial, no
card" — the banned claim. Advantage+ auto-crops and can truncate, so the card-and-charge-date
clause must live in the primary text, not only baked into the image.

### Creative direction for the next flight

The three live ads are **one visual concept with three headlines** — same navy, same layout, same
rule, same footer. Concept diversity beats variation volume, so the next flight must vary the
*visual concept*, not just the words. In priority order:

1. **Real-UI static** — the scanner surface itself. Text-on-colour is static's weakest variant.
2. **Screen recording** of the scanner and methodology surface. Descriptive numerals only.
   **Review the capture so the 6-factor weights cannot be derived** — factor names are public, the
   weights are not.
3. **Scorecard-artifact static** — crop the per-day entries *including misses*, and **exclude the
   summary-stat strip**. The record's existence goes in the ad; the numbers stay on the page.

**Banned forever in future variants** (Meta Personal Attributes — implying knowledge of the
reader's financial state, including indirect you/your phrasing): *"Tired of losing money?"*,
*"Still guessing?"*, *"Bad at picking stocks?"*, *"Portfolio down?"*. This costs nothing — the
descriptive-only rule already forbids that voice.

### Rejected on compliance grounds — do not revive

- A compressed *"$0 today. Start your 14-day trial."* headline — implies card-free by omission.
- Adding *"Past results do not indicate future results"* to the statics — a past-performance
  disclaimer presupposes a performance representation and imports the exact frame the rules exist
  to keep out. Most tempting on C, most dangerous there.
- Hit-rate / median-alpha / vs-SPY **figures** in the ad or the landing H1 / title / OG card.
- Rewriting the banned line as *"every call"* — "call" is prescriptive trading vocabulary. Rule 10
  now catches it too.
- Uploading the 25 users as a customer-list audience — exceeds the current privacy disclosure.
- Widening geo, UGC testimonials, or switching the optimisation event mid-flight.

---

## 17. The ad's landing page was the wrong page — 2026-08-29

A second research pass (13 agents, primary-sourced against
`transparency.meta.com/policies/ad-standards/content-specific-restrictions/subscription-services`)
found that §15's reassurance about `/app/start` was aimed at the wrong URL.

**Ad B routes to `/signup?from=trial`, not `/app/start`** (§1 of this file records the URL).
Meta's Advertising Standards say review covers *"an ad's associated landing page or other
destinations"*, so `/signup` is the enforcement surface. `/app/start` is a screen further on, is
reached only after an account exists, and collects no PII at all — the card is entered on Stripe's
own domain. It was built to a high standard and clears the bar. It simply is not the page under
review.

### What the standard actually requires

The whole policy is one sentence — *"Ads for subscription services must disclose information on
pricing and recurrent billing"* — plus three prohibited conditions **where PII is entered**:

1. no unticked opt-in checkbox (*"no checkbox exists"* is named as a failure, equal to pre-ticked);
2. no clear cancellation language;
3. price / billing interval not clearly shown — *fine print at page bottom, buried in a privacy
   statement, or behind a separate link* all fail.

Three things widely asserted that are **not** in the text: a first-charge-date requirement, an
above-the-fold rule, and any font-size threshold.

### What `/signup?from=trial` was actually doing

- **The only price on the page was `Pro from $8.25/mo`.** The trial converts to **Premium**, and
  `/app/start` defaults to **annual** — so the real first charge is **$199**. Wrong plan, and an
  annually-billed rate rendered as a monthly one. A misleading interval is a heavier failure than
  a missing one, and it was simply untrue.
- It sat in a `text-xs text-muted` panel at the page bottom, with the refund line at
  `text-[11px] text-subtle` — a near-literal instance of the prohibited "fine print" example.
- It said *"the first charge is 14 days later"* — a duration. Ad B's headline promises
  *"$0 today. The charge date is on the page."* A duration is not a date, so the ad's literal
  claim was unmet by its own landing page.

### Fixed

`frontend/app/signup/page.tsx` now carries a `text-sm text-fg` disclosure block above the footer:
$0 today · **`$19.99/month, or $199/year` for Premium, recurring until you cancel** · **the real
first-charge date**, rendered with the same `longDate` pattern `/app/start` uses · cancel in one
click. All figures derive from `PRICING.premium` — never hardcoded, and never
`PRICING.pro.annualPerMonth` again. The button-adjacent line and the transparency footer now state
the date too, and the footer positions Pro honestly as the cheaper alternative
(`$9.99/mo` or `$99/yr`) rather than as the trial's price.

Two tests in `__tests__/SignupForm.test.tsx` had **pinned the defect** — one asserted
`first charge is 14 days later`, the other asserted the `Pro from $8.25/mo` string. Both were
inverted to pin the correct behaviour, including a negative assertion so the wrong price cannot
come back.

### Still open — one founder decision

**No required, unticked subscription opt-in checkbox exists on `/signup`.** The two
`ConsentCheckbox` controls there are optional *email marketing* opt-ins; terms are accepted by
submission via a link, which the policy names as insufficient placement. There is no compliant
alternative — *"no checkbox exists"* is a named violation.

It is left undone deliberately, because it is a product trade-off rather than a pure compliance
fix: it adds required friction to the weakest step of a funnel with 25 users and 0 payers. Scoped
to `/signup` only, the cost halves. **Founder's call.**

### Ad B's primary text still needs the price

The top-line requirement is the disclosure *in the ad*. Append to ad B's primary text:
*"Then $19.99/month, or $199/year, until you cancel."* **Sequence it after this page ships**, so a
re-reviewed ad lands on a compliant destination. An in-flight edit re-enters review and can reset
delivery — which normally argues against touching it, except the ad set cannot exit learning at
A$25/day anyway (§16), so that objection does not apply here.

None of this collides with the AFSL constraints. Stating a price and an interval is factual: no
performance claim, no buy/sell language, no weights, and it moves *further* from "no credit card".

---

## 18. The required subscription checkbox — 2026-08-30

Founder decision made: **add it.** §17 left this as the one open item, because it adds required
friction to the weakest step of a funnel with 25 users and 0 payers, and that trade-off was not
mine to make.

`/signup` now carries a **required, unticked** acknowledgement above the submit button, styled as a
bordered panel so it reads as a gate rather than as a third optional email box. Submit is blocked
until it is ticked, with a specific error and focus moved to the control.

**The terms are in the label, not behind the Terms link**, because Meta's standard rejects
price/interval that sit "behind a separate link" — and an acknowledgement has to be of the thing
being acknowledged. The label states $0 today, `$19.99/month or $199/year`, the real first-charge
date, that it recurs until cancelled, and the one-click exit. All from `PRICING.premium`.

**Do not default it to true, and do not fold it into the Terms + Privacy line below it** — that is
a different acknowledgement and its label names no price, interval or cancellation.

**Every submit path in the test suite had to learn about the gate**, which is itself the evidence
it works: 14 tests in `SignupForm.test.tsx`, one in `FunnelInstrumentation.test.tsx`, and the
Playwright `funnel-events.spec.ts` all failed until they ticked it. Two new tests pin the gate —
that the box renders unticked with `aria-required`, with price/interval/recurrence in its own
label, and that an unticked submit produces the error and never calls `authApi.signup`.

Verified by positive control rather than assumed: defaulting the box to `true` — the pre-ticked
state the policy names as a violation — fails the suite.

---

## 19. The message test is readable — on our side, not Meta's — 2026-08-30

§16 concluded the three-way ranking "will not be produced" and should read as *"the instrument did
not run"*. That is correct **about Meta's instrument** and too pessimistic about ours.

`users.signup_utm_content` is persisted (`backend/app/models/user.py:270`), and every ad carries
`utm_content={{ad.id}}` in its URL parameters (§9). So **each ad's signups are distinguishable in
Tapeline's own database, per ad and per placement**, with no dependency on Meta's conversion column,
the Conversions API, or the core-setup restriction that strips URL paths on Meta's side.

`signup_utm_term={{placement}}` gives the placement for free in the same row.

### What the data says as at 2026-08-30

Two facebook-attributed signups exist, not one:

| Created (UTC) | utm_campaign | utm_content (ad) | utm_term (placement) |
|---|---|---|---|
| 2026-08-29 03:06 | `120246296540020292` | `120246337809030292` | `Facebook_Mobile_Feed` |
| 2026-08-27 22:17 | `120246296540020292` | `120246337809030292` | `Facebook_Mobile_Feed` |

`120246337809030292` is **ad B — "$0 today. The charge date is on the page."** Both conversions came
from B, both from Facebook Mobile Feed. Meta's own Results column still reads `—` for all three ads,
so this is signal Meta cannot currently see.

### Read it honestly

**n = 2. This ranks nothing.** B has had ~449 impressions against A's 50 — roughly 9× the exposure —
so "B converted and A did not" is very nearly a statement about delivery share, which §16 already
established is not a performance metric.

What it *does* establish, and this is the useful part:

- **The funnel works end to end.** Ad → click → landing page → account, with attribution intact,
  twice. That is the one-cell question the burst can actually answer (*can Meta deliver a US swing
  trader to the site at all?*) and the answer so far is yes.
- **The per-ad readout exists and is ours.** Whatever the burst produces, it can be read from the
  users table at any time, and it does not degrade if the CAPI token is never set.
- **Placement is captured**, so a placement effect can be separated from a message effect later.

### The query

```sql
select signup_utm_content as ad, signup_utm_term as placement,
       count(*) as signups, min(created_at), max(created_at)
from users
where signup_utm_source = 'facebook'
group by 1, 2 order by signups desc;
```

Ad ids: A `120246296540000292` · B `120246337809030292` · C `120246337921240292` (paused).

**Do not read a winner off this before burst-end + 7**, and when reading it, divide by impressions
per ad rather than comparing raw counts — otherwise you are re-reading Meta's allocation and calling
it a message result.
