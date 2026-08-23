# Weekly ledger

*The artifact for gap **G16** in `docs/PAID_ADS_METRICS_BIBLE.md` §2.8. One row per ISO week — spend by channel, visits, signups, card-adds, trials, payers, confounds — appended in the last four minutes of the §6 reading ritual. At founder scale this table is the mix model; there is no other one. It is also the shape an MMM would need if that day ever comes (18+ months of varied weekly data · C). Nothing here is a decision rule and nothing here is legal advice.*

## How to use this

The reading order, the surfaces and every pre-registered action threshold live in **`PAID_ADS_METRICS_BIBLE.md` §6** (and §7.6 for the Meta-specific cut). Run the ritual there; this file is only where the numbers land. Restating the thresholds here would create a second copy to drift out of sync with the first.

Four rules for the file itself:

1. **Append, never overwrite.** A closed row records what was believed that week. A number that later turns out wrong is corrected in the *next* row's Notes, not in place — conversions report on the click date, so a recent week always finishes better than it read, and that drift is itself data.
2. **Start the week BEFORE spend.** The baseline block below is filled in and dated first (§7.5 item 9). Without it the §6 min 0–8 step-change read has no denominator — and a near-zero baseline is exactly the case where a pre/post read is most credible.
3. **DB before dashboard** (§2 reading rule 1). Where a platform number and the DB disagree, the DB number goes in the column and the platform number goes in Notes.
4. **One currency** (§ preamble). Spend is recorded in A$ — the invoice currency — with the week's A$→US$ rate beside it, so a US$ benchmark can be compared later without reconstructing the rate. Treating AUD at par flatters every cost-per-registration read by roughly a third.

## Pre-spend baseline — record BEFORE the first dollar

Fill in once, dated, on Day 1 of any burst (`PAID_ADS_METRICS_BIBLE.md` §7.5 item 9). Do not overwrite; a re-baseline gets a new dated block underneath this one.

| Baseline | Value | Date recorded | Read from |
|---|---|---|---|
| Signups/day, trailing 4 weeks | | | `GET /api/admin/growth-funnel?days=28` → `signups` ÷ 28 (admin-only) |
| Branded-search impressions, trailing 28 days | | | Google Search Console → Performance, 28-day range, query filter contains `tapeline` |
| `/scorecard` direct traffic, weekly | | | GA4, measurement id `G-YRK73W9NS9` (`frontend/lib/trackers.ts`) → Pages and screens, path `/scorecard`, Direct channel. Reporting identity must be **Device-based**, Google Signals off (§2 reading rule 5) |
| Activation rate | | | `/app/admin/revenue` → `activation_rate` (`GET /api/admin/revenue`) |
| Median time to value, hours | | | same surface → `median_time_to_value_hours` |

**Take the activation rate from `/api/admin/revenue`, not from `/api/admin/growth-funnel`.** The revenue endpoint reads `User.activated_at`, which is the definition of record in `docs/activation-definition.md` (first watchlist add OR first authed ticker-detail view). `growth-funnel`'s `activation_rate_pct` counts a different thing — users holding any watchlist item or any alert rule — so the two disagree by construction. Baseline against the definition of record, or the burst is scored against a moving target.

Two more worth stamping in the same sitting, because §7.5 items 7–8 want them dated and neither gets easier to reconstruct: the Events Manager **EMQ** read (~48 h after events flow, before spend) and the **domain-restriction** state screenshot.

## The ledger

| Week (ISO, Mon–Sun) | Meta A$ | Google A$ | Other A$ | Total A$ | A$→US$ | Visits | Signups | Card-adds | Trials | Payers | Confounds / notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| *EXAMPLE — 2026-W37 (09-07→09-13) · illustrative, NOT data* | *196* | *21* | *0* | *217* | *0.65* | *604* | *11* | *4* | *4* | *0* | *Meta burst days 8–14, budget held flat. Open-access revert landed Tue 09-08 (Free scanner rows 1,000→10), so Wed–Sun signups met a different Free product than Mon–Tue. r/stocks thread Wed ≈ 180 of the visits. Ads Manager reported 6 registrations against the DB's 11 — DB wins, gap logged, EMQ re-read next month.* |
| | | | | | | | | | | | |

*The row above is a worked illustration of the format, and of the voice the Notes column wants. It is not a measurement: when this file was created Tapeline had 0 payers and A$0 of Meta spend. Leave it in place as the format reference, or delete it once several real rows exist.*

**The one derived number is deliberately not a column.** §6 min 8–10's blended cost per new signup — total spend ÷ (signups − baseline/day × 7) — is computed during the ritual from this row plus the baseline block. Storing it would leave a stale figure behind the day the baseline is corrected, and it is the number the kill criteria bind to, so it should be recomputed from raw inputs every time.

### Monthly extras — first read of the month only

Appended as a short block under that week's row rather than as more columns, since they would be blank three weeks in four.

| Extra | Read from | What it changes |
|---|---|---|
| Frequency trend | Ads Manager → Delivery | Refresh cue only above 2.5–3.0. At A$25–50/day against a broad US audience it stays ~1.x, so this is a sanity check, not a lever |
| View-/engage-through share of reported conversions | Ads Manager → Compare Attribution Settings | Above ~30%, treat the reported cost per registration as optimistic by roughly that share |
| Ad Library competitor check | Meta Ad Library (public) | Nothing mechanical — competitor message inventory for the copy bank |
| AI-visibility panel overlap | the 20-prompt panel run per `PAID_MARKETING_PLAYBOOK.md` §6.7, logged in `docs/` | Whether a signup step-change is paid or the AEO channel. Pair with the `chatgpt.com` / `copilot.com` referrer counts in `acquisition_channels` |

## Column dictionary — where each number is read

| Column | Definition | Read from | The caveat that must not be forgotten |
|---|---|---|---|
| **Week** | The ISO week that has *closed*, not the one you are standing in | — | Attribution is not settled inside 7 days of a window closing. The row is a record; a verdict against it waits for burst-end + 7 (§7.7 criterion 5) |
| **Meta / Google / Other A$** | Invoiced spend for the week, per channel, plus the total | Ads Manager billing; Google Ads billing; the finance ledger for anything without a platform invoice (newsletter placements, tools) | Blended CAC takes its numerator from the **ledger**, not from a platform's spend column (§2.5). "Other" is where a placement or a tool subscription goes, so the total stays honest |
| **A$→US$** | The rate used to compare this week against USD benchmarks | your own note at the time | Record it in the row. Reconstructing a historical rate months later is the small chore that quietly stops getting done |
| **Visits** | Unique visits for the week | GA4, measurement id `G-YRK73W9NS9` (`frontend/lib/trackers.ts`), Device-based identity, Signals off | GA4 at this volume is a traffic-mix thermometer, not an attribution system (§2 reading rule 5). Thresholding blanks rows under ~40–50 users while Signals is on; the free BigQuery export bypasses thresholds entirely |
| **Signups** | Accounts created during the week | `GET /api/admin/growth-funnel?days=7` → `signups`; the growth digest `GET /api/admin/growth-tick/preview` (the surface §6 min 0–8 opens with) and the real-time founder Telegram signup pings are the running cross-checks | The DB is ground truth. UTM-attributed signups are a **floor** — in-app browsers and cross-device undercount, and every Facebook click arrives via the `l.facebook.com` shim, so `signup_referrer_host` cannot separate paid from organic |
| **Card-adds** | Gated-cohort accounts that completed the `/app/start` card wall | `GET /api/admin/growth-funnel?days=7` → `card_wall.cards_added` (with `gated_total`, `completion_pct` and `gated_since` beside it) — shipped 2026-08-23 in #586, cohort mirroring `tier.must_add_card` | **Still no client event on gate completion** (gap G1's frontend half): `begin_checkout(surface:"card_gate")` fires on entry and nothing fires on exit, so this number is server-side DB truth or nothing. `gated_since` is `max(window cutoff, CARD_GATE_START)`, so the denominator is never ambiguous — and the cohort is defined by `created_at`, not by who landed on `/app/start`, because that redirect also fires for grandfathered accounts and bookmarked subscribers who were never walled |
| **Trials** | Trials started during the week | the same `trial_started_at` column | **For a gated account these two columns are the same event.** `must_add_card` clears on `trial_started_at`, which the Stripe `trialing` webhook stamps when the card wall's checkout completes. They diverge only for a pre-2026-08-22 account taking the explicit `POST /api/billing/checkout {"start_trial": true}` path. Keep both columns — the day the gate changes they separate again — but do not read a card-add→trial ratio as a funnel step |
| **Payers** | Subscriptions past the trial with a charge collected | `GET /api/admin/revenue` → `active_subscriptions` / `subs_by_status["active"]`; Stripe → Payments as the tiebreak | **Do not use `paid_customers` or `growth-funnel`'s `paying`.** Both still count `stripe_customer_id IS NOT NULL`, which the card gate stamps at TRIAL start, so from 2026-08-22 they read every trialist as a payer. The per-channel tally was the other half of that gap (G12) and **was fixed 2026-08-23 in #586**: `acquisition_channels[*]` now carries `trials_started` and `paid_active_subs` separately, with `paid` kept as an alias of `paid_active_subs` (an active-subscription join), so the channel columns are safe to read and the two account-wide stats are not |
| **Confounds / notes** | Everything that moved the numbers without the ads doing it: AEO/AI-referral spikes, a launch or a post, a newsletter send, a product change, a platform-vs-DB disagreement worth keeping | AEO share: `GET /api/admin/revenue` → `acquisition_channels` (utm_source → referrer host → direct). Everything else: your own record of what shipped and what was sent | This column is what makes the table a mix model rather than a spreadsheet. A blank Notes cell inside a spend window is almost always an unrecorded confound, not a quiet week |

## What this table cannot answer

**Trial → paid.** Zero payers, ever. No amount of spend measures that step and no number of ledger rows will; the instrument is interviews with the existing trialists, at $0 (§2.4, §7.7). Recording the Payers column honestly — usually as `0` — is the point. It is what keeps the `PAID_MARKETING_PLAYBOOK.md` §4 gate from being argued around later.
