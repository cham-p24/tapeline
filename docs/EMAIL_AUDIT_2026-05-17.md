# Email System Audit — 2026-05-17

End-to-end audit of Tapeline's transactional, alert, and drip emails: which
renderers exist, which are wired to fire automatically, and whether any are
silently broken or unwired.

**Bottom line:** every renderer is wired to at least one trigger. The trial
drip dispatcher (`run_daily_drip`) is correctly invoked by the worker every
24h. Zero drip emails have actually fired in prod because there are no real
trial users in the DB (only 2 owner accounts, both `trial_ends_at IS NULL`).
Three minor issues found — none block launch, all are one-line fixes (listed
under "Concrete fixes" at the bottom).

---

## Renderer-by-renderer status

Status legend:
- **WIRED + FIRING** — code path exists, evidence in prod Resend log
- **WIRED, NOT YET FIRED** — code path exists, no real trigger event has
  occurred yet (e.g. trial drip with zero trial users)
- **WIRED, FIRED ONLY VIA TEST** — only smoke / itest bounces seen
- **DEFINED ONLY** — no caller found anywhere in the repo

| Renderer | Caller | Trigger | Status |
| --- | --- | --- | --- |
| `render_alert_email` | `services/alerts.py:328` (`_fire`) | Per-rule evaluator hits a threshold (score / squeeze / regime / news) | **WIRED + FIRING** (94-row Resend window shows `[Tapeline] Health alert · ...` lines from internal monitoring rules) |
| `render_welcome_email` | `routers/auth.py:230-246` | POST `/api/auth/signup` (non-referral path) | **WIRED, FIRED ONLY VIA TEST** — 37 sends in recent Resend window, ALL bounced (smoke/itest synthetic emails). Zero real-user sends because real-user signups haven't happened yet pre-launch. |
| `render_trial_day3_email` | `services/email.py:803` (`run_daily_drip` window `"3"`) | Worker daily tick when `trial_ends_at ∈ (now+10d, now+11d)` | **WIRED, NOT YET FIRED** |
| `render_trial_day7_email` | `services/email.py:806` (window `"7"`) | `trial_ends_at ∈ (now+6d, now+7d)` | **WIRED, NOT YET FIRED** |
| `render_trial_day11_email` | `services/email.py:809` (window `"11"`) | `trial_ends_at ∈ (now+2d, now+3d)` | **WIRED, NOT YET FIRED** |
| `render_trial_day13_email` | `services/email.py:812` (window `"13"`) | `trial_ends_at ∈ (now, now+1d)` | **WIRED, NOT YET FIRED** |
| `render_trial_expired_email` | `services/email.py:816` (window `"expired"`) | `trial_ends_at ∈ (now-1d, now)`, no Stripe customer | **WIRED, NOT YET FIRED** |
| `render_trial_post_expiry_email` | `services/email.py:819` (window `"post3"`) | `trial_ends_at ∈ (now-4d, now-3d)`, no Stripe customer | **WIRED, NOT YET FIRED** |
| `render_trial_ended_email` | `workers/signal_publisher.py:671-682` (`_downgrade_expired_trials`) | Worker hourly tick after auto-downgrade flips an expired-trial user to `tier=free` | **WIRED, NOT YET FIRED** |
| `render_eod_watchlist_digest` | `services/email.py:637` (called by `run_eod_watchlist_digest`) | Worker daily tick after 21:00 UTC (≈US market close) | **WIRED + FIRING** — Resend log shows `Tapeline EOD · ...` daily through May 13–16 to `owner@tapeline.io` |
| `render_referral_referee_email` | `routers/auth.py:214` | Signup with `?ref=` cookie present | **WIRED, FIRED ONLY VIA TEST** — 1 send in Resend window, bounced (smoke-e-... synthetic) |
| `render_referral_referrer_email` | `routers/auth.py:220` | Signup with `?ref=` cookie present (paired send) | **WIRED, FIRED ONLY VIA TEST** — 1 send in window, bounced |
| `render_payment_failed_email` | `routers/webhooks.py:180` | Stripe `invoice.payment_failed` event | **WIRED, NOT YET FIRED** (zero paying customers yet → no failed charges) |
| `render_re_engagement_email` | `services/email.py:916` (called by `run_re_engagement_drip`) | Daily tick, `last_seen_at ∈ (now-15d, now-14d)`, no active trial, no `re14` token | **WIRED, NOT YET FIRED** |

No renderer is defined-only. All have at least one caller.

---

## Dispatcher status

### `run_daily_drip` — **firing daily**

`backend/app/workers/signal_publisher.py:249-262` invokes it inside the
normal worker tick, gated by `_last_drip_check` (24h cadence). The exception
handler logs `drip.run_failed` on any error. Same block also invokes
`run_re_engagement_drip`. Worker process verified running on machine
`48e7e7efd71668` (PID 638: `python -m app.workers.signal_publisher`).

The CLAUDE.md claim that "the worker runs the daily drip check" is **real,
not aspirational** — the wiring landed somewhere between the email.py
comment block at lines 751-764 (which still suggests the wiring "needs to
be added") and the actual call at signal_publisher.py:252. That comment in
email.py is now stale and should be deleted.

### `run_re_engagement_drip` — **firing daily** (alongside the drip block)

Same trigger block, runs every 24h. Filters: `last_seen_at ∈ [now-15d,
now-14d)`, `trial_ends_at IS NULL or < now`, `re14 NOT IN drip_state`.

### `run_eod_watchlist_digest` — **firing daily, verified**

`backend/app/workers/signal_publisher.py:405-416` invokes it once per UTC
day when `started.hour >= 21`. Per-day dedupe via `_last_eod_digest_date`.
Resend log confirms a `Tapeline EOD · ...` send at 21:00 UTC on May 13, 14,
15, and 16. (May 14 fired three times — the in-process dedupe doesn't
survive a worker restart, which is mentioned and accepted in the docstring.)

### `_downgrade_expired_trials` — **firing hourly**

`backend/app/workers/signal_publisher.py:222-226` invokes it every 3600s.
After downgrading, it loops the candidates list and sends
`render_trial_ended_email` to each (lines 670-684). So the trial-end nudge
is wired to the downgrade event, not to a calendar window — this is by
design.

---

## Live data findings

Queried via `fly ssh console -a tapeline-backend -C "python /tmp/audit_drip.py"`
(read-only `SELECT`, no writes):

```
trial_users_total: 0
users_total: 2
users_in_drip_window: 0
drip_state_dist:
  '': 2
```

**Both users have `trial_ends_at = NULL`** (the owner-seeded accounts, no
trial). **Zero users in any drip window**. Therefore:

- No "drip fired prematurely" anomaly possible — `drip_state` is empty for
  every user.
- No "day-13 didn't fire" anomaly possible — no user has
  `trial_ends_at = today`.
- The drip code paths are fully exercised by the tests
  (`backend/tests/test_re_engagement_email.py`) but have not yet been
  exercised in prod because no real signups have happened.

This is consistent with the launch-day claim in CLAUDE.md and the README:
Tapeline is **pre-launch**.

---

## Resend / delivery findings

Queried `GET https://api.resend.com/emails` with the prod API key (read-only
list endpoint, no sends triggered):

- 94 total emails in the visible history window
- 37 welcome emails — **all bounces**, every recipient is a smoke-test or
  itest synthetic address (`smoke-*@example.com`, `itest-*@example.com`)
- Zero drip-tagged subjects in the entire window (searched for "three days
  in", "halfway through", "3 days left", "ends tomorrow", "trial ended",
  "trial just ended", "Last note from Tapeline", "missed you" — all zero
  hits)
- EOD digest firing daily, confirmed delivered to `owner@tapeline.io`
- Internal health-alert emails firing several times per day to
  `support@tapeline.io` (`[Tapeline] Health alert · ...`)
- A handful of address-routing test emails on 2026-05-17 (Christian / Billing
  / Legal / Press / Support alias tests)

**`RESEND_API_KEY` is set in Fly secrets** — confirmed via
`fly secrets list`. So `send_email` will not no-op when a real trigger fires.

---

## Issues found — flagged for follow-up PRs

These are minor, none block launch. Bug-fix is **not** included in this PR
per task constraints; this audit is the deliverable.

### 1. Stale wiring comment in `services/email.py:751-764`

The block of comments above `run_daily_drip` says:

> When the key arrives, add this to signal_publisher.py tick():
> `from app.services.email import run_daily_drip ...`
> Note: this MVP version may double-send if the worker restarts mid-day.
> To guard against that, add a `drip_state` JSON column to User and check it
> before each send.

Both pieces of advice have already landed:
- The worker invocation IS in `signal_publisher.py:252-255`
- The `drip_state` column IS on `User` (migration `0009_user_drip_state`)
  and IS read/written by the dispatcher

**Fix:** delete the 14-line comment block. One-liner.

### 2. Incomplete observability — log line drops 3 new stages

`workers/signal_publisher.py:257`:

```python
logger.info("drip.sent day3=%d day7=%d day13=%d", counts["day3"], counts["day7"], counts["day13"])
```

`run_daily_drip` returns 6 keys (`day3`, `day7`, `day11`, `day13`, `expired`,
`post3`) but the log line only reads three of them. If the day-11, expired,
or post3 stages fire, the log will not record it.

**Fix:** change the format string to include all six counts. One-liner.

### 3. Copy bug in `render_trial_day11_email` body

`services/email.py:368`:

```
($39.99/mo or $39.99/mo billed annually saves $120/yr)
```

Premium monthly is **$49.99/mo**, not $39.99/mo (the annual rate). Confirmed
against `docs/PRICING.md` and `frontend/components/PricingTable.tsx`. The
copy reads as if both monthly and annual cost $39.99, which is wrong.

**Fix:** change to `($49.99/mo or $39.99/mo billed annually — saves $120/yr)`
to match the day-7 email's format. One-liner.

---

## Concrete fixes (one-liner per gap)

1. Delete the stale comment block at `backend/app/services/email.py:751-764`.
2. Fix the log line at `backend/app/workers/signal_publisher.py:257` to
   print all six stage counts (`day3 day7 day11 day13 expired post3`).
3. Fix the price typo at `backend/app/services/email.py:368` (`$39.99/mo or
   $39.99/mo` → `$49.99/mo or $39.99/mo`).

No structural changes needed. The drip system is **production-ready** —
it just hasn't had any real users yet to drip-mail.
