# Tapeline autonomy architecture

How the launch keeps moving without the founder touching anything.

Last updated: 2026-05-22 (PR #176 — growth bot + scheduled-Claude tier).

---

## TL;DR

Three autonomous tiers, increasing capability as you unblock each one:

```
TIER 1 — fully autonomous (live now, zero founder action)
  - Daily Top 10 newsletter digest      (Fly worker, 13:00 UTC Mon-Fri)
  - Daily growth-bot tick               (Fly worker, 22:00 UTC Mon-Fri)
  - Trial drip emails (day 3 / 7 / 13)  (Fly worker, daily)
  - End-of-day watchlist digest         (Fly worker, 21:00 UTC daily)
  - Weekly market digest                (Fly worker, Monday 13:00 UTC)
  - Web push, alerts, scoring tick      (Fly worker, every 60s)
  - SEO content + blog post crawl       (Vercel auto-deploys per PR)

TIER 2 — cloud-scheduled Claude sessions (zero founder action,
         require one-time `/schedule` setup)
  - Daily growth-tick session           (Claude cloud, weekday 22:00 UTC)
    → Pulls latest fintwit tweets from priority-1 handles via public X web
    → Personalises the growth-bot's draft templates with real tweet refs
    → Commits drafts to outputs/ in repo for audit trail
    → Posts to /admin/growth-tick/run to fire the email digest
  - Weekly SEO post session             (Claude cloud, Monday 21:00 UTC)
    → Picks next keyword from docs/growth/seo_keyword_backlog.md
    → Writes 1,200-word blog post, opens PR, auto-merges
  - Daily metrics digest session        (Claude cloud, daily 11:00 UTC)
    → Pulls prod metrics via /admin/growth-tick/preview
    → Emails deltas to christian@tapeline.io if anything moved

TIER 3 — autonomous publishing (requires ONE founder one-time setup,
         then zero touch forever)
  - X autoposting from @tapeline_io      (requires X API tokens, ~10 min)
    → docs/setup/X_API_SETUP.md is the 10-min walkthrough
    → After setup: bot posts daily own-feed tweet + 1-2 fintwit replies
  - LinkedIn cross-post via RSS bridge   (requires Buffer/Zapier hookup,
                                          ~15 min)
    → Our RSS feed at /feed/scorecard.xml is the bridge surface
    → Buffer/Zapier ingest RSS, post to LinkedIn
```

### Hard wall — channels that are STRUCTURALLY impossible to automate

- **Show HN** (login required, no API)
- **Press / journalist DMs** (LinkedIn DM API is partner-only, X DM same)
- **Stripe webhook secret rotation** (Stripe dashboard, manual)
- **Real-card smoke tests** (financial-action rule)
- **CAPTCHA-gated forms** (lawyer-consult, Microsoft OAuth setup)

If a channel isn't listed in Tiers 1-3, assume it's in this set.

---

## The growth-bot worker (Tier 1)

Lives in `backend/app/services/growth_bot.py`. Single entry point:
`run_daily_growth_tick(session)`. Fires from
`backend/app/workers/signal_publisher.py` at 22:00 UTC weekdays.

What it produces per run, delivered as one email to `growth_digest_to`
(default `tapeline.inbox@gmail.com`):

1. **Conversion-funnel snapshot.** Total users, signed up 24h, on
   trial, paid, newsletter subs (+ delta), top UTM sources 24h.
2. **Day's X tweet draft.** Top 3-5 picks by composite, link to
   /scorecard with per-edition UTM tag.
3. **Day's LinkedIn post draft.** Rotates through 5 themes by ISO
   weekday (factor explainer → win/miss → methodology → factor →
   trust).
4. **Three fintwit reply candidates.** Templates anchored on current
   composite of the top 3 picks. The cloud-scheduled Claude session
   (Tier 2) personalises these by finding fresh tweets that mention
   the picks.

Kill switch: `fly secrets set GROWTH_BOT_ENABLED=false`. Inert until
turned on; default `false` so a fresh deploy doesn't surprise anyone.

Manual trigger: `POST /api/admin/growth-tick/run` (admin-gated). For
testing or to recover from a missed tick.

Preview without sending: `GET /api/admin/growth-tick/preview` returns
the structured drafts as JSON. The Tier 2 Claude session calls this.

---

## The cloud-scheduled Claude session (Tier 2)

How it works:

1. Set up once via the `/schedule` skill in any Claude Code session.
   The skill calls Anthropic's CronCreate-style backend to register a
   recurring prompt.
2. Each firing spawns a **new Claude session in the cloud** with full
   tool access (Bash, web fetch, file edit, Gmail MCP if connected,
   etc.).
3. The session runs the saved prompt to completion, then exits. No
   chat UI required — fires whether or not the founder has Claude
   Code open.

### The daily growth-tick prompt (saved in the cron)

```
You are Tapeline's autonomous growth bot. Today's task:

1. Fetch GET https://api.tapeline.io/api/admin/growth-tick/preview
   with the X-Admin-Key header from $TAPELINE_ADMIN_KEY env var.
   Capture the metrics + draft content.

2. For each of the 3 fintwit_candidates, fetch the most recent 5
   tweets from each priority-1 handle via x.com/<handle>'s public
   timeline. Pick the FRESHEST one (within last 24h) that mentions a
   US ticker the bot has a composite score for. If none match,
   fall back to the candidate as-is — the founder can pick a target.

3. Write the day's plan to outputs/growth-tick/YYYY-MM-DD.md (commit
   via git from the cloud session's worktree). Include:
     - The metrics snapshot
     - The day's X tweet
     - The day's LinkedIn post
     - The 3 fintwit candidates, EACH paired with a fresh-tweet URL
       and the recipient handle
     - One sentence on what changed since yesterday

4. Hit POST /api/admin/growth-tick/run to fire the digest email.
5. Auto-merge any PR you opened.
6. Report back briefly.
```

Scheduling: `/schedule` skill in any Claude Code session → save with
cron `0 22 * * 1-5` (22:00 UTC Mon-Fri) → done.

### The weekly SEO post prompt

```
You are Tapeline's autonomous SEO post writer. Today's task:

1. Read docs/growth/seo_keyword_backlog.md. Pick the top unchecked
   keyword (mark it done after).
2. Write a 1,200-word commercial-investigation blog post for that
   keyword. Voice: methodology-first, factual, names competitors
   honestly. Format matches docs/blog/_template.md.
3. Create a new branch growth/blog-<slug>, commit the post, open
   PR via gh, auto-merge.
4. Verify Vercel deploys (poll the PR's deployment URL).
5. Submit the new URL to Bing IndexNow API for fast indexing.
6. Report back briefly.
```

Scheduling: cron `0 21 * * 1` (Monday 21:00 UTC).

### The daily metrics digest prompt

Lightweight — runs at 11:00 UTC, hits the growth-tick preview, emails
the metrics deltas only. Fires regardless of Tier 1's growth bot state
so the founder always knows the conversion-funnel numbers.

---

## Tier 3 — what unblocks autopublishing

The growth bot today writes DRAFTS to the founder's inbox. To flip to
TRUE autopublishing:

### X API (10 min, ONE-TIME)

See `docs/setup/X_API_SETUP.md`. Founder creates a free X developer
account, registers an app, copies 4 strings into Fly secrets:

```
fly secrets set \
  X_API_KEY=... \
  X_API_SECRET=... \
  X_ACCESS_TOKEN=... \
  X_ACCESS_TOKEN_SECRET=... \
  -a tapeline-backend
```

After that, the growth bot stops emailing drafts and starts posting
directly. Switch behaviour with `fly secrets set X_AUTO_POST=true`.

### LinkedIn (15 min, ONE-TIME)

Option A: **Buffer / Typefully / Hypefury** — paid tools that ingest
the daily growth digest emails and post to LinkedIn. Setup is a
single OAuth flow against the founder's LinkedIn account.

Option B: **Zapier RSS-to-LinkedIn** — point Zapier at
https://tapeline.io/feed/scorecard.xml. New entries → LinkedIn post.
This is what we'd use if the founder doesn't want a Buffer
subscription.

Either way, ONE setup, then autonomous forever.

---

## Where it all lives in the repo

```
backend/
  app/
    config.py
      ↳ growth_bot_enabled / growth_digest_to / growth_fintwit_handles
    services/
      growth_bot.py
        ↳ pull_growth_metrics, pull_top_picks, draft_daily_tweet,
          draft_linkedin_post, draft_fintwit_reply_candidates,
          render_growth_digest_html, run_daily_growth_tick
    routers/
      admin.py
        ↳ GET  /api/admin/growth-tick/preview  (read-only)
        ↳ POST /api/admin/growth-tick/run      (fires email)
    workers/
      signal_publisher.py
        ↳ Daily 22:00 UTC tick wired in via _last_growth_tick_date
docs/
  launch/
    AUTONOMY_ARCHITECTURE.md   (this file)
  setup/
    X_API_SETUP.md             (Tier 3 unblock for X)
  growth/
    seo_keyword_backlog.md     (Tier 2 SEO-post-writer's queue)
outputs/
  growth-tick/
    YYYY-MM-DD.md              (one file per autonomous tick, audit trail)
```

---

## Monitoring

The growth bot is a worker task — failures show up in `fly logs -a
tapeline-backend`. Sentry catches uncaught exceptions if `SENTRY_DSN`
is configured. The digest email itself is the smoke test — if it
arrives, the bot ran cleanly.

If the digest stops arriving:

1. Check the kill switch: `fly secrets list -a tapeline-backend | grep GROWTH_BOT_ENABLED`
2. Check the worker log: `fly logs -a tapeline-backend | grep growth_bot`
3. Manually fire: `curl -X POST https://api.tapeline.io/api/admin/growth-tick/run -H "X-Admin-Key: $TAPELINE_ADMIN_KEY"`

---

## Why this design

Three reasons it's split across three tiers instead of "just one
autonomous loop":

1. **Tier 1 is irreducible — it must work even if no Claude is
   running.** A Fly worker fires regardless of Anthropic
   infrastructure health.
2. **Tier 2 needs LLM judgment — pick the freshest tweet, write a
   blog post.** Worker code can't do creative judgment well; cloud
   Claude does.
3. **Tier 3 is the bottleneck — actual posting requires platform
   API tokens.** Both founder action and ongoing cost discipline.
   Splitting it out makes the constraint obvious.

The wedge between Tier 1 and Tier 3 is what the founder sees as
"autonomous infrastructure built but not connected to publishing."
That gap is unavoidable for any indie SaaS on X / LinkedIn until the
founder either creates API tokens or signs up for a third-party
scheduler.
