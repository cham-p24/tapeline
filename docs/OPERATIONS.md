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

Direct dashboard URLs, in the order you'll need them:

| Step | URL | What to grab |
|---|---|---|
| 1. Confirm you're in **Live** mode (not Test) | https://dashboard.stripe.com/dashboard | toggle top-right |
| 2. Create the four prices below | https://dashboard.stripe.com/products?create=product | 4 × `price_...` IDs |
| 3. Copy the secret key | https://dashboard.stripe.com/apikeys | `sk_live_...` |
| 4. Add the webhook + grab signing secret | https://dashboard.stripe.com/webhooks | `whsec_...` |

**The four prices to create** (matches canonical pricing in `CLAUDE.md` — the `Pro/Premium $29/$49` numbers that appeared in earlier docs are stale, do NOT use them):

| Product | Recurring | Amount | Lookup key (optional but handy) |
|---|---|---|---|
| Tapeline Pro | Monthly | $9.99 USD | `pro_monthly` |
| Tapeline Pro | Yearly | $99 USD | `pro_annual` |
| Tapeline Premium | Monthly | $19.99 USD | `premium_monthly` |
| Tapeline Premium | Yearly | $199 USD | `premium_annual` |

Annual rows are intentional "charm" prices — `$99/yr` displays in-app as `$8.25/mo billed annually` (saves $20/yr vs monthly), `$199/yr` displays as `$16.58/mo billed annually` (saves $40/yr). Those savings are computed off the founding prices ($9.99 × 12 − $99 = $20.88; $19.99 × 12 − $199 = $40.88) and match `frontend/lib/pricing.ts` and `docs/PRICING.md`. The frontend pricing UI in `frontend/components/PricingTable.tsx` does that math; the Stripe-side amount stays the annual total.

**Webhook endpoint**: `https://api.tapeline.io/api/webhooks/stripe` — subscribe to:
- `checkout.session.completed` — links the Stripe customer_id back to the Tapeline user
- `customer.subscription.created` — initial paid subscription; also where the referral-credit consumer fires (see `backend/app/routers/webhooks.py:111`)
- `customer.subscription.updated` — tier changes, cancellation flags
- `customer.subscription.deleted` — drops the user back to Free
- `invoice.payment_succeeded` — optional, useful for renewal alerts later

The webhook handler is idempotent (logs every processed event_id in `stripe_webhook_events`), so Stripe's automatic redeliveries are safe.

**Set on Fly** (one command, triggers an automatic redeploy of api + worker):
```powershell
fly secrets set `
  STRIPE_SECRET_KEY="sk_live_..." `
  STRIPE_PUBLISHABLE_KEY="pk_live_..." `
  STRIPE_WEBHOOK_SECRET="whsec_..." `
  STRIPE_PRICE_PRO_MONTHLY="price_..." `
  STRIPE_PRICE_PRO_ANNUAL="price_..." `
  STRIPE_PRICE_PREMIUM_MONTHLY="price_..." `
  STRIPE_PRICE_PREMIUM_ANNUAL="price_..." `
  -a tapeline-backend
```
(Bash equivalent: replace each `` ` `` line-continuation with `\`.)

**Local dev**: paste the same values into `.env` instead.

**Local webhook testing**: `stripe listen --forward-to localhost:8000/api/webhooks/stripe` prints a temporary `whsec_...` you can use in `.env` for the duration of the CLI session.

**Rotating the webhook secret without the Stripe dashboard** (last done 2026-05-14 via Stripe REST API; dashboard.stripe.com is blocked from the Claude Code MCP, so this path is the fallback):

```bash
# 1. Grab the live API key from the running Fly machine
export STRIPE_KEY=$(fly ssh console -a tapeline-backend -C "printenv STRIPE_SECRET_KEY" | grep "^sk_")

# 2. Find the existing endpoint id (we_...) — current URL is https://api.tapeline.io/api/webhooks/stripe
curl -s -u "$STRIPE_KEY:" https://api.stripe.com/v1/webhook_endpoints

# 3. Create a NEW endpoint with the same 6 enabled events
NEW=$(curl -s -u "$STRIPE_KEY:" https://api.stripe.com/v1/webhook_endpoints \
  -d "url=https://api.tapeline.io/api/webhooks/stripe" \
  -d "enabled_events[]=checkout.session.completed" \
  -d "enabled_events[]=customer.subscription.created" \
  -d "enabled_events[]=customer.subscription.updated" \
  -d "enabled_events[]=customer.subscription.deleted" \
  -d "enabled_events[]=invoice.payment_succeeded" \
  -d "enabled_events[]=invoice.payment_failed" \
  --data-urlencode "description=Production billing events for tapeline.io")
NEW_ID=$(echo "$NEW" | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
NEW_SECRET=$(echo "$NEW" | python -c "import sys,json; print(json.load(sys.stdin)['secret'])")

# 4. Push new secret to Fly + force a redeploy so the machine picks it up
echo "$NEW_SECRET" | fly secrets set STRIPE_WEBHOOK_SECRET=- -a tapeline-backend --stage
fly secrets deploy -a tapeline-backend

# 5. Once the new machine is up (~30s), DELETE the old endpoint so Stripe stops
#    double-sending events to both endpoints. Old endpoint signatures wouldn't
#    verify against the new secret anyway — the handler is idempotent
#    (stripe_webhook_events table) so the brief overlap is harmless.
curl -s -X DELETE -u "$STRIPE_KEY:" https://api.stripe.com/v1/webhook_endpoints/<OLD_ID>
```

**Smoke test the referral coupon path** (post-wire):
1. Sign up two users; the second uses `https://tapeline.io/signup?ref=<code-from-first>`.
2. Confirm both `/app/referrals` pages show `Unused credit (months): 1`.
3. As either user, click **Upgrade** in `/app/billing`. The Stripe Checkout page should show a `100% off for 1 month` line item (the coupon `create_checkout_session` minted).
4. Complete the purchase with a real card. After `customer.subscription.created` fires, that user's credit drops to 0 and Stripe records the discount on the subscription.

Without all six secrets above, `POST /api/billing/checkout` returns `400 No Stripe Price ID configured for ...` — that's the canary that something is missing.

### Step 4 — Resend (Free tier OK, 5 minutes)

1. Sign up at https://resend.com
2. Verify the `tapeline.io` domain (DNS records)
3. Grab the API key
4. Paste into `.env`: `RESEND_API_KEY=re_...` and `EMAIL_FROM=alerts@tapeline.io`
5. Test: trigger a signup, the day-0 welcome email should arrive within 30s

The day-3 / day-7 / day-13 drip and trial-ended email all auto-fire from the
worker's daily task once Resend is live. No additional wiring needed.

### Step 5 — Telegram — FOUNDER notifications only (Free, 10 minutes)

**Telegram is not a customer feature.** It was retired as a customer alert
channel on 2026-08-11: `AlertRuleCreate.channel` in `backend/app/routers/alerts.py`
accepts only `email` / `web_push` (a `channel="telegram"` POST returns 422),
`services/alerts.py:_fire` has no Telegram arm, there is no Telegram card at
`/app/billing`, and the old hourly customer digest is gone from the worker.
Set the bot up only for the **founder-facing** uses: new-signup and
new-subscription pings, the weekly SEO-health digest, and the inbox Tier-1
Approve/Reject card.

1. DM `@BotFather` on Telegram, send `/newbot`, name it `TapelineBot`
2. Get the bot token
3. Paste into `.env`: `TELEGRAM_BOT_TOKEN=...`
4. Get your own numeric chat id (DM `@userinfobot`) and paste it as
   `INBOX_FOUNDER_TELEGRAM_CHAT_ID=...` — `services/telegram.py:deliver_founder_alert`
   needs **both** vars before it will use Telegram
5. Test: trigger a signup. The founder ping should arrive in Telegram within a
   few seconds. With either var unset, `deliver_founder_alert` silently falls
   back to email (Resend) instead — exactly one channel fires, never both

### Step 5a — Twilio SMS — RETIRED 2026-05-04 (re-enable path only)

**None of the steps below do anything as written.** SMS was retired on 2026-05-04: `alerts.sms` is no longer in `tier.py:FEATURES`, so the `/app/billing` SMS card does not render and no rule can fire on SMS. `services/sms.py` and the DB columns were deliberately kept, so re-enabling needs no migration — re-add `alerts.sms` to `tier.py:FEATURES` first, then follow the steps.

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

### Step 6 — Quiver QuantData — REMOVED (nothing to do)

The Quiver subscription was cancelled. `services/quiver_feed.py`, the `_refresh_elite_13f` worker task, the `InstitutionalHolding` model and the `quiver_api_key` setting are all deleted, so setting `QUIVER_API_KEY` activates nothing. The `institutional_holdings` table is left behind as a harmless orphan.

`/app/holdings` is now the **Recent insider buys** surface — SEC Form 4 transactions from Finnhub, refreshed daily. It needs only `FINNHUB_API_KEY`, which is already set. `/api/holdings/funds` is a legacy empty stub kept for frontend compatibility.

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

### Force-downgrade a user (manual override)

```sql
UPDATE users SET tier = 'free' WHERE email = 'user@example.com';
```

### Watch the worker logs

Look for these tick lines:
- `tick.done snapshots=N squeezes=N regime=X trades_added=N elapsed=Ns`
- `alerts.fired count=N` (when alert rules trigger)
- `insider.refreshed scored=N score_cache=N feed_size=N` (daily; SEC Form 4 via Finnhub)
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

### "A customer says their Telegram alerts stopped"

Nothing to fix — **there is no customer Telegram channel.** It was retired
2026-08-11. The hourly customer digest task is gone from the worker, no Telegram
dispatch arm remains in `services/alerts.py:_fire`, and `POST /api/alerts/rules`
with `channel="telegram"` now 422s at validation. The `telegram_chat_id` column
and the `telegram_alerts_per_day` cap in `tier.py` are leftovers with no
consumer. Point the customer at email (Pro+) or browser push instead.

### "Founder Telegram pings stopped"

1. Confirm `TELEGRAM_BOT_TOKEN` **and** `INBOX_FOUNDER_TELEGRAM_CHAT_ID` are both
   set — `deliver_founder_alert` needs both, and falls back to email if either
   is missing
2. Check `latest_run.log` for `telegram.skipped no_bot_token` or
   `telegram.send_failed`
3. If pings are arriving by email instead of Telegram, that IS the documented
   fallback — set the chat id to switch the route back

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

- **Six-factor scoring formula and weights** — the composite weighting is the moat, so don't retune it casually. **It is not public and must not be described as public:** PR #342 stripped the exact weights, the equation and the per-factor indicator recipe from the site. What IS published is the six factor *names*, what each measures, and their weight **ordering** ("most toward Trend and Relative Strength, least toward Momentum"). Never write "publishes its formula" or "published weights".
- **Descriptive signal labels** — never use "BUY", "ACCUMULATE", "WATCH" in any user-facing copy. Use the descriptive labels in `mock_feed.py:_signal_from_score`.
- **Public scorecard** — never gate it. It's the trust mechanism. Free users see it; paying users see the live data.
- **Owner login** — only created via `seed_owner.py`. Never expose admin promotion via the signup form.
- **Three-tier price points** — Pro $9.99/mo ($99/yr) / Premium $19.99/mo ($199/yr), founding pricing, locked in for early subscribers. Only revisit with conversion data.
- **The public record shows real product** — the daily Top 10, the full scorecard and every per-ticker page are live, real data, readable with no account and no card. Not a feature-stripped mock. (The signed-in app takes a card at first sign-in from 2026-08-22 — see docs/PRICING.md.)
- **Trial tier is Premium** — gives users the best, takes it away on expiry. Don't drop to Pro-trial without an A/B.

---

## INTERNAL_SSR_TOKEN — stop the backend rate-limiting its own frontend

**Status: code shipped, secret NOT yet set. The exemption is inert until you set it.**

### The problem

`limit_api` caps `/api/*` at 120 req/min **per client IP**. Server-side
rendering funnels every page render for the whole site through a *single* Fly
egress IP, so all of it shares one bucket. A ticker page fans out to ~3 upstream
calls, so roughly **40 cold page renders a minute drains the budget** — after
which the backend returns 429 to its own frontend, and
`frontend/app/t/[symbol]/page.tsx` turns that into an **HTTP 500**.

Any bulk crawl trips it:

* The weekly SEO digest reported **"1534 URLs returning non-2xx/3xx"** — URLs it
  had broken itself. Every one of them served 200 to a normal visitor minutes later.
* **Googlebot** walking the ~8,400-page ticker sitemap sees the same 500s, which
  is a deindexing risk on the site's biggest crawl surface.

(`main.py` already exempted `/api/embed/` for this identical one-shared-IP
reason; this closes the same gap for the SSR reads themselves.)

### Setting it

Generate once and set the **same value on both apps**:

```bash
TOKEN=$(openssl rand -base64 32)
fly secrets set INTERNAL_SSR_TOKEN="$TOKEN" -a tapeline-backend
fly secrets set INTERNAL_SSR_TOKEN="$TOKEN" -a tapeline-web
```

* **Never** name it `NEXT_PUBLIC_*` — Next inlines those into the browser bundle,
  which would hand every visitor a rate-limit bypass. It is read server-side only
  (`frontend/lib/ssrHeaders.ts` also hard-guards on `typeof window`).
* Rotate by setting a new value on the backend first, then the frontend; during
  the gap SSR is merely rate-limited again, never broken.
* Unset/mismatched ⇒ no exemption at all. The failure mode is today's behaviour,
  not an open door — verified by `backend/tests/test_ssr_rate_limit.py`.

### Verifying

```bash
# Should stay 200 well past 120 requests/min:
for i in $(seq 1 200); do
  curl -s -o /dev/null -w "%{http_code} " \
    -H "x-tapeline-internal: $TOKEN" https://api.tapeline.io/api/status
done
```

The other two halves of the fix (429-aware retry in the ticker page, and the
audit's re-check pass) work immediately on deploy and need no secret.
