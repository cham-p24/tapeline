# Tapeline — Launch posts (compliant, ready to fire)

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

Corrected 2026-06-26 to the **locked positioning** (process + honesty + time-saving,
**never performance**) and the **current product**. The prior version of this file was
stale and non-compliant (it claimed "+0.4% above SPY", described the old 20-ticker/24h
free tier, and pitched the removed Quiver/13F feature) — all removed.

## Hard rules (do not undo)
- **No performance claims.** The public scorecard currently trails SPY (~42% hit-rate).
  Any "beat the market / +X% vs SPY" line is false AND a Google/FTC/ASIC violation. The
  hook is the honesty: *"Most scanners show you the wins. We show the whole record —
  losses included."*
- **Current facts:** ~2,500 US-listed tickers scored every minute · six-factor score whose
  factor set and weight ordering are public (the exact weights are not) · one-sentence "why"
  per ticker · public scorecard freezes each daily top-10 and back-checks vs SPY, keeping the
  losing days · **Free with no account at all:** the daily Top 10, the complete scorecard, a
  page per scored ticker and the raw CSV/JSON export · a **new account puts a card on file at
  first sign-in**, which starts the 30-day Premium trial ($0 today, first charge day 14,
  one-click cancel); accounts created before 2026-08-22 are grandfathered on Free (top-10 rows
  live, 12 look-ups/day, 5-ticker watchlist) · **Pro** $9.99/mo ($8.25/mo annual) · **Premium** $19.99/mo
  ($16.58/mo annual, founding pricing — locked in for early subscribers) adds Congressional-trades feed, recent insider buys (SEC Form 4),
  unlimited email alerts, public API. (No 13F/Quiver — removed.)

---

## X / Twitter — launch tweet (pin it)

**Variant A — anti-hype:**
```
Most stock scanners show you a highlight reel.

Tapeline publishes the whole tape: one 0–100 score on every US stock from six named
factors, and a scorecard that freezes every daily top-10 and grades it against
the S&P — losing days kept on the page.

The published record is free — no account, no card. The 30-day Premium trial takes one:
$0 today, one click to cancel. tapeline.io
```

**Variant B — origin:**
```
For years I cancelled every stock scanner within a month — they all hide what goes into the
score and bury their losers.

So I built one that publishes both: the six factors behind every score and how they rank,
and a public scorecard that keeps its losing days. Not tips. A transparent screen. tapeline.io
```

**Reply 5 min later (the method):**
```
What's in the score, published on /how-it-works:

trend · relative strength · fundamentals · smart money · macro · momentum

Weighted most toward trend and relative strength, least toward momentum. The factor set and
the ordering are published; the exact numbers aren't. The day it stops working, the
scorecard will show it and you can leave.
```

---

## Show HN
**Title:** Show HN: Tapeline – a stock scanner that publishes its methodology and its losing days
```
I built Tapeline. It scores every US-listed stock (~2,500) every minute on one published
6-factor methodology (trend, relative strength, fundamentals, smart-money, macro, momentum —
factor set and weight ordering on /how-it-works) and writes a one-sentence plain-English
"why" per ticker.

The part I care about: it freezes each day's top-10 and back-checks them against SPY on a
public scorecard that keeps the losing days. Honest status — the record currently trails
SPY. I leave it up exactly as-is; the whole point is you can check my work instead of
trusting a screenshot.

It is NOT a tip service — no buy/sell calls. It's a fast, transparent screen; you see which
factors drove each score and decide for yourself.

The public record (daily Top 10, scorecard, per-ticker pages, CSV/JSON) needs no account and
no card; the signed-in product takes a card at first sign-in — $0 today, first charge on day
14, cancel in one click. I'd love the methodology torn apart — what factor would you add or
drop?
tapeline.io
```

---

## Reddit (r/algotrading, r/stocks, r/investing, r/SecurityAnalysis)
> Needs account karma/age or it's auto-removed. Comment helpfully for a few days first.
> Lead with the idea; link low/in a comment. One sub, no same-day cross-posting.

**Title:** I built a stock scanner and made it publish its own losing days. Here's the record.
```
Almost no prosumer scanner publishes its scoring methodology or its track record, for two
honest reasons: publish the method and users can audit it (and leave the day it stops
working); publish the record and you eat your losers in public.

I did both anyway. The method:
Six factors — trend, relative strength, fundamentals, smart money, macro, momentum —
weighted most toward trend and relative strength, least toward momentum. The ordering is
published; the numbers are not.

The scorecard freezes each day's top-10 and grades it against SPY — wins and losses both
stay up. Honest status: it currently trails SPY. Small sample, and I'm leaving it public
regardless — editing it would defeat the point.

Not advice, no buy/sell calls — descriptive analytics you verify yourself. ~2,500 US names
scored every minute. The daily Top 10 and the full record are public — no account, no card.

Genuine question for the sub: would you trust a score more if you could read what goes into
it, or is the obscurity doing useful work? (links in a comment)
```

---

## Product Hunt
**Schedule:** Tuesday, 12:01 AM PT. Line up 5–10 friends to upvote in hour 1.
**Tagline:** "Live stock scanner that shows its work — and keeps its receipts."

**First comment (post immediately):**
```
Hey all — Christian, founder.

I got tired of every commercial scanner hiding its method and its track record, so
Tapeline publishes both:
· One 0–100 score per US ticker from six published factors (weight ordering public, exact
  numbers not)
· One plain-English sentence why, on every row
· A public scorecard that freezes each day's top-10 vs SPY — losing days kept

Honest note: the record currently trails SPY, and it's all on the page. The product is the
transparency and the time saved, not a promise of returns.

The published record needs no account at all. The 30-day Premium trial takes a card, charges
$0 today, first charge day 14, cancels in one click. AMA.
Feedback I'd love: is /how-it-works clear, and would you share a /t/[ticker] page?
```

---

## IndieHackers — /launches/new
**Title:** "After years of stock scanners, I built one that shows its work"
```
TL;DR: Tapeline scores every US ticker (~2,500) with a published 6-factor methodology, writes
a one-line why, and publishes a scorecard that back-checks each day's top-10 vs SPY — losses
kept. tapeline.io · the published record is free with no account · 30-day Premium trial, card
required ($0 today, first charge day 14).

Every prosumer scanner I tried fails the same way: black-box score, no track record, and a
free tier crippled to upgrade-trap you. So I built the opposite — a published factor set and
weight ordering, a public scorecard that keeps its losing days (it currently trails SPY;
that's the honest data, and it stays up), and a record anyone can read with no account at all.

Founding pricing while it earns a track record: Pro $8.25/mo annual, Premium $16.58/mo annual (adds Congress
trades, insider Form 4, unlimited alerts, API). Stack: FastAPI + Postgres + Next.js;
Massive for prices, Finnhub for fundamentals + Form 4, FRED for macro.

It's descriptive research tooling, not advice — no buy/sell calls. Kick the tires and tell
me what's broken.
```

---

## Email — supporters / waitlist
```
Subject: Tapeline is live (please beat it up)

Tapeline is live at tapeline.io. The short version:
· 6-factor score on every US ticker, one-sentence why per row
· A public scorecard that keeps its losing days (honest: it currently trails SPY)
· The published record is free and needs no account; the 30-day Premium trial takes a card
  ($0 today, first charge day 14, one-click cancel)

Two things I'd love feedback on:
1. /how-it-works — is the methodology clear to a non-technical trader?
2. Set up a 3-ticker watchlist for 24h — are the alerts actually useful?

Reply with anything broken — I read every one. — Christian
```

---

## Posting order + what NOT to do
**Order:** your X (pin) → IndieHackers → one Reddit sub → Show HN (only if the tweet got
traction) → Product Hunt (Tue) → 10 warm DMs to traders you respect. One channel/day.
**Never:** claim returns or "beats the market" · post to r/wallstreetbets · email-blast a
cold list · run paid ads in week one. Descriptive labels only.
