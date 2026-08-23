# Activation — definition of record

_Decision record · owner: growth/data · last updated August 2026_

## The event

**A signup is "activated" the first time they experience Tapeline's core value — defined as either:**

1. **Adding a ticker to their watchlist**, or
2. **Viewing a ticker's full six-factor score breakdown** (the `/app/ticker/[symbol]` / `/t/[symbol]` detail, while logged in).

Whichever happens first stamps `User.activated_at`. It is **idempotent** — set once, never overwritten — so it measures *time-to-activation*, not last activity.

## Why this event

The core value of Tapeline is **seeing why a stock scores what it does** — the transparent, six-factor read. So activation must mean *"the user experienced that value,"* not *"the user logged in."*

- A login-only definition understates activation badly (fintech activation reads ~5% on a login-only definition vs ~44% on a real value event — Userpilot/ProductQuant 2026). We avoid that trap.
- The previous definition (**watchlist add only**) was a good but *narrow* signal — it missed every user who looked at the scores, got the value, but never added a watchlist item. Broadening to include a full-breakdown view captures those real activations.
- We deliberately do **not** count "opened the scanner" (it auto-loads → too close to login) or an anonymous SSR page render (those hit the public endpoint with no user and never stamp).

## How it's measured

- **Stamp points:** `backend/app/routers/watchlist.py` (first watchlist add) and `backend/app/routers/ticker.py` (first authed ticker-detail view, after the look-up meter passes). Both guard on `activated_at IS NULL`.
- **Activation rate** = `activated_users / total_signups` — surfaced on the admin `/revenue` dashboard.
- **Time-to-value (TTV)** = median hours from `created_at` to `activated_at` over the activated cohort — also on `/revenue`. This is the onboarding target behind the rate; users who hit first value fast convert 3–5× more.

## Benchmarks & triggers

- SaaS median activation ~37.5%; well-defined fintech ~44%. Median TTV ~22 min; elite <3 min.
- **<20%** → onboarding is broken; watch session replays before changing anything.
- **20–40%** → healthy; push attention to the price wall (trial→paid).
- **>40%** → activation isn't the problem; the constraint is arrivals (weekly sessions).

## Future refinements (not done yet)

- A **time-boxed** variant ("activated *within 48h*") is more predictive but changes the metric's meaning; revisit once there's enough volume to compare.
- Consider counting a **saved/applied scanner screen** as a third value event once saved-screens usage is meaningful.
