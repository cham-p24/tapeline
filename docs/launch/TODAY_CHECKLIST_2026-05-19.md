# Today's launch-day checklist — Tue 19 May 2026

Built by the agent during the parallel-execution session. Tabs are
pre-opened in Chrome MCP group. Open files referenced below from
`C:\Project 1\docs\launch\`.

---

## ✅ Code already shipped (other agents merged in parallel)

- **PR #124** — Phase A: POST `/api/watchlist` `list_id` + PATCH
  `/api/watchlist/{id}` move-to-list. Same contract as the agent's
  patch in `outputs/task7a-7b-8.patch` (different naming —
  `WatchlistMove` vs `WatchlistItemMove`). The agent's patch is now
  obsolete; ignore it.
- **PR #126** — `/blog/ticker/{X}` SEO buildout (Task 8 equivalent).
- **PR #123** — site-wide light-mode theme polish.
- **PR #125** — LinkedIn / X thread drafts.
- **f845276** — Google Analytics 4 wired (G-YRK73W9NS9).

Local main is at `f845276`, six commits ahead of where this session
started.

## ⏳ Deploy in flight

`.deploy-now.bat` is running in a hidden terminal. It does:
1. `git fetch origin && git checkout main && git pull --rebase`
2. `fly deploy -a tapeline-backend --remote-only`

Verify by curling `https://api.tapeline.io/openapi.json` and checking
that `paths./api/watchlist.get.parameters` includes `list_id`. Right now
it's still `[]` — deploy not done yet.

If the script errored out (it might, because the local working tree has
CRLF normalization noise on existing files):
- Bring the hidden terminal window to front, read the error.
- Worst case: `git stash` the noise, re-run `fly deploy -a tapeline-backend --remote-only` from PowerShell directly.

---

## 🎯 Tonight's launch window

### Show HN — 8 AM ET (22:00 AEST) — ~11 hours away

**Tab pre-filled.** Open the "Submit | Hacker News" tab in Chrome
(should be near the top of your tab strip). Title, URL, and body
text are filled with Variant A (back-check angle, live scorecard
numbers as of this morning).

To launch: hit Submit. Then **immediately** post the 6-factor formula
as the first comment on your own post:

```
score = 0.25 × Trend
      + 0.20 × Relative Strength
      + 0.15 × Fundamentals
      + 0.15 × Smart Money
      + 0.15 × Macro
      + 0.10 × Momentum
```

**Hang around for 90 minutes after submission.** First-hour reply
velocity drives HN front-page placement. Prepared responses to the
4 most predictable objections are in `LAUNCH_PLAYBOOK.md` §1.

### Reddit r/stocks — 9 AM ET (23:00 AEST) — ~12 hours away

Tab not pre-filled (Reddit hard-blocked at MCP layer). Copy-paste
from `REDDIT_PASTE_READY.md` §1 — title + body are ready. Critical:
that file's r/stocks body has the **corrected** Premium line (stripped
the stale "Elite 13F holdings" from LAUNCH_PLAYBOOK and replaced with
"Recent insider buys (SEC Form 4)" per PR #74).

Same playbook: post, then reply to every comment for the first 60 min.

---

## 🛠️ Founder-only ops (no time pressure)

### Apps Script paste — cuts sheet→Tapeline lag 5min → 2sec
- **Tab open:** Google Sheets home. Open "Live Dashboard - Stocks" → Extensions → Apps Script.
- **Exact script + script-property name + trigger config:** `HANDOFF_2026-05-19.md` Package B.
- Founder must approve the OAuth permission popup when adding the `On change` trigger.

### Stripe webhook secret rotation
- **Tab not pre-opened** — dashboard.stripe.com hard-blocked at MCP layer.
- Founder rotates the secret at dashboard.stripe.com/webhooks (endpoint `we_1TWeuYJ23wFFL5Y3Kn54dZ2p`), pastes new value in chat. Agent runs `fly secrets set STRIPE_WEBHOOK_SECRET=...`.

### LinkedIn profile photo
- **Tab open:** linkedin.com/in/christian-piyatilaka-16192a40a/
- Upload export from `https://tapeline.io/profile-square`. Drag-and-drop required (file upload protocol-blocked in MCP).

### Cloudflare WHOIS re-trigger
- **Tab open:** dash.cloudflare.com (showing accounts/domains list — pick tapeline.io → Registration → Contact info → Save (no edits needed)).
- Postcard verification email lands in `tapeline.inbox@gmail.com` /u/2/.

### AlternativeTo resubmit
- **Tab open:** alternativeto.net — log in, find or create Tapeline listing.
- The earlier `/software/tapeline/` 404'd — the prior submission appears to have been removed entirely. May need to start fresh.

### Stocktwits signup
- **Tab not pre-opened** — stocktwits.com hard-blocked at MCP layer.
- Founder signs up at stocktwits.com/signup with handle `tapeline_io` + email `christian@tapeline.io`.

### GBP "Get verified" address
- **Tab open:** Google search for "Tapeline" (business.google.com/dashboard redirected here, likely needs sign-in).
- Founder signs in with the right Google account, navigates to GBP dashboard, finds the Tapeline business card, hits "Get verified", enters address (`4 Aubergine Road, Mickleham VIC 3064` — keep address discreet, choose "Hide my address" since it's a service-area business).

### Gmail forwarding finish
- Founder: cpiyatilaka@gmail.com → Settings → Forwarding → add `tapeline.inbox@gmail.com` → click verification email at /u/2/ → re-run filter creation (search criteria in `HANDOFF` Package E §5).

---

## 📨 LinkedIn DM triage (15 active threads — Task 14)

- **Tab open:** linkedin.com/messaging/ — title shows "(9) Messaging" so 9 unread visible right now.
- Workflow: paste the latest message from each thread into chat. The agent drafts a calm, factual reply in the email-renderer voice. You review + post.

---

## 📋 Open Chrome MCP tabs (the agent's session)

| Tab | URL | Status |
|-----|-----|--------|
| HN Submit | `news.ycombinator.com/submit` | Pre-filled — hit Submit at 22:00 AEST |
| Google Sheets home | `docs.google.com/spreadsheets/u/0/` | Find "Live Dashboard - Stocks" |
| Cloudflare Dashboard | `dash.cloudflare.com` | Re-save tapeline.io contact info |
| AlternativeTo | `alternativeto.net/software/tapeline/` | 404 — resubmit listing |
| (was GBP) | Google search for "Tapeline" | Manual sign-in to business.google.com |
| LinkedIn Messaging | `linkedin.com/messaging/...` | 9 unread |
| LinkedIn Profile | `linkedin.com/in/christian-piyatilaka-16192a40a/` | Upload profile photo |

---

## Order of operations if pressed for time

1. Confirm deploy shipped (curl OpenAPI for list_id param).
2. (At 22:00 AEST tonight) Hit Submit on the HN tab. Stay engaged 90 min.
3. (At 23:00 AEST tonight) Paste-and-post on r/stocks. Stay engaged 60 min.
4. Tomorrow: Apps Script, then Stripe webhook rotation, then GBP verify (postcard takes 5–7 days so kick off early).
5. Whenever: LinkedIn photo + DM triage + AlternativeTo resubmit + Stocktwits signup + Cloudflare WHOIS + Gmail forwarding.
