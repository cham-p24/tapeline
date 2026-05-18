# Items confirmed deferred — not blocking launch

The launch playbook (`LAUNCH_PLAYBOOK.md`) flagged certain integrations as
"intentionally deferred." This file is the cross-reference for any future
handover doc that lists these as "TODO" — they're not. They're closed-as-
deferred, with the rationale and the un-defer trigger documented per item.

Last audited: 2026-05-18.

---

## Microsoft OAuth

**Status:** Deferred indefinitely (post-launch).

**Why:**
1. The "Continue with Microsoft" button is already **hidden in production** —
   `OAuthButtons.tsx` only renders when `/api/auth/oauth/providers` returns
   `microsoft: true`, which requires both `OAUTH_MICROSOFT_CLIENT_ID` and
   `OAUTH_MICROSOFT_CLIENT_SECRET` Fly secrets to be set. They aren't. So
   there is zero broken-UI risk from leaving this off.
2. M365 Developer tenant provisioning requires the founder's M365 Dev account
   sign-up (~15-30 min) and the Persona/biometric step is device-bound and
   can't be MCP-driven.
3. HN/Reddit/fintwit launch traffic is overwhelmingly Google/GitHub identity.
   Microsoft Sign-In is checkbox-feature territory for a fintech-prosumer
   audience.

**Un-defer trigger:** revisit when EITHER (a) Tapeline has 50+ paying users
AND one specifically requests it, OR (b) the founder pivots toward B2B
procurement where M365 SSO becomes a checklist item.

**Setup path when ready:** `LAUNCH_PLAYBOOK.md §6` documents the exact
10-minute path (Entra App Registration → client ID + secret → `fly secrets
set`).

---

## Quiver QuantData / elite 13F holdings

**Status:** Dropped from the product per PR #74 (2026-05-17).

**Why:**
1. Quiver Trader-tier TOS explicitly states "No Commercial Use Rights" —
   surfacing 13F holdings in a paid SaaS is a direct license violation.
2. The 45-day lag on 13F data eats the alpha anyway. Form 4 insider
   transactions (free via Finnhub, 2-business-day filing window) carry the
   same Smart Money signal with no license issue.
3. Premium marketing was scrubbed of "Elite 13F holdings" claims in PR #74.
   `quiver_feed.py` + the `_refresh_elite_13f` worker task still run with
   mock-data fallback to keep the `InstitutionalHolding` table populated;
   nothing surfaces it.

**Un-defer trigger:** revisit only if EITHER (a) Premium re-adds an elite-13F
UI surface under a commercial Quiver license (~$200+/mo), OR (b) a vendor
shipping legally-clear elite-fund holdings becomes available.

**No action required:** the integration is dormant, not broken. Setting
`QUIVER_API_KEY` now wires a real-data feed that no UI reads from — pure
overhead.

---

## What this means for any TODO list mentioning these items

The handover docs from 2026-05-13 through 2026-05-17 still list both as
"open" or "founder must do." That's stale. Treat both rows as **closed,
deferred** unless the founder gives an explicit override. Future handover
generators should reference this file.
