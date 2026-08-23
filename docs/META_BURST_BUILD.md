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

## 5. 🔴 The blocker, and what it is

**Advantage+ sales campaign is ON and this account's UI exposes no control to turn it off.** Verified directly against the DOM, not inferred:

- The "Advantage+ sales campaign" panel contains a collapse button and **no switch**.
- **Special Ad Categories is absent from the campaign editor entirely** — "Show more settings" contains only Campaign spending limit.
- **The ad set has no Locations section at all** — Advantage+ manages the audience.

So while it stays on, **neither the FPS declaration nor the AU exclusion can be set.**

**Do not publish the existing draft.** It has the right name, objective, dataset, conversion event, budget (A$25/day) and bid strategy — but no geo exclusion, which means it could serve to Australian users. It cannot spend today (no payment method), so nothing is at risk while it sits.

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
