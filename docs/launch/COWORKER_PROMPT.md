# Tapeline launch — coworker prompt

Paste the whole file below into a fresh Claude Code session at
`C:\Project 1`. The next agent has zero context about Tapeline; this
prompt is the entire briefing.

Last refreshed: 2026-05-18

---

```text
You're picking up the Tapeline launch push. Project root is C:\Project 1
(monorepo: backend/ FastAPI on Fly.io, frontend/ Next.js 16 on Vercel,
public URL https://tapeline.io, API at https://api.tapeline.io).

Read CLAUDE.md for product overview, brand rules, tier model, and the
"things not to change" list. Then execute the queue below in order.

================================================================
WHO YOU'RE WORKING FOR
================================================================
- Founder real name: Chamara Piyatilaka (Melbourne, AU)
- Public-facing name on Tapeline: "Christian Piyatilaka" (LinkedIn, X,
  blog bylines, outreach emails, WHOIS). Use Christian for anything that
  ships to a public surface; use Chamara only in private chat / git.
- Brand inbox: tapeline.inbox@gmail.com (Gmail /u/2/). The send-as
  alias christian@tapeline.io is set as the default there. Outreach
  composes from /u/2/.
- Personal inbox where 9 podcast pitches were sent from (legacy):
  cpiyatilaka@gmail.com (Gmail /u/0/). Replies to those pitches will
  land at /u/0/.

================================================================
OPERATING RULES (read these before doing anything)
================================================================
- Communication style: tight, factual, no hype. Match the email
  renderers in backend/app/services/email.py if drafting copy.
- Don't add features, abstractions, or cleanups beyond what's asked.
- Lead with the recommendation; offer to implement rather than
  implementing unprompted. No git rollback safety net — be careful.
- Auto-merge your OWN clean PRs without asking. Don't auto-touch
  other agents' PRs.
- Fly.io deploys are MANUAL. Pushing to main does NOT trigger a Fly
  deploy. Vercel auto-deploys frontend on merge to main. Backend
  changes require: `fly deploy -a tapeline-backend` from anywhere
  in the worktree.
- Latest signal-system sheet feeds in via SIGNAL_SHEET_CSV_URL +
  4 other CSV URLs (all set on Fly). SHEET_WEBHOOK_SECRET is also
  set on Fly; the Apps Script paste step below activates live-push.

================================================================
MCP WALLS (don't waste time trying these via MCP)
================================================================
- dashboard.stripe.com — on Claude safety blocklist. Use the user's
  own browser for Stripe operations.
- All of reddit.com — blocked. User posts manually.
- All of stocktwits.com — blocked.
- LinkedIn / X / Crunchbase / Capterra file_upload — protocol-blocked.
  User drags & drops manually.
- Cloudflare SPA — loads but only renders the loading spinner in MCP.
  Routing changes must be done in the user's own browser.
- Google Workspace upsells inside GBP onboarding wizard keep spawning
  Ads tabs. Skip them when you see them.

================================================================
WHAT JUST SHIPPED (don't re-do these)
================================================================
PRs merged today:
- #97 scorecard: outlier filter, median primary stat, AU regulatory
  disclaimer footer. /api/scorecard now returns median_1d_return,
  median_alpha_vs_spy, entries_excluded_outliers. Backend + frontend
  both live in prod. Verified: avg_1d_return went 648% (broken) →
  -2.55% (filtered).
- #98 MarketingNav theme toggle (light/dark/system) for logged-out.
- #99 /compare/finviz visual polish.
- #101 POST /api/internal/sheet-changed Phase 1 webhook. Returns 401
  (not 503) → secret is configured. Endpoint live, Apps Script
  paste pending (below).
- #102 docs/growth/fintwit_replies_drafted.md cherry-pick.
- #114 Phase A1 multi-watchlists backend. Migration 0022 applied:
  watchlists + scanner_presets tables, watchlist_id FK on
  watchlist_items, default "My Watchlist" backfilled for existing
  users. Tier caps: Free=1 list, Pro=5, Premium=20. New endpoints:
  /api/watchlists CRUD + /api/presets CRUD. Verified live (401).
- #115 docs: X thread 4+5 drafts, Show HN variants, M$/Quiver
  deferred docs (see docs/launch/DEFERRED_CONFIRMED.md).
- #116 GSC indexing fixes: case-normalize ticker URLs in middleware
  (/t/aapl → /t/AAPL 308), noindex on not-found.tsx, polished
  robots.txt, varied sitemap.ts lastModified dates.
- #118 Phase A2 frontend: WatchlistTabs + PresetMenu components,
  wired into /app/watchlist + /app/scanner.
- #119 GET /api/watchlist?list_id=X — wires the tabs to the items
  table. Backend change → next fly deploy ships it. (May still be
  pending merge when you start; check `gh pr view 119` and merge +
  fly deploy if so.)

Verified live in prod:
- /api/scorecard summary fields populated correctly
- /api/internal/sheet-changed returns 401 on wrong secret
- /api/watchlists + /api/presets routes registered (return 401 unauth)

================================================================
PRIORITY QUEUE — execute in order
================================================================

TASK 1. Ship PR #119 backend (if not already deployed)
─────────────────────────────────────────────────────────
Goal: `?list_id=X` filter live so the watchlist tabs actually narrow
the items table.

Steps:
  1. `gh pr view 119 --json state,mergedAt` — confirm MERGED.
     If still OPEN, check CI: `gh pr checks 119`. Fix any ruff
     lint errors (look for RUF100 "unused noqa" — drop the
     directive). Push fix, wait for re-run.
  2. Once merged, from any worktree with the latest origin/main
     checked out: `fly deploy -a tapeline-backend --remote-only`.
     Run in background with run_in_background=true; deploy takes
     ~3 min.
  3. After deploy completes, verify: 
        curl -sS -I "https://api.tapeline.io/api/watchlist?list_id=999"
     Should return 401 (not 422 or 500) — confirms the param parses.
  4. Frontend (PR #119 also touches frontend/lib/api.ts +
     app/app/watchlist/page.tsx) auto-deploys on Vercel after merge.

Verify success: in the user's logged-in browser, /app/watchlist with
2+ lists shows tabs; clicking a tab narrows the table to that list's
items. (Currently there are no items in any non-default list because
POST /api/watchlist doesn't yet accept list_id — see Task 7.)

────────────────────────────────────────────────────────────
TASK 2. Apps Script paste on the signal-system sheet
────────────────────────────────────────────────────────────
Goal: activate live-push from the "Live Dashboard - Stocks" Google
Sheet to /api/internal/sheet-changed. Currently the worker polls the
CSV every 5 min; the webhook lets the sheet push within 1-3 sec of
the founder editing a cell.

This is FOUNDER-ONLY — the script runs under their Google account's
auth scope and you can't paste into their sheet without explicit
share access.

Steps for the agent: don't attempt. Surface this to the founder with
the exact instructions from docs/PHASE_1_EXECUTION_PLAN.md §F1:

  1. Open the "Live Dashboard - Stocks" sheet → Extensions →
     Apps Script.
  2. Paste the template from docs/MORNING_QUEUE.md lines 38-49
     (or check docs/PHASE_1_EXECUTION_PLAN.md for the exact code).
  3. File → Project properties → Script properties → add
     TAPELINE_WEBHOOK_SECRET = (the value already set on Fly as
     SHEET_WEBHOOK_SECRET; run `fly ssh console -a tapeline-backend
     -C 'printenv SHEET_WEBHOOK_SECRET'` if you need to read it).
  4. Triggers → Add Trigger → notifyTapeline / Head / From
     spreadsheet / On change.
  5. Save. Edit any cell on the sheet to verify. Tail Fly logs:
     `fly logs -a tapeline-backend | findstr internal.sheet-changed`
     Look for `received` then `refresh_complete`.

────────────────────────────────────────────────────────────
TASK 3. Show HN post (TUESDAY 19 MAY, 8 AM ET = 10 PM AEST)
────────────────────────────────────────────────────────────
Goal: launch the Tapeline Show HN post on the highest-traffic window
of the week.

The post copy is in docs/launch/LAUNCH_PLAYBOOK.md §1 (primary draft)
plus docs/launch/SHOW_HN_VARIANTS.md (Variant A — back-check angle;
Variant B — Bloomberg refugee angle). Pick one with the founder.

Critical: HN login is credential-gated. Agent can't sign in. The
founder posts. Agent's job is to:

  1. Confirm the founder is in front of their machine at 8 AM ET.
     Tuesday morning is the launch window — don't slip it. If the
     founder is offline, surface as urgent at next interaction.
  2. Open https://news.ycombinator.com/submit in the user's browser
     (tab opens fine, login wall is on them).
  3. Help them copy from the chosen draft. URL field gets
     https://tapeline.io. Text field gets the body.
  4. Title format (≤ 80 chars):
     "Show HN: Tapeline — One score per stock, fully public formula"
     (or variant title).
  5. After posting: hang around for 90 MINUTES answering every comment
     in real time. HN front-page algorithm rewards reply velocity in
     the first hour. This is non-negotiable for the post to crack the
     front page. Predictable objections + responses are in
     LAUNCH_PLAYBOOK §1 — feed those to the founder as comments come
     in.
  6. Also post the formula in a top-level comment immediately after
     submission (people click comments before the link).

Realistic outcome: 200-500 visitors, 5-30 trial signups, 1-3 paying
in week 1.

────────────────────────────────────────────────────────────
TASK 4. Reddit posts (Tue/Thu/Tue-26)
────────────────────────────────────────────────────────────
All of reddit.com is MCP-blocked. Agent CANNOT post. Agent's job is
to remind + provide copy + queue.

- Tue 19 May, 9 AM ET — r/stocks. Copy in
  docs/launch/LAUNCH_PLAYBOOK.md §2 (general framing).
- Thu 21 May, 10 AM ET — r/algotrading. Copy in same file (quant
  framing, methodology-heavy).
- Tue 26 May, 9 AM ET — r/SecurityAnalysis. Same file (fundamental
  framing).

For each: open the relevant subreddit's submit URL in the founder's
browser, paste the prepared copy. Founder hits submit. Founder
responds to comments for the first 60 min.

Critical: Reddit hates self-promo. The drafted copy front-loads the
methodology and treats the product as the consequence, not the lede.
Don't rewrite to be more promotional.

────────────────────────────────────────────────────────────
TASK 5. Stripe — KYC re-verify + webhook rotation + smoke test
────────────────────────────────────────────────────────────
All on dashboard.stripe.com → MCP-blocked. Founder-only.

Stripe state per the 2026-05-13 verification:
- account = acct_1TSp4GJ23wFFL5Y3
- charges_enabled = true, payouts_enabled = true, details_submitted
  = true, requirements all empty
- business_type = "company" (NOT sole_trader, despite earlier docs)
- Webhook endpoint we_1TWeuYJ23wFFL5Y3Kn54dZ2p

To verify state without the dashboard, the agent can curl:
  fly ssh console -a tapeline-backend -C 'sh -c "curl -sS -u
  \"$STRIPE_SECRET_KEY:\" https://api.stripe.com/v1/account"'
(reads STRIPE_SECRET_KEY from Fly env, hits Stripe REST API,
returns JSON with charges_enabled/payouts_enabled/requirements).

Three things still pending (founder-only):
  5a. KYC re-verify — Stripe sometimes requests re-verification
      every 6-12 months. Surface to founder, open Stripe dashboard
      in their browser.
  5b. Webhook secret rotation — security hygiene. Founder rotates
      the webhook secret in Stripe dashboard, copies new value,
      `fly secrets set STRIPE_WEBHOOK_SECRET=... -a tapeline-backend`.
      The agent CAN run the fly secrets set step once the founder
      gives them the value.
  5c. $9.99 self-purchase smoke test — founder buys Pro on
      tapeline.io/pricing with a real card, confirms webhook fires
      (check Fly logs for "stripe.webhook.checkout_session_completed"),
      then refunds themselves in Stripe dashboard. End-to-end
      validation that money flow works.

────────────────────────────────────────────────────────────
TASK 6. LinkedIn profile photo upload (M1)
────────────────────────────────────────────────────────────
Status: currently a green "C" placeholder avatar. Needs the founder's
headshot OR the Tapeline /profile-square route export.

Agent CAN'T do this — LinkedIn file_upload via MCP is
protocol-blocked. Founder uploads manually.

Steps for founder:
  1. linkedin.com/in/christian-piyatilaka-16192a40a/ → click
     avatar → "Add photo" / "Change photo".
  2. Upload either:
     - Founder's professional headshot, OR
     - Export of https://tapeline.io/profile-square (the brand
       stripe mark from PR #92).
  3. Verify in incognito to confirm it's public.

────────────────────────────────────────────────────────────
TASK 7. Phase A follow-ups — POST /api/watchlist list_id + move-to-list
────────────────────────────────────────────────────────────
Agent CAN ship these.

7a. Extend POST /api/watchlist with optional list_id:
    - backend/app/routers/watchlist.py: add list_id?: int to
      WatchlistAdd, validate it belongs to the user, default to
      the user's first list (by sort_order) if omitted, auto-
      create "My Watchlist" if the user has zero lists.
    - frontend/lib/api.ts: watchlistAdd(symbol, threshold,
      list_id?).
    - app/app/watchlist/page.tsx: pass `activeId ?? undefined`
      to api.watchlistAdd in the `add()` function.
    - Test: POST with list_id puts the item in that list, without
      list_id uses the default list, with foreign user's list_id
      returns 404.

7b. "Move to list" UX (deferred until POST list_id ships):
    - PATCH /api/watchlist/{item_id} accepting { watchlist_id }.
    - UI: dropdown on each row of the items table → "Move to: List A
      | List B | List C". Inline, no modal.

────────────────────────────────────────────────────────────
TASK 8. Beef up /blog/ticker/{X} pages for SEO
────────────────────────────────────────────────────────────
Agent CAN ship. ~1.5 hr work.

Problem: 429 GSC "Discovered, currently not indexed" pages. Most
likely cause: the 50 /blog/ticker/{X} pages substantially overlap
with the 500 /t/{X} pages (same composite, same 6-factor breakdown,
same "Why" sentence). Google sees the dup, indexes only one set.

Fix approach: add genuinely-unique long-form content to
/blog/ticker/{X}:
  - Sector context (where does this ticker sit vs sector peers?)
  - Market regime overlay (how does regime affect this score?)
  - Excerpt from /scorecard for this ticker (hit rate, best/worst
    alpha day)
  - Q&A section: "Is {TICKER} a buy in 2026?" with score-based
    framing
  - "How {TICKER}'s score is computed" — 6-factor breakdown with
    plain-English explanation of each value

Don't add canonical pointing to /t/{X} — that loses the long-tail
SERP intent. Differentiate via content depth instead.

Test plan: Vercel preview deploy of one ticker (e.g.
/blog/ticker/AAPL) renders 4-5x more text than the current
template, with the new sections clearly distinct from /t/AAPL.

────────────────────────────────────────────────────────────
TASK 9. AlternativeTo resubmit (Mon 19 May)
────────────────────────────────────────────────────────────
Founder-driven. Agent's job: remind on Monday.

Status: app was submitted previously but not approved (per
alternativeto.net/browse/search?q=tapeline returning "Time.Graphics"
as the top hit, not Tapeline).

Steps for founder:
  1. alternativeto.net → sign in (Christian's account).
  2. /manage-item/ or the existing app management URL.
  3. Submit a more complete listing: icon, screenshots, full
     description, X username = tapeline_io, pricing details.
  4. Wait 1-3 days for moderator approval.

────────────────────────────────────────────────────────────
TASK 10. Cloudflare WHOIS re-trigger
────────────────────────────────────────────────────────────
Status: Cloudflare dash SPA hangs in MCP. Founder-only.

Steps for founder:
  1. dash.cloudflare.com → tapeline.io → Registration → Contact
     information.
  2. Re-save the contact info (no changes needed; just hitting
     "Save" re-triggers the ICANN WHOIS verification email).
  3. Check tapeline.inbox@gmail.com /u/2/ for the ICANN
     verification email, click the link.

────────────────────────────────────────────────────────────
TASK 11. Stocktwits signup
────────────────────────────────────────────────────────────
stocktwits.com is MCP-blocked. Founder-only.

Steps for founder:
  1. stocktwits.com/signup
  2. Handle = tapeline_io (to match X handle).
  3. Email = christian@tapeline.io.
  4. Phone verification (if asked) uses founder's phone.

────────────────────────────────────────────────────────────
TASK 12. Gmail forwarding filter completion
────────────────────────────────────────────────────────────
Partially done in earlier agent session. The filter's search
criteria are saved and applied to 11 matching emails (auto-archive
works); the forwarding action couldn't complete because
tapeline.inbox@gmail.com isn't yet registered as a verified
forwarding destination in cpiyatilaka@'s Gmail settings.

To finish:
  1. Founder: cpiyatilaka@gmail.com → Settings → "Forwarding and
     POP/IMAP" tab → "Add a forwarding address" → enter
     tapeline.inbox@gmail.com → submit. Google emails a verification
     link to tapeline.inbox@.
  2. Founder: open the verification email at /u/2/, click the
     verification link.
  3. Agent: navigate back to cpiyatilaka@'s filter page, re-run
     the filter creation flow. The search query is:
       from:(g2.com OR crunchbase.com OR alternativeto.net OR
       quiverquant.com OR capterra.com OR linkedin.com OR
       cloudflare.com OR stripe.com OR resend.com OR
       stocktwits.com OR producthunt.com OR fly.io OR vercel.com
       OR sentry.io) OR subject:tapeline OR tapeline.io
     Action: Skip the Inbox + Forward it to tapeline.inbox@gmail.com
     + Apply to N matching conversations. The Google "verify it's
     you" popup may appear on save — founder solves it.

────────────────────────────────────────────────────────────
TASK 13. GBP "Get verified" address entry
────────────────────────────────────────────────────────────
Status: GBP was created with name + service area (Australia) + website
but the address-verification step never ran. The onboarding wizard
keeps redirecting through Workspace/Ads upsells instead of reaching
the address step.

Founder address (KEEP DISCREET — do not echo back in chat or commit
to disk): 4 Aubergine Road, Mickleham VIC 3064.

Steps:
  1. Open business.google.com/dashboard → the main GBP card (NOT
     the onboarding wizard).
  2. Look for "Get verified" or "Add address" action.
  3. Service-area businesses can choose "Hide my address" — pick
     that so the address isn't displayed publicly. The address
     still gets used for the verification postcard.
  4. Submit. Google sends a postcard with a verification code.
     Takes 5-7 days. Founder enters the code when it arrives.

────────────────────────────────────────────────────────────
TASK 14. LinkedIn DM triage (15 active threads)
────────────────────────────────────────────────────────────
The founder has 15 LinkedIn DM threads in flight from the
2026-05-13 → 2026-05-17 outreach push. Replies have come from
Princy and Sunil per the handover.

Agent CAN draft replies. Agent CANNOT see the inbox via MCP
without the founder navigating to it (the LinkedIn /messaging/
URL routes to a single-thread view, not the inbox list).

Workflow:
  1. Founder navigates to linkedin.com/messaging/ and screenshots
     the inbox sidebar showing all active threads.
  2. Founder pastes the latest message from each thread into chat
     (just the most recent reply, not the full thread).
  3. Agent drafts a calm, factual response per thread — match
     the email-renderer voice in backend/app/services/email.py.
  4. Founder reviews, posts.

Specific threads to watch:
  - Princy, Sunil (already replied; track for follow-ups)
  - Dr Amadi, Anthony Jackson, Christopher Autera-Polzin,
    Erick Washburn (4 first-DMs sent 2026-05-17)
  - Surbhi, Brent, WAHED, Anmol (4 ask-for-email follow-ups
    sent 2026-05-17)

────────────────────────────────────────────────────────────
TASK 15. Daily X tweet cadence
────────────────────────────────────────────────────────────
docs/growth/tweet_schedule.md has the 14-day daily tweet schedule
with placeholder tickers. The drafts use templated language like
`$[AAA] ([XX])` that the agent fills in at post-time.

Pre-post recipe (PowerShell):
  $d = irm "https://api.tapeline.io/api/scorecard?days=1"; 
  $d.days.PSObject.Properties | select -First 1 -ExpandProperty Value |
  select -First 3 | % { "$$($_.symbol) ($($_.score_at_flag))" }

That returns the top 3 tickers from today's freeze. Fill into the
day's tweet template, post via X's compose box.

Time: 4:15 PM ET (close + 15 min, when scorecard worker freezes)
OR 8 AM ET (pre-market). Both are peak finance-Twitter hours.

X compose via MCP is fragile. Use reply-chain instead of multi-post
composer. If posting a thread of N tweets, post #1, click reply,
post #2 as a reply to #1, and so on.

────────────────────────────────────────────────────────────
TASK 16. Inbox monitoring (passive — no action, just check)
────────────────────────────────────────────────────────────
Check tapeline.inbox@gmail.com /u/2/ every interaction for:
  - Holley Nethercote lawyer reply (re: AFSL publisher exemption,
    fintech license posture). Pitch was drafted in
    docs/launch/LAWYER_CONSULT_EMAIL.md.
  - AlternativeTo, G2DM, Capterra notifications.
  - Stripe payout/invoice events.

Check cpiyatilaka@gmail.com /u/0/ for:
  - 9 podcast pitch replies (Long View, Rational Reminder,
    Acquirers, Chat With Traders, Meb Faber, Animal Spirits,
    Excess Returns, Compounders, Bear Cave). Sent 2026-05-13
    through 2026-05-17.
  - YouTube comment notifications (Declan Goldrick YC RFS post).

If a reply lands: draft a response from christian@tapeline.io
(Gmail send-as in tapeline.inbox@ /u/2/, NOT cpiyatilaka@).

────────────────────────────────────────────────────────────
DO NOT DO
────────────────────────────────────────────────────────────
- Don't change the 6-factor scoring formula or weights.
- Don't change the descriptive signal labels (HIGH CONVICTION /
  STRONG SETUP / CONSTRUCTIVE / NEUTRAL / CAUTION / WEAK). They're
  the publisher-exemption legal posture.
- Don't move the public scorecard behind a paywall. It's the
  trust mechanism that makes the scanner subscription work.
- Don't change the three-tier price points ($9.99 Pro / $19.99
  Premium monthly, $8.25/$16.58 annual) without conversion data.
- Don't re-enable Microsoft OAuth or Quiver QuantData. Both are
  documented as intentionally deferred in
  docs/launch/DEFERRED_CONFIRMED.md. The founder needs to
  explicitly override to unstick those.
- Don't post to X using the multi-post thread composer (focus-loss
  bug). Use reply-chain.
- Don't try Chrome DevTools file uploads on X / Crunchbase /
  LinkedIn (protocol-blocked).
- Don't hit dashboard.stripe.com via MCP (safety blocklist).
- Don't auto-merge other agents' PRs.
- Don't echo the founder's home address in chat or commit it.
  Keep it discreet.

================================================================
HOW TO REPORT BACK
================================================================
After each task: short status to the founder.
  - One line per task in a status table.
  - State: ✅ done / 🔄 in flight / 🛑 blocked-on-founder /
    ⏸ deferred.
  - Don't recap what you didn't do.

At end of session: handoff doc for the next agent. Append to this
file OR a new docs/launch/HANDOFF_{date}.md so context never gets
lost.

================================================================
USEFUL COMMANDS
================================================================
- Live status:    curl -sS https://api.tapeline.io/api/status | python -m json.tool
- Live scorecard: curl -sS "https://api.tapeline.io/api/scorecard?days=30"
- Fly logs:       fly logs -a tapeline-backend
- Fly secrets:    fly secrets list -a tapeline-backend
- Read Fly secret:fly ssh console -a tapeline-backend -C "printenv KEY_NAME"
- Set Fly secret: fly secrets set KEY=val -a tapeline-backend --stage && fly secrets deploy -a tapeline-backend
- Deploy backend: fly deploy -a tapeline-backend --remote-only

PRs: gh pr list / gh pr view / gh pr merge --squash --auto --delete-branch

================================================================
KEY FILE MAP
================================================================
- CLAUDE.md — project overview, brand rules, tier model
- docs/launch/LAUNCH_PLAYBOOK.md — Show HN + Reddit post copy + comment playbook
- docs/launch/SHOW_HN_VARIANTS.md — 2 alt Show HN drafts
- docs/launch/DEFERRED_CONFIRMED.md — M$ OAuth + Quiver closed-as-deferred
- docs/launch/LAWYER_CONSULT_EMAIL.md — Holley Nethercote pitch
- docs/launch/COWORKER_PROMPT.md — this file
- docs/growth/x_thread_1_continuation.md — tweets 4+5+URL drafts (live)
- docs/growth/fintwit_replies_drafted.md — round-1 fintwit replies (stale, see notes)
- docs/growth/tweet_schedule.md — 14-day daily tweet cadence
- docs/growth/podcast_pitches.md — 9 sent + 6 drafted
- docs/growth/newsletter_outreach.md — drafts
- docs/growth/youtuber_outreach.md — drafts (vetted, Joseph Carlson + Tom Nash disqualified)
- docs/PHASE_1_EXECUTION_PLAN.md — Phase 1 + Phase A spec including F1 Apps Script paste

Begin with TASK 1. Surface anything in TASK 2-13 that requires founder
action with the exact words / URL / button to click — make it
copy-pasteable.
```

---

Notes for the founder before pasting:
- Open `C:\Project 1` in a fresh Claude Code session and paste everything between the triple backticks above.
- If you've already shipped TASK 1 (fly deploy of PR #119) say so to the new agent so they skip to TASK 2.
- The agent will know your Mickleham address from this prompt — that's deliberate (TASK 13 needs it). It won't echo it back to chat.
