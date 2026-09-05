# Product Hunt launch kit — the Reddit-free fast channel (2026-08-01)

> **CARD GATE — 2026-08-22. Check every claim below against `docs/PRICING.md` before posting.**
>
> From 2026-08-22 a **new account must put a card on file at first sign-in**
> before it can use the logged-in product (Stripe Checkout, $0 charged that day,
> 30-day Premium trial, first charge on day 30, one click to cancel before then).
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

**Why this instead of Reddit:** Reddit's finance subs auto-remove self-promo from
new/low-karma accounts. Product Hunt is the opposite — it's *built* for "I made
this," first-time makers launch there daily, and there's no karma/age wall. A
solid launch drives hundreds of visitors in a day. You post once; everything
below is paste-ready.

All copy is descriptive-only (no "beat the market"/buy/sell) — same compliance
rules as everywhere else.

---

## What only you supply
1. A **Product Hunt account** (free signup — no aging/karma needed).
2. **3–4 screenshots** (1270×760px): (a) the scanner table, (b) a ticker page's
   6-factor breakdown, (c) the /scorecard record, (d) the /verify download page.
   Just screen-grab them from the live site — no design work needed.
3. A **logo/thumbnail** (240×240 — the existing Tapeline mark works).
4. **Launch day:** be at your desk from **12:01am PT** (that's **5:01pm AEST**
   for you — actually a civilised hour) to reply to every comment for the first
   ~6 hours. First-hour engagement drives the ranking.

*(Optional but helps: ask someone with a PH following to "hunt" it. Self-launch
is fine now — don't block on finding a hunter.)*

---

## The listing

**Name:** Tapeline

**Tagline** (60 char max):
```
The stock scanner that publishes its track record
```
*(Alt: `A stock score you can audit — public factors, public record` — 59 char)*

**Topics/categories:** Fintech · Investing · Stocks · SaaS · Analytics

**Links:** website `https://tapeline.io` · pricing `https://tapeline.io/pricing`

**Description** (260 char max):
```
Every scanner shows you picks and hides what happened next. Tapeline scores every US stock 0–100 on six named factors, explains each in one line, and logs every daily top-10 vs SPY next day — wins and losses, never edited. Record free to read, no account.
```

---

## Maker's first comment (post this the moment you launch)

```
Hey Product Hunt 👋

I built Tapeline because every stock scanner I'd paid for had the same tell: they show you a leaderboard of picks and never show you what happened next.

So Tapeline does the opposite three ways:

1. One score, explained. Every US stock gets a 0–100 score from six named factors (Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum) — with a plain-English sentence on every row saying what's driving it. The six factors and their weight ordering are public at /how-it-works.

2. A record you can't edit. Every market day it freezes the top 10 and logs each name's next-day return vs SPY. Wins stay, losses stay, nothing gets quietly deleted. It's ~52 days deep and — honestly — the top-10 is beating SPY only about 47% of the time so far. I'm posting that on purpose. The point is that it's auditable, not that it's magic.

3. You can download the whole record and check my math (/verify).

The published record is genuinely usable on its own (live scores, the daily Top 10, a page per ticker, the full scorecard). Pro is $9.99/mo, Premium $19.99/mo (Congress trades + SEC Form 4 insider buys). The published record never asks for an account or a card. An account puts a card on file at first sign-in and starts the 30-day Premium trial — $0 charged today, first charge on day 30, one click to cancel.

Built solo from Melbourne. I'd genuinely love for this crowd to tear apart the methodology — which factor am I under-weighting? What would make the back-check defensible over a 1-year horizon instead of 1-day?
```

**Voice rules for replies:** describe, never prescribe. Never "buy/sell/should/
recommend/beat the market." If someone challenges the 47% record, agree it's
below a coin flip and link /scorecard — that candor is what earns upvotes here.

---

## Same-day cross-post: Show HN (second sanctioned venue)

The Show HN post is already written in [`FIRE_NOW.md`](FIRE_NOW.md) — post it the
same week (Tue or Thu, 8am ET) from any HN account. HN doesn't have Reddit's
new-account removal problem for Show HN submissions.

## Low-effort listings (do these once, they compound via SEO backlinks)

| Venue | Effort | Payoff |
|---|---|---|
| **Indie Hackers** — "I built…" post + product page | 15 min | Founder-friendly audience + dofollow-ish link |
| **BetaList** | 10 min | Early-adopter traffic + backlink |
| **AlternativeTo** — list as a Finviz / Trade Ideas alternative | 10 min | Captures "X alternative" searchers + backlink |
| **StockTwits** — profile + share the scorecard | 10 min | Finance-native, far less anti-promo than Reddit |

Each is a signup-and-submit — no karma wall. I can draft the copy for any of them.

---

## The honest timeline
Product Hunt = a **one-day spike** (real, but it fades). Show HN = another spike.
The listings = a slow trickle + SEO backlinks. **None of these replace the
compounding SEO base** (already indexed, climbing — I keep accelerating it in the
background). Think of PH/HN as the jump-start and SEO as the engine.
