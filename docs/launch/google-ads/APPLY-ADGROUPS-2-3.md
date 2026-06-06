# Apply Ad Groups 2–3 + Negatives — Handoff

> ## ✅ COMPLETED — applied and verified live 2026-06-06
> Everything in this handoff is done; the steps below are kept for history only.
> Verified directly in account 271-638-2397 on 2026-06-06:
> - **Ad groups 2 & 3 are live + Eligible** — "Track Record" and "Best Stock
>   Screener" are both present under the campaign (uploaded 2026-06-01 via
>   `tapeline-adgroups-2-3-import.csv`, "16 successful"). "Best Stock Screener"
>   is already pulling traffic (1,229 impr / 53 clicks / A$103.78 as of
>   2026-06-06); "Track Record" is Eligible but low search volume (0 impr).
> - **All 28 campaign Phrase negatives are live** (verified 28/28).
> - RSAs were later improved via `tapeline-rsa-improved.csv` (2026-06-05).
> - Conversion tracking is now also wired: **Sign-up** (PR #266) and
>   **Subscribe** (PR #269) conversions are live and forwarding.
>
> **Do NOT re-import `tapeline-adgroups-2-3-import.csv`** — it would create
> duplicate ad groups + keywords. Nothing in this file is still pending.

**Status (2026-06-01):** Campaign **"Tapeline - Search Test (Jun 2026)"** (ID `23891985522`)
is **LIVE / Enabled / Eligible**, bid strategy still **learning**, **A$0.00 spent**.
It currently has **1 ad group** ("Ad group 1" = Finviz Alternative — complete RSA, keywords live).
Ad groups **2 & 3 + campaign negatives are built and validated but NOT yet applied.**

## Why they're not applied yet (the blocker)
**It is not an ad blocker.** The Google Ads **web** console's **Ad groups grid** stalls because
Google's own page-ready endpoint `/aw/ipl_status` returns **HTTP 503** (server-side error) in an
endless poll loop, so the editing table never renders. The account **Overview loads fine** and the
**live campaign is unaffected** — only the *editing grid* is blocked. 503s are transient and usually
clear on their own (minutes–hours). Evidence: every `ipl_status` poll returned 503 across multiple
reloads on 2026-06-01, while `/aw/overview` rendered live data normally.

## Files (all in this folder)
- **`tapeline-adgroups-2-3-import.csv`** — the one to import. Google Ads Editor format.
  Contains ONLY ad group 2 (Track Record) + ad group 3 (Best Stock Screener): 12 keywords + 2 RSAs.
  Finviz Alternative is deliberately excluded — it is already live; importing it would duplicate.
- **`tapeline-negative-keywords.csv`** — 28 campaign-level Phrase negatives.
- `tapeline-search-test.csv` — full source of truth (all 3 ad groups), for reference only.

## How to apply (pick one)

### Option A — Web bulk upload (once the grid loads again)
1. Google Ads → **Tools** (wrench) → **Bulk actions** → **Uploads**.
2. **Upload** → select `tapeline-adgroups-2-3-import.csv`.
3. **Preview** → confirm **2 ad groups / 12 keywords / 2 ads, 0 errors** → **Apply**.
4. **Upload** again → `tapeline-negative-keywords.csv` (adds 28 campaign negatives).
   If bulk upload rejects negatives, add them manually: Campaign → **Keywords → Negative keywords**
   → paste the list → match type **Phrase**.
5. Rename "Ad group 1" → **Finviz Alternative** (Ad groups grid → pencil/rename).

### Option B — Google Ads Editor (bypasses the web 503 entirely)
1. Install **Google Ads Editor** (desktop) → sign in → download account **271-638-2397**.
2. **Account → Import → From file** → `tapeline-adgroups-2-3-import.csv` → review → **Keep**.
3. Import `tapeline-negative-keywords.csv` the same way.
4. **Post** changes.
Editor uses a different backend that does not hit the web `ipl_status` 503.

## Landing pages — verified HTTP 200 (2026-06-01)
- `/compare/finviz` ✓ — ad group 1 (live) destination
- `/scorecard` ✓ — ad group 2 destination
- `/best-stock-scanners` ✓ — ad group 3 destination

No clicks are landing on a broken page.

## Flags for the founder
- **Budget:** campaign is **A$21.24/day (~A$646/mo)**, not the A$15/day originally discussed.
  Lower it under Campaign settings if unintended.
- **Bid strategy:** **Maximize Clicks** (not Manual CPC as first specced). Fine for a search test;
  switch to Manual/Target CPA once there is conversion data.
- **Conversion tracking:** do **NOT** accept the GA4 tag-overwrite "Confirm" in the Ads conversion
  setup — it would clobber the existing 'Tapeline Web' GA4 stream (`G-YRK73W9NS9` / `GT-KDDHGCH7`).
  Link GA4 as a data source instead of re-tagging.
