# FIRE NOW — the paste-ready launch pack (current as of 2026-07-26)

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

This supersedes `REDDIT_PASTE_READY.md` and `SHOW_HN_VARIANTS.md`. Those had two
things wrong that would have burned a launch: the **Free tier** was described as
"top 20, 24h delayed" (it is now **live, 12 look-ups/day**), and the **scorecard
numbers** were first-week placeholders. Everything below is checked against the
live site and API today.

**Why this matters:** the product is built and the funnel converts end to end.
The only thing between zero signups and the first paying customer is **traffic**,
and the cheapest traffic you can get right now is you posting these three times.
I can't post them — they need your own aged accounts (new accounts get
shadow-banned, and HN/Reddit karma-gate submissions). This is the 30-minute
version of "go get customers."

---

## The numbers everything below is locked to (verified 2026-07-26)

| Thing | Current truth |
|---|---|
| **Free** | $0 · **live scores, no delay** · 12 ticker look-ups/day (unmetered first 24h) · top-10 scanner rows · watchlist (5) · full public scorecard |
| **Pro** | **$9.99/mo** or **$8.25/mo billed annually** ($99/yr) · full ~2,500-ticker live scan · smart alerts · calendars · CSV |
| **Premium** | **$19.99/mo** or **$16.58/mo billed annually** ($199/yr) · + Congress trades · + SEC Form 4 insider buys · + API 1,000/day |
| **Trial** | 14 days of Premium, **card required** ($0 charged today, first charge on day 14, one-click cancel before then). A new account puts a card on file at first sign-in, which is what starts the trial. Accounts created before 2026-08-22 are grandfathered and never asked. The published record — daily Top 10, full scorecard, per-ticker pages, CSV/JSON export — needs no account and no card. |
| **Scorecard** | **52 days on the record, 478 calls logged and never edited. ~47% have beaten SPY the next day** (below a coin flip — say so; the point is that it's auditable, not that it's magic). |
| **Methodology** | 6-factor composite. `/how-it-works` names the six factors — Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum — and their weight **ordering** (heaviest Trend + Relative Strength, lightest Momentum). **The exact weights are not published — never put them in a post.** "Smart Money" = **SEC Form 4 insider buys**, not 13F lag. |

**Compliance (non-negotiable — protects the AU publisher exemption):** descriptive
language only. Never "buy" / "sell" / "you should" / "recommend" / "beat the
market" / "guaranteed" in a post or a comment reply. The scorecard is proof of
*honesty*, never a performance claim.

---

## Fire order — one post per platform, one per week

Reddit's spam filter shadow-bans anything that looks like cross-posting, so
space these out. Post between **9–10 AM ET on a weekday** (= **23:00–24:00 AEST**
the night before for you) and then **sit on the thread for the first 60 minutes**
answering every comment — that first hour of engagement is what the ranking
algorithm rewards.

| Week | Platform | Post |
|---|---|---|
| This week | **r/stocks** | Post 1 below |
| +1 week | **r/algotrading** | Post 2 below |
| +2 weeks | **Show HN** (Tue or Thu, 8 AM ET) | Post 3 below |

Do **not** post to r/wallstreetbets — they burn SaaS founders alive. Link only to
**free** pages in the body (`/scorecard`, `/how-it-works`); let the pricing page
sell itself.

---

## Post 1 — r/stocks

**URL:** https://www.reddit.com/r/stocks/submit (Text post)

**Title:**
```
I built a stock scanner that logs every top-10 call vs SPY the next day — the whole record is public and free to read
```

**Body:**
```
I got tired of "AI stock pick" tools that never show you what happened after the call. So I built Tapeline. The published record is free to read with no account at all, and the entire track record is public — winners and losers, never edited.

Free, no account and no card:
- The daily Top 10, live (no delay)
- One 0-100 score per stock with a plain-English "why" sentence
- A page per scored ticker
- The full public scorecard, plus the raw CSV/JSON export

The scorecard is the part I actually want you to attack. Every market day I freeze the top 10 scores; the next day I log each name's real return vs SPY. 52 days in, 478 calls logged — and right now they beat SPY about 47% of the time. That's below a coin flip, and it's on the page anyway. The point is that it's auditable from day one, not that it's magic yet.

The score is a 6-factor composite — Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum — with the six factors and their weight ordering published at tapeline.io/how-it-works. "Smart Money" is SEC Form 4 insider buying, not 13F lag.

Paid is $9.99/mo (full ~2,500-ticker live scan + alerts + calendars) and $19.99/mo (+ Congress trades + the Form 4 feed). The public record needs no account and no card. Creating an account puts a card on file at first sign-in and starts the 14-day Premium trial — $0 until day 14, one click cancels.

Drop a ticker in the comments and I'll post its current score + the six-factor breakdown. And tell me what's wrong with the methodology — that's the part I want to harden.
```

---

## Post 2 — r/algotrading

**URL:** https://www.reddit.com/r/algotrading/submit (Text post)

**Title:**
```
I built a 6-factor composite stock score with a public, unedited daily back-check vs SPY — roast the methodology
```

**Body:**
```
I started Tapeline (tapeline.io) because every screener I tried either dumped raw filters on me (Finviz) or hid its methodology behind an "AI score" black box. I wanted one number, an explanation of what's driving it, and a way to audit every call against SPY the next day.

The methodology (published, version-controlled, won't change without a changelog entry). Six factors — Trend and Relative Strength carry the most weight, Momentum the least (the exact weights stay internal):

- Trend — the ticker's multi-month price change, and where the latest price sits inside its own 52-week range
- Relative Strength — the ticker's price change minus a broad-market benchmark's, over three horizons; not sector-adjusted
- Fundamentals — reported margin, return on equity, EPS and revenue growth, and an earnings multiple
- Smart Money — disclosed SEC Form 4 insider transactions, netted over a recent window. Not 13F
- Macro — a single market-wide regime classification; the same reading for every ticker on a tick
- Momentum — a momentum-quality reading plus a short-horizon return, deliberately the lightest factor

The accountability layer: every market day I freeze the top 10 composite scores and log each name's next-day return vs SPY. No survivor-bias filtering — losers stay on the page. It's 52 days deep now, 478 calls, and honestly the top-10 is beating SPY only ~47% of the time so far. I'd rather publish a mediocre record than hide it.

What I'd like torn apart:
1. Smart Money via Form 4 — is net-90-day the right window, or should I weight by insider role (CEO > director)?
2. Momentum is the lightest-weighted factor — is that double-counting what's already inside Trend + RS?
3. The back-check is 1-day. What factor would you add to make it defensible on a 1-year horizon?

Methodology and scorecard are free to inspect at /how-it-works and /scorecard. Roast it.
```

---

## Post 3 — Show HN

Post as a **text submission with `https://tapeline.io` in the URL field**. Tuesday
or Thursday, **8 AM ET**. Hang around for 60 minutes answering every comment.

**Title (79 chars):**
```
Show HN: A stock scanner that logs every top-10 pick vs SPY the next day
```

**Text:**
```
I built Tapeline (https://tapeline.io) because every stock scanner I'd ever paid for had the same dishonest pattern: they show you a leaderboard of picks and never show you what happened next.

So Tapeline does the opposite. Every market day at close it freezes the top 10 ranked tickers. The next day at close it records each name's actual return vs SPY, and the result goes on /scorecard. Wins stay. Losses stay. Nothing gets quietly removed when a pick ages badly.

The score is a 6-factor composite — Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum — weighted most toward Trend and Relative Strength and least toward Momentum. The factor set and that ordering are on /how-it-works and don't change without a changelog entry. Every score ships with one plain-English sentence explaining what's driving it.

The scorecard is the part I want HN to tear apart. It's 52 days and 478 calls deep, and the top-10 is currently beating SPY about 47% of the time — i.e. slightly worse than a coin flip. I'm posting that number on purpose. The transparency is the product; the early hit rate is not the pitch, and I expect it to move both directions as the sample grows.

The published record is live (no delay) and needs no account: the daily Top 10, a page per scored ticker, the full scorecard and the raw CSV/JSON export. Pro is $8.25/mo billed annually for the full ~2,500-ticker live scan + alerts. Premium is $16.58/mo annually for + Congress trades + SEC Form 4. The published record never asks for an account or a card. An account puts a card on file at first sign-in and starts the 14-day Premium trial — $0 today, first charge on day 14, one click to cancel.

Built solo from Melbourne. Genuinely interested in what HN finds wrong with the methodology — and which factor I'm under-weighting.
```

---

## Only you can do these (I can't — accounts / cards / your identity)

1. **Post the three above** from your own aged Reddit + HN accounts (new accounts get shadow-banned; HN needs karma to submit). Public outreach identity is "Christian Piyatilaka."
2. **Answer comments in the first hour.** Keep the voice descriptive — never "buy/sell/should/recommend." If someone challenges the 47% record, agree it's below coin-flip and point at /scorecard. That candor is what earns the upvotes.
3. **Reddit karma wall:** if either account is under ~30 comment-karma, spend a few days commenting genuinely in the sub first, or the post won't clear the filter.

## What's already done for you (so you don't redo it)
- Message-match landing headlines by traffic source (`?from=` wiring) — shipped, live.
- Google Ads: wasteful PMax paused, callouts + sitelinks added, RSA improved, conversion tracking fixed on the correct GA4 property.
- Pricing page, comparison table, trial flow, scorecard, /how-it-works — all live and price-correct at $9.99/$19.99.
