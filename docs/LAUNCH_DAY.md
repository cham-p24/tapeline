# Tapeline — Launch Day & Week 1

Companion to `OPERATIONS.md` (the pre-launch infrastructure setup playbook).
This doc is "the site is live, here's what to do today and this week" — the
checklist of user-action items I cannot do for you, plus how to verify each.

Keep this open during launch week.

---

## Status of the platform — already shipped

Every line below is verified live on `https://tapeline.io` / `https://api.tapeline.io`.

| Layer | What works | How to verify |
|---|---|---|
| Marketing site | 12 public pages with shared nav + footer + risk disclaimer | Visit `/`, `/pricing`, `/how-it-works`, `/scorecard`, `/blog`, `/changelog`, `/roadmap`, `/status`, `/legal/{terms,privacy,risk}`, `/compare/{finviz,zacks,wallstreetzen}` |
| Per-ticker share | Public `/t/[symbol]` pages with dynamic OG cards (tier-coloured live score) | Tweet `https://tapeline.io/t/NVDA`, see preview |
| Sitemap | 132+ URLs, auto-grows as worker scores more tickers + you add blog posts | `curl -s https://tapeline.io/sitemap.xml \| grep -c '<loc>'` |
| OG cards | 7 distinct (root, pricing, how-it-works, scorecard, changelog, roadmap, dynamic per-ticker) | `curl -sI https://tapeline.io/{page}/opengraph-image` returns `image/png` |
| Security headers | HSTS 2yr+preload, X-Frame DENY, nosniff, Referrer + Permissions Policy, XSS-Protection | `curl -sI https://tapeline.io \| grep -i strict-transport` |
| Backend | scoring 5,757 tickers per minute, real Massive prices, Finnhub fundamentals + insider, FRED macro, Quiver 13F | `curl -s https://api.tapeline.io/api/status \| jq` |
| Reliability | Worker daily refreshes don't block ticks; SSE auto-reconnects with exponential backoff | Watch `LiveBadge` during a backend deploy — flips offline briefly, returns to live within ~2s |
| Observability | Public `/status`, in-app stale-data banner, client-error endpoint logs to Fly | Visit `https://tapeline.io/status` |
| Activation | Welcome email embeds 3 live ticker scores; onboarding tip on `/app/*` for new accounts; watchlist 1-click starter pack | Sign up with a fresh email, check inbox |
| Conversion | Charm-priced annual ($8.25 Pro / $16.58 Premium); billing page with embedded comparison + Stripe portal link; Day-7 drip pushes annual | Visit `/app/billing` |
| Tests | 14 backend + 17 frontend, all green | `cd backend && python -m pytest tests/ -q` |

---

## Five things only you can do — priority order

These are the launch items only you can complete. Listed in the order to do them. **Several previously-listed items here were resolved in the 2026-05-13/14 session — see the updated status below.**

### 1. Stripe — technical integration ✅ DONE; account-side identity verification still pending

The technical wiring is **already deployed and green**:
- All 6 Stripe env vars set in Fly (`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, 4× `STRIPE_PRICE_*`)
- Webhook endpoint live at `https://api.tapeline.io/api/webhooks/stripe` and **subscribed to all 6 relevant events** including `invoice.payment_failed` (added 2026-05-14 during secret rotation)
- Idempotency table `stripe_webhook_events` deduplicating Stripe's automatic retries
- `/api/status` shows `"stripe": true`

**What's still on you**: Stripe-side identity verification — bank account, ID upload, tax setup. Sign in to https://dashboard.stripe.com → Settings → Account details → finish the Sole Trader onboarding so payouts can leave Stripe and arrive in your account. **Once verified, your existing technical setup will let payments flow immediately — no code changes needed.**

If you ever need to rotate the webhook secret without dashboard access, see `OPERATIONS.md` "Rotating the webhook secret without the Stripe dashboard" — uses the Stripe REST API end-to-end. Last done 2026-05-14.

### 2. Analytics ✅ DONE (Vercel Web Analytics + Speed Insights, not Plausible)

**You do NOT need Plausible.** Tapeline already runs **Vercel Web Analytics + Speed Insights**, free on Vercel's Hobby tier, wired into `frontend/app/layout.tsx` at lines 266-267. No env var, no script tag, no $9/mo. Cookieless, IP-anonymised, GDPR-compliant by default.

Open the Vercel project → Analytics tab to see traffic. If you ever outgrow it (Vercel's free tier caps at 100k events/month), then consider Plausible or self-hosted Umami — but you won't hit that ceiling for a long time.

### 3. Lawyer consult — THIS WEEK

Before your first big marketing push.

1. Holley Nethercote Melbourne — financial-services compliance specialists (~$400-800 for a Tapeline-style review)
2. Email them with: link to `/legal/{terms,privacy,risk}` + your business setup (Sole Trader)
3. Get sign-off on:
   - The not-investment-advice positioning (descriptive labels, public-formula moat)
   - The publisher-exemption claim
   - GDPR/CCPA language in the privacy policy (placeholder right now)
4. Replace `legal/*` placeholder pages with their lawyered-up versions

### 4. Social handles — THIS WEEK

To enable per-share `creator` / `site` meta tags.

1. Register `@tapelineio` on X (or your preferred handle)
2. Same on LinkedIn
3. DM me the handles and I'll wire them into `app/layout.tsx` `metadata.twitter.creator` + `site`

### 5. First marketing post

**Launch thread is LIVE + PINNED** on https://x.com/tapeline_io as of 2026-05-13. See `LAUNCH_PLAYBOOK.md` section 3 for the full tweet-by-tweet URL list.

Still to do (priority order):

- **Show HN post** — copy is ready in `LAUNCH_PLAYBOOK.md` section 1. Submit Tue 19 May / Wed 20 May at **10 PM AEST = 8 AM ET** to land in the optimal HN traffic window. You must be online for the first 90 min of comments.
- **Reddit** — three subs, three different post bodies (see `LAUNCH_PLAYBOOK.md` section 2). r/stocks first (Tue 9 AM ET), r/algotrading second (Thu 10 AM ET), r/SecurityAnalysis third (next Tue).
- **Crunchbase profile** — SUBMITTED to moderation queue 2026-05-14. Goes live in 24-72h. You can add logo + founder Person profile via Edit once it's live.
- **ProductHunt** — schedule for a Tuesday at 12:01 AM PT. Ask 5-10 friends to upvote in the first hour.
- **IndieHackers** — `/launches/new` with the full origin story.

---

## Operational tools

When a launch user emails you about their tier — comping a beta user,
crediting a Founder's Lifetime, demoting a refund — use:

```bash
# Locally (against the local SQLite or whichever DB DATABASE_URL points at)
cd backend && .venv/Scripts/python.exe -m app.scripts.set_tier alice@example.com pro

# Premium with the trial countdown cleared (use when comping a paying user)
.venv/Scripts/python.exe -m app.scripts.set_tier alice@example.com premium --clear-trial

# Founder's Lifetime — Premium that survives webhook downgrades
.venv/Scripts/python.exe -m app.scripts.set_tier alice@example.com premium --lifetime --clear-trial

# Against the running Fly machine — no local checkout needed
fly ssh console -a tapeline-backend -C "python -m app.scripts.set_tier alice@example.com pro"
```

The script prints before/after state so you have a record. Idempotent
— safe to re-run.

## Daily during launch week

Quick checks (each <1 min):

```bash
# 1. Is the API healthy?
curl -s https://api.tapeline.io/api/status | jq '.status'  # should be "ok"

# 2. Is the worker still ticking?
curl -s https://api.tapeline.io/api/status | jq '.checks.worker_last_tick.age_seconds'
# should be < 120

# 3. How many tickers + news right now?
curl -s https://api.tapeline.io/api/status | jq '.checks.database'

# 4. Did my latest deploy actually land?
curl -s https://api.tapeline.io/api/version | jq

# 5. New users today?
fly ssh console -a tapeline-backend -C "python -c 'from app.db import SessionLocal; from app.models import User; from datetime import datetime, timedelta, UTC; s = SessionLocal(); print(s.query(User).filter(User.created_at >= datetime.now(UTC) - timedelta(days=1)).count())'"

# 6. Any client-side errors in the last hour?
fly logs -a tapeline-backend | grep client_error | tail -10

# 7. Any backend exceptions?
fly logs -a tapeline-backend | grep -E "ERROR|Exception" | tail -10
```

The `https://tapeline.io/status` page renders most of the above visually if you'd rather click than curl.

---

## Week 2-4 follow-ups

Once you have ~50 signups and a few payments through Stripe:

1. **Sentry**: sign up free tier (5k events/month), set `SENTRY_DSN` in `fly secrets`. Backend wiring is already in `main.py`, just needs the DSN.
2. **UptimeRobot or Better Uptime**: free monitor pinging `https://api.tapeline.io/api/health` every 5 min. Email + SMS on failure.
3. **A real founder bio + photo on /about** (route doesn't exist yet — would land well after some launch traction).
4. **A second blog post per week** for SEO compound. The 4 already shipped target buyer intent; next ones should be commentary on actual market events using your scoring data ("What our scanner showed during the NVDA drop").

---

## What's NOT shipped that you might want eventually

| Item | Why not yet |
|---|---|
| Onboarding tour with 5+ steps | Single-callout converts better than multi-step (see `OnboardingTip.tsx`) |
| `/about` founder page | Better after some traction so you have stats to point at |
| API documentation page | Premium-tier API access is wired but only needs docs once you have your first API user |
| Mobile app | Web is mobile-responsive (verified on `/t/[symbol]` + `/app/billing`); native app is post-PMF |
| Real-time push notifications | Web Push is wired (`alerts.web_push` Pro+ feature); native iOS/Android post-PMF |
| Welcome-email A/B subject testing | Needs Plausible analytics first to measure |

---

## File map for launch-day debugging

| Symptom | Where to look |
|---|---|
| Signup is broken | `backend/app/routers/auth.py` + `backend/tests/test_smoke.py::test_signup_signin_me_full_flow` |
| User can't pay | Stripe webhook secret in Fly + `STRIPE_PRICE_*` env vars set + `backend/app/routers/billing.py` |
| Welcome email not sending | `RESEND_API_KEY` in Fly + `backend/app/services/email.py:render_welcome_email` |
| Scanner shows stale data | `https://tapeline.io/status` first; if worker stale, `fly logs -a tapeline-backend \| grep tick.done` |
| /t/[symbol] preview broken on social | `https://tapeline.io/t/NVDA/opengraph-image` should return image/png |
| /pricing shows old prices | Hard-refresh; if persistent, redeploy frontend |

---

## Production state at launch (this commit)

```
Health           status=ok · tick consistently <30s · all integrations green except Stripe
Universe         5,757 tickers in DB · ~2,500 actively scored (top by $-volume) · /api/public/top-tickers seeds sitemap
Tests            14 backend + 17 frontend, all green
Sitemap          132+ URLs · all per-page OG cards rendering · JSON-LD on every page
Security         HSTS 2yr+preload · X-Frame DENY · Sentry env-gated · client-error endpoint live
```

You built this. Now ship it.
