# Google Ads — Conversion Runbook (get MORE paying subscribers)

*Assembled 2026-07-29. Reconciles `docs/PAID_ADS_PATHWAY.md` (the strategy) with what's **actually built in the codebase today** + the live account state, so nothing gets rebuilt and the only open items are the ones that genuinely move conversions. Pairs with `PAID_ADS_PATHWAY.md`. Not legal/tax advice.*

---

## 0. The one thing that changed: the reprice moved the goalposts
Tiers are now **Pro $9.99/mo ($99/yr) · Premium $19.99/mo ($199/yr)** (was $29.99/$49.99). Recomputed (see `PAID_ADS_PATHWAY.md` Part 1): even a fully-tuned funnel lands at **~1.85:1 LTV:CAC — below the 3:1 scale gate.** Consequence: **cold Google Search is not a profit engine at this price.** Run it small (branded + retargeting), and put the real budget into **affiliates (pay-on-conversion) + organic**. Everything below is about squeezing the *most* out of the small, disciplined paid layer.

## 1. What's ALREADY built — do NOT redo these
- **Conversion tracking is wired end-to-end** (`frontend/lib/gtag.ts`): `sign_up` (label `PLnpCJvM8LgcELTRhthD`) and `subscribe` (label `1GH_CIT50rkcELTRhthD`, sends per-tier value) forward to Google Ads `AW-18169833652`. `begin_checkout` fires (`app/app/billing/page.tsx`) but has **no Ads conversion action yet** (label intentionally empty). `start_trial` is deliberately NOT forwarded (fires at the same instant as `sign_up` → would double-count).
- **GCLID capture** for offline import is built (`lib/utm.ts` stores `gclid/gbraid/wbraid`; `lib/auth.ts` writes them to the User row). The *upload* job is the missing half (see §2.4).
- **Conversion-optimized landing pages exist** — the `LandingCta` block (message-matched via `?from=`, price single-sourced from `lib/pricing.ts`, compliance-clean) is live on 9 pages including all three ad-group destinations. `/scorecard` has its own `?from=scorecard` hero CTA. **No new `/lp/*` pages needed** — the ads already land on real offers.

## 2. Operator actions that get MORE conversions (in priority order — Ads console / infra)
**2.1 — Unblock spend.** Confirm Google Ads **advertiser identity verification** is complete (deadline was ~2026-07-04, now past). Until it is, the one demand channel is throttled. *(Owner-only: identity docs.)*

**2.2 — Bid toward PAYERS, not clicks.** Campaign is on **Maximize Clicks**. Once you have **≥30 `subscribe` conversions in 30 days** → switch to **Maximize Conversions**, then **Target CPA on the `subscribe` action** (not `sign_up`, not clicks). This is the single biggest in-console lever — it tells Google to find people who *pay*.

**2.3 — Create the `begin_checkout` conversion action.** Goals → Conversions → New conversion action → Website → **Manual event**, set **SECONDARY** (so it doesn't compete with Subscribe for Smart Bidding). Then set `NEXT_PUBLIC_GOOGLE_ADS_BEGIN_CHECKOUT_LABEL` in Vercel to its label. The event already fires — this just lights up the funnel's missing middle so you can see where checkout leaks.

**2.4 — Offline-conversion import (GCLID → paid).** The paid conversion happens *after* the 14-day trial, off-session — a page pixel can't catch it. Build the daily upload: read User rows where trial→paid converted, push `{gclid, conversion_time, value}` to Google Ads via the API. **Needs: a Google Ads API developer token + OAuth creds** (owner). This is what lets Smart Bidding optimize on real LTV. *Capture side is already done; only the upload + creds remain.*

**2.5 — Stand up retargeting** (Display/YouTube; Reddit later). Audiences: visited-LP-no-signup, signed-up-not-activated, trial-expiring. Creative: the scorecard *with a losing week shown* (proof), a 15-sec live-scanner clip, "trial ends in 2 days." Retargeting clicks are $0.50–1 and convert far higher — this is what pulls blended CPC toward the ~$2.50 that makes the math least-bad.

**2.6 — Weekly hygiene.** Mine the **Search Terms report** weekly → add negatives, harvest converters. Keep Search Partners + Display **OFF** on the Search campaign; auto-apply recommendations **OFF**. Watch **`subscribe`**, not signups.

**2.7 — The scale gate.** Add budget only while **LTV:CAC ≥ 3 and payback < 12 mo on `subscribe`**. At the new price that bar is hard on cold Search — so expect to keep this campaign **capped/branded** and route growth budget to affiliates + organic.

## 3. Optional bigger lever (product decision, not a quick task)
**Card-required trial on PAID traffic only.** No-card trial→paid ≈ 8.9%; card-required ≈ 31% (~3.5×). Keep no-card for organic; A/B a card-on-trial variant for the paid segment (with clear auto-charge disclosure, day-13 email, one-click cancel). This is the highest-value conversion change — but it touches the signup/billing flow and changes the offer, so it's a founder decision + a scoped build, not a console toggle.

## 4. Compliance (keeps the account alive — non-negotiable)
A scanner needs **no** certification (not CFD/forex/broker). **Never** in ad copy or LPs: "beat the market / guaranteed returns / winning picks / profit / get rich / price predictions / signals." Safe framing only: *scanner, screener, research, transparent methodology, back-checked vs SPY (shown publicly), losses included.* Descriptive, never promissory — also the only *true* pitch, since the public record trails SPY. Keep the "informational only — not investment advice" line on every LP. **Do not run AU-targeted ads until the AFSL/ASIC disclaimer + lawyer sign-off are done.**

## 5. Live account facts (for reference)
- Account **271-638-2397**; campaign **"Tapeline – Search Test (Jun 2026)"** `23891985522`; budget **A$21.24/day (~A$646/mo)**; bid **Maximize Clicks**.
- 3 single-theme ad groups → matched pages: **Finviz Alternative** → `/compare/finviz`, **Track Record** → `/scorecard`, **Best Stock Screener** → `/best-stock-scanners`. 28 phrase negatives live.
- Ads tag `AW-18169833652`; GA4 `G-YRK73W9NS9`. ⚠️ Do NOT accept the GA4 tag-overwrite prompt in Ads conversion setup (it clobbers the GA4 stream) — link GA4 as a data source instead.
