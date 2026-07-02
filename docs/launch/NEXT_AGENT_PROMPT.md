# Prompt to paste into Claude Code (or any local CLI-capable agent)

Project root: `C:\Project 1`. Read `CLAUDE.md` first for product context,
brand rules, tier model, and "things not to change". Then execute the
queue below in order.

## Today's state (as of 2026-05-19 ~11 AM AEST)

**Already shipped today** (verified live in prod via OpenAPI schema):
- PR #119 + #124 + #126 + #123 + #125 — Phase A multi-watchlists end-to-end
  (`POST /api/watchlist list_id`, `PATCH /api/watchlist/{id}` move-to-list,
  `GET /api/watchlist?list_id=X` filter), `/blog/ticker/{X}` SEO buildout,
  site-wide light-mode polish, X/LinkedIn thread drafts in docs.
- Google Analytics 4 wired (G-YRK73W9NS9 + sign_up + start_trial events).
- Multi-watchlist UX is end-to-end functional in /app/watchlist.

**Launch decisions made today:**
- Show HN — **HELD.** HN globally restricted Show HNs at /showlim. Pivot to
  Reddit + X + LinkedIn instead. Revisit Show HN later if HN lifts.
- Cloudflare WHOIS — founder re-saved contact info manually, waiting on
  ICANN postcard verification email in tapeline.inbox@/u/2/.

**Decisions to revisit by week's end:**
- Stripe webhook secret rotation (founder must do at dashboard.stripe.com,
  paste new value back to agent).
- Lawyer consult (Holley Nethercote, ~$400-800 — higher priority since
  docs/LICENSE_AUDIT.md confirmed Polygon/Massive Starter + Finnhub Free
  are "personal/non-business only").

## Queue — execute in order

### TASK A. Apps Script live-push webhook (CLI part only — ~3 min)

Founder generated webhook secret: `ggx-wsXGvgvbhlsAPOXb-75U_OybBy6acxveO0pCaIQ`.

Run from PowerShell:

```powershell
cd 'C:\Project 1'
fly secrets set SHEET_WEBHOOK_SECRET=ggx-wsXGvgvbhlsAPOXb-75U_OybBy6acxveO0pCaIQ -a tapeline-backend
fly deploy -a tapeline-backend --remote-only
```

Verify deploy completed by curling
`https://api.tapeline.io/openapi.json` and confirming the schema still
shows `list_id` on GET /api/watchlist (i.e. the deploy didn't regress).

Then surface to the founder these exact Apps Script paste instructions
(they'll do the browser part — needs their OAuth approval):

1. Open the "Live Dashboard - Stocks" Google Sheet → Extensions → Apps
   Script. Google will open the bound script in a new tab (probably named
   "Untitled Project").
2. Replace the default `Code.gs` with:

   ```javascript
   function notifyTapeline() {
     UrlFetchApp.fetch('https://api.tapeline.io/api/internal/sheet-changed', {
       method: 'post',
       contentType: 'application/json',
       payload: JSON.stringify({
         secret: PropertiesService.getScriptProperties().getProperty('TAPELINE_WEBHOOK_SECRET')
       }),
       muteHttpExceptions: true
     });
   }
   ```

3. File → Project Settings → Script Properties → Add property:
   - Name: `TAPELINE_WEBHOOK_SECRET`
   - Value: `ggx-wsXGvgvbhlsAPOXb-75U_OybBy6acxveO0pCaIQ`

4. Triggers (left sidebar clock icon) → Add Trigger:
   - Function: `notifyTapeline`
   - Deployment: Head
   - Event source: From spreadsheet
   - Event type: On change
   - Save → approve Google's OAuth permission popup.

5. Verify: edit any cell on the sheet, then
   `fly logs -a tapeline-backend | Select-String "internal.sheet-changed"`
   — should see "received" then "refresh_complete" within ~2 sec.

### TASK B. Stripe webhook secret rotation (founder-only, agent supports)

Founder rotates secret at dashboard.stripe.com → Developers → Webhooks
→ endpoint we_1TWeuYJ23wFFL5Y3Kn54dZ2p → reveal/rotate signing secret.

When founder pastes new value, agent runs:

```powershell
fly secrets set STRIPE_WEBHOOK_SECRET=<paste_value_here> -a tapeline-backend
fly deploy -a tapeline-backend --remote-only
```

Then founder does the $9.99 smoke test on tapeline.io/pricing with a
real card, watches Fly logs for `stripe.webhook.checkout_session_completed`,
and refunds themselves in the Stripe dashboard.

### TASK C. LinkedIn DM triage (15 active threads, 6 currently unread)

Founder needs to paste the latest message from each unread thread into
chat. Agent drafts replies in the email-renderer voice
(`backend/app/services/email.py`). Founder reviews + posts.

Specific threads in flight (per yesterday's handover):
- Princy, Sunil (already replied; track for follow-ups)
- Dr Amadi, Anthony Jackson, Christopher Autera-Polzin, Erick Washburn
  (first-DMs sent 2026-05-17)
- Surbhi, Brent, WAHED, Anmol (ask-for-email follow-ups sent 2026-05-17)

### TASK D. Reddit r/stocks post

Tue 19 May, 23:00 AEST (= 9 AM ET). Copy ready in
`docs/launch/REDDIT_PASTE_READY.md` (corrected — Form 4 not Elite 13F per
PR #74). All of reddit.com is MCP-blocked at protocol layer; founder
posts manually at https://www.reddit.com/r/stocks/submit.

After founder submits, they should hang around for 60 minutes replying.
Agent can draft responses if founder pastes comments into chat.

### TASK E. Daily X tweet

`docs/growth/tweet_schedule.md` has 14-day templates with placeholder
tickers. Pre-post recipe:

```powershell
$d = irm "https://api.tapeline.io/api/scorecard?days=1"
$d.days.PSObject.Properties | select -First 1 -ExpandProperty Value | select -First 3 | % { "$$($_.symbol) ($($_.score_at_flag))" }
```

Fill placeholders with the result, post via X compose at 8 AM ET or
4:15 PM ET. Use reply-chain (not multi-post composer) for threads.

### TASK F. Other founder-only browser tasks (no agent help possible)

- **LinkedIn profile photo** — drag-drop export of
  https://tapeline.io/profile-square at
  linkedin.com/in/christian-piyatilaka-16192a40a/ → change photo.
- **AlternativeTo resubmit** — alternativeto.net → log in (founder's
  account) → submit fresh Tapeline listing. The previous one was
  removed (URL /software/tapeline/ now 404s).
- **Stocktwits signup** — stocktwits.com/signup with handle
  `tapeline_io`, email `christian@tapeline.io`. (Stocktwits is MCP-
  blocked at protocol layer.)
- **GBP "Get verified"** — business.google.com/dashboard → find Tapeline
  business card → "Get verified" → enter service address with "Hide my
  address" enabled. Postcard takes 5-7 days.
- **Gmail forwarding finish** — cpiyatilaka@gmail.com → Settings →
  Forwarding → add `tapeline.inbox@gmail.com` → click verification email
  at /u/2/ → re-run filter creation (search query in HANDOFF Package E §5).

## Operating rules

- Communication style: tight, factual, no hype. Match email-renderer
  voice in `backend/app/services/email.py`.
- Don't add features beyond what's asked.
- Auto-merge your OWN clean PRs without asking. Don't auto-touch other
  agents' PRs.
- Fly.io deploys are MANUAL (`fly deploy -a tapeline-backend --remote-only`).
  Vercel auto-deploys frontend on merge to main.

## Things NOT to change

- 6-factor scoring formula and weights
- Descriptive (not prescriptive) signal labels (HIGH CONVICTION / STRONG
  SETUP / CONSTRUCTIVE / NEUTRAL / CAUTION / WEAK)
- Public scorecard summary stats stay live for everyone (trust mechanism)
- Three-tier price points ($9.99 Pro / $19.99 Premium monthly,
  $8.25/$16.58 annual)
- Don't re-enable Microsoft OAuth or Quiver QuantData (deferred per
  docs/launch/DEFERRED_CONFIRMED.md)
- Don't echo founder's home address in chat or commit it

## Files written this session

- `docs/launch/HANDOFF_2026-05-19.md` — primary handoff from yesterday
- `docs/launch/REDDIT_PASTE_READY.md` — Reddit copy, corrected
- `docs/launch/TODAY_CHECKLIST_2026-05-19.md` — today's prioritized list
- `docs/launch/NEXT_AGENT_PROMPT.md` — this file
- `.deploy-phase-a-followups.ps1` / `.bat` — superseded, ignore
- `.deploy-now.bat` — superseded, ignore
- `.deploy-minimal.bat` — the one that actually shipped today's deploy
- `outputs/task7a-7b-8.patch` — superseded by parallel agent's PR #124,
  ignore
