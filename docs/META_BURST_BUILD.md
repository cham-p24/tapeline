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
