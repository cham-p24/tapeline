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
- [x] **Deliverability: SPF + DKIM are CORRECT.** Audited 2026-09-05 by DNS lookup.
  `tapeline.io` SPF is `v=spf1 include:_spf.google.com ~all`, and Resend sends via
  its own subdomain — `send.tapeline.io` carries `include:amazonses.com`, and
  `resend._domainkey.tapeline.io` carries the DKIM public key. That is Resend's
  standard setup and it is right. No change needed.
- [ ] **DMARC is published but inert — fix is one DNS record.** `_dmarc.tapeline.io`
  reads exactly `v=DMARC1; p=none;`. Two problems: `p=none` enforces nothing, and
  there is **no `rua=` address**, so nobody is collecting the reports that `p=none`
  exists to produce. It neither protects the domain nor tells anyone what is being
  sent in its name. It does clear the Gmail/Yahoo bulk-sender minimum, so this is
  not urgent — but it is 5 minutes in Cloudflare DNS:
  `v=DMARC1; p=none; rua=mailto:dmarc@tapeline.io; fo=1`, then move to
  `p=quarantine` once a few weeks of reports come back clean.
- [ ] Seed-inbox deliverability test on the Resend domain (still to do — needs
  sending, so founder-gated)
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

# 9g — 2026-09-06, fourth pass: adopt-now, and the thing found underneath it

- [x] **A new account never saw the product** (#767) — signup defaulted to
  `/app/billing?trial=start`, so a brand-new account met a payment decision
  before its first result, on both the email and Google paths. Every free-plan
  competitor checked does the opposite. The founder's own card-wall data already
  said so: three accounts, none carded, none scanned, two never opened the
  payment page. Default is now the scanner; the trial offer moved to a
  dismissible panel above the table with the disclosure wording unchanged. Also
  adds "Or skip the trial and subscribe" on the paid cards, hitting the existing
  checkout without `start_trial` — the one payer bought outright.
  Latent bug found on the way: `app/app/layout.tsx` wrapped only the banners in
  `FirstRunTipProvider`, not `{children}`, so page content read the no-op default
  and no page-level banner could ever yield to the welcome.
- [x] **3,516 ticker pages that no AI could quote** (#768) — they are 91% of the
  sitemap and produce ZERO unbranded AI discovery, while eleven
  `/best-stocks-for/` pages produce all of it. The h1 was a bare symbol, the
  numbers sat in tables, and `article:modified_time` was `new Date()` — render
  time, a lie about freshness. Now: company name in the h1, a dated prose
  restatement of the score, a visible "Updated" line and a real `dateModified`,
  all from the row's own stamp. Plus counted Premium locks ("128 SEC Form 4
  filings in the last 90 days") that are a SEPARATE block and never replace a
  factor's em-dash — those mean missing data, not a paywall, and the page now
  says which is which. Look-up meter counts up from look-up 1.
- [x] **338,015 fabricated congressional disclosures were being served** (#770) —
  found while building those counted locks, because a congressional count could
  not honestly be built. Eight politicians, ~42,000 invented trades each, all
  written 2026-05-03 to 2026-07-18, attributed to real named living people. The
  WRITE path was already gated (`_mock_writes_enabled`); the SERVING path never
  was. Premium got them as disclosures, the free preview served three to every
  signed-in account under a comment saying it existed "to prove the feed is real
  and populated", and the alert evaluator could EMAIL a user that a named
  politician traded a named stock. `congress_integrity.is_publishable()` now
  filters every path including the counts. Suppressed, not deleted.
- [x] **The Premium "Congressional trades feed" claim is removed** (#770) — false
  while the data was fabricated, false again once the feed is honestly empty.

- [ ] **Decide what to do with the 338,015 fabricated rows.** They are suppressed,
  not purged. Deleting them is an operator decision with no undo, which is why an
  agent did not take it. Either purge them or leave them suppressed — but do not
  leave the question open indefinitely, because the next person to read the table
  will see 338,015 rows and assume a populated feed.
- [ ] **Wire real congressional data, or leave the feature retired.** CORRECTED
  2026-09-07 — an earlier version of this item (and a summary given to the
  founder) said the sheet already carries the real trades and only needs
  "wiring up". It does not. `parse_smart_money_csv`'s own docstring is explicit:
  the `SMART MONEY & CONGRESS` tab is free text, not structured rows, which is
  precisely why it boosts `sub_smart_money` by per-ticker appearance count
  instead of building `CongressTrade` rows. A real feed therefore needs a real
  SOURCE — House/Senate disclosure filings, or a licensed vendor — not a
  parser change. That is a build, not a repair, and it is what the Premium
  claim would cost to bring back. Until then Premium is one bullet shorter,
  which is the honest state.
- [x] **`sub_smart_money` was NOT contaminated by the mock generator** —
  checked 2026-09-07, clean. `CongressTrade` appears in exactly seven modules
  (`models/`, `routers/{alerts,congress}.py`, `services/{alerts,
  congress_integrity,sheet_feed}.py`, `workers/signal_publisher.py`) and in
  none of them on a scoring path; `sheet_feed.py`'s only mention of the model
  is inside a docstring. The factor has two inputs — the sheet's appearance
  count and the Finnhub Form 4 cache — and neither reads the `congress_trades`
  table. So the fabricated rows were a SERVING defect only; no published score
  was ever computed from them, and no score needs restating.
# 9h — Shipped 2026-09-07: the factor fix was only half a fix

- [x] **The insider pass had never run once** — found while verifying yesterday's
  coverage fix (#762) against production. `last_fundamentals_at` was stamped on
  1,320 rows and climbing; `last_smart_money_at` was stamped on **0 of 11,781**.
  Not lagging — never executed since the column shipped, so `sub_smart_money`
  (15% of the composite) was NEUTRAL 50 universe-wide and the "check on
  2026-09-13" note would have half-failed.

  The cause was a budget, not an ordering. Both passes ran to a per-run budget
  of `ACTIVE_UNIVERSE_SIZE` = 12,000, which at the mandatory 1.1s Finnhub pacing
  is **3.7 hours for the first pass alone** — so the second only began on a
  process that had already survived 3.7 uninterrupted hours, and production
  restarts on every deploy. Moving the factors to the front (#762) was necessary
  but not sufficient: whichever pass ran second was starved at any position, so
  swapping them would only have moved the hole onto fundamentals.

  Two comment blocks had also under-counted the chain by 5x ("roughly two hours"
  off "per-run budgets of 2,500"), which is how a total starvation read as a
  queue. Both corrected.

  Fix: the passes now ALTERNATE in `_FACTOR_SLICE` (400-row, ~7min) slices under
  a shared phase budget, so one round advances both and a restart leaves them
  within a slice of each other. When both frontiers close, the loop drops to one
  rotation slice each and falls through, so the display-column backfills behind
  it are not held off. Guard: `backend/tests/test_factor_stage_alternation.py`
  (watched red on the reverted worker — all 6).

# 9f — Shipped 2026-09-06, third pass: the three fixes

Founder said fix them. All three merged and deployed. Written in parallel
worktrees, then verified together — which is where the interesting failure was.

- [x] **Leveraged and inverse funds are out of the default view** (#761) —
  yesterday's anonymous top ten had CONX (Direxion Daily COIN Bull 2X) at rank 7
  and BIB (ProShares Ultra NASDAQ Biotech) at rank 8, both labelled STRONG SETUP.
  Nothing in the codebase could detect a geared fund. New `services/leverage.py`
  name predicate (seven rules, ETF-bucket gated, deliberately under-claiming),
  `tickers.is_leveraged` column with a backfill that imports the shipping
  predicate rather than reimplementing it in SQL, excluded by default from the
  scanner, CSV export and MCP `daily_picks` with an `include_leveraged` opt-in.
  **Verified live after deploy: zero leveraged rows in the top ten; DELL and
  Marathon Petroleum took ranks 9-10** — the first recognisable large-caps that
  list has carried. 140 new tests.
- [x] **The scorecard scope change is disclosed on the site** (#761) — the branch
  also stopped geared funds entering the permanent record and said so only in a
  commit message and a code comment. The scorecard's whole value is that a reader
  can check it, so that got a dated `scope` entry on /changelog, stating that
  entries frozen before today stay exactly as recorded and that a comparison
  spanning this date crosses two definitions of what could enter. Worth keeping:
  the obvious justification is FALSE — geared rows are the *calmer* half of the
  record (stdev 6.21 vs 104.89). The argument is consistency, not variance.
- [x] **The ad-lint CI step was green over files it never opened** (#757) — its
  file list ended a line with a literal `\n` where a continuation was meant, so
  bash read it as the filename `n`, and `docs/launch/google-ads/*.md` and `*.txt`
  were never linted while the step reported success. Counted the findings by hand
  rather than trusting either prior claim: **11 findings, 6 false positives, 5
  genuine across 3 real defects** — a runbook describing the removed card wall in
  the present tense, a `"trial ends in 2 days"` countdown in a retargeting brief,
  and a `"free trial"` merge on a card-required trial. #747 had called them "pure
  false positives"; they were not. The linter now exits 2 on a path it was handed
  and could not read — a guard that cannot tell *clean* from *never opened* is the
  whole bug.
- [x] **The composite was a four-factor score for 77% of the universe** (#762) —
  see 9e for the measurement. Fixed as plumbing: warm both caches from the DB on
  boot, gap-first selection with attempt-stamps so a restart resumes instead of
  re-fetching the same rows, factor passes moved to the front of the chain, and
  the API process warms too (it never runs the chain at all, so its caches were
  empty for the life of the process and every sheet webhook blanked both factors).
  Weights, NEUTRAL fallback and the composite floor all untouched. Dated
  `methodology` entry on /changelog; **no scorecard row recomputed or removed.**
- [x] **Two migrations, one head** — both branches independently added a migration
  chained off `0064_scan_logs`. Each passed alone; together they are two heads and
  CI asserts one. Caught on review, renumbered to `0066_factor_stamps` and
  rechained onto `0065_ticker_is_leveraged`. **This is the standing hazard of
  parallel worktrees: verify the combination, never just the branches.**
  Full suite on the merged pair: 2,286 backend, 991 frontend, tsc, mypy, ruff,
  copy linter — all green.

- [ ] **Watch the factor coverage actually converge.** The plumbing is deployed and
  test-verified; the fill is NOT done. NVDA/AAPL/MSFT/SPY still read null on both
  factors minutes after deploy, which is expected — the pass moves ~2,500 rows a
  day against ~11,800 symbols, so a first full sweep is roughly **5 days per
  factor**, and only if the worker gets ~1.5h uninterrupted. What changed is that a
  deploy no longer resets progress. **Check in a week:** the share of scored
  tickers with both factors null should fall from 77%, and `/api/ticker/NVDA`
  should stop returning `fund null / smart null`. If it has not moved by
  2026-09-13, the gap query is not doing what its tests say and this needs
  reopening. Expect the top ten to churn while it converges — that is the ceiling
  coming off, not market movement.

## Answered while checking the list — two items were already done

- [x] **`/api/ticker/{symbol}/history` DOES carry the 7-day delay.** Verified live:
  the anonymous response returns `delay_days: 7`. The open question was stale.
- [x] **The Resend bounce webhook is no longer silent** (#738) — `_warn_resend_secret_missing`
  is on main and fires once per process naming the exact `fly secrets set` command.
  What remains is only the founder setting `RESEND_WEBHOOK_SECRET`, which is
  recorded under §5 rather than as an engineering item.

# 9e — 2026-09-06: the deep dive, and what it found under the floorboards

A nine-angle competitor teardown (onboarding, retention, pricing, score
presentation, content, distribution, trust, community, core UX), each angle's
adaptable claims re-verified against the live competitor sites, then synthesised.
Three findings below are not "adapt from a competitor" items at all — they are
things the teardown tripped over in Tapeline itself, each verified by hand.

- [x] **The billing page showed a first-charge date sixteen days early** (#745,
  after #744 from another session fixed the /pricing and /legal/refund copies).
  `app/app/billing/page.tsx` — the page that STARTS a trial — kept its own
  `const TRIAL_DAYS = 14` after the backend moved to 30. It computed and rendered
  the first-charge date as now + 14, labelled the CTA "Start the 14-day trial",
  and its test hardcoded 14 too, so the assertion vouched for its own fixture.
  Nine more "charge on day 14" claims survived the sweep (pricing FAQ, refund
  policy ×3, how-it-works, daily-picks, whats-new ×2, three blog posts). A dated
  22-Aug changelog entry had been rewritten to "30-day trial … first charge on
  day 14" — restored. Guard: `__tests__/singleTrialLengthSource.test.ts`.

- [ ] **P1 — The composite is a FOUR-factor score for ~77% of the universe, and
  that — not the market — is why the record has zero mega-caps.** Verified
  2026-09-06 by read-only SQL + live API. `_FUND_SCORE_CACHE` and
  `_SMART_MONEY_SCORE_CACHE` are in-process dicts filled by stages 3–4 of the
  ~2-hour serial Finnhub chain (`_serial_finnhub_refreshes`); the latches are
  in-memory too, so **every deploy wipes both caches and restarts the chain
  from stage one** (its own comment: stages four and five "were NEVER reached").
  The fundamentals stage selects by dollar volume, not `WHERE … IS NULL`, so a
  restart re-fetches the same rows instead of resuming. `composite_from_factors`
  substitutes NEUTRAL 50 per missing factor (deliberate), so with 30% of the
  weight pinned the max reachable score is 85, and to clear today's cutoff of
  81.1 the four live factors must average 94.4.
  Measured: 7,316 scored tickers, **77% with both factors null**; of 1,033
  scored names ≥ $10B, **1,001 (97%)**; highest score any both-null ticker has
  EVER reached: **80.2**, below the cutoff, while all 16 above it have full
  coverage. Even on the exact 2,500 rows the pass targets, fundamentals are
  filled for 36% and for 22 of 364 mega-caps. AAPL/NVDA/MSFT/AMZN/META/TSLA/SPY
  all null on both; sheet-governed DSX/PLX full. `percentile.py` documents
  "~15% coverage" as intended for the *percentile* display; the composite
  ceiling is the undocumented consequence.
  **The fix is plumbing, not methodology** — weights unchanged, inputs that were
  always meant to be filled get filled: (1) warm both caches from
  `Ticker.sub_fundamentals` / `sub_smart_money` on boot, or persist them;
  (2) make stages 3–4 self-gating on NULL like stages 1–2 so restarts resume;
  (3) spread the 2,500 cap over days. It changes published scores for ~5,600
  tickers → **needs a `/changelog` entry**; the record stays append-only. ~1 day.
  This supersedes the "second cap-filtered record" idea from the 05-Sep sweep:
  a cap-filtered list built on four-factor scores would be honest only if
  labelled as such. Fix the inputs first. Memory:
  `tapeline_factor_cache_wiped_by_deploys.md`.

- [ ] **Two leveraged ETFs in today's anonymous top 10, labelled STRONG SETUP.**
  Rows 7–8 on 2026-09-06: CONX (Direxion Daily COIN Bull **2X**) and BIB
  (ProShares **Ultra** NASDAQ Biotech). A first-time visitor's first result is
  a 2× leveraged crypto-miner fund. No leveraged/inverse detection exists
  anywhere in `backend/app` (grep: only mock_feed names). Cheapest fix: a
  name-pattern flag (`\b(2X|3X|Ultra|UltraShort|Bull|Bear|Daily .* Bull)\b`)
  excluded from the default anonymous view with an "include leveraged" toggle,
  same shape as the existing liquidity-floor toggle. Also row 1 (DSX) renders
  sector "Uncategorized". Hours.

- [ ] **A brand-new account is routed to the trial-offer fork before it ever
  sees the scanner.** Verified from source: `signup/page.tsx` `postAuthNext`
  defaults to `/app/billing?trial=start` (via `/app/onboarding`) when there is
  no `?next=` and no plan intent — on both the email and OAuth paths. Every
  competitor with a free plan (Stock Rover, Simply Wall St, Stock Unlock,
  TradingView, Danelfin, Koyfin) drops a new account straight into the product;
  none interposes a payment decision before the first result. Fix: default to
  `/app/scanner` and render the existing `TrialOfferPanel` as a dismissible
  panel above the table (the `FirstRunTip` context already coordinates banner
  yielding); keep `?plan=` routing for /pricing intent. Hours. Compliance:
  none — the disclosure moves, its wording does not change.

- [ ] **The anonymous visitor cannot touch the scanner at all** —
  `/app/scanner` 307s to `/signin`. Finviz, TradingView, StockAnalysis, Simply
  Wall St and WallStreetZen all open their screener logged-out on a
  recognisable universe with a live match count. Serve the route logged-out
  with the top 10 open and rows 11–25 masked Danelfin-style (symbol hidden,
  scores shown), and show "Showing 10 of 1,987 matching" instead of the cap.
  Days. Depends on the two items above for the first ten rows to be names a
  visitor recognises.

# 9d — Shipped 2026-09-05, second pass

Triggered by handing the ad account to an external team, which surfaced a
compliance gap nobody had tested for.

- [x] **The copy linter caught none of the ad copy it was supposed to** (#735) —
  twelve lines a performance marketer writes reflexively, including
  `COMPLIANCE_COPY_RULES.md`'s OWN two flagship bad examples, all passed:
  `0 blocking findings`. So "run the linter before you ship" — the natural
  instruction to an agency — was worthless. New `--ads` mode is a second,
  stricter pass: it applies the ad-vocabulary rule to any file named on the
  command line (the `docs/ads/**` path gate meant that rule had **never once
  run in CI**), unmasks the score-band names, and adds eight rules. Result on
  the same twelve lines: 12 findings across 10 rules. On fourteen compliant
  rewrites: zero — that second number is what stops an agency switching it off.
  `signals?` was missing from the vocabulary list entirely and is now added.
- [x] **The Resend bounce webhook was silently inert** (#738) — its docstring
  claimed "we log once per process at module load (further down)". There was no
  such log anywhere in the file; the sentence describing the safeguard was the
  entire safeguard. This endpoint is the only thing that marks an address
  undeliverable, so inert it means we keep mailing hard-bouncing addresses and
  the sending domain's reputation degrades invisibly. Now warns once per
  process, naming the exact `fly secrets set` command.
- [x] **Sales had no route on the contact page** (#738) — `PricingTable`
  advertises `sales@tapeline.io` for 5+ seats and the $59 Trader plan's ONLY
  CTA is "Talk to us" → `/contact`, which listed support, press, legal, privacy
  and security. Both highest-revenue paths on the site ended on a page that did
  not list the address they had just named.
- [x] **Deliverability audited** (read-only DNS, no change needed to SPF/DKIM) —
  see the new DMARC item below for the one thing that is actually wrong.

# 9c — Shipped 2026-09-05

Found by a ten-agent audit of the founder's five strategic items, every verdict
independently challenged. The challenge phase corrected two of the five, and one
of its own corrections was wrong — recorded here because the near-miss is the
useful part.

- [x] **The crypto guard only knew two spellings** (#729) — #715 dropped rows whose
  Asset Class normalises to `crypto`, which covers only the spellings already in
  the map. `token`, `digital asset` or any new icon normalised to None, passed the
  guard, and published at the token's price. Now fails closed on any class it
  cannot read, while blank still passes (sheet-governed ETFs leave it empty by
  design). Watched failing first: 7 red, 15 green.
- [x] **Migration 0063 claimed something false** (#729) — it said deleting the four
  collision rows would let `_refresh_universe` re-create them. Verified live: all
  four still 404. They are **correctly** absent — EOS/BGB/LEO are closed-end funds
  that `VENDOR_TYPE_TO_ASSET_CLASS` excludes on purpose, and SOL (Emeren) was
  delisted from the NYSE on 2025-12-15 when it went private. An audit read this as
  a P0 regression I had caused. **It is not one — do not go looking for it.**
- [x] **Seven paste-ready growth files still carried the retired card block** (#730)
  — `docs/**` sits outside the copy linter's include globs, so #686 could not reach
  them and they kept instructing their own reader to write the claim #686 removed
  from 42 files. Two body lines had already been generated from it.
- [x] **Homepage newsletter chip** (#730) — `Free · no card` sat directly above "Not
  ready for a trial?" and ~300 lines from the binding sentence. Now
  `Free · no account`. The homepage fine-print and PricingTable were also flagged
  as live exposures and are **not** — both already bind the two facts adjacently.
- [x] **Roadmap promised crypto "scored on the same framework"** (#730) — two of the
  six factors have no crypto analogue, so ~45% of the weight would be constant and
  no token could exceed 77.5/100. Reworded.
- [x] **The deep dive contradicted its own correction** (#731) — §1, §4.6 and action
  row 11 all said stop Meta on 7 September, on a promo-revert premise that the
  doc's own correction C2 refutes. §1 is the half a reader acts on first. All three
  now say run to the 15th, with the retractions left visible.
- [x] **Lawyer brief + both vendor letters SENT** (#727) — see §7. The lawyer address
  was the real blocker: Holley Nethercote publish no email address anywhere and
  their contact form renders no fields at all.

**Where the five strategic items actually stand.** Comparison pages DONE (18 gone,
410 + noindex, 165 stock-vs-stock survived). Ads PARTIAL — A$1,074.53 lifetime spend,
zero payers, tracking now genuinely fixed. Scale strategy ANSWERED but not actioned,
and gated on the 0/6 interview count. Trading ANSWERED, brief now sent. Crypto and
world markets ANSWERED — neither is reachable without a commercial data licence,
which is exactly what the vendor letters are now asking the price of.

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
