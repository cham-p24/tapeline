# Operating rules

*Written 2026-08-20 per `SAAS_OPTIMISATION_PLAYBOOK.md` §5.1 item 9. These are the standing rules the founder has agreed to hold himself to. They exist so decisions are made once, in writing, rather than re-argued every week. Change them deliberately, with a date.*

## 1. The engineering cap — and the gate in front of it

**Cap:** engineering is limited to **≤ 1 day per week** (8 hours) until the gate below is met.

**Gate:** no engineering item on the 30/60/90 list starts until **≥ 6 user interviews are recorded** in `docs/FEEDBACK_LOG.md`. The only exception is a confirmed correctness bug on a surface a user can see (the 2026-08-19 public-API freshness fix was one; the next one must be argued in the PR body, not assumed).

**Why both:** a bare cap has already been broken — on 2026-08-19 the repo's own analysis said "stop building and go get users" and a 755-line browser extension shipped the same day. Caps get hit; gates don't. The done column of the scorecard is everything a solo technical founder can build alone; the not-done column is everything only the founder can *do*. The gate forces the second column.

## 2. The three milestone dates

| Date | Milestone | Evidence that proves it |
|---|---|---|
| **2026-09-20** | 6 interviews recorded; positioning thesis validated or re-anchored | `docs/FEEDBACK_LOG.md` has ≥6 entries with alternative-tool, workflow-moment, price-paid and verbatim words |
| **2026-11-20** | One content channel held for 90 days; first AI-visibility readout | YouTube channel with ≥6 videos; three monthly AI-panel runs logged; `chatgpt.com` / `copilot.com` referrer count vs Aug baseline |
| **2027-02-20** | First organic payers and a measured trial→paid rate | ≥10 paying customers acquired organically with ≥60-day retention; `churn_events` populated; LTV:CAC computable on a real cohort |

Missing a date is information, not failure. Each one is reviewed on the day and either extended with a written reason or used to trigger the next decision.

## 3. The venture kill-or-persevere criterion

**Date: 2027-05-31.**

**Persevere if** all three are true on that date: (a) ≥ 25 paying customers, (b) monthly logo churn ≤ 8% over the trailing 90 days, (c) at least one acquisition channel has produced ≥ 5 payers without founder 1:1 effort.

**Otherwise** the decision is made consciously — wind down, pivot, or open-source — rather than drifting. The date is not a threat; it is the thing that makes every month between now and then count.

## 4. The founding-price exit trigger (internal — never in customer-facing copy)

Founding pricing ($9.99 Pro / $19.99 Premium) is reviewed, not automatically ended, when **either** of these is true: ≥ 50 paying customers, **or** the first monthly cohort with ≥ 20 payers shows trial→paid ≥ 8%. At that point the question is whether the market has told us the price is low, and the answer comes from the interviews and the cohort, not from a calendar. Any change grandfathers existing subscribers.

This trigger is **internal only**. Customer-facing copy states the current price and the fact that it is locked in for existing subscribers — it never states a deadline, a countdown, or a "price going up" warning (compliance rule 6, no manufactured urgency).

## 5. One channel at a time

Exactly one new content channel is opened per month, and a channel is not judged for **90 days**. Every channel has a written kill number before it starts. Current sequence: YouTube (month 1) → Reddit answering (month 2, only if YouTube is being held) → X / MCP / brand-term ads only after day 90 and only with the preconditions in `PAID_MARKETING_PLAYBOOK.md` §4 written down.

## 6. Counts, not rates

Below 100 users every P0 target is stated as a **count over a fixed denominator** ("of the next 50 signups, ≥ 20 activate within 24h"), never as a percentage. Rates at n=20 are noise; counts are honest.

## 7. Every signup gets a human reply within 24 hours

Same-day personal email from the founder, one behaviour question, a 15-minute call offered. Logged in `docs/FEEDBACK_LOG.md`. This is the interview pipeline, the best-customer table, and the voice-of-customer sheet in one — and it is the single lever the playbook ranks above all others right now.

## 8. What is never written down

Under compliance rule 8, the log and the interview notes never record a named person's capital, holdings, experience level, risk tolerance, or goals. If a user volunteers it, it is heard and not written. Recorded: the alternative tool, the workflow moment, the price they paid or would pay for *software*, and their words.

---

*Review cadence: every milestone date, and any time a rule is about to be broken — in which case the rule is changed in this file first, with a dated reason, rather than silently ignored.*
