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
- [ ] Validate the 3 never-exercised Stripe price IDs (`PRO_ANNUAL`, `PREMIUM_MONTHLY`, `PREMIUM_ANNUAL`) — blocked on the Fly token

# 5 — Credentials

Seven exposures found independently across four sessions. The Massive vendor key is a separate, already-decided accepted risk and is deliberately not re-opened here.

- [ ] **Open GitHub secret-scanning alert #1** — Stripe webhook signing secret, **public repo**, unresolved. Appears as a `TEST_SECRET` fixture so it is probably fabricated; if it is not, anyone can forge Stripe webhooks and grant themselves Premium. Two minutes to confirm and dismiss
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

- [ ] **Lawyer consult** (Holley Nethercote, $400–800). Flagged as the *"oldest open critical item"*; the original June email may never have been sent. Brief covers: Massive/Finnhub personal-use terms vs commercial use; the per-user next-day-vs-SPY track record; the extension rendering a score beside broker order flow; post-aha microsurveys vs rule 8; scorecard summary stats vs rule 4
- [ ] **Vendor data-rights letters** to Massive/Polygon + Finnhub — 2–6 week lead time that starts only when sent. Not sent
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

- [ ] **Feed-coverage audit** — one query: which top-500 US names by dollar volume have no price/volume read on prod, grouped by cause. **This is the one item allowed to jump the interview gate** if the cause is a mapping bug
- [ ] **[gate]** Positioning + hero rewrite, using the customers' own words
- [ ] **[gate]** Remaining activation code — pre-armed alert on the seeded name, 3-item checklist, T+0 founder welcome
- [ ] **[gate]** Ruler-lite — `core_action_at`, `churn_events` + reason taxonomy + reactivation stamp, the saved weekly SQL
- [ ] Flip `watchlist.track_record` off pending the lawyer's answer
- [ ] One-time catch-up so the ~23 users who aged out of every drip window can ever receive a lifecycle email
- [ ] `RESEND_WEBHOOK_SECRET` unset — the bounce/complaint webhook silently returns `{"ok": true, "skipped": ...}`
- [ ] Public-repo decision: go private, or stop treating the scoring weights as a boundary

# 10 — Housekeeping

- [x] **CLAUDE.md corrected** (2026-08-30) — it still described the card wall as live and Free as having 2 web-push alerts. Both false since #683/#686
- [ ] Stale docs still to fix: `PRICING_ANALYSIS_2026-08.md` ("Free — no card, forever"), `finance/spend-policy.md` ("Paid ads: PAUSED" — Meta is live), `operator-role-and-session-map.md` (Premium $39.99 + FOUNDERFRIENDS 50%), `docs/PRICING.md`
- [ ] **`C:\Tapeline` is not a git repository.** `CHROME_STORE_LISTING.md` — which is needed for the extension submission — plus the audit dumps live there untracked and unbacked-up
- [ ] 368 remote branches, ~204 with unmerged commits. Most of the agent fleet's output never landed
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
