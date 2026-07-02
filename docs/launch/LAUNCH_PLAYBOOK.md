# Tapeline Launch Playbook

Self-contained reference for the launch push. Drafted 2026-05-13 alongside the email/SEO/Sentry buildout.

---

## 1. Show HN post

**When to post**: Tuesday or Wednesday, **8 AM ET** (peak HN traffic, US East Coast morning).
**Why that window**: news.ycombinator.com front-page churn is heaviest 8–11 AM ET on weekdays. Posts that land outside that window typically die at rank 30+ within 90 min.
**Account requirements**: HN account with ≥ 30 karma posts better. Use your existing account, don't make one fresh — fresh accounts get flagged.
**Hang around for 2 hours after posting** answering every comment. Engagement in the first 60 min drives the front-page algorithm.

### Title (keep ≤ 80 chars; HN hides what doesn't fit)

> **Show HN: Tapeline – One score per stock, fully public formula**

### Body (paste verbatim into the URL field is wrong — HN needs the URL in the URL slot, the body goes in "text")

URL field: `https://tapeline.io`

Text field:

```
Hey HN — I built Tapeline because I was tired of stock screeners that ask you to set up 47 filters and give you back a list with no opinion. The whole point of a scanner should be "here's what looks interesting and here's why."

So Tapeline scores every US ticker with a single 0–100 composite — Trend 25%, Relative Strength 20%, Fundamentals 15%, Smart Money 15%, Macro 15%, Momentum 10%. The weights are public on /how-it-works and can't change without a changelog entry. Every score comes with one plain-English sentence explaining what's driving it.

The thing I care most about: a public scorecard. Every day I log the top 10 names. Next day I compute their actual return vs SPY and the result goes on a public page anyone can audit. No cherry-picking, no "we removed 3 underperformers". Live at https://tapeline.io/scorecard — currently in its first 60 days of back-checking, so the win-rate column is still filling in.

Free tier: top 20 tickers, 24-hour delay, 5-name watchlist.
Pro $9.99/mo: full 2,500-ticker live scan + watchlist with smart alerts.
Premium $19.99/mo: + Congress trades, insider Form 4 activity, Telegram alerts.
14-day Premium trial, no card required.

Stack: Next.js 14 + FastAPI + Polygon (now Massive) + Finnhub + FRED. Deployed on Vercel + Fly.io.

Built solo over the last few months. Genuinely curious what HN finds wrong with the scoring methodology — it's the part I want to harden first.
```

### Comment-thread playbook
- **First comment from you** (post immediately after submitting): paste the 6-factor formula in a code block. People click into HN comments before the link.
- **Anticipated objections + your responses ready**:
  - *"Your scorecard only has 2 days"* → "Yes, it just launched. The whole point of /scorecard is that it's auditable from day one — even with the win-rate still filling in, you can see every call and every back-check."
  - *"Why not open-source"* → "The score formula is public on /how-it-works. The infrastructure (data pipelines, live scanner) is the moat. Happy to discuss specific factor calculations in depth."
  - *"Has the formula been backtested"* → "Walk-forward back-test on 2024-2025 is in progress. The /scorecard page is the live forward-test — that's the one that counts for trust."
  - *"What about $TICKER"* → "Try it — `https://tapeline.io/t/$TICKER` works for any ticker in the universe. Drop your own examples in comments."

### Realistic outcome
- 200–500 visitors over 24h, 5–30 trial signups, 1–3 paying conversions in week 1
- Even if it doesn't hit front page, the comments are gold — that's user research you'd otherwise pay $5K for

---

## 2. Reddit launch — three subs, three different angles

Reddit hates self-promo. Substance + transparency + responding to every comment carries you. **One post per sub per week max** — moderators ban for cross-posting.

### r/algotrading (~700K subs, quant-savvy)

**Title**: `I built a 6-factor composite stock scoring system — formula, weights, and a public back-check page`

**Body**:
```
Three months ago I started Tapeline (tapeline.io) because every screener I tried either showed me raw filters (Finviz) or hid its methodology behind an "AI score" black box (Simply Wall St). I wanted something that picks a single number, tells me what's driving it, and lets me audit every call against SPY the next day.

Here's what I shipped:

**The formula** (public, version-controlled, won't change without a changelog entry)

- Trend 25% — 20/50/200 DMA stack, slope, days above 50DMA
- Relative Strength 20% — Mansfield RS vs SPY, sector RS, 12-1 momentum
- Fundamentals 15% — revenue growth, margin trend, ROE, F-score
- Smart Money 15% — Form 4 insider transactions (net 90-day) — *not* 13F lag
- Macro 15% — composite of VIX percentile, breadth, 10Y, regime score
- Momentum 10% — 20-day rate-of-change, RSI position, accumulation/distribution

**The accountability layer**

Every market day I freeze the top 10 composite scores. The next day I log each name's actual return vs SPY. The full history lives at /scorecard with no survivor bias filtering — losers stay on the page. Win-rate / avg alpha / beat-SPY rate columns fill in 24h after each close.

**What I'd like feedback on**

1. Smart Money via Form 4 — is net-90-day buying the right window, or should I weight by insider role (CEO > director)?
2. Should momentum get less weight (currently 10%) given it's already inside trend + RS?
3. What factor would you add to make this defensible for a 1Y horizon vs the current 1D back-check?

Roast it. The formula is the part I want to harden.
```

### r/stocks (~3M subs, general retail)

**Title**: `Built a free stock score tool — every call back-checked vs SPY next day, full history public`

**Body**:
```
I got annoyed at every "AI stock recommendation" service refusing to show its track record. So I built Tapeline (free tier covers the top 20 tickers).

What's free:
- One 0-100 score per stock with a plain-English why
- Public scorecard tracking every top-10 pick I make, back-checked against SPY the next day
- 5-ticker watchlist

What costs $9.99/mo (Pro):
- Full ~2,500 ticker live scan
- Smart watchlist alerts when scores move
- IPOs / earnings / news calendar

What costs $19.99/mo (Premium):
- + Congress trades feed (House + Senate disclosed)
- + Elite 13F holdings (Buffett, Burry, Ackman, etc.)
- + Unlimited Telegram alerts

14-day Premium trial, no card.

Try it on any ticker you like — `tapeline.io/t/AAPL`, `tapeline.io/t/NVDA`, whatever. Drop your favorite ticker in comments and I'll post its current score + the breakdown.

Tell me what's missing. Roast the methodology at /how-it-works.
```

### r/SecurityAnalysis (~250K subs, fundamentals-skewed)

**Title**: `Tapeline — synthesises 6 factor signals into one score, plain-English Why per ticker, public daily scorecard`

**Body**:
```
Live at tapeline.io. Built it because I wanted to stop manually weighing trend / RS / fundamentals / insider activity every time I screened.

The 15% Fundamentals factor breaks down into:
- Revenue growth (trailing 4 quarters)
- Operating margin trend
- ROE (current vs sector median)
- F-score (Piotroski 9-point)

Score is recomputed every ~30 sec during market hours from a live data feed (Polygon/Massive for prices, Finnhub for fundamentals + Form 4, FRED for macro).

Concrete example a SecurityAnalysis crowd might find useful: filter to `/sector/financials` and the score will give you a 0-100 read on every financial. Click any ticker → /t/$X → see the six-factor breakdown so you can drill into which factor is dragging or pulling.

Free tier covers everything I'd want as a generalist (score + scorecard + 5-ticker watchlist). Pro $9.99 unlocks the full universe. Premium $19.99 adds Congress / 13F / Telegram alerts.

Happy to take fundamentals-specific critique. The Piotroski F-score implementation in particular — would love eyes on edge cases (financial vs non-financial scoring).
```

### Posting schedule
- Week 1, Tuesday 9 AM ET: r/stocks (broadest reach)
- Week 1, Thursday 10 AM ET: r/algotrading
- Week 2, Tuesday 9 AM ET: r/SecurityAnalysis (give it space from the others)

### Anti-pattern checklist (do NOT do)
- Don't post in r/wallstreetbets — that crowd burns SaaS founders alive
- Don't link to a paywall in the post body — link to the free public page (/scorecard, /how-it-works) and let the pricing page sell itself
- Don't reply to "shilling" accusations defensively — link to /scorecard and let the public track record do the work
- Don't post the same body to multiple subs — Reddit's spam filter will shadowban the cross-posts

---

## 3. X / Twitter pinned thread

**STATUS — POSTED + PINNED 2026-05-13** ✅

Live on [@tapeline_io](https://x.com/tapeline_io). Pinned tweet (1/6) is the first one below; tweets 2–6 are self-replies forming a thread chain.

| # | URL |
|---|---|
| 1 (📌 pinned) | https://x.com/tapeline_io/status/2054350238891295068 |
| 2 | https://x.com/tapeline_io/status/2054350575094120801 |
| 3 | https://x.com/tapeline_io/status/2054350954573754577 |
| 4 | https://x.com/tapeline_io/status/2054351264830697890 |
| 5 | https://x.com/tapeline_io/status/2054351516954513647 |
| 6 | https://x.com/tapeline_io/status/2054351713709310077 |

Tweet 4 published with `+ Congress + insider Form 4 activity + unlimited Telegram alerts` (the playbook draft below still has the stale `13F` wording — left as-is for posterity; the *published* tweet matches the current product).

The thread was published as **5 self-replies** (each reply chains the previous tweet), not via the multi-post composer — the composer dropped focus on long types and triggered X keyboard shortcuts mid-stream. Reply-chain works around that cleanly and renders identically as a thread on profile.

---

**Length**: 6 tweets max. People stop reading after 4.

```
1/ Built Tapeline (https://tapeline.io) — one transparent score per US stock.

Most scanners give you 47 filters and no opinion. Most "AI" tools hide their formula. Tapeline picks a number, tells you why, and back-checks every call against SPY the next day. Publicly.

2/ The formula is public and won't change without a changelog entry:

Trend 25 · Relative Strength 20 · Fundamentals 15 · Smart Money 15 · Macro 15 · Momentum 10

You can audit it at https://tapeline.io/how-it-works

3/ Every market day, I freeze the top 10 composite scores. Next day I log each name's actual return vs SPY.

The full history — winners and losers — lives at https://tapeline.io/scorecard

Currently in its first 60 days of back-checking. Win-rate column fills in real-time.

4/ Free tier: top 20 tickers, 24h delay, 5-name watchlist.

Pro $9.99/mo: full ~2,500-ticker live scan + smart watchlist alerts + IPO/earnings calendar.

Premium $19.99/mo: + Congress + 13F + unlimited Telegram alerts.

14-day Premium trial, no card.

5/ Three things I care about most:

→ Public formula
→ Public scorecard (no survivor bias)
→ Plain-English Why on every row

If any of those break, the product fails. I'd rather lose to a better methodology than win with a black box.

6/ Try any ticker → https://tapeline.io/t/$YOUR_TICKER

What ticker should I run the scorecard on next? Drop one and I'll reply with its current 6-factor breakdown.
```

**Pin this thread**. Reply to fintwit accounts when they discuss something Tapeline would have called — *don't* spam, do it when it's actually relevant.

---

## 4. Discord setup (community)

**Why Discord over Slack**: Discord is built for public communities. Slack is built for orgs. Free-tier Discord has unlimited message history; free-tier Slack hides messages past 90 days.

### 10-minute setup
1. Sign up at https://discord.com (you, on your phone or computer — needs your account)
2. Create new server: "Tapeline" (icon: your logo)
3. Channel structure (keep small to start):
   - `#announcements` (read-only for everyone except admins, ✏️ icon)
   - `#general` (default chat)
   - `#feedback` (where users tell you what to build)
   - `#ticker-talk` (where they discuss specific stocks the scorer is calling)
   - `#bugs-issues` (so support emails don't get duplicated here)
4. Roles:
   - `@founder` (you, all permissions)
   - `@premium` (auto-assign when someone DM-verifies their Tapeline email — Discord bot can do this; defer for now)
   - `@everyone` (default — read all, post in #general/#feedback/#ticker-talk)
5. Invite link: Discord → Server Settings → Invites → Create invite → "Never expire, unlimited uses" → copy
6. Footer link on Tapeline: add "Discord" link to the MarketingFooter → ~5 min code change, I can do this after you give me the invite URL

### When NOT to launch the Discord publicly
- If you have < 50 trial users yet, an empty Discord looks worse than no Discord. Wait until launch traffic gives you the seed of 10–20 active members on day 1. Then post the invite on the homepage + in your launch posts.

### Moderation rule of thumb
You're the only mod. Set a clear rule: no shilling specific tickers as buy/sell calls (you can discuss what Tapeline scored them at, that's fine). Pin this rule in #announcements. Removes 80% of moderation burden.

---

## 5. The /compare/finviz table — visual issues I'd fix

Audit findings (took screenshots in this session):

| Issue | Impact | Fix effort |
|---|---|---|
| Right column ("Finviz Elite") has 3 cells in a row that are just `—` — looks like data dump errors, not contrast | Page feels like an attack ad instead of a comparison | S — replace bare `—` with one-line description e.g. "Not available" |
| Row heights inconsistent (1-line vs 2-line wraps) | Visual rhythm broken | S — set min-row-height, allow text to truncate cleanly |
| No alternating row backgrounds | Eye loses horizontal track on wide table | S — add 2% lighter row tint on every other row |
| No subtle vertical column divider | Reader can't tell which "—" belongs to which row when scrolling | S — add 1px column rule in dark theme color |
| "9 categories Tapeline wins outright. 3 honest tradeoffs." pill above the table | Reads as hype, not honesty | S — drop the pill, let the table speak |
| "ALL PRICES IN USD" floats top-right | Looks orphaned | S — move into table footer or kill it |

These are all small CSS changes. Can ship as one PR (~1 hour) when you say go.

---

## 6. Microsoft OAuth — DEFERRED post-launch (2026-05-14)

**STATUS: Intentionally deferred. Not blocking launch.**

The "Continue with Microsoft" button is **already hidden in production** — `OAuthButtons.tsx` only renders the button when the backend `/api/auth/oauth/providers` endpoint returns `microsoft: true`, and that endpoint only returns true when both `OAUTH_MICROSOFT_CLIENT_ID` and `OAUTH_MICROSOFT_CLIENT_SECRET` are set in Fly secrets. They aren't. So zero broken-UI risk.

### Why we hit a wall on 2026-05-14

Tried two account paths, both blocked:

1. **`tapeline.inbox@gmail.com`** (brand inbox, newly created as a personal Microsoft account): no Azure AD tenant attached → `login.microsoftonline.com/organizations/` endpoint that Entra admin center uses rejects it. To proceed, you'd need to provision a free Microsoft 365 Developer tenant first (~15-30 min signup at `developer.microsoft.com/microsoft-365/dev-program`).
2. **`chamara.piyatilaka@hotmail.com`** (personal account, has prior tenant): Microsoft flagged it for "unusual activity" mid-session (because bot-driven), forcing a password-reset detour. And the sign-in requires passkey/biometric — device-bound, can't be MCP-driven.

### When to revisit

Recommended **after launch traction is real** — Microsoft OAuth is checkbox-feature territory for a fintech-prosumer audience (your HN/Reddit/X traffic is overwhelmingly Google/GitHub identity). Pick this up as a focused 30-min session when:
- You have 50+ paying users and one of them specifically asks for Microsoft sign-in, OR
- You're going B2B/enterprise and need it for procurement

### When you DO pick it back up

Path of least resistance:
1. Provision a free Microsoft 365 Developer tenant under `tapeline.inbox@gmail.com` at `developer.microsoft.com/microsoft-365/dev-program` (free, renewable, brand-owned)
2. Wait for tenant provisioning (~5 min)
3. Sign into `entra.microsoft.com` with the new tenant credentials
4. Entra → App registrations → New registration:
   - Name: `Tapeline`
   - Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**
   - Redirect URI: `Web` → `https://api.tapeline.io/api/auth/oauth/microsoft/callback`
5. After Register: copy **Application (client) ID** from overview page → that's `OAUTH_MICROSOFT_CLIENT_ID`
6. Left nav → Certificates & secrets → New client secret → 24-month expiry → copy the **Value** column (not Secret ID) → that's `OAUTH_MICROSOFT_CLIENT_SECRET`
7. `fly secrets set OAUTH_MICROSOFT_CLIENT_ID=... OAUTH_MICROSOFT_CLIENT_SECRET=... -a tapeline-api`
8. Fly auto-restarts the API container, the `/oauth/providers` endpoint flips to `microsoft: true`, the button renders, done.

~10 min after the tenant exists.

---

## 7. Next.js 16 major bump — deliberately deferred

Currently on Next.js 14.2.35. Upgrading to 16.x is **two major versions in one jump** (skipping 15). Breaking changes you'd hit:

- `next/legacy/image` removed (used in some marketing pages)
- `app-router-experimental-features` removed
- Caching defaults flipped (App Router used to opt into cache; 15+ flipped to opt-out)
- Middleware contract changed slightly
- Server Actions API tightened

**Why I'm not bundling this with the other "do everything" work**:

A Next major bump needs:
1. Dedicated branch + isolated PR (no other code changes)
2. Full Vercel preview deploy + smoke test of every key page (/, /pricing, /scorecard, /t/[symbol], /app/scanner, /app/ticker/[symbol])
3. Lighthouse rerun to confirm no perf regression
4. Live test on a few key flows (signup, Telegram connect, Stripe checkout)
5. Roll forward with the option to revert if anything breaks

That's a **focused 2-3 hour session**, not a "while I'm doing other things" task. If I crammed it into tonight's batch and something broke at 1 AM, the cost is your live site is down for unknown users.

**Recommendation**: Schedule a dedicated session. I'll do it cleanly. The two open advisories it closes (Image Optimizer DoS + request smuggling) are **theoretical** — neither has been observed in the wild against a Vercel-hosted Next app like yours, so the urgency is "this month" not "tonight."

---

## 8. Public API endpoint — deliberately deferred

The marketing claim was removed in PR #11 because no API existed. To actually build one:

**Minimum viable**:
- API key model + table (user_id, key_hash, created_at, last_used_at, requests_today)
- Auth middleware that checks `Authorization: Bearer tk_…` header
- Rate-limit middleware: Free=blocked, Pro=100/day, Premium=1000/day
- Endpoints: `GET /api/v1/score/{symbol}`, `GET /api/v1/scanner?limit=20`, `GET /api/v1/scorecard?days=30`
- Key management UI inside `/app/settings/api-keys` (generate, name, revoke)
- Docs page at `/api` with curl examples + OpenAPI spec

**Time estimate**: 2-3 focused days (backend ~1.5d, UI ~0.5d, docs ~0.5d, testing).

**Why I'm not doing it tonight**: it's a real product feature, not a fix-it-now task. Putting it in the same batch as bug fixes and email plumbing increases the chance of half-shipping it and breaking auth for actual users.

**Recommendation**: Park this until you have your first 50 paying users. Real demand for the API surfaces from talking to Pro/Premium subscribers — they'll tell you what they actually want to automate. Build to that demand, not to a marketing copy promise.

---

## 9. Conversion & analytics — what's live, what to verify

Wired across the stack as of PR #98 (2026-05-20). Brief rundown so you
can sanity-check it's all flowing and know where to read the numbers.

### Analytics layers (in order of read priority)

| Layer | What it captures | Where to read |
| --- | --- | --- |
| **Google Analytics 4** | Acquisition, behaviour, conversions (sign_up, start_trial, subscribe, view_*) | analytics.google.com → Tapeline property |
| **Vercel Analytics** | Per-route pageviews + custom events fired via `track()` | vercel.com/cham-p24/tapeline → Analytics |
| **Speed Insights** | Core Web Vitals + custom perf metrics | Same Vercel dashboard |
| **PostHog** | Session recordings + event funnel | posthog.com |
| **Plausible** | Privacy-first aggregate view (no cookies) | **disabled in prod** — set `NEXT_PUBLIC_PLAUSIBLE_DOMAIN=tapeline.io` in Vercel to enable |

### GA4 setup verification

GA4 measurement ID is hardcoded as `G-YRK73W9NS9` (default in
`frontend/app/layout.tsx`). Override with `NEXT_PUBLIC_GA4_ID` env var
in Vercel if the property rotates.

After deploy, smoke-test it's actually firing:

1. Open analytics.google.com → Admin → DebugView (left panel)
2. In a separate tab, open https://tapeline.io with `?_gl=1*debug*1` (forces debug mode)
3. Click around — pageviews should arrive in DebugView within ~30s
4. Submit the newsletter form on the homepage → `sign_up` event with `method=newsletter` arrives
5. Submit a signup → `sign_up` event with `method=email` arrives + `start_trial`

If nothing arrives, in GA4 → Admin → Account → Account access management,
confirm the property has at least one data stream pointing at `tapeline.io`.

### UTM attribution — how it works end-to-end

Captured first-touch with 30-day TTL:

1. Visitor lands at e.g.
   `tapeline.io?utm_source=podcast&utm_campaign=acquirers&utm_medium=podcast`
2. `frontend/components/UtmCapture.tsx` (mounted in root layout) writes
   the UTM triplet to `localStorage` under `tapeline_utm_v1`
3. If the user signs up (any time within 30 days, even from a different page):
   - `frontend/app/signup/page.tsx` reads `getStoredUtm()` and POSTs the
     UTMs to `/api/auth/signup`
   - Backend stores them on `users.signup_utm_*` (migration 0021)
4. If the user joins the newsletter:
   - `frontend/components/NewsletterCapture.tsx` does the same forward
   - Backend stores on `newsletter_subscribers.utm_*` (same migration)

### Outbound UTM conventions

Tag every outbound link to tapeline.io with the standard triplet:

```
?utm_source=<channel>&utm_medium=<format>&utm_campaign=<specific>
```

| Channel | utm_source | utm_medium | utm_campaign example |
| --- | --- | --- | --- |
| X bio link | `x` | `social` | `bio` |
| X tweet | `x` | `social` | `tweet_<date>` |
| Fintwit reply | `x` | `reply` | `<handle_short>_<date>` |
| Reddit post | `reddit` | `community` | `r_stocks_launch` |
| Podcast show notes | `podcast` | `podcast` | `<show_short>` |
| Cold email | `email` | `outreach` | `<segment>_<batch>` |
| Newsletter (own) | `newsletter` | `email` | `daily_<YYYYMMDD>` |
| Show HN | `hn` | `community` | `show_hn` |
| Press / TechCrunch | `press` | `referral` | `<publication>_<date>` |

Rule of thumb: keep `utm_source` short and singular (`x`, not `twitter,
also-x`). The composite columns `signup_utm_source/medium/campaign` are
all stringly-typed; nothing parses them — they're for SQL grouping in
post-launch attribution reports.

### Newsletter lead-magnet (added PR #98)

`/api/newsletter/subscribe` — public POST, IP rate-limited, honeypot +
disposable-domain filtered. Fires a Resend welcome email from
`christian@tapeline.io` and stores the row in `newsletter_subscribers`.

Surfaces with the capture form rendered today:
- Homepage footer band ("Not ready for a trial?")
- Scorecard footer ("Get tomorrow's Top 10 in your inbox")

Daily-digest worker is NOT yet wired — that's a follow-up PR. Until
then, subscribers get the welcome and nothing else; document that
clearly in the UI copy (we do — "first daily digest hits the next US
market morning") and ship the worker quickly.

### Conversion events fired today (audit map)

| Event | Where | What it means |
| --- | --- | --- |
| `signup_started` | /signup mount | Visitor opened the form |
| `signup_completed` / `sign_up` | /signup submit | Account created |
| `trial_started` / `start_trial` | /signup submit | 14-day Premium trial begins |
| `newsletter_subscribed` / `sign_up{method=newsletter}` | NewsletterCapture submit | Email captured |
| `pricing_page_viewed` | /app/billing render | In-app upgrade view |
| `trial_converted` | /app/billing on trial → paid | Conversion to paid Premium |
| `trial_downgraded` | /app/billing on trial → free | Lost trial |
| `checkout_started` | /app/billing checkout-click | Stripe redirect initiated |
| `onboarding_submitted` | /app/onboarding submit | Profile captured |
| `scanner_first_use` | /app/scanner first mount | Activation |
| `trial_early_capture_*` | TrialEarlyCapture | Mid-trial upgrade nudge |
| `trial_ended_modal_*` | TrialEndedModal | Post-trial recovery |

To flag any of these as a "conversion" in GA4 (so they appear in
Acquisition reports / show up in attribution): GA4 Admin → Events →
toggle "Mark as conversion" on the row.

---

## Punch list snapshot — what's done tonight vs what's outstanding

### Done this session
- ✅ News-freshness alert thresholds refined (PR #16, merged)
- ✅ Audit of site tables — /compare/finviz flagged as the offender
- ✅ Show HN + Reddit + Twitter posts drafted (this file)
- ✅ Discord setup guide (this file)

### Pending your action
- ⏳ Microsoft OAuth — 10 min in Entra portal, send me 2 strings
- ⏳ Real-money smoke test ($9.99 self-purchase) — still untested
- ⏳ Stripe webhook secret rotation
- ⏳ Smart Money / `/app/holdings` decision (A/B/C path)
- ⏳ Show HN actually posted — needs your HN account, your timing

### Pending dedicated future sessions (intentionally deferred)
- 🗓️ Next.js 16 major bump — 2-3h focused session
- 🗓️ Public API endpoint — 2-3 day build
- 🗓️ Stock Financials + Insider tabs on `/app/ticker/[symbol]`
- 🗓️ Multiple watchlists + saved screener presets
- 🗓️ Welcome email drip + trial-end nudge sequence

End of playbook.
