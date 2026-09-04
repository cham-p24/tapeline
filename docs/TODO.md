# The list

*Consolidated 2026-08-30 from every Tapeline session (11 chats + this one, ~70,000 messages) plus live checks against prod, Stripe, GitHub and the scheduled-task runner.*

**This file supersedes four ledgers that went stale in mid-June and were never picked back up:** `C:\Tapeline\sales\queue\{ALL_CHATS_TODO,FOUNDER_TODO,TAPELINE_TODO}.md` and `docs/MORNING_QUEUE.md` (still titled 2026-05-17). Those live outside any git repo. This one is in the repo, so it is backed up and diffable.

**The headline finding: of 63 open items, 5 can be done by an agent.** Everything else needs a card, a password, a browser session, or a decision. That is not a tooling gap — every session independently hit the same wall and said so.

---

## Dated — these resolve themselves whether or not anyone acts

| Date | What happens |
|---|---|
| **2026-09-08** | Meta ad burst ends (A$350 spent). Open-access month auto-reverts — no deploy needed |
| **2026-09-12** | Both Premium trials convert or lapse |
| **2026-09-20** | 6-interview gate (`OPERATING_RULES.md` §1). Currently **0/6**. Blocks all engineering |
| **2026-09-29** | The one payer's access ends — they cancelled the day they paid |
| **2026-10-15** | Chrome Web Store API v1.1 shuts off |
| **~2026-11-15** | 90-day kill-number decision (clock started 2026-08-19) |
| **2026-11-20** | One content channel held 90 days + first AI-visibility readout |
| **2027-02-20** | First organic payers, measured trial→paid rate |
| **2027-05-31** | Venture kill-or-persevere: ≥25 payers, ≤8% monthly logo churn, one channel with ≥5 payers unassisted |

## Where the numbers actually sit (verified 2026-08-30)

29 real users · 28 verified · 7 activated · **1 paying (cancelled same day)** · 2 trials · 6 signups in the last 7 days.
Subscriptions: 1 `active` with `cancel_at_period_end = True`, 2 `trialing`.

---

# 1 — Blocking everything

- [ ] **Read `tapeline.inbox@gmail.com`.** 10+ unread, including replies to the 2026-08-11 email to 17 users. The cheapest path to the interview gate. No agent can reach this mailbox.
- [ ] **Re-arm the open feedback session for a new date.** The 2026-08-29 session went out **unannounced** — the reminder task fired 2026-08-28T13:01, began its guard check, called PowerShell once and stopped. No `SENT.flag`, no send. Its own rule now refuses a retry after the session start time.
- [ ] **Ask the one payer why they cancelled.** Paid $9.99 on 2026-08-29, set `cancel_at_period_end` the same day. This is the highest-signal data point the product has ever produced.

# 2 — Decisions only the founder can make

- [ ] **The D0 bundle** — merged paid-tier price + name; monthly-first CTA y/n; un-gate the personal watchlist record; public identity (real name vs "Christian"); `OPERATING_RULES` §4 amendment vs the published "founding pricing locked" promise. *Growth reduced this to "three words is enough" and still got nothing.*
- [ ] **Monthly living cost + months of savings.** CFO asked across four separate turns. Without them the 90-day go/no-go has no date. *"The company has infinite runway. You don't."*
- [ ] **Growth's "say go"** — the daily-post generator (pulls yesterday's picks + result from live data, emits paste-ready posts) plus the first 10 posts and directory copy. Idle since 2026-08-21.
- [ ] **Microcap-heavy Top 10 — the default-view call.** Open across Manager and CEO. Deliberately not guessed at: the naive fix empties the prod scanner.
- [ ] **Extension: submit or shelve.**
- [ ] Ad concept C — stays paused? (Recommendation: yes. 8 days at A$25/day can't exit learning, and a three-way split worsens the read.)
- [ ] Should `/api/ticker/{symbol}/history` carry the 7-day delay?
- [ ] Purge already-collected suitability data? **Irreversible.**

# 3 — Chrome extension: built, never submitted

Item `eainjcenlknbojblklapgjilafgebiii`, version 1.2.3, all four `CWS_*` secrets set. ~40 minutes of founder time.

- [ ] Paste the listing from `C:\Tapeline\CHROME_STORE_LISTING.md` (description, category Finance, language)
- [ ] **Four screenshots at 1280×800** of the extension actually running — cannot be fabricated
- [ ] Privacy tab: **tick "Authentication information: yes"** (it does ship a bearer token; a mismatch here gets items pulled). Privacy URL must be `/legal/extension-privacy`, **not** `/legal/privacy`
- [ ] Press **Submit for review**. Expect manual review: new developer, new extension, finance category
- [ ] Next CI publish must be **1.2.4+** — 1.2.3 is now the store version
- [ ] Consider a `@tapeline.io` support address instead of personal Gmail (trust flag under finance review)

*Before spending the time: the session's own research put the category ceiling at 6,000–10,000 installs and a realistic 90-day outcome at 20–80 installs → 0–2 signups. It recommended MCP over the extension and was overridden. It then wrote its own rule: don't touch the extension again until 100 weekly uniques or one paying customer.*

# 4 — Money

- [ ] **Put a real card through live checkout, end to end.** Never once done. Checkout was silently dead for 37 days and nothing alerted
- [ ] Stripe Tax on
- [ ] Payout bank verification; business/personal money split; Radar check; sole-trader KYC upload
- [ ] **Plan-change gap** — an active subscriber switching plans today gets "contact support". Zero-code fix: enable plan switching in Stripe portal settings
- [ ] Cancel the Quiver $30/mo subscription
- [x] **All four Stripe price IDs validated against LIVE Stripe** (2026-09-02, `stripe-preflight` workflow). pro monthly $9.99/mo, pro annual $99/yr, premium monthly $19.99/mo, premium annual — all `ok`; all four shadow checkouts created and expired; `webhook parse: OK (signature verified, .get() works)`; account `charges_enabled=True payouts_enabled=True`. **Never needed the founder** — the workflow uses the repo's `FLY_API_TOKEN` secret, not the expired local one

# 5 — Credentials

Seven exposures found independently across four sessions. The Massive vendor key is a separate, already-decided accepted risk and is deliberately not re-opened here.

- [x] **Secret-scanning alert #1 resolved** (2026-09-02, `used_in_tests`). False positive: the file is `test_inbox_webhook.py` — the **Resend/Svix** inbound test, and Svix shares the `whsec_` prefix that GitHub's Stripe classifier matched. Fabricated `TEST_SECRET` fixture, GitHub validity `unknown`, and `RESEND_INBOUND_SECRET` was never provisioned in production, so there is no live secret it could correspond to. The file never reached `main`; its branch (`claude/cool-shockley-ac08f3`, inbox-bot phases A–F) was fully superseded by the shipped inbox bot and has been deleted
- [ ] Rotate **Anthropic + OpenAI API keys** — pasted into chat 2026-05-12, no rotation recorded
- [ ] Rotate **Alpaca key + secret** — pasted into chat 2026-06-15
- [ ] Rotate **Fly deploy token** — pasted into chat 2026-06-04, **and it is now expired**, which is actively blocking work
- [ ] Rotate **PostHog `phx_` key**
- [ ] Confirm Google OAuth client secret `…21IC` is still **Disabled** (leaked via a copy button's `aria-label`, disabled, re-enabled for a re-mint, disabled again)
- [ ] Resend inbound webhook signing secret — rotation flagged founder-only, never confirmed

# 6 — Access walls that keep blocking agents

- [ ] **Refresh the Fly API token** (`C:\Tapeline\sales\queue\.fly_api_token`, 401). Blocks the microcap fix, the #491 prod-pulse tracker and price-ID validation
- [ ] OAuth connectors: Search Console, GA4, Google Ads, Ahrefs, Supermetrics — *"the recurring wall I keep hitting"*
- [ ] **Two Google Sheet tabs return 400** — `smart_money_fetch_failed`, `spike_fetch_failed`. Needs a founder republish + Fly secret update
- [ ] GA4 API secret
- [ ] Google Ads `begin_checkout` conversion action
- [ ] **Microsoft Clarity** — paste `NEXT_PUBLIC_CLARITY_PROJECT_ID`. 5 minutes; the code shipped env-gated in #484
- [ ] PostHog key as a build arg
- [ ] Reddit password reset — the account was locked by our own automation
- [ ] LinkedIn — compromised twice; blocks the DM outreach channel
- [ ] Connect `tapeline.inbox@gmail.com` so agents can see outreach replies at all

# 7 — Legal

- [x] **Lawyer consult** (Holley Nethercote) — **SENT 2026-09-05** to `law@hnlaw.com.au`, Gmail thread `1a06d461fe5712c4`. Covers all seven surfaces, leads with data licensing. The firm publishes NO email address and their "Get expert advice" form renders no fields (the only form on hnlaw.com.au is site search) — the address came from the IMAP member listing and their own Treasury submissions, corroborated by the Level 32 / 140 William St address matching their contact page. One line was corrected before sending: the draft said revenue was "a few subscriptions a month", which would have scoped their fee quote too high. **Clock started 2026-09-05; expect a scoping reply in 1–2 business days. If nothing by 2026-09-12, phone +61 3 9670 8200.**
- [x] **Vendor data-rights letters** — **BOTH SENT 2026-09-05**. Massive → `support@massive.com`, thread `1a06d446b4f5baac`. Finnhub → `support@finnhub.io`, thread `1a06d4485e9f7d06`. Both ask what the commercial tier COSTS rather than whether current use is permitted (deliberate; the trade-off is written down in the draft doc). Sent from `cpiyatilaka@gmail.com`, so replies land in a mailbox that is actually read. **2–6 week clock started 2026-09-05. Chase once at 3 weeks (2026-09-26); after that it stops being a vendor question and becomes a lawyer question.**
- [ ] Trademark search: "Tapeline" vs tapelinehq.com

# 8 — Distribution

- [ ] Send the 3 review-site drafts sitting in Gmail (WallStreetZen, Liberated Stock Trader, The Stock Dork) — from `christian@tapeline.io`, not personal
- [ ] Directory listings: AlternativeTo, ScreenerMatch, SaaSHub, Crunchbase, G2, Capterra, StockTwits, Product Hunt (30-day account-aging clock)
- [ ] **Warm re-engagement: Joe Sciammarella.** Replied 2026-07-25 from `joescam@hotmail.com` (not the address he was mailed at) calling Tapeline *"perfect… extremely helpful"* for finding day-trade candidates. Was answered with a thanks and never converted. One soft nudge only, then mark dormant
- [ ] Video 1 — "reading a score in 60 seconds"
- [ ] First AI-visibility panel — 20 prompts × ChatGPT / Copilot / Perplexity, including the collision prompt
- [ ] Deliverability: SPF/DKIM/DMARC + seed-inbox test on the Resend domain
- [ ] GSC: indexed count + impressions per template, and the 5xx re-check that was scheduled for 2026-08-26 and needs a logged-in browser

*Channel reality check, from Growth: most channels have not failed — they were never tried. Show HN dead, Product Hunt 1 point, **A$951 of Google ads → 0 signups and 0 gclid in the entire user table**, 8 roundup pitches → 0 replies, zero directories listed, the Reddit post never sent. The original 2026-05-12 brief excluded paid ads as "too expensive for the LTV at this tier"; that judgment was overridden and the data has since confirmed it.*

# 9 — Engineering (capped ≤1 day/week, gated on 6 interviews)

- [x] **Feed-coverage audit DONE, and the bug it found is FIXED** (#696 audit, #698 fix, 2026-08-30). Not a licence or mapping problem: `_refresh_aggregates` ranked on the column it populates, so coverage froze alphabetically — A 94% down to Y/Z 0%, 72.2% of the universe with no volume. Fixed with a 60/40 exploit/explore split and `tickers.last_aggregates_at` (migration 0062). Full coverage lands ~9 days from 2026-08-30
- [ ] **[gate]** Positioning + hero rewrite, using the customers' own words
- [ ] **[gate]** Remaining activation code — pre-armed alert on the seeded name, 3-item checklist, T+0 founder welcome
- [ ] **[gate]** Ruler-lite — `core_action_at`, `churn_events` + reason taxonomy + reactivation stamp, the saved weekly SQL
- [x] **`watchlist.track_record` held dark** (#712, 2026-09-02). NOT by deleting the FEATURES entry — `has_feature` fails OPEN on an unknown key, so that would have granted it to every tier including free. New `DISABLED_FEATURES` frozenset checked first, mirrored in `frontend/lib/auth.ts`, with a test asserting the two sets are identical. The component now renders nothing rather than an upsell for something unbuyable, and `PricingTable` stopped selling it
- [x] **Catch-up mechanism BUILT** — `backend/app/scripts/catchup_send.py` + `tests/test_catchup_send.py` (shipped by a parallel session). Correctly a deliberate script, not an auto-firing task, and it splits the audience so nobody legacy-trialled is promised a trial they cannot take. **Running it is a send, so it is founder-only**
- [ ] `RESEND_WEBHOOK_SECRET` unset — the bounce/complaint webhook silently returns `{"ok": true, "skipped": ...}`
- [ ] Public-repo decision: go private, or stop treating the scoring weights as a boundary

# 9b — Shipped 2026-09-02/03 (was not on the original list)

Found while working the list. All merged, deployed and verified in production.

- [x] **Four real listed securities were published at a crypto's price** (#715). `/t/SOL` served a six-factor score and a CAUTION label for **Emeren Group Ltd** — a real NYSE solar company — computed from **Solana's $64.45**, with JSON-LD aimed at answer engines, under a no-AFSL posture. Same for EOS (Eaton Vance fund), BGB and LEO. The sheet upserts by symbol and the crypto namespace collides with real listings. Crypto now dropped at ingest; migration 0063 deleted all 54 rows; verified 0 remain
- [x] **`normalize_asset_class` failed on a leading space** (#715). `"  <emoji> stock"` returned `None` instead of `"equity"`, silently defeating the self-heal its own docstring describes — and it would have re-opened the crypto door, since the drop keys off that return value
- [x] **The site claimed crypto and FX coverage** (#716). It never had either. Also retired `/compare`'s promise to "publish a new comparison every two weeks" — none had been added in months
- [x] **The scorecard download and the page gave different answers** (#721). The summary excluded moves over 50% and reported only a count; the export flagged nothing. ADAC on 2026-05-13 shows **+2,832.23%** — 126x the next largest move in the record, an unadjusted reverse split. New `excluded_from_summary` column and ONE shared threshold constant, with a test asserting both sides use the same object
- [x] **The aggregates pass could never reach 80% of the universe** (#698). It ranked on the column it populates, so coverage froze alphabetically: A 94%, D 65%, E 26%, **Y and Z 0%**. 60/40 exploit/explore split + `tickers.last_aggregates_at` (migration 0062)
- [x] **Liquidity floor raised and re-based** (#704). Scanner $50k and scorecard $250k both to **$1M**, and both moved off the session's RUNNING volume onto `avg_volume_30d`. Live: `total_matched` 2,390 to 1,849
- [x] **The 18 competitor comparison pages removed** (#718). 410 Gone, not silent 404s. The ~165 stock-vs-stock matchups kept. 44 inbound references fixed first
- [x] **Random-returns regression guard ported** (#696)
- [x] **I broke `main` and fixed it** (#719). My `pytest.mark.anyio` marker was the only one in ~180 test files; both async plugins claimed the tests and raced at teardown. Green locally, red in CI

# 10 — Housekeeping

- [x] **Liquidity floor added** (#704, 2026-08-30) — scanner $50k and scorecard $250k both raised to **$1M**, and both moved off `Ticker.volume` (the session's RUNNING total, which made the same ticker fail at 10am and pass at 4pm) onto `avg_volume_30d`. Live: `total_matched` 2,390 to 1,849; CRWD in, CHCI/CIX out. Null reads still kept — load-bearing until coverage fills in
- [x] **Random-returns regression guard ported** (#696, 2026-08-30) — `change_pct_5d`/`change_pct_1m` were `random.gauss` draws in production. The forward fix was on main; its test was orphaned on a branch whose migration id is now taken. Verified failing against the reintroduced bug before landing
- [x] **CLAUDE.md corrected** (2026-08-30) — it still described the card wall as live and Free as having 2 web-push alerts. Both false since #683/#686
- [x] **Stale docs fixed** (2026-08-30) — `PRICING_ANALYSIS_2026-08.md` ("Free — no card, forever"), `finance/spend-policy.md` ("Paid ads: PAUSED" — Meta is live), `operator-role-and-session-map.md` (Premium $39.99 + FOUNDERFRIENDS 50%), `docs/PRICING.md`
- [x] **Store listing backed up into the repo** (#692) at `docs/extension/CHROME_STORE_LISTING.md` with a provenance note. `C:\Tapeline` is still not a git repository and the audit dumps there are still unbacked-up — but the one file needed to submit the extension is now versioned
- [x] **Branches pruned** (2026-08-30) — 369 to 9. Every one deleted was the head ref of a merged PR, so the content is in `main` and GitHub still serves them from their PR pages. The 9 survivors carry genuinely unmerged commits
- [ ] **Audit/Bugs session** — resume or close. It ends mid-sentence on *"I need to correct something I told you"* with a defect sweep that never reported
- [ ] Recovery email to the 3 users who hit the trial-decline trapdoor on 27–28 Aug — drafted, held for founder sign-off (see `docs/drafts/`)

---

## Standing rules that constrain all of the above

- **Never write to the production database. Never email anyone without fresh founder approval. Never spend money.** Carried verbatim through 17 compactions of the Sales session.
- Never reply to Product Hunt or Hacker News comments — founder-only voice.
- **Never accept the GA4 tag-overwrite "Confirm"** — it would clobber `G-YRK73W9NS9` / `GT-KDDHGCH7`.
- Never automate Reddit posting. The account is locked precisely because that rule was broken once.
- Compliance: descriptive language only — never "buy", "sell", "you should", "recommend", "beat the market", "guaranteed". The Australian publisher exemption from AFSL licensing depends on it.
- Founding-member copy is CI-enforced: no counts ("first 50"), no deadlines, no "limited", no "hurry".
- The exact six-factor weights stay unpublished (#342). *"I don't people to reverse engineer it."*
- `C:\signal-system\` is a separate project — never edit outside `C:\Project 1\`.
- The `body::before` atmosphere wash was manually restored by the founder after #195 removed it. Do not re-remove.
