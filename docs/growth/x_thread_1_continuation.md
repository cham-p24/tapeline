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
> **DISCLOSURE BOUNDARY — never publish the exact factor weights or the scoring
> equation.** `/how-it-works` names the six factors and their weight *ordering*
> ("weighted most toward Trend and Relative Strength, least toward Momentum") and
> nothing more. No line here may say Tapeline publishes "the formula" or "the
> exact weights". Nor may it publish a factor's inputs at parameter level —
> named lookback windows, thresholds, indicator recipes or sub-weights are all
> out of bounds. Describe what a factor measures and stop.
>
> **OPEN-ACCESS MONTH — reverts 2026-09-08.** While it runs, a **signed-in**
> Free account sees the full 1,000-row scanner rather than the standard top 10.
> Nothing else lifts — look-ups, watchlist and push-rule caps are unchanged and
> no Pro feature unlocks — and logged-out visitors still see the top 10. Lines
> below that describe the Free row cap are the **post-promo** steady state, so
> re-check them against `tier.py` before posting them as today's product.
>
> Some drafts here are stale on product facts as well (a "top 20, 24-hour
> delayed" free tier is long gone; the per-rule Telegram alert channel was
> retired and `AlertRuleCreate` now accepts only email|web_push). Treat unmarked
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

## Tweet 5 (~275 chars)

```
The full record is free to read, no account. Pro $8.25/mo billed annually = full live universe + smart alerts. Premium $19.99 adds Congress trades + SEC Form 4. An account takes a card: 14-day Premium trial, $0 today, one click cancels. Built solo from Melbourne.
```

**Why this works:** transparent pricing with the genuinely card-free surface as
the hook — the published record needs no account at all — and the trial's terms
stated rather than buried. "Built solo
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
The six factors, heaviest-weighted first (Trend and Relative Strength most, Momentum least):

Trend
Relative Strength
Fundamentals
Smart Money
Macro
Momentum

Heaviest Trend and RS, lightest Momentum. The ordering is fixed and public, and it doesn't change retroactively. Argue with it on /how-it-works.
```

**Tweet 5:**
```
The published record shows the real product, live and complete, with no account. Free accounts get top-10 rows and 12 look-ups a day. Pro $8.25/mo annual = full ~2,500-ticker live scan + smart alerts. Premium $19.99/mo adds Congress trades + SEC Form 4.
```

**URL reply:** `https://tapeline.io`

Skipped because it rehashes the methodology content already in tweets 2/3.
Kept here in case the founder prefers to lead with the factor list.
