# Autonomy map — what ships itself, and the irreducible human floor

How much of Tapeline now builds, ships, and self-monitors with **no human in
the loop** — and the small set of one-time actions a human *must* do, because
they are identity / credential / money boundaries, not missing automation.

## Fully autonomous today
| Stage | Mechanism |
|---|---|
| **Build + review** | Code lands on a branch; CI gates it — backend: `ruff` + `mypy` + `pytest`; frontend: `tsc` + `next build` + `vitest`. |
| **Merge** | Clean PRs are squash-merged automatically. |
| **Ship frontend** | Vercel auto-deploys `main` on every push. |
| **Ship backend** | `.github/workflows/deploy-backend.yml` runs the test gate then `flyctl deploy` on every merge to `main`; migrations run via the `alembic upgrade head` release command. **Live once `FLY_API_TOKEN` is set (see bootstrap #1).** |
| **Self-monitor** | `.github/workflows/uptime-monitor.yml` probes the live site + heavy API every 6h and fails loudly (owner email) on any outage/slowness. |

End to end: **PR → CI → auto-merge → Vercel + Fly deploy → uptime watch.** No
human touch required for any of it once the bootstrap below is done once.

## The irreducible one-time bootstrap (~3 minutes, once)
These cannot be automated away. An automation that *could* do them could also
spend your money, leak your secrets, or impersonate you — so the boundary is
deliberate. Ranked by leverage:

1. **Unlock backend auto-deploy** — the big one; after this, every code change
   ships itself forever:
   ```
   fly tokens create deploy -a tapeline-backend          # prints a token
   gh secret set FLY_API_TOKEN --repo cham-p24/tapeline  # paste the token
   ```
   Until set, the deploy workflow runs green but skips (backend stays manual:
   `fly deploy` from `C:\Project 1`).

2. **Complete Google Ads advertiser identity verification** — by **2026-07-04**,
   or Google pauses/limits the live search campaign ("Tapeline - Search Test",
   A$21.24/day, already spending — 740 impr / 30 clicks / A$58 as of 2026-06-05).
   Requires the founder's ID / business docs in the Ads account, so it's an
   identity action — operator-only. This is the near-term risk to ad spend now
   that conversion tracking is wired.

3. **Rotate the leaked PostHog `phx_…` key** — PostHog dashboard (your login).

### ✅ Done since first draft
- **Ad conversion tracking is live.** The "Sign-up" conversion action (Manual
  event, Primary, count=One, value A$1, data-driven attribution; enhanced
  conversions deliberately OFF) is created in Google Ads, and its label
  (`PLnpCJvM8LgcELTRhthD`) is hardcoded in `lib/gtag.ts` (PR #266) and verified
  live in the production bundle. Signups now count as conversions from signup
  #1 — **no Vercel env var needed**. The label is not a secret (it ships in
  client-side JS by design, only meaningful paired with the public AW-ID). The
  GA4-*import* route stays unusable pre-launch (no `sign_up` events to import);
  the tag/label route works from signup #1, which is why it was the right one.
- **Subscribe (revenue) conversion is live.** The "Subscribe" conversion action
  (Manual event, Primary, count=One, "use different values" so it reads the
  per-tier price) is created in Google Ads; its label (`1GH_CIT50rkcELTRhthD`)
  is hardcoded in `lib/gtag.ts`, and `/app/billing` fires it on Stripe
  checkout-success with the tier's first-charge value in USD (PR #269, verified
  live in prod). The campaign can now optimise toward paying customers, not just
  signups. (`start_trial` is intentionally left unwired — it fires at the same
  instant as `sign_up`, so a separate conversion would double-count.)
- **Ad groups 2–3 + 28 campaign negatives confirmed already applied.** Verified
  live in account 271-638-2397 on 2026-06-06 (the founder uploaded them
  2026-06-01). The campaign has 3 ad groups (Finviz Alternative, Best Stock
  Screener, Track Record) + 28 Phrase negatives. The
  `docs/launch/google-ads/APPLY-ADGROUPS-2-3.md` handoff is therefore done —
  do NOT re-import its CSV (would duplicate).

## Why these specific things stay human
- **Secrets / tokens** must be minted in the vendor dashboard by an
  authenticated human; an AI minting + installing them would leak them into
  logs and is a security-settings change.
- **A money-spending ad account** and the conversion *data* (which doesn't
  exist pre-launch) can't be fabricated or safely configured blind.
- **Account identity / passwords / OAuth grants** are the owner's by definition.

Everything that *can* be automated — the building, shipping, and watching — is.
