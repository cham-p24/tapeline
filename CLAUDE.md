# Tapeline

SaaS quantitative market scanner for retail stock pickers. Lives at `C:\Project 1\`. Built by a Melbourne-based founder. Pre-launch.

**Pitch:** "Every other scanner gives you 500 filters and a blank stare. Tapeline gives you one number, one sentence, and a public track record."

**Domain:** `tapeline.io` — **REGISTERED + LIVE** (Cloudflare DNS, Fly.io frontend `tapeline-web` serving `tapeline.io`, Fly.io backend at `api.tapeline.io`).

## Boundary — do not touch
The personal trading system at `C:\signal-system\` is a separate project. Tapeline does NOT share **files** with it (no imports, no symlinks, no cross-repo dependencies — never edit anything outside `C:\Project 1\`). **Tapeline DOES share data** with it via the signal-system's published Google Sheet ("Live Dashboard - Stocks"). The sheet is the bridge:

- signal-system writes to the sheet (scoring + ranking + per-ticker sub-scores for ~200-500 tickers)
- Tapeline reads `ALL SIGNALS` tab via `backend/app/services/sheet_feed.py` and upserts the universe into the `Ticker` table
- Configured via `SIGNAL_SHEET_CSV_URL` (Fly secret); dormant when unset (falls back to `mock_feed.TICKER_UNIVERSE`)
- 5-min refresh throttle (`SIGNAL_SHEET_REFRESH_SECONDS`)
- Sheet's prescriptive labels (BUY NOW / ACCUMULATE / HOLD / WATCH / AVOID) are NEVER passed through — `sheet_feed.score_to_signal()` re-derives Tapeline's descriptive labels (HIGH CONVICTION / STRONG SETUP / CONSTRUCTIVE / NEUTRAL / CAUTION / WEAK) from the composite score per the publisher-exemption posture

All four other tabs (SPIKE INTELLIGENCE, MARKET INTELLIGENCE, SMART MONEY & CONGRESS, ETF BENCHMARKS) are **already wired and ingesting in prod** (not "Phase 2 future" — that framing is stale). Each has a parser + upsert in `services/sheet_feed.py`, the worker calls all five every tick (`signal_publisher.py`), and all five `*_CSV_URL` secrets are set on Fly (each gated independently by its own URL). `refresh_all_tabs()` + the `/api/internal/sheet-changed` webhook drive the live-push path; per-tab column order is documented in each `parse_*_csv()`. (RUN HEALTH is deliberately not pulled.) **Caveat:** SMART MONEY only boosts `sub_smart_money` by per-ticker appearance count — the individual congress/insider/13F trades are read but NOT stored as structured rows; each tab also keeps only a subset of its columns.

## Operational facts
- **Git is live** at https://github.com/cham-p24/tapeline. **The frontend auto-deploys to Fly.io** (app `tapeline-web`, serving `tapeline.io` directly) via `.github/workflows/deploy-frontend.yml` on push to `main` touching `frontend/**` — **Vercel-independent since 2026-06-14** after a Vercel Hobby pause caused a multi-day outage; gated on the `FLY_WEB_API_TOKEN` secret with a post-deploy smoke check (fails hard if the token is missing). Vercel still builds PR previews via its git integration (you'll see a passing Vercel check on PRs), but no longer serves production `tapeline.io` — `frontend/vercel.json` only configures those previews now. **Backend auto-deploys to Fly.io** via `.github/workflows/deploy-backend.yml` on merge to `main` (ruff + mypy + pytest gate, then `flyctl deploy --remote-only`, which runs the `alembic upgrade head` release command) — but **only once the `FLY_API_TOKEN` repo secret is set** (`fly tokens create deploy -a tapeline-backend`). Until then that workflow runs green but *skips* the deploy, so backend deploys stay manual (`fly deploy` from `C:\Project 1`). Use normal commit/push flow.
- **No Docker required for dev.** Run `.\scripts\run_nodocker.ps1` from project root. Uses SQLite, opens browser to `http://localhost:3000`.
- **Owner login** (already seeded): `owner@tapeline.io` / `TapelineOwner!2026` — premium tier, admin. Re-seed via `python -m app.scripts.seed_owner` from `backend/` (idempotent; reads `OWNER_EMAIL` / `OWNER_PASSWORD` env vars).
- **Dev auth bypass:** `Authorization: Bearer dev-bypass` returns a premium token, but the gate (`auth.py:142`) only fires when `settings.app_env == "development"`. Production has `APP_ENV=production` set in `fly.toml`, so the bypass is inert in prod — verified live: `/api/me` with the bypass token returns `authenticated: false` against api.tapeline.io.
- **Today's date for relative refs:** see system date.

## Stack
FastAPI + SQLAlchemy + Alembic (Python 3.12) backend. Next.js 16 + TypeScript + Tailwind frontend. SQLite dev / Postgres prod (Supabase or Neon). SSE for live updates. Native cookie-JWT auth (built) + Clerk + Google/Microsoft OAuth (env-gated). Stripe billing (env-gated). Resend email (env-gated). Hosting: Fly.io backend + Fly.io frontend (both on Fly since the 2026-06-14 Vercel migration).

## Worker
Single scoring worker at `backend/app/workers/signal_publisher.py`. Default tick = **60s** (`SCORE_REFRESH_SECONDS` in `.env.example`). Dev script overrides to 10s for faster iteration. Also: ~5min news refresh, daily scorecard back-check, daily EOD watchlist email digest, on-boot universe + calendar seed. (There is **no** Telegram digest for customers — that task is gone; see Notification channels.)

## Tier model — canonical source: `backend/app/services/tier.py`
**Three tiers** (decided 2026-04-26, Free hardened 2026-04-27, annual charm-priced 2026-05-03, founding reprice 2026-07-03):
- **Free** $0 — **top-10 scanner rows, LIVE (no delay)**, 12 ticker-detail lookups/UTC day, watchlist (5 tickers, 1 list), 2 web-push alert rules; no email alerts, no CSV, no API. The old "top 20, 24-hour delayed" framing is **dead** — the 2026-06-20 freemium retune set `FREE_DATA_DELAY_MINUTES = 0` and `FREE_SCANNER_ROWS = 10`, so conversion pressure comes from breadth + the lookup meter, not stale data. The Free watchlist survives: the 2026-08-02 cutover to 0 was **reversed 2026-08-19** (#525) and `free_watchlist_cap()` now returns 5 unconditionally. **Reaching this tier now takes a card:** since 2026-08-22 a NEW account hits the `/app/start` card wall before it can use the logged-in product — see the card gate below. Accounts created before that date are grandfathered forever.
- **Pro** $9.99/mo OR **$8.25/mo billed annually** ($99/yr · save $20) — full universe live, squeeze + regime + heatmap, watchlist (50), email alerts (10/day), CSV, browser push
- **Premium** $19.99/mo OR **$16.58/mo billed annually** ($199/yr · save $40) — everything in Pro + Congressional trades, **Recent insider buys (SEC Form 4)**, email unlimited, watchlist 200, saved scans 100, priority support. (**Public API SHIPPED 2026-06-01, PR #247** — live at `/api/v1` with API-key auth + `api_requests_per_day=1000` daily quota from `tier.py:TIER_LIMITS`; key-management UI at `/app/api-keys`, backend in `routers/{api_v1,api_keys}.py` + `services/api_keys.py`, table via migration `0032_api_keys`. Marketing is now surfaced: `ComparisonTable.tsx` + `PricingTable.tsx` both show the "Public API access · 1,000 requests/day" Premium line, and a public `/developers` landing page (2026-06-06) documents the live endpoints — added to the sitemap + footer, with a tailored OG card.)

**⚠️ OPEN-ACCESS MONTH — RUNNING NOW, AUTO-REVERTS 2026-09-08** (`tier.py:PROMO_OPEN_ACCESS_UNTIL` + `free_open_access()`). The Free bullet above is the **post-promo steady state**, not what a signed-in Free user gets today. Founder experiment (2026-08-08, at 0 payers with users who activate but don't convert): while the window is open, **`scanner_rows` and nothing else** lifts for Free from 10 → Pro's **1,000**. Last open day is 2026-09-07; the revert needs no deploy.

The lift is deliberately narrow, and `backend/tests/test_open_access_month.py` asserts every exclusion:
- **Signed-in accounts only.** Anonymous callers score against the FREE table too, so `limit()` takes an `authenticated` flag — logged-out visitors keep the standard top-10. The lift is the reward for having an account, since the promo exists to drive signups (and it keeps the scanner's anonymous offset-walk guard closed).
- **NOT lifted:** `daily_lookups` (still 12/day — the look-up meter's cap-hit and stale-read guards depend on it), `watchlist_tickers` (still 5), `web_push_alerts` (still 2).
- **No Pro features unlock.** `has_feature()` is untouched: CSV, squeeze, heatmap, regime, congress and the public API all stay gated. This is a numeric cap lift, not "Free becomes Pro".

**Copy rule while it runs:** "Upgrade to unlock the full scanner" is **false** for a signed-in Free user today, and true again on 2026-09-08 — sell only what Pro/Premium genuinely add on top. `services/email.py` already branches on `free_open_access()` for exactly this reason.

**Two stale sources here — trust the `limit()` body and the test file over both:** (a) `tier.py` says to keep a matching `PROMO_OPEN_ACCESS_UNTIL` in `frontend/lib/pricing.ts`, but **there isn't one** — `FREE_LIMITS.scannerRows` is hard-coded to 10, so frontend Free-tier copy currently understates the live cap; (b) the `free_open_access()` docstring still describes the original "caps + every Pro feature" plan, which the implementation never did.

**Retired customer alert channels:** Discord webhook + Twilio SMS (2026-05-04), and **Telegram (2026-08-11)**. Discord/SMS: service files at `services/{discord,sms}.py` and DB columns left in place; re-enable by re-adding `alerts.discord` / `alerts.sms` to `tier.py:FEATURES`. **Telegram went further** — `AlertRuleCreate.channel` in `routers/alerts.py` is now `Field("email", pattern="^(email|web_push)$")`, so a `channel="telegram"` POST 422s, and `services/alerts.py:_fire` has no Telegram dispatch arm at all (regression guard: `backend/tests/test_free_alert_taste.py::test_free_user_blocked_from_email_and_telegram_channel_retired`). `tier.py` still carries a vestigial `telegram_alerts_per_day` cap with **no consumer** — do not read it as evidence the channel is live. **Never write customer-facing Telegram copy** (no "Telegram alerts", no "unlimited Telegram", no "paste your chat ID"). Telegram remains live for FOUNDER-facing notifications only — see Notification channels.

Anchor offerings (custom-sold; all map to `premium` in the DB): **Team** $149/mo for 5 seats, **Enterprise** custom from $2k/mo, **Founder's Lifetime** $399 once for first 100.

**Trial + card gate — read this before writing ANY copy.** Two dated changes stack here. Get both or the copy is false.

**1. Signup still stamps no trial** (PR #536). Creating an account is email + password; the row is written `tier="free", trial_ends_at=None` — see the "NO trial is granted here" block in `backend/app/routers/auth.py`. Nothing grants a trial at signup, ever.

**2. Since `CARD_GATE_START = 2026-08-22` a NEW account must put a card on file before it can use the logged-in product** (PR #548). A new signup meets a card wall at `/app/start`: Stripe Checkout, $0 today, 14-day trial, first charge at trial end, one click to cancel. `tier.must_add_card(user)` is the single predicate every surface reads (exposed on `/api/me` and on `/api/auth/session` via `_user_out`). It returns True only when ALL of: account `created_at >= CARD_GATE_START`, no `stripe_customer_id`, `trial_started_at is None`, and not admin / lifetime / hand-comped pro-premium. It **fails open** on an unknown `created_at`.

  - **Grandfathering is load-bearing, not a knob.** The gate compares the ACCOUNT's own creation date to the cutover — never "is this user currently free". Every account created before 2026-08-22 signed up under "free, no card" and keeps that deal permanently. Do not simplify the `created_at` comparison away, and do not move the date backwards over existing accounts.
  - **The public surface stays open with no account and no card**: `/scorecard`, `/daily-picks`, the record CSV/JSON exports, per-ticker pages, marketing pages and the public API. Anonymous callers have no `User` row, so the predicate never runs for them. That is what keeps "read the record before you decide anything" true, and it is the escape hatch offered at the wall itself.
  - **Known limit, stated plainly:** the gate is a UX boundary, not a security boundary — `/api/*` is not hard-gated, so a signed-in gated account calling the API directly still gets normal free-tier service.

The 14-day **Premium** trial is a separate, explicitly-chosen, **card-required** step: `POST /api/billing/checkout {"start_trial": true}` opens a Stripe Checkout that collects a card, charges **$0 today**, and states the exact first-charge date. It's gated on never-having-trialled, and returns `trial_end` + `trial_days` so the confirmation UI restates the same instant Stripe was given. `tier` / `trial_ends_at` / `trial_started_at` are written by the `trialing` subscription webhook in `backend/app/routers/webhooks.py` from the subscription's own `trial_end` — never at signup. Declining the checkout leaves the account exactly as created.

**Never write "14-day trial, no credit card" in marketing, ad, or email copy — and since 2026-08-22, never call a NEW ACCOUNT card-free either.** This is a financial product; both claims would be false advertising. What is still true and safe to say: the **public record** (scorecard, daily picks, exports, ticker pages, API) needs no account and no card. What is now false: "free account, no card to sign up", for anyone signing up today. PR #548 rewrote 47 such claims across 30 files — pricing, 13 comparison pages, listicles, blog, `llms.txt`, the inbox/newsletter templates that reply to strangers, and live Google Ads RSA copy. `/free-stock-scanner-no-credit-card` was **rewritten, not deleted** — it kept a true story about the public record. Tapeline's own comparison-table row now reads "Card to sign in".

The CARD HONESTY block in `frontend/app/signup/page.tsx` remains the canonical statement of the trial half of the rule. `TrialBanner.tsx` branches on card-on-file (first charge lands at trial end, one click cancels before then) vs the legacy card-free trial (nothing charged, the account just moves to Free) — never mix the two.

The hourly `_downgrade_expired_trials` worker task still drops expired-trial users with no `stripe_customer_id` straight to `free` (skipping the Pro middle so loss aversion bites hardest) — but it is now a **legacy safety net** for the old auto-granted trials, since a card-required trial always has a `stripe_customer_id` and lapses through Stripe instead.

## Pricing source-of-truth (all kept in sync as of 2026-05-03)
- `backend/app/services/tier.py` — feature gating + caps (no $ amounts here)
- `frontend/components/PricingTable.tsx` — pricing UI on /pricing landing
- `frontend/components/ComparisonTable.tsx` — feature comparison table (used on /pricing AND /app/billing)
- `frontend/app/app/billing/page.tsx` — in-app upgrade flow with embedded ComparisonTable
- `docs/PRICING.md` — narrative + unit economics
- `docs/OPERATIONS.md` — Stripe Price ID setup steps

## Signal labels — do not change (legal posture)
Descriptive, NOT prescriptive — protects the publisher's exemption.
- `HIGH CONVICTION` (85–100) — was "BUY NOW"
- `STRONG SETUP` (70–84) — was "STRONG ACCUMULATE"
- `CONSTRUCTIVE` (55–69) — was "ACCUMULATE"
- `NEUTRAL` (40–54) — was "HOLD"
- `CAUTION` (25–39) — was "WATCH"
- `WEAK` (0–24) — was "AVOID"

## Scoring formula — do not change (the composite weighting is the moat)
Internal computation (do not change the weights without a `/changelog` entry):
```
score = 0.25*trend + 0.20*relative_strength + 0.15*fundamentals
      + 0.15*smart_money + 0.15*macro + 0.10*momentum
```
**NOT published publicly.** PR #342 deliberately stripped the exact weights, the
scoring equation, and the per-factor indicator/parameter recipe (MACD, Bollinger,
RSI, moving averages, Piotroski) from the public site. The public methodology
(`/how-it-works` + the six `/how-it-works/{factor}` pages) names the six factors
and their weight **ordering** ("weighted most toward Trend + RS, least toward
Momentum") only — never the numbers. Guarded by
`frontend/__tests__/methodologyPages.test.ts` (the "disclosure boundary" suite).
The transparency that's public is the factor *set + ordering + what each measures*,
which is enough to justify the descriptive-only posture without handing over a
cloneable recipe. Keep it that way — marketing copy must not claim the exact
weights are published.

## Mock-to-real data switch
**Production runs on real data.** The worker imports `app.services.polygon_feed` (Massive-backed). `mock_feed` only fires when no `MASSIVE_API_KEY` / `POLYGON_API_KEY` is set (dev fallback). The adapter file is still named `polygon_feed.py` because Polygon.io rebranded to Massive on 2025-10-30 — same API, same auth, same endpoint shapes, only the hostname changed (`api.polygon.io` → `api.massive.com`). Massive accepts both `MASSIVE_API_KEY` and the legacy `POLYGON_API_KEY` env vars.

**Vendor-key gating gotcha (fixed 2026-05-03):** several services originally checked only `settings.polygon_api_key`. With `MASSIVE_API_KEY` set they fell through to mock. Fixed in `news_feed.py` (per-ticker headlines were duplicate-Barrons mock entries), `signal_publisher._refresh_universe` (weekly IPO / ETF discovery never ran). When adding new vendor-key gates, **always check both** — see `polygon_feed._api_key()` for the canonical pattern.

## Universe + commodities
Mock universe is 112 tickers (80 equities + 32 commodity ETFs). Commodity ETFs added 2026-04-26 with sector="Commodities" — gold, silver, oil, gas, ag, copper, uranium, miners. Polygon Starter doesn't include futures contracts, so commodity exposure is via ETFs only.

**Auto-discovery IS wired** (`polygon_feed.discover_active_us_tickers`, called weekly + on boot by `signal_publisher._refresh_universe`) — the "post-launch, not wired yet" framing here was stale. Two defects in it were fixed 2026-08-28 (PRs #654, #658) after a sweep of all 2,463 live tickers; both are easy to reintroduce, so:

- **`max_tickers` is a runaway guard, NOT a sizing knob.** The cap counts ACCEPTED rows and the vendor returns tickers in ascending symbol order, so any cap that binds truncates the universe **alphabetically**. At the old default of 5,000 the walk stopped around letter H/I: the live universe held 750 A-tickers, 626 B, 671 C — and exactly **one** E-ticker. `DISCOVERY_MAX_TICKERS` is now 25,000 (13,148 active US tickers exist, ~11,400 of scoreable types) and a binding cap logs at ERROR.
- **`VENDOR_TYPE_TO_ASSET_CLASS` is the type filter.** It was `("CS", "ETF")`, which silently dropped **ADRC** (376 — every US-listed foreign company; Massive types **ASML as ADRC**) and **ETV** (90 — GLD/SLV/USO, i.e. the whole Commodities sector). Now CS/ADRC → equity, ETF/ETV/ETS/ETN → etf. PFD/WARRANT/RIGHT/UNIT/SP/FUND stay **out on purpose** — a trend read on a warrant is noise, and CEFs trade at NAV premiums/discounts. Don't "simplify" the map back to a tuple.
- **`_refresh_universe` reconciles, it is not insert-only.** It corrects `asset_class` whenever the vendor disagrees and fills `name` only when ours is a placeholder (`_is_placeholder_name` — an EXACT symbol match, never a prefix, or it would eat real names like "AAPL Corp"). It must never write `sector`: discovery always reports "Unknown" and would erase `_backfill_sectors`' work.
- `_backfill_sectors` also repairs placeholder names off the profile call it already makes; SPY's key stats come from the benchmark bars (it's excluded from the per-symbol loop, which is also where 52w range + avg volume are derived).

## Vendor API key — header only, never a URL
`polygon_feed.auth_headers()` sends `Authorization: Bearer <key>`. **Never put the key in a query string.** httpx logs full request URLs at INFO, `main.py` sets INFO globally, and `HTTPStatusError` embeds the URL — so a query-param key reaches logs, stack traces and Sentry on every call. On 2026-08-27 it reached **world-readable GitHub Actions logs on this PUBLIC repo, 1,086 times**, via the `rederive-scorecard` workflow that streams worker stdout. GitHub masks GitHub secrets; this one lives in Fly, so nothing masked it. **The founder was told and decided on 2026-08-28 NOT to rotate** — the exposed key stays in use. That is a deliberate accepted risk, not an oversight: do not re-raise it every session. The fix here only stops FUTURE leaks; the four `rederive-scorecard` runs listed above still hold the key in world-readable logs and cannot be un-published. If the key is ever rotated later, nothing in the code needs to change (it reads `MASSIVE_API_KEY` / `POLYGON_API_KEY` either way). Guard: `backend/tests/test_vendor_key_never_in_urls.py` (strips docstrings as well as comments, because the docstring explaining the fix contains the banned string).

## Bot / abuse protection — `backend/app/services/bot_protection.py`
Three application-level layers (Cloudflare Bot Fight Mode is the recommended free baseline once domain is proxied):
1. **Honeypot field** — invisible `company` input on signup form. Bots fill it; humans don't see it. Tripped → fake-success response (no account created, no session cookie).
2. **Disposable-email block** — built-in set of ~62 throwaway providers (mailinator, guerrillamail, tempmail, etc.). Rejected with 400.
3. **Cloudflare Turnstile** — env-gated. `CLOUDFLARE_TURNSTILE_SITE_KEY` + `CLOUDFLARE_TURNSTILE_SECRET_KEY`. Pass-through when unset (dev), enforced when set.

Rate limit: `services/rate_limit.py` `limit_auth` caps `/api/auth/*` at 10 attempts per IP per minute (vs default 120 for /api/*).

## Sign-in codes (new-device second factor) — `backend/app/services/signin_codes.py`
Password sign-in from an **unrecognised browser** does NOT mint a session: it emails a 6-digit code and returns the same `{mfa_required, mfa_token}` challenge the TOTP flow uses, plus `method: "email"` and a masked `email_hint`. `POST /api/auth/2fa` accepts that code, mints the session, and sets a signed 30-day **trusted-device cookie** (`tapeline_device`) — so routine logins from a known browser stay a plain password step.

- **Deliberately new-device-only, not every sign-in.** Requiring a code every time would make Resend a hard dependency of logging in at all, so a mail outage would lock out every user (founder included). Decided 2026-08-19.
- **TOTP keeps precedence** — an account with an authenticator app never gets an emailed code, and the TOTP/recovery-code path in `/2fa` is untouched.
- **Codes** are 6 digits, 10-minute TTL, single-use (burned with a conditional UPDATE so a replay can't mint a second session), stored as a keyed HMAC-SHA256 bound to the user id — never plaintext. Table `signin_codes`, migration 0052.
- **The trust cookie carries `session_epoch`**, so sign-out-everywhere / password reset revoke every remembered device for free.
- **Two caps**: issuance is capped per ACCOUNT (`signin_code:{user_id}`, 5 per 15 min) so /signin can't be used to mail-bomb someone; verification reuses the existing per-account `2fa:{user_id}` budget.
- **OAuth sign-in is not gated** — Google/Microsoft run their own device checks and never hit `/api/auth/signin`.
- Tests: `backend/tests/test_signin_email_codes.py`.

## News + analyst ratings
- **News** — `news_feed.py` queries Massive/Polygon and Finnhub in parallel,
  merges by `published_at desc`, dedupes by id. SEC EDGAR 8-Ks are fed into
  the same news table by the worker. Per-ticker headlines + the live news bar
  read from this combined feed.
- **Analyst ratings** — `finnhub_feed.fetch_analyst_ratings(symbol)` returns a
  consensus tally (Buy/Hold/Sell) and total from Finnhub's aggregate
  `/stock/recommendation` endpoint. Endpoint `/api/ticker/{symbol}/ratings`,
  lazy-loaded by the `<AnalystRatings>` widget on the ticker page. Cached 12h
  per symbol. Finnhub's free tier exposes only the aggregate, so per-firm
  events + avg price target are empty. **Not factored into the 6-factor
  score** — displayed alongside it as a complement.

Without coverage the ratings widget renders a "No analyst coverage" empty state.

## Smart-money / Recent insider buys
**Marketing pivot 2026-05-17 (PR #74).** Premium no longer promises "Elite 13F holdings" — that copy was stripped across 15 frontend files (PricingTable, ComparisonTable, JSON-LD, llms.txt, OG image, blog, how-it-works, roadmap, share pages, ScannerPreview, etc.). The driver was Quiver Trader-tier TOS: "No Commercial Use Rights" (see `docs/LICENSE_AUDIT.md`). Premium's smart-money surface is now **Recent insider buys** — SEC Form 4 transactions across the active universe via Finnhub, refreshed daily.

What's live now:
- `/app/holdings` page renders Form 4 buys/sales with date / insider / shares / price / value columns. Same `holdings.elite` Premium feature gate (kept for migration simplicity — name is stale but the gate works).
- `/api/holdings` returns Form 4 transactions from `get_recent_insider_transactions_db()` (Finnhub-backed). The legacy `/api/holdings/funds` endpoint exists for frontend compatibility but returns `{"items": []}` — the "elite funds" concept is off-roadmap.

Quiver 13F removed (subscription cancelled — never wired in production, so the
feature only ever served mock data):
- `services/quiver_feed.py`, the `_refresh_elite_13f` worker task, the
  `InstitutionalHolding` model, and `quiver_api_key` are all deleted. The
  `institutional_holdings` DB table is left as a harmless orphan (no migration —
  CI asserts a single migration head).
- `holdings.elite` feature flag + `/app/holdings` + `/api/holdings` are KEPT —
  they now gate/serve the Finnhub Form 4 "Recent insider buys" feed, not Quiver.
- `Paywall.tsx` labels `holdings.elite` as "Recent insider activity".

## Known issues / partially-built
- **`rate_direction` is now live from FRED** — `polygon_feed.fetch_regime` reads the 10Y yield's last 30 obs from FRED and classifies RISING / FALLING / SIDEWAYS via `fred_feed._direction()` (0.5 % threshold). Falls back to SIDEWAYS without a FRED key. Breadth_pct still placeholder; sector_leaders computed live each tick.
- **Finnhub fundamentals not yet wired into per-tick `sub_fundamentals`** — `services/finnhub_feed.py` has `fetch_basic_financials()` + `compute_fundamentals_score()` working live (verified AAPL scored 79.1/100). Calendars (IPO + earnings) already use Finnhub when configured. To wire fundamentals into the score: pre-fetch all 870 tickers weekly, cache results, have `polygon_feed.fetch_snapshots` read from cache instead of generating random.
- **Sector backfill is wired** — `signal_publisher._backfill_sectors` runs daily via `_serial_finnhub_refreshes`, queries `Ticker.sector IN (NULL, "Unknown")`, hits Finnhub `/stock/profile2` per symbol at 1.1s/call, caps at 200/day to stay under the free-tier budget. Auto-discovered tickers get their real sector within 24h.
- **`pywebpush` is now in `pyproject.toml`** (>=2.0.1). Web push send works as soon as VAPID env vars are set.
- **Frontend tests cover ~6 surfaces** — Paywall, PricingTable, SignupForm honeypot, ScannerPreview labels, BillingToggle, HoldingsPage. Grow with billing flow + alerts CRUD + scanner page next.
- **Playwright E2E scaffold lives at `frontend/e2e/`** — 3 spec files covering landing, pricing, and auth-form rendering. To run locally:
  ```powershell
  cd frontend
  npm install              # picks up @playwright/test from package.json
  npm run e2e:install      # downloads chromium binary (~150MB, one-off)
  npm run e2e              # runs all tests headless
  npm run e2e:ui           # opens Playwright UI for debugging
  ```
  Add `firefox` and `webkit` projects in `playwright.config.ts` when ready for cross-browser coverage. Tests boot Next.js automatically via the `webServer` block; backend isn't required (UI-rendering tests, no API hits).

## Notification channels
**Two** live delivery channels for alerts — `AlertRuleCreate.channel` in `backend/app/routers/alerts.py` accepts nothing else (`pattern="^(email|web_push)$"`), and `backend/app/services/alerts.py:_fire` has arms for exactly these two:
- **Email** (Pro+) — Resend, no extra cost. Default channel for every rule. Always on.
- **Browser push / Web Push** — VAPID + Service Worker (`frontend/public/sw.js`). Free to deliver. The one channel a **Free** user gets a taste of: `alerts.web_push` is `Tier.FREE` and the allowance is a COUNT cap (Free = 2 rules, paid tiers effectively uncapped at 10,000), enforced at rule creation. One-click enable on Chrome/Firefox/Edge desktop + Android. iOS requires PWA install.

**Retired:** Discord webhook + Twilio SMS (2026-05-04), and **Telegram as a customer alert channel (2026-08-11)**. Discord setup friction was a real conversion blocker; SMS unit economics didn't work at low volume. `services/{discord,sms}.py` + DB columns retained — re-add `alerts.discord` / `alerts.sms` to `tier.py:FEATURES` to bring them back without a migration. Telegram is rejected at validation (a `channel="telegram"` POST 422s) and has no dispatch arm; the old hourly customer Telegram digest is gone from the worker, and there is no Telegram card at `/app/billing`. The leftover `telegram_alerts_per_day` cap in `tier.py` has no consumer.

**Telegram IS still live — but FOUNDER-facing only, never a customer feature.** `backend/app/services/telegram.py` + `backend/app/routers/telegram.py` back `notify_founder_new_signup`, `notify_founder_new_subscription`, the weekly SEO-health digest, and the inbox Tier-1 approval bot (inline Approve/Reject buttons). `TELEGRAM_BOT_TOKEN` + `INBOX_FOUNDER_TELEGRAM_CHAT_ID` exist for those. Don't delete them, and don't market them.

End-of-day watchlist email digest fires daily ~21:00 UTC for every Pro+ user with watchlist items (`services/email.py:run_eod_watchlist_digest`).

## Inbox auto-handler bot
Server-side bot that triages inbound messages across Reddit, email, and Telegram into Tier 1 / 2 / 3. Tier 2 auto-replies via deterministic templates (ticker_score / pricing / trial / thanks). Tier 1 gets the real Anthropic Claude classifier + a drafted reply, then routes to the founder's Telegram for inline-button approval. Tier 1.5 fires an immediate "I'll get back within 24h" auto-ack so US-business-hours senders aren't ghosted overnight while the Melbourne founder is asleep.

**Architecture (after the LLM + Reddit + safety-nets port, 2026-05-24):**
- **Classifier** (`services/inbox_classifier.py`) — rule-based fast path catches ~70% of obvious cases. Ambiguous messages hit the real Anthropic Claude API (default `claude-haiku-4-5`, override via `INBOX_CLAUDE_MODEL`). Prompt-cached system block. Every LLM call logs to `inbox_classification_log` table (cost + latency + tier audit). `classify_async()` is the async entry; `classify()` kept as a sync compatibility wrapper.
- **Kill switches** (`services/inbox_kill_switch.py`) — `bot_enabled()` / `dry_run()` / `channel_enabled(channel)` / `cap_exceeded(session)`. Backed by env vars. `spend_today()` SUMs today's classification cost with 60s in-process cache.
- **Router** (`services/inbox_router.py`) — `handle_inbound()` is the canonical dispatcher used by every channel. Status state machine: `new → classified → [approved | auto_replied | ignored] → sent`. `send_tier_1_5_ack()` fires the immediate "within 24h" reply on the inbound channel for Tier 1.
- **Tier 2 templates** (`services/inbox_templates.py`) — async renderers for ticker_score (HTTP call to live API), pricing, trial, thanks. Voice-rule-locked: never "buy"/"sell"/"you should"/"recommend"; unsigned.
- **Tier 1 alerts** (`services/inbox_telegram_alert.py`) — formatted card to `INBOX_FOUNDER_TELEGRAM_CHAT_ID` with inline keyboard (Approve / Reject buttons + "Edit in browser" deep-link). Callback handler in `routers/inbox.py` processes the button taps.
- **Channel adapters:**
  * **Email** (`routers/inbox.py:POST /api/inbox/email`) — Resend inbound webhook, Svix-signed against `RESEND_INBOUND_SECRET`. Fail-closed when secret unset.
  * **Reddit** (`services/reddit_inbox.py`) — PRAW poller for DMs + comment-replies on own posts + finance-sub mentions (r/wallstreetbets, r/stocks, r/investing, r/SecurityAnalysis, r/ValueInvesting by default). Reply-loop guards (`_is_self_authored`, `_is_parent_self_authored`) prevent infinite ping-pong. New-account throttle caps replies at 3/day when account < `REDDIT_NEW_ACCOUNT_THROTTLE_DAYS` days old. Wrapped in `asyncio.to_thread` so PRAW's sync calls don't block the event loop.
  * **Telegram** (existing webhook in `routers/telegram.py` + `inbox_telegram_alert` callback handler) — strangers messaging the bot get classified; founder approval flow uses inline-button callbacks.
- **Worker integration** — `signal_publisher.tick()` calls `_run_inbox_tick()` every 5 min during US market hours, 15 min off-hours. Currently only polls Reddit; email + Telegram are webhook-driven.

**Kill switches** (all `INBOX_*` env vars, default on):
- `INBOX_BOT_ENABLED=false` — master pause; classify + send both skip
- `INBOX_DRY_RUN=true` — full pipeline runs but adapter calls log instead of sending
- `INBOX_<CHANNEL>_ENABLED=false` — per-channel kill (reddit/email/telegram)
- `INBOX_CLAUDE_DAILY_CAP_USD=5.0` — daily LLM spend cap (default $5/day ≈ 7.5K Haiku classifications); once tripped, ambiguous messages default to Tier 1 manual review until UTC midnight
- `INBOX_TIER1_AUTO_ACK=false` — disable the immediate Tier 1.5 auto-ack

**Required secrets to actually run** (none currently set on Fly):
- `ANTHROPIC_API_KEY` — without it, every ambiguous message defaults to Tier 1
- `INBOX_FOUNDER_TELEGRAM_CHAT_ID` — founder's chat_id for Tier 1 alerts (DM `@userinfobot` to find)
- `RESEND_INBOUND_SECRET` — Resend dashboard, plus MX records for `inbound@tapeline.io` → Resend
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USERNAME` / `REDDIT_PASSWORD` — script-tier app at https://www.reddit.com/prefs/apps (use an aged Reddit account to dodge new-account anti-spam triggers)

**Voice rules (legal-critical):** descriptive language only — never "buy"/"sell"/"you should"/"recommend". Australian publisher exemption from AFSL depends on this. `tests/test_inbox_voice_rules.py` is the regression guard.

**Observability:** `GET /api/inbox/stats` (admin-only) returns today's classification spend, cap-tripped flag, tier/channel/status counts, p50/p95 latency, cache hit ratio, pending queue depth, and the live bot_enabled / dry_run state. Surfaced as a chip strip + cap-tripped / dry-run banners at the top of `/app/inbox` (polled every 30s).

**Test coverage:** 97 inbox-specific tests across `test_inbox_*.py` (classifier rule-based + LLM, kill switch, voice rules, router, reddit poller, the founder Telegram approval card, stats endpoint).

## Per-ticker confidence
Each Ticker row carries a `confidence_pct` (0-100) that varies with which underlying data feeds returned data for that symbol. Mega-caps with full Quiver/Finnhub/FINRA coverage land 88-96, ETFs without traditional fundamentals land 45-70, the typical liquid stock lands 60-85. Surfaced as a column on the scanner table + as an inline pill on the ticker page. Documented on `/how-it-works`. Pattern ported from the personal signal-system. Mock value via `mock_feed._compute_mock_confidence(symbol)` (deterministic per symbol). Real polygon_feed should compute from actual data-feed presence.

## Webhook idempotency
`stripe_webhook_events` table logs every processed event id. Replay attacks and Stripe redeliveries return `{ok: true, replay: true}` instead of double-processing. Migration 0010.

## Tests
Backend: 8 smoke tests at `backend/tests/test_smoke.py`, pytest config at `backend/pytest.ini`. Run: `pytest` from `backend/`. Frontend: no tests.

## Things NOT to change without thinking
- 6-factor scoring formula and weights
- Descriptive (not prescriptive) signal labels
- **The scorecard is measured CLOSE-TO-CLOSE.** `price_at_flag` reads
  `Ticker.day_close` (`session["close"]`, migration 0059), falling back to
  `Ticker.price` only when the vendor gave no close. Do not "simplify" it back
  to `price`: `price` is `session["price"]` — the last trade INCLUDING extended
  hours — and the freeze runs at 21:15 UTC = 17:15 ET, inside after-hours. That
  was the bug (PR #643): 34% of frozen rows sat 2-18% off the real close, and
  since `spy_change_pct_1d` comes from SPY's daily-bar closes, the published
  alpha subtracted a close-to-close move from an after-hours-to-close move.
  `backend/app/scripts/rederive_scorecard.py` repairs already-published rows by
  rebasing BOTH legs; run it via the `rederive-scorecard.yml` workflow, which
  slices the ~2.5h pass so a dropped ssh session can't half-rewrite the record.
- Public scorecard SUMMARY from day 1 (the trust mechanism). Per-day picks
  are gated since 2026-05-18: anonymous + Free see picks delayed 7 days,
  Pro + Premium see live. Summary stats (hit rate, median alpha, days
  tracked) stay live for everyone so the JSON-LD Dataset markup and
  marketing trust signal don't degrade. Gate lives in
  `backend/app/routers/scorecard.py` (`_FREE_DELAY_DAYS`).
- Three-tier price points (founding pricing 2026-07: $9.99 Pro / $19.99 Premium, framed "locked in for early subscribers"; 30-day money back) — only revisit with conversion data
- Free tier shows the real product, LIVE — not a feature-stripped version, and not a delayed one (the 24h delay cliff went 2026-06-20; the Free caps are row count, lookups/day, and watchlist size)
- Owner login mechanism (only seeded via `seed_owner.py`, never via signup form)

## Critical file map
- `backend/app/main.py` — FastAPI entry, router mounts, CORS
- `backend/app/config.py` — every env var, Pydantic-typed
- `backend/app/services/tier.py` — **canonical** tier gating + caps
- `backend/app/services/auth.py` — native + Clerk JWT verification + dev-bypass
- `backend/app/services/mock_feed.py` — fake data generator (112 tickers incl. 32 commodity ETFs)
- `backend/app/services/polygon_feed.py` — real Polygon adapter (stubbed in places)
- `backend/app/routers/holdings.py` — `/api/holdings` (Recent insider buys, Form 4 via Finnhub). `/api/holdings/funds` is a legacy empty-stub for frontend compatibility. (Quiver 13F `quiver_feed.py` was deleted when the Quiver subscription was cancelled — it only ever served mock data.)
- `backend/app/services/finnhub_feed.py` — Finnhub fundamentals + earnings + IPO calendars + insider Form 4. Calendar replacement wired into `calendar_feed.upcoming_*`; fundamentals → score wiring still TODO.
- `backend/app/services/bot_protection.py` — honeypot + disposable email + Turnstile
- `backend/app/services/fred_feed.py` — FRED macro indicators (DXY, 10Y, VIX) with 1h cache
- `backend/app/services/alerts.py` — per-rule alert evaluators (score / squeeze / regime / congress) with **two**-channel delivery (email / web push)
- `backend/app/services/sms.py` — RETIRED 2026-05-04, file kept for re-enable
- `backend/app/services/discord.py` — RETIRED 2026-05-04, file kept for re-enable
- `backend/app/services/telegram.py` + `backend/app/routers/telegram.py` — **FOUNDER-facing only.** Founder signup/subscription pings, weekly SEO digest, inbox approval bot. The customer Telegram alert channel was RETIRED 2026-08-11 — these files are not it.
- `backend/app/services/web_push.py` — Web Push via VAPID + pywebpush (no-op when either is missing)
- `frontend/public/sw.js` — Service Worker for Web Push notification handling
- `frontend/lib/webPush.ts` — client-side subscribe/unsubscribe/test helpers
- `backend/app/routers/roadmap.py` — public roadmap voting (Premium-gated)
- `frontend/__tests__/` — Vitest + RTL scaffold (run `npm test` after `npm install`)
- `backend/app/workers/signal_publisher.py` — scoring tick worker
- `backend/app/scripts/seed_owner.py` — creates/updates the owner account
- `backend/alembic/versions/` — 7 migrations, run via `alembic upgrade head`
- `frontend/components/PricingTable.tsx` — **canonical** pricing UI
- `frontend/components/TrialBanner.tsx` — trial countdown UI
- `frontend/middleware.ts` — gates `/app/*` routes
- `frontend/lib/auth.ts` — session + tier check helpers
- `docs/ARCHITECTURE.md` — system overview, deployment plan
- `docs/LEGAL_CHECKLIST.md` — pre-launch legal must-dos
- `docs/DATA_SOURCES.md` — what's licensed vs not
- `backend/app/routers/inbox.py` — Resend inbound webhook + Tier 1 Telegram callback handler + admin list/approve/reject
- `backend/app/services/inbox_classifier.py` — rule-based + Anthropic LLM tier classification (`classify_async` is the real path; `classify` is the sync compat wrapper)
- `backend/app/services/inbox_kill_switch.py` — bot_enabled / dry_run / channel_enabled / cap_exceeded gates
- `backend/app/services/inbox_router.py` — `handle_inbound()` canonical dispatcher + `send_tier_1_5_ack()` immediate-ack
- `backend/app/services/inbox_templates.py` — Tier 2 reply templates (ticker_score / pricing / trial / thanks)
- `backend/app/services/inbox_telegram_alert.py` — Tier 1 founder alert card with inline-button keyboard
- `backend/app/services/reddit_inbox.py` — PRAW poller (DMs + comments + mentions) + reply adapter + reply-loop guards + new-account throttle
- `backend/app/models/inbox.py` — `InboundMessage` (idempotent on channel+msg_id)
- `backend/app/models/inbox_classification_log.py` — per-LLM-call audit row backing the daily cost cap
- `frontend/app/app/inbox/page.tsx` — admin inbox review UI

## Pending TODOs (only the user can do these — needs accounts/cards)
Full step-by-step in `docs/OPERATIONS.md`. Most of the wire-up landed in late April / early May 2026. As of **2026-05-13** verified via `fly secrets list -a tapeline-backend`, all of these are **wired in prod**: GitHub remote (push flow live), Cloudflare DNS + Turnstile, Massive (data feed), Stripe (all 6 STRIPE_* secrets — SECRETS are wired, but do NOT read this as "billing works": from 2026-07-18 to 2026-08-25 every Checkout Session 400'd on an invalid parameter and returned 502, so no account has ever completed a checkout (`stripe_customer_id` is null for all 23 users). Fixed in #635, which also added key-name allowlists — `backend/tests/test_checkout_subscription_data_keys.py` and `test_stripe_coupon_names.py` — because a permissive mock let a wrong-but-plausible Stripe field pass tests for 37 days while production 502'd. The first real paid checkout is still UNVERIFIED). **#639 then found the other half:** the webhook that GRANTS the paid tier 500'd on every real Stripe delivery, because `stripe.Event` is not a dict in stripe-python >=12 (`event.get()` raises AttributeError) and `current_period_end` moved off the Subscription onto the subscription ITEM in API 2025-04-30.basil. So a customer could have been charged and never granted their tier. Both were hidden by the same blind spot: all nine webhook tests monkeypatch `parse_webhook` to return a plain dict, which has `.get()` and whatever keys the fixture author typed. `backend/tests/test_stripe_vendor_object_shapes.py` now drives REAL signature-verified `stripe.Event` objects — do not 'simplify' it back to a dict, the dict is the bug, Resend, Telegram bot token (founder notifications + inbox bot only — not a customer alert channel), FRED, Finnhub, Google OAuth, VAPID web push, Neon Postgres (DATABASE_URL), Fly.io backend + Fly.io frontend.

**Inbox bot go-live secrets** (the bot is shipped but dormant until set):
- `ANTHROPIC_API_KEY` — Anthropic console; without it every ambiguous message defaults to Tier 1 manual review
- `INBOX_FOUNDER_TELEGRAM_CHAT_ID` — DM `@userinfobot` on Telegram → copy the id
- `RESEND_INBOUND_SECRET` + MX records for `inbound@tapeline.io` → Resend (configure inbound webhook to POST `https://api.tapeline.io/api/inbox/email`)
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USERNAME` / `REDDIT_PASSWORD` — script-tier app at https://www.reddit.com/prefs/apps; use an aged Reddit account
- Recommended first deploy: `INBOX_DRY_RUN=true` for the first week so the bot classifies + logs but doesn't actually send. Shadow-audit via `/app/inbox`, then flip to live.

Short list of what's actually left:

1. **Microsoft OAuth** client ID + secret (Google is done; Microsoft setup steps in `docs/launch/LAUNCH_PLAYBOOK.md` §6)
2. **Lawyer consult** — Holley Nethercote Melbourne ($400-800). Now higher-priority than before: `docs/LICENSE_AUDIT.md` (2026-05-17) flagged that Polygon/Massive Starter + Finnhub Free are also "personal/non-business only" — Quiver was just the most visibly-marketed exposure.

**Quiver QuantData removed (subscription cancelled).** Premium had already dropped "Elite 13F holdings" from marketing in PR #74 (Quiver Trader-tier TOS says "No Commercial Use Rights"); the feature only ever served mock data because `QUIVER_API_KEY` was never provisioned in production. The `quiver_feed.py` adapter, `_refresh_elite_13f` worker task, `InstitutionalHolding` model, and `quiver_api_key` config are now deleted; the `institutional_holdings` table is left as a harmless orphan. Smart-money inputs are SEC Form 4 insider data (Finnhub) + Congressional disclosures.

## Communication style
- The user prefers tight, factual responses over long narration.
- When suggesting changes, lead with the recommendation; offer to implement rather than implementing unprompted (since there's no git rollback).
- Don't add features, abstractions, or "while I'm here" cleanups beyond what was asked.
