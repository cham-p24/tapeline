# X thread #1 — tweets 4 + 5 + URL reply

> **CARD GATE — 2026-08-22. Check every claim below against `docs/PRICING.md` before posting.**
>
> From 2026-08-22 a **new account must put a card on file at first sign-in**
> before it can use the logged-in product (Stripe Checkout, $0 charged that day,
> 14-day Premium trial, first charge on day 14, one click to cancel before then).
> Accounts created **before** that date are grandfathered: they keep the free
> access they signed up for and are never asked for a card.
>
> So: **no line in this file may say an account is free, that there is a free
> tier a new user can sign up for, or that signing up needs no card.** What is
> still true and should be said instead — the **published record is free with no
> account at all**: the daily Top 10, the complete scorecard, a page per scored
> ticker, and the raw CSV/JSON export.
>
> Some drafts here are stale on product facts as well (a "top 20, 24-hour
> delayed" free tier and Telegram alerts are both long gone). Treat unmarked
> copy as a draft to re-check, not as approved copy.

Continues the @tapeline_io launch thread from May 13. Tweets 1-3 are already
live (hook + black-box reveal + "we publish them"). This file holds the
agent-drafted continuation so the founder can copy-paste-post when ready.

Posting order:
1. Open the LAST tweet in the existing chain on @tapeline_io
2. Click Reply, paste Tweet 4
3. From Tweet 4 → Reply, paste Tweet 5
4. From Tweet 5 → Reply, paste the URL reply

All tweets verified ≤ 280 chars (Twitter counts URLs as 23 chars regardless).

---

## Tweet 4 (~190 chars)

```
And every top-10 pick gets back-checked vs SPY the next day. Wins AND losses both stay on the page — no quiet edits, no survivor bias. 5 sessions in, median 1D alpha is -0.73% on 35 clean entries (4 outliers flagged + excluded).
```

**Why this works:** the median alpha figure is live and defensible (came
straight from `/api/scorecard` after the PR #97 outlier filter shipped).
The "wins AND losses both stay on the page" line is the trust-builder.
Self-skeptical tone matches the rest of the thread.

---

## Tweet 5 (~210 chars)

```
Free tier: top 20 names, 24h delayed. Pro $8.25/mo billed annually = full live universe + smart alerts. Premium $19.99 adds Congress trades + SEC Form 4 + Telegram. Free tier needs no card; the 14-day Premium trial takes one and charges $0 today. Built solo from Melbourne.
```

**Why this works:** transparent pricing with the card-free free tier as the hook, and the trial's terms stated rather than buried. "Built solo
from Melbourne" adds founder context without being self-promotional. No CTA
verb — the URL reply that follows IS the CTA.

---

## URL reply (~95 chars including 2 URL allowances)

```
The record so far: https://tapeline.io/scorecard
The product: https://tapeline.io
```

**Why this works:** two distinct destinations — `/scorecard` is the proof
surface, `/` is the product entry. URL-only replies on X get treated
differently by the algorithm than text-with-URL — sometimes better, sometimes
worse. We err on the side of "let them click through to verify."

---

## Alternative Tweet 4 + 5 (if Option A doesn't feel right)

Drafted as a fallback before Option A was picked. The six-factor breakdown
angle:

**Tweet 4:**
```
The six factors and their weights, in full:

Trend 25
Relative Strength 20
Fundamentals 15
Smart Money 15
Macro 15
Momentum 10

Sums to 100. Doesn't change retroactively. Open for arguing about on /how-it-works.
```

**Tweet 5:**
```
Free tier shows the real product (top 20, 24h delayed). Pro $8.25/mo annual = full ~2,500-ticker live scan + smart alerts. Premium $19.99/mo adds Congressional trades + SEC Form 4 insider feed + unlimited Telegram. Free tier needs no card; the 14-day trial takes one and charges $0 today.
```

**URL reply:** `https://tapeline.io`

Skipped because it rehashes the formula content already in tweets 2/3.
Kept here in case the founder prefers the explicit weights list.
