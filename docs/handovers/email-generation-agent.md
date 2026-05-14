# Handover: Email generation agent

## Mission

Own the entire email surface for Tapeline — transactional, drip,
weekly digest, re-engagement, and outbound (cold + nurture). Every
email is concise, factual, and reinforces the transparency moat. No
emoji-stuffed marketing tone; no "Dear Valued Customer" boilerplate.
The voice is "Melbourne founder writing personally to one customer."

## Why this matters

Email is the only channel where Tapeline owns the relationship
end-to-end. Twitter can rate-limit you, Google can deindex you,
Reddit can shadowban you — but a customer who opted in to the email
list is a direct asset. Done right, email becomes Tapeline's most
profitable channel: trial conversion via the day 0/3/7/13 drip, plus
weekly recap retention, plus warm re-engagement when scorecard wins.

Done wrong, email burns the brand fast — every "PROMOTIONAL" tag
Gmail slaps on a Tapeline email costs trust forever.

## Scope

### IN scope
1. Audit existing emails (`backend/app/services/email.py`) for tone,
   accuracy, deliverability
2. Draft + ship the **day-10 personalised "your scorecard wins"**
   email — uses the user's actual watchlist + scorecard data
3. Draft + ship the **weekly digest** — Sunday-evening recap of top
   movers, the user's watchlist score changes, and the public
   scorecard's hit rate
4. Draft the **trial-ended re-engagement series** — day 14 (drop-to-
   Free), day 21 (winback offer), day 35 (final delete-warning)
5. Build a **cold outreach generator** — given a name + role + company,
   generate 80-120 word personalised email referencing something real
   about them
6. Maintain a **send-time + deliverability log** — `outputs/email-2026-MM.md`
   covering open rates, click rates, complaint rates, what worked

### OUT of scope
- Marketing channel content (Twitter/Reddit/HN — separate agent)
- Transactional system events that need code (signup welcome, password
  reset, payment receipt — these should be code, not LLM-generated, to
  guarantee deliverability)
- Buying email lists (illegal under CAN-SPAM and Australian Spam Act)

## Concrete tasks (priority-ordered)

### 1. Audit existing email surface

Read `backend/app/services/email.py` and review every template:
- `render_welcome_email`
- `render_day3_email`, `render_day7_email`, `render_day13_email`
- `render_trial_ended_email`
- `render_eod_watchlist_digest`

For each:
- [ ] Subject line — under 50 chars, no clickbait, no emoji unless
  earned
- [ ] Preview text (first 100 chars of body) — should sell the open
- [ ] Body — under 250 words, single CTA, no boilerplate signoff
- [ ] Personalisation — user's first name, their watchlist tickers
  where relevant
- [ ] HTML + plaintext both render — Gmail prefers multipart
- [ ] No spam triggers ("Free!", "Act now", "Click here")
- [ ] Footer — physical address, unsubscribe link in plain text (not
  hidden in tiny grey font)

Output: `outputs/email-audit-2026-MM-DD.md`.

### 2. Day-10 personalised "your scorecard wins"

Trial users get day 0/3/7/13. Day 10 is a gap. Fill it with the
strongest possible "the product worked for you" message:

```
Subject: 3 of your watchlist hit HIGH CONVICTION this week

Hi {first_name},

You added {ticker_a}, {ticker_b}, {ticker_c} to your Tapeline
watchlist last week. Here's where they landed today:

  {ticker_a}  72.4 → 86.1   STRONG SETUP → HIGH CONVICTION  (+13.7)
  {ticker_b}  68.0 → 71.2   CONSTRUCTIVE → STRONG SETUP     (+3.2)
  {ticker_c}  82.0 → 79.4   STRONG SETUP — held             (-2.6)

The Tapeline Score updates every 60 seconds. The full breakdown for
each is one click away on your watchlist page.

Reminder: 4 days left in your trial. If the scanner has earned its
keep, the Pro plan is $29/mo and Premium is $49/mo. Cancel in one
click any time.

— Christian, Tapeline founder
{watchlist_link}
```

- [ ] Backend: query the user's watchlist, fetch current scores,
  compare against scores at the time the user added each ticker
- [ ] Skip if the user's watchlist is empty (send a different "tell
  us what you're watching" prompt instead)
- [ ] Add to `signal_publisher.py` daily drip task

### 3. Weekly digest (Sunday evening)

```
Subject: Tapeline weekly · {N} HIGH CONVICTION picks last week

This week on the public scorecard:
  Days tracked       7
  Top-10 picks       70
  Beat SPY hit rate  56%
  Avg next-day alpha +0.18%

Your watchlist movers (top 5):
  {symbol}  {score_change}  {signal_change}
  ...

Editor's note: {one paragraph reflection from the founder on the
week — what worked, what didn't, what changed in the methodology if
anything}.

Read the full scorecard at https://tapeline.io/scorecard.
```

- [ ] Sunday 18:00 user-local-time sending (use stored timezone or
  default to UTC if unknown)
- [ ] Generate the editor's note from the actual past-week scorecard
  data — agent should never make up numbers
- [ ] Premium feature? Probably free for all paid tiers (Pro + Premium)
  to maximise retention; trial users get it as a value-add

### 4. Trial-ended re-engagement series

Currently `render_trial_ended_email` fires once on day 14. Extend to
3 emails:

**Day 14 (existing, polish):** *"Your trial just ended"* — calm tone,
recap what they got + what they kept (Free tier still has scorecard
+ top 20). One CTA: upgrade.

**Day 21 (new):** *"One last reason"* — a specific scorecard win from
their watchlist if they had one. If they didn't, generic recap of
that week's HIGH CONVICTION names. CTA: upgrade.

**Day 35 (new):** *"We're going to delete your account in 7 days"* —
GDPR-compliant data-retention nudge. Links to keep / delete /
download data. Often produces the biggest re-engagement spike
(loss aversion on the data + relationship).

### 5. Cold outreach generator

Given an input row `{name, role, company, why_relevant}`, output an
80-120 word email:

```
Subject: {one-line specific hook tied to why_relevant}

Hi {first_name},

{Single sentence acknowledging something concrete about their work —
must reference why_relevant, not flatter generically.}

I'm building Tapeline (tapeline.io). It's a quantitative stock
scanner that publishes its scoring formula on the homepage and
back-checks every pick against SPY publicly. Most of the prosumer
scanners hide both — figured you'd find the transparency
interesting.

Free to play with at /t/AAPL or /scorecard — no signup needed for
either. Worth a 60-second look?

— Christian
```

- [ ] Use case: warm intros, journalist pitches, podcast hosts,
  fintech product people
- [ ] NEVER mass-send. The agent generates ONE email per request,
  human reviews + sends from a personal inbox
- [ ] If the agent can't credibly fill `why_relevant` with something
  specific, REFUSE TO GENERATE — refusing a bad cold email is more
  valuable than producing one

### 6. Monthly performance + deliverability review

`outputs/email-2026-MM.md`:
- Open rate per template (target: 40%+ for transactional, 25%+ for
  drips, 15%+ for cold)
- Click rate per template (target: 8%+ for drips, 3%+ for cold)
- Complaint rate (target: <0.1% — anything above hurts domain
  reputation hard)
- Unsubscribe rate (target: <0.5%/send)
- Top 3 best-performing emails (with hypothesis)
- Recommended changes for next month

## Files / surfaces

```
backend/app/services/email.py            # all template + send logic
backend/app/workers/signal_publisher.py  # drip scheduling lives in run_daily_drip
backend/app/models/user.py               # User.drip_state column tracks per-stage delivery
backend/app/scripts/                     # could add scripts/preview_email.py for HTML preview
docs/PRICING.md                          # message house for upgrade CTAs
```

## Tools / integrations

- Resend API for sending (already wired, `RESEND_API_KEY` in Fly secrets)
- Read access to user data for personalisation
- Output: agent generates HTML + plaintext templates as
  `outputs/email-{template-name}-{date}.html` for owner review
- Owner deploys via the normal commit/push flow (the agent ships code
  changes for new templates; never sends directly)

## Success criteria

1. **Day-10 email** has open rate >35%, click rate >12% over the
   first 30 sends
2. **Weekly digest** has unsubscribe rate <0.3% (it's frequent — has
   to be earning its place)
3. **Trial-ended series** lifts re-engagement from current rate by
   25%+ (specifically: trial-expired users who upgrade in days 14-45)
4. **Zero domain reputation hits** — `tapeline.io` stays out of any
   blacklist (tracked monthly via mxtoolbox or similar)
5. **Cold outreach** averages 25%+ reply rate (because the volume is
   low and personalisation is real)

## Recommended starter prompt

> I'm picking up the email-generation handover at
> `docs/handovers/email-generation-agent.md`. Read it, then read
> `backend/app/services/email.py` carefully — every existing template.
> Your first deliverable is `outputs/email-audit-2026-05-08.md` — a
> row-by-row review of every existing template covering subject,
> preview, body, CTA, deliverability risk. Don't write any new
> templates yet; I'll review the audit first.
