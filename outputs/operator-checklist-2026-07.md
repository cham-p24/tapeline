# Tapeline — Operator Checklist ("only you can press")

**Date:** 2026-07-26 · **Site:** https://tapeline.io (LAUNCHED)

These are the items an autonomous agent cannot do — they need the human because they involve account creation, posting under the brand, identity verification, or logged-in GSC/OAuth. Each row points to the doc where the **paste-ready copy already lives**, so no re-drafting is needed.

> Compliance: all linked copy is descriptive. When posting, do not add performance/return claims; the scorecard "currently trails SPY" per `strategies.ts:135`, so keep framing accountability-not-outperformance.

| # | Action | Where the ready copy lives | Notes |
|---|---|---|---|
| 1 | **Fire the Show HN launch** | `TAPELINE_GROWTH_STRATEGY_10X.md` (launch section, §"high-reach launch moment"; line ~52 lists it as drafted-not-executed) and `handovers/marketing-agent.md:49` "Launch playbook" / `:58` "Day 0" | Docs say Show HN is drafted but never fired. Requires your HN account. |
| 2 | **Fire the Reddit launch post** | `handovers/marketing-agent.md` launch playbook (§1, "BEFORE LAUNCH"); referenced in `TAPELINE_GROWTH_STRATEGY_10X.md:52` | Drafted, not executed. Requires your Reddit account + relevant subs. |
| 3 | **Fire the Product Hunt launch** | `handovers/marketing-agent.md` launch playbook; `TAPELINE_GROWTH_STRATEGY_10X.md:52` | Drafted, not executed. Requires your Product Hunt account. |
| 4 | **Claim / build brand profiles** (Capterra, G2, and the off-site profiles in the SERP kit) | `BRAND_SERP_KIT.md` — canonical one-paragraph at `:55`, fact sheet at `:65`, Capterra entry at `:197` (A4); reused by A2/A3/A5 | ⚠️ Before pasting: the canonical paragraph still says "$25-40/mo" (`:55`) — I will fix that to "$10-20/mo" in the doc + `press/page.tsx` first (CODE), so paste the corrected string. |
| 5 | **Google Ads — advertiser identity verification status** | `TAPELINE_GROWTH_STRATEGY_10X.md:55` and `:75` | The doc's 2026-07-04 deadline is **22 days past**. Confirm whether verification completed or the account lapsed — operator-only. |
| 6 | **Submit / re-submit sitemap.xml in Google Search Console** | Live sitemap: https://tapeline.io/sitemap.xml (200, 1,078 URLs) | Requires GSC login. |
| 7 | **Confirm live indexed-page count in GSC** | Replaces the stale "site:tapeline.io returned 0" line in `TAPELINE_GROWTH_STRATEGY_10X.md:53` and `SEO.md:11` | Needed before any doc/report states an indexed number. |
| 8 | **Provide live business figures** (paying customers, MRR, DB account count, current Lifetime price if any) | Fills the unverified blanks in `TAPELINE_GROWTH_STRATEGY_10X.md:11` (scoreboard) and `:111` ($399 Lifetime) | Only you can read the live DB / billing. |

**After you complete 5–8**, the corresponding doc-freshness edits (indexation status, Google Ads status, MRR/customer counts, Lifetime price) become concrete and I can apply them in the docs.
