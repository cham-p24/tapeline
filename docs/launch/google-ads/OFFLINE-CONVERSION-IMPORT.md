# Google Ads offline-conversion import — how to turn it on

*The code is built (2026-07-29). This is the founder-only setup: get the Google Ads API credentials, create/confirm the conversion action, drop 7 secrets into the backend, run once in dry-run, then go live. Until you do, the job runs in DRY-RUN and does nothing.*

## Why this matters (the one-line version)
Your paid conversion happens ~14+ days after the ad click (the free trial), off-session — so no browser pixel can see it. This job reports each paying subscriber's stored Google click id back to Google Ads with the first-charge value, so **Smart Bidding optimises on real payers instead of free-trial signups.** It's the single biggest bidding lever left. (See `PAID_ADS_PATHWAY.md` Step 1.4 and `CONVERSION-RUNBOOK.md` §2.4.)

## What's already built (you don't touch code)
- **Click-id capture:** `frontend/lib/utm.ts` stores `gclid/gbraid/wbraid` on landing; `backend/app/routers/auth.py` writes them to `users.signup_gclid/gbraid/wbraid` at signup.
- **The upload job:** `backend/app/scripts/upload_google_ads_conversions.py` — finds users with a click id + an `active` (paid) subscription that haven't been uploaded, and reports them. Idempotent (a new `users.ads_conversion_uploaded_at` column is the key — set once, never double-counts). Migration `0043_ads_conversion_upload`.
- **Value-based:** uploads the first-charge value ($9.99 / $99 / $19.99 / $199 by tier+period) so annual payers are weighted higher.

## Setup (do these once, in order)

### 1. Conversion action (Google Ads console — account 271-638-2397)
You already have the **Subscribe** conversion action (created 2026-06-06). Use it — you'll need its numeric **conversion action ID**:
- Goals → Conversions → click **Subscribe** → the ID is in the URL (`...conversionActions/**1234567890**`), or via Google Ads Editor.
- It must be an **"Import → from clicks/API"**-compatible action. The existing Subscribe action (Manual event, Primary, value = "use different values") works.

### 2. API access (Google Ads API)
- Apply for a **developer token**: Google Ads → Tools → API Center → request access (Basic access is enough). Approval can take a day or two.
- Create an **OAuth client** (Desktop app) in Google Cloud Console → APIs & Services → Credentials → note `client_id` + `client_secret`.
- Generate a **refresh token** for your Google Ads login: the official one-liner is `python -m google_ads.util.get_refresh_token` or follow https://developers.google.com/google-ads/api/docs/oauth/cloud-project (5 minutes).
- Note your **login customer ID** (the manager/MCC account, digits only, no dashes) and the **customer ID** (271-638-2397 → `2716382397`).

### 3. Set the 7 secrets on the backend (Fly)
```bash
fly secrets set -a tapeline-backend \
  GOOGLE_ADS_DEVELOPER_TOKEN=... \
  GOOGLE_ADS_CLIENT_ID=... \
  GOOGLE_ADS_CLIENT_SECRET=... \
  GOOGLE_ADS_REFRESH_TOKEN=... \
  GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890 \
  GOOGLE_ADS_CUSTOMER_ID=2716382397 \
  GOOGLE_ADS_CONVERSION_ACTION_ID=1234567890
```
Also install the optional dep where the job runs (it's excluded from the main image on purpose): `pip install 'tapeline-backend[ads]'` — on Fly this means adding `[ads]` to the image build, or running the job in a machine that has it.

### 4. Dry-run first (safe — uploads nothing)
```bash
fly ssh console -a tapeline-backend -C "python -m app.scripts.upload_google_ads_conversions --dry-run"
```
It prints exactly which conversions it *would* send. Confirm the users, values, and click ids look right.

### 5. Go live + schedule
```bash
# one live run
fly ssh console -a tapeline-backend -C "python -m app.scripts.upload_google_ads_conversions"
```
Then schedule it **daily** (conversions must land within the click's conversion window). Options:
- **Fly scheduled machine** (preferred — it has DB + creds already): a `fly machine run` on a daily schedule invoking the command above.
- A GitHub Actions cron is possible but would require the production `DATABASE_URL` as a CI secret — avoid unless you accept that exposure.

## How it behaves (so there are no surprises)
- **Idempotent:** each user is uploaded once; `ads_conversion_uploaded_at` guards against re-sending. Google also dedups on `order_id` (the Stripe subscription id).
- **Partial failure safe:** a bad row is skipped (logged), the rest still upload, and only accepted rows are marked — the skipped ones retry next run.
- **Conversion time** is the run time (job runs daily → within ~1 day of the real charge; well inside the conversion window). If you later want exact charge time, stamp a `first_paid_at` in the Stripe webhook and read it here — deliberately left out to keep the payment path untouched.
- **Value** mirrors `frontend/lib/pricing.ts`; update the `_PRICE_USD` map on any reprice.

## After it's running
- In Google Ads, the **Subscribe** conversion column will start counting the *paid* conversions (not just signups). Once you have **≥30 in 30 days**, switch the campaign bid strategy to **Target CPA on Subscribe** (`CONVERSION-RUNBOOK.md` §2.2) — that's when Smart Bidding starts finding payers for you.
