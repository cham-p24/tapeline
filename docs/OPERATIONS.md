# Tapeline — Operations

The launch-day playbook. Everything you need to do, in the order to do it,
with the file paths and commands. Keep this open during launch week.

## Quick reference

| Concern | Where |
|---|---|
| Run dev locally | `.\scripts\run_nodocker.ps1` |
| Reset the dev DB | `rm backend/tapeline_dev.sqlite && cd backend && .venv\Scripts\python.exe -m alembic upgrade head && .venv\Scripts\python.exe -m app.scripts.seed_owner` |
| Owner login | `owner@tapeline.io` / `TapelineOwner!2026` |
| Run smoke tests | `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q` |
| Apply new migrations | `cd backend && .venv\Scripts\python.exe -m alembic upgrade head` |
| All env vars | `.env.example` (root) + `frontend/.env.local.example` |
| Tier gating | `backend/app/services/tier.py` |
| Pricing UI | `frontend/components/PricingTable.tsx` |
| Worker | `backend/app/workers/signal_publisher.py` |

---

## 1. Going live — order of operations

Each step unlocks one or more env vars. Do them in this order; later steps
depend on earlier ones being live.

### Step 1 — Domain (Cloudflare, ~$35/yr, 10 minutes)

1. Register `tapeline.io` at Cloudflare (also gives you Bot Fight Mode for free)
2. Enable **Bot Fight Mode** under Security → Bots (free, blocks the obvious automated traffic at the edge)
3. Create a **Turnstile** widget at Security → Turnstile (also free):
   - Domain: `tapeline.io`, `www.tapeline.io`, `localhost` for dev
   - Get the **site key** + **secret key**
   - Paste site key into `frontend/.env.local`: `NEXT_PUBLIC_TURNSTILE_SITE_KEY=...`
   - Paste secret key into `.env`: `CLOUDFLARE_TURNSTILE_SECRET_KEY=...`
4. After deploy, point DNS A records at the Vercel/Fly endpoints (see Step 9)

The honeypot field and the disposable-email block are always active regardless
of Turnstile. Turnstile adds the third layer.

### Step 2 — Massive Stocks Starter ($29/mo, 15 minutes)

(Polygon.io rebranded to Massive on 2025-10-30. Adapter is already pointed at `api.massive.com` — Massive also accepts legacy Polygon keys.)

1. Sign up at https://massive.com/pricing (Stocks Starter tier, monthly)
2. Grab the API key from the dashboard
3. Paste into `.env`: `MASSIVE_API_KEY=...` (or `POLYGON_API_KEY=...` if migrating an existing Polygon account)
4. **Manually swap the worker imports** at `backend/app/workers/signal_publisher.py` (top of file):
   ```python
   # FROM:
   from app.services.mock_feed import (
       fetch_congress_trades, fetch_regime, fetch_snapshots, fetch_squeezes, universe,
   )
   # TO:
   from app.services.polygon_feed import (
       fetch_congress_trades, fetch_regime, fetch_snapshots, fetch_squeezes, universe,
   )
   ```
5. Restart the worker. Check `latest_run.log` for `tick.done snapshots=N` with N matching the live universe size
6. **Note**: `polygon_feed.py` has TODOs for live DXY / 10Y / breadth (currently hardcoded). These can stay until launch but are on the post-launch fix list.

### Step 3 — Stripe ($0 to set up, ~30 minutes)

1. Create a Stripe account (https://stripe.com)
2. Create **four Price IDs** under Products → Pricing:
   - `Pro Monthly` — $29 USD recurring monthly
   - `Pro Annual` — $299 USD recurring yearly (charm price; displays as $24.99/mo)
   - `Premium Monthly` — $49 USD recurring monthly
   - `Premium Annual` — $479 USD recurring yearly (charm price; displays as $39.99/mo)
3. Paste into `.env`:
   ```
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_PUBLISHABLE_KEY=pk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   STRIPE_PRICE_PRO_MONTHLY=price_...
   STRIPE_PRICE_PRO_ANNUAL=price_...
   STRIPE_PRICE_PREMIUM_MONTHLY=price_...
   STRIPE_PRICE_PREMIUM_ANNUAL=price_...
   ```
4. Add a webhook endpoint pointing at `https://tapeline.io/api/webhooks/stripe`. Subscribe to:
   `customer.subscription.created`, `customer.subscription.updated`,
   `customer.subscription.deleted`, `invoice.payment_succeeded`
5. Test with the Stripe CLI: `stripe listen --forward-to localhost:8000/api/webhooks/stripe`

### Step 4 — Resend (Free tier OK, 5 minutes)

1. Sign up at https://resend.com
2. Verify the `tapeline.io` domain (DNS records)
3. Grab the API key
4. Paste into `.env`: `RESEND_API_KEY=re_...` and `EMAIL_FROM=alerts@tapeline.io`
5. Test: trigger a signup, the day-0 welcome email should arrive within 30s

The day-3 / day-7 / day-13 drip and trial-ended email all auto-fire from the
worker's daily task once Resend is live. No additional wiring needed.

### Step 5 — Telegram (Free, 10 minutes)

1. DM `@BotFather` on Telegram, send `/newbot`, name it `TapelineBot`
2. Get the bot token
3. Paste into `.env`: `TELEGRAM_BOT_TOKEN=...`
4. Test: sign in as a Premium user, go to `/app/billing` → Notifications card,
   paste your own chat_id (DM `/start` to your bot, it'll reply with your numeric id), hit "Save" then "Send test message"

### Step 5a — Twilio SMS (Optional, ~$0.008/msg US, 15 minutes)

Skip this if you don't want SMS as a third alert channel. Email + Telegram cover most use cases.

1. Sign up at https://www.twilio.com (free trial gives ~$15 credit)
2. Buy a phone number (~$1.15/mo for a US number)
3. Get the Account SID + Auth Token from the dashboard
4. Paste into `.env`:
   ```
   TWILIO_ACCOUNT_SID=AC...
   TWILIO_AUTH_TOKEN=...
   TWILIO_FROM_NUMBER=+15551234567
   ```
5. Test: sign in as a Premium user, go to `/app/billing` → SMS card, enter your number, hit "Save" then "Send test SMS"

**Cost discipline**: SMS rules should be reserved for high-conviction events
(HIGH CONVICTION crossings, regime flips, big congress trades). Don't enable
SMS on a high-frequency rule — every message is billed.

### Step 6 — Quiver QuantData (Free tier, 5 minutes)

1. Sign up at https://api.quiverquant.com/
2. Grab the API key
3. Paste into `.env`: `QUIVER_API_KEY=...`
4. Restart the worker. Within 24h the elite-13F holdings will switch from mock
   to real data (or sooner if you nuke the cache: `rm backend/.cache/quiver_*.json`)
5. Verify: `/app/holdings` should show real fund positions (Buffett, Burry, etc.)

### Step 6a — Benzinga news + analyst ratings (~$30/mo, 10 minutes)

Activates two features at once:
- News feed swaps from Polygon/Massive (slow, sparse cashtags) to Benzinga
  (sub-second wire, every cashtag tagged) for the live news bar + per-ticker headlines.
- **NEW:** Analyst ratings widget on `/app/ticker/{symbol}` showing consensus
  (Buy/Hold/Sell tally), average price target with upside vs. current price, and
  recent rating actions (firm + prior → current + PT changes).

1. Sign up at https://www.benzinga.com/apis (Newsfeed + Analyst Ratings tiers).
2. Grab the API token (format `bz.XXX...`).
3. Paste into `.env`: `BENZINGA_API_KEY=bz.XXX...`
4. Push to production: `fly secrets set BENZINGA_API_KEY=bz.XXX... -a tapeline-api`
5. Restart the worker locally (or Fly redeploys automatically). The next news
   tick (~5 min) will pull from Benzinga; the ratings widget loads on first
   ticker-page visit (cached 6h per symbol).

Without a key, news still works via Massive and the ratings widget renders an
empty state with a friendly note — no errors, nothing breaks.

### Step 7 — Google + Microsoft OAuth (Both free, 30 minutes total)

**Google:**
1. https://console.cloud.google.com → New Project → "OAuth consent screen"
2. Add the scope `email` + `profile`
3. Credentials → Create OAuth client ID (Web application)
4. Authorised redirect URIs: `https://tapeline.io/api/auth/oauth/google/callback`
5. Paste into `.env`: `OAUTH_GOOGLE_CLIENT_ID=...`, `OAUTH_GOOGLE_CLIENT_SECRET=...`

**Microsoft:**
1. https://entra.microsoft.com → App registrations → New registration
2. Redirect URI: `https://tapeline.io/api/auth/oauth/microsoft/callback`
3. Certificates & secrets → New client secret
4. Paste into `.env`: `OAUTH_MICROSOFT_CLIENT_ID=...`, `OAUTH_MICROSOFT_CLIENT_SECRET=...`

The `OAuthButtons.tsx` component auto-detects which providers are configured
and shows only the matching buttons.

### Step 8 — Database (Postgres, ~$25/mo)

Pick one:
- **Supabase Pro** — $25/mo, includes auth/storage you may use later
- **Neon** — $19/mo, slightly cheaper, pure Postgres

1. Create a project, grab the connection string
2. Paste into production `.env`: `DATABASE_URL=postgresql://...`
3. Run migrations against prod: `cd backend && .venv\Scripts\python.exe -m alembic upgrade head`
4. Seed the owner: `python -m app.scripts.seed_owner` (set `OWNER_PASSWORD` env first)

### Step 9 — Deploy (Free tiers, 30 minutes)

**Backend (Fly.io):**
1. `fly auth login`
2. From repo root: `fly launch` (uses existing `fly.toml`). Choose region (Sydney for AU)
3. Set secrets: `fly secrets set POLYGON_API_KEY=... STRIPE_SECRET_KEY=... ...`
4. `fly deploy`
5. Confirm health: `curl https://tapeline-api.fly.dev/api/health`

**Frontend (Vercel):**
1. `vercel login`
2. From `frontend/`: `vercel link` then `vercel`
3. Add env vars in the Vercel dashboard:
   - `NEXT_PUBLIC_API_URL=https://tapeline-api.fly.dev` (or behind tapeline.io)
   - `NEXT_PUBLIC_TURNSTILE_SITE_KEY=...`
4. Deploy: `vercel --prod`

**DNS:**
- `tapeline.io` → Vercel (frontend)
- `api.tapeline.io` → Fly.io (backend, via fly cert)
- Update `APP_URL=https://tapeline.io` and `API_URL=https://api.tapeline.io` in the Fly secrets

### Step 10 — Lawyer ($400-800, 1 hour)

Schedule a consult with **Holley Nethercote** (Melbourne) or another AU fintech firm.

Bring: `docs/LEGAL_CHECKLIST.md`, the publisher-exemption framing, the descriptive (not prescriptive) signal labels documented in `tier.py` / `mock_feed.py`. Goal: get their opinion in writing before the first paying customer.

---

## 2. Daily operations

### Wipe and reseed the dev DB

```powershell
rm backend/tapeline_dev.sqlite
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m app.scripts.seed_owner
```

### Change the owner password

```powershell
$env:OWNER_PASSWORD = "NewSecurePassword!"
cd backend
.venv\Scripts\python.exe -m app.scripts.seed_owner
```

### Force a 13F refresh (skip the 24h cache)

```powershell
rm backend/.cache/quiver_*.json
# Worker will refetch on next 24h tick — or restart it
```

### Force-downgrade a user (manual override)

```sql
UPDATE users SET tier = 'free' WHERE email = 'user@example.com';
```

### Watch the worker logs

Look for these tick lines:
- `tick.done snapshots=N squeezes=N regime=X trades_added=N elapsed=Ns`
- `alerts.fired count=N` (when alert rules trigger)
- `holdings.13f_refreshed source=quiver|mock count=N` (daily)
- `trial.downgraded count=N` (hourly check; usually 0)
- `drip.sent day3=N day7=N day13=N` (daily)

### Run smoke tests

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q
```

All 7 should pass. The rate-limit test runs last to avoid poisoning the others.

---

## 3. Bot / abuse layers (active now)

| Layer | Where | Active? |
|---|---|---|
| Cloudflare Bot Fight Mode | Cloudflare dashboard | Once domain is on Cloudflare |
| Per-IP rate limit (general) | `backend/app/services/rate_limit.py` `limit_api` (120/min) | ✅ |
| Per-IP rate limit (auth) | `rate_limit.py` `limit_auth` (10/min) | ✅ |
| Honeypot field | Signup form — invisible `company` input | ✅ |
| Disposable-email block | `backend/app/services/bot_protection.py` (62 domains) | ✅ |
| Cloudflare Turnstile | `bot_protection.py` `verify_turnstile` | When env keys are set |

If a real user gets blocked, look at the auth.py logs — every block writes a
`auth.honeypot_tripped` / `auth.disposable_email_blocked` line with the email.

---

## 4. Common emergencies

### "I'm getting 429 on every request"

The token-bucket rate limiter ran out. Wait 60s, or restart the API to reset
the in-process buckets. Production should swap to Redis-backed for a
multi-instance setup.

### "Email alerts aren't sending"

1. Confirm `RESEND_API_KEY` is set
2. Check `latest_run.log` for `email.skipped reason=no_api_key`
3. Test directly: `curl -X POST https://api.resend.com/emails -H "Authorization: Bearer $RESEND_API_KEY" -d '...'`
4. If Resend returns 401, the key is wrong. If 422, the from-domain isn't verified.

### "Telegram digest stopped"

1. Confirm `TELEGRAM_BOT_TOKEN` is set
2. Check users actually have `telegram_chat_id` set: `SELECT email, telegram_chat_id FROM users WHERE telegram_chat_id IS NOT NULL`
3. The hourly digest only runs for `tier='premium'` users. Free/Pro users won't get it (by design).

### "13F holdings are still showing mock data with QUIVER_API_KEY set"

1. Force-clear the cache: `rm backend/.cache/quiver_*.json`
2. Restart the worker (the 24h timer is in-memory)
3. Check logs for `quiver.13f_fetched count=N` — if you see `quiver.13f_empty no_funds_returned_data`, the API endpoints have changed shape; look at `_try_fund_endpoints` in `quiver_feed.py`

### "Trial users aren't being downgraded"

The hourly task only runs every 60 seconds × 60 = 3600s. Check the worker has
been running > 1h. Otherwise inspect:
```sql
SELECT id, email, tier, trial_ends_at, stripe_customer_id, is_lifetime
FROM users WHERE trial_ends_at < NOW();
```
A user with `stripe_customer_id` set OR `is_lifetime = true` is intentionally
exempt from the downgrade.

### "I committed something I shouldn't have"

You have git now. Worst case:
```powershell
git log --oneline               # find the bad commit
git revert <commit-sha>         # creates a new commit undoing it
# OR (destructive, only for un-pushed):
git reset --soft HEAD~1         # undo last commit, keep changes staged
```

### "The whole worker keeps crashing"

Check `latest_run.log` for the traceback. Most likely culprits in order:
1. DB connection failed — check `DATABASE_URL`
2. Missing env var — Pydantic Settings will throw at startup with the missing field name
3. New Alembic migration not applied — run `alembic upgrade head`

---

## 5. Things to do post-launch

These don't block launch but should land within the first month:

- Replace hardcoded macro indicators (`polygon_feed.py:209-212`) with live FRED or Polygon data
- Auto-discover universe via Polygon `/v3/reference/tickers` daily (~30 min once Polygon is live)
- Frontend tests (Vitest + React Testing Library)
- Onboarding email content review by an editor
- Cart-abandonment + win-back email sequences
- Public roadmap page (paid users only)
- Live changelog page
- `/compare` SEO pages: `Tapeline vs Finviz`, `Tapeline vs Zacks`, `Tapeline vs WallStreetZen`
- 90-second Loom on the hero (handoff said this gives 2× conversion)
- Affiliate program (30% recurring, fintwit micro-influencers)
- AppSumo lifetime listing once you have ~50 paid users

---

## 6. Hard limits (don't change without thinking)

- **Six-factor scoring formula and weights** — `backend/app/services/mock_feed.py` `fetch_snapshots()`. Transparency is the moat.
- **Descriptive signal labels** — never use "BUY", "ACCUMULATE", "WATCH" in any user-facing copy. Use the descriptive labels in `mock_feed.py:_signal_from_score`.
- **Public scorecard** — never gate it. It's the trust mechanism. Free users see it; paying users see the live data.
- **Owner login** — only created via `seed_owner.py`. Never expose admin promotion via the signup form.
- **Three-tier price points** — Pro $29 / Premium $49. Don't revisit until 500+ paying users with conversion data.
- **Free tier shows real product** — 24h delayed and 20 tickers, but real data. Not a feature-stripped mock.
- **Trial tier is Premium** — gives users the best, takes it away on expiry. Don't drop to Pro-trial without an A/B.
