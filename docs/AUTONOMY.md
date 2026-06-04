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

2. **Finish ad conversion tracking** — the Google Ads *tag* is already live
   (`AW-18169833652`, hardcoded default in `app/layout.tsx`), so the "missing
   Google tag" warning is cleared. To make signups *count as conversions*:
   - In Google Ads, open the "Sign-up" conversion action → copy its **label**.
   - In Vercel, set `NEXT_PUBLIC_GOOGLE_ADS_SIGNUP_LABEL` to that label → redeploy.
   - `lib/gtag.ts` then fires `gtag('event','conversion', {send_to:'AW-18169833652/<label>'})`
     on every signup automatically.
   - Note: the GA4-*import* route can't be used yet — pre-launch, no `sign_up`
     events have occurred for Ads to import. The tag route above works from
     signup #1, which is why it's the right one for now.

3. **Rotate the leaked PostHog `phx_…` key** — PostHog dashboard (your login).

## Why these specific things stay human
- **Secrets / tokens** must be minted in the vendor dashboard by an
  authenticated human; an AI minting + installing them would leak them into
  logs and is a security-settings change.
- **A money-spending ad account** and the conversion *data* (which doesn't
  exist pre-launch) can't be fabricated or safely configured blind.
- **Account identity / passwords / OAuth grants** are the owner's by definition.

Everything that *can* be automated — the building, shipping, and watching — is.
