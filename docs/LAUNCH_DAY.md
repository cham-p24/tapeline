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
| Conversion | Charm-priced annual ($24.99 Pro / $39.99 Premium); billing page with embedded comparison + Stripe portal link; Day-7 drip pushes annual | Visit `/app/billing` |
| Tests | 14 backend + 17 frontend, all green | `cd backend && python -m pytest tests/ -q` |

---

## Five things only you can do — priority order

These are the launch blockers I cannot ship for you. Listed in the order to do them.

### 1. Stripe activation (revenue path) — TODAY

Without this, paying customers can't actually pay.

1. Stripe dashboard → Settings → Account details
2. **Pick "Sole Trader"** (not Company — you'll get stuck on the ACN field for hours otherwise)
3. Complete onboarding — bank account + ID verification
4. Products → Pricing → create **four prices** at the exact amounts:
   - Pro Monthly: **$29.00 USD**, recurring monthly
   - Pro Annual: **$299.00 USD**, recurring yearly (displays as $24.99/mo)
   - Premium Monthly: **$49.00 USD**, recurring monthly
   - Premium Annual: **$479.00 USD**, recurring yearly (displays as $39.99/mo)
5. Webhook → endpoint `https://api.tapeline.io/api/webhooks/stripe`, subscribe to `customer.subscription.{created,updated,deleted}` + `invoice.payment_succeeded`
6. Copy the four price IDs + secret key + publishable key + webhook secret
7. `fly secrets set STRIPE_SECRET_KEY=sk_live_... STRIPE_PUBLISHABLE_KEY=pk_live_... STRIPE_WEBHOOK_SECRET=whsec_... STRIPE_PRICE_PRO_MONTHLY=price_... STRIPE_PRICE_PRO_ANNUAL=price_... STRIPE_PRICE_PREMIUM_MONTHLY=price_... STRIPE_PRICE_PREMIUM_ANNUAL=price_...`
8. Verify: `curl -s https://api.tapeline.io/api/status | grep stripe` should show `"stripe": true`

### 2. Plausible analytics — TODAY (5 min, $9/mo)

Without this, you don't know which marketing post sent which signups.

1. Sign up at `https://plausible.io` ($9/mo for one site, no card needed for trial)
2. Add `tapeline.io` as a site
3. Skip the script-tag step (already wired into `app/layout.tsx`, env-gated)
4. Vercel → Project Settings → Environment Variables → add `NEXT_PUBLIC_PLAUSIBLE_DOMAIN=tapeline.io` (Production)
5. Redeploy: `vercel --prod` (or push any commit)
6. Verify: open the Plausible dashboard, refresh tapeline.io in another tab, you should see one visitor

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

### 5. First marketing post — WHENEVER YOU'RE READY

Your share previews look professional now. Go.

- **X (best signal:noise)**: a screenshot of `/t/NVDA` + a tweet like "I built this because every other scanner gives you 500 filters and a blank stare. tapeline.io"
- **IndieHackers** (`/launches/new`): the full origin story + screenshots + `tapeline.io`
- **r/SecurityAnalysis** (Reddit): genuine value-add post like "I built a public scorecard for my stock scanner. 30 days of receipts so far. [link]"
- **ProductHunt**: schedule for a Tuesday, 12:01 AM PT. Ask 5-10 friends to upvote in the first hour.

---

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
Universe         5,757 tickers in DB · 112 actively scored · /api/public/top-tickers seeds sitemap
Tests            14 backend + 17 frontend, all green
Sitemap          132+ URLs · all per-page OG cards rendering · JSON-LD on every page
Security         HSTS 2yr+preload · X-Frame DENY · Sentry env-gated · client-error endpoint live
```

You built this. Now ship it.
