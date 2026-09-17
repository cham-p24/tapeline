# Tapeline — Launch posts (compliant, ready to fire)

> **WHERE THE CARD SITS — updated 2026-09-15. Check every claim below against `docs/COPY_FACTS.md` and `docs/PRICING.md` before posting.**
>
> **WHAT CHANGED ON 14 SEPTEMBER 2026 — read before posting anything below.**
> The founder approved an integrity wave on 14 September 2026 that corrected the
> product and the site. Drafts below were written before it. False lines found
> on 15 September 2026 were corrected in place, but check each one against
> `docs/COPY_FACTS.md`, which has the measurements and times:
>
> - **Prices are delayed about 15 minutes.** Tapeline re-reads them for every
>   covered stock and ETF about every 60 seconds during US market hours (longer
>   around a deploy), and a score usually changes about once a day. Never call
>   the data live: not real-time, not sub-60s, not "every minute".
> - **Coverage** is about 11,500 US stocks and ETFs, plus about 100 crypto pairs
>   updated once a day. Not ~2,500.
> - **Congressional trades and squeeze detection do not exist today.** Do not
>   offer either as a feature, a Premium benefit or a score input.
> - **The record:** entries are not re-ranked or deleted. We have corrected
>   recorded values twice, and said so: prices on 25 August 2026, and scores from
>   18 May to 12 June capped on 15 June 2026. No top 10 was recorded for
>   31 August, 2 September, 4 September or 9 September 2026.
> - **The pre-charge email** goes about 7 days before the first charge.
>
> **Signing up takes an email and a password.** The account it makes lands on
> the Free plan and opens the scanner — the top ten scored rows of any
> scan, one saved screen. **A card is what starts the 30-day Premium trial**
> (Stripe Checkout, $0 charged that day, first charge on day 30, one click to
> cancel before then), and the trial is what turns on every matching row rather
> than the first ten, plus alerts, CSV export and per-ticker SEC Form 4
> filings.
>
> The **published record is free with no account at all**: the daily Top 10, the
> public scorecard, a page per scored ticker, and the raw CSV/JSON export. The
> scorecard's summary figures are current; its per-day entries are on a 7-day
> delay without Pro or Premium, and the CSV/JSON export stops 7 days back for
> every caller (`_FREE_DELAY_DAYS` in `backend/app/routers/scorecard.py`).
>
> So: **no line in this file may attach the card to the ACCOUNT or to SIGNING
> IN.** Attach it to the TRIAL, which genuinely requires one. Three layers, in
> this order: the record needs no account; signing up takes an email and a
> password; a card starts the trial.
>
> _History: until 15 September 2026 this block was headed "CARD GATE —
> 2026-08-22" and described the card wall on new accounts, and told writers
> that no line may call an account free. That was true only while the wall
> ran (#548, 2026-08-22, to #683, 2026-08-30)._
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
- **No performance claims.** The public scorecard trails SPY (read the current hit rate on `/scorecard`; do not quote it in copy).
  Any "beat the market / +X% vs SPY" line is false AND a Google/FTC/ASIC violation. The
  hook is the honesty: *"Most scanners show you the wins. We show the whole record —
  losses included."*
- **Current facts (corrected 2026-09-15 — see `docs/COPY_FACTS.md`):** about 11,500 US stocks and ETFs scored on prices delayed about 15 minutes, re-read about every 60 seconds in US market hours (scores usually change about once a day) · six-factor score whose
  factor set and weight ordering are public (the exact weights are not) · one-sentence "why"
  per ticker · public scorecard freezes each daily top-10 and back-checks vs SPY, keeping the
  losing days · **Free with no account at all:** the daily Top 10, the public scorecard (per-day
  entries on a 7-day delay), a page per scored ticker and the raw CSV/JSON export (to 7 days ago) · signing up takes an email and a password
  and opens Free (top-10 rows, 12 look-ups/day, 5-ticker watchlist) · a card starts the 30-day
  Premium trial ($0 today, first charge day 30, an email about 7 days before it, one-click cancel) · **Pro** $9.99/mo ($8.25/mo annual) · **Premium** $19.99/mo
  ($16.58/mo annual, founding pricing — locked in for early subscribers) adds per-ticker SEC Form 4 insider filings,
  unlimited email alerts, public API. (No 13F/Quiver — removed. No congressional trade data and no working squeeze detection — removed from sale 2026-09-14.) Entries on the record are not re-ranked or deleted; recorded values were corrected twice (prices on 25 August 2026; scores from 18 May to 12 June capped on 15 June 2026); no top 10 was recorded for 31 August, 2, 4 or 9 September 2026.

---

## X / Twitter — launch tweet (pin it)

**Variant A — anti-hype:**
```
Most stock scanners show you a highlight reel.

Tapeline publishes the whole tape: one 0–100 score on about 11,500 US stocks and ETFs from six named
factors, and a scorecard that freezes the daily top-10 and grades it against
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
I built Tapeline. It scores about 11,500 US stocks and ETFs on one published
6-factor methodology (trend, relative strength, fundamentals, smart-money, macro, momentum —
factor set and weight ordering on /how-it-works) and writes a one-sentence plain-English
"why" per ticker.

The part I care about: it freezes the daily top-10 and back-checks them against SPY on a
public scorecard that keeps the losing days. Honest status — the record currently trails
SPY. I leave it up; entries are not re-ranked or deleted, and the two corrections I've made
to recorded values are dated on the page. The whole point is you can check my work instead of
trusting a screenshot. (Prices are delayed about 15 minutes; most score inputs are daily.)

It is NOT a tip service — no buy/sell calls. It's a fast, transparent screen; you see which
factors drove each score and decide for yourself.

The public record (daily Top 10, scorecard, per-ticker pages, CSV/JSON) needs no account and
no card. Signing up takes an email and a password. A card starts the 30-day Premium trial —
$0 today, first charge on day 30, cancel in one click. I'd love the methodology torn apart — what factor would you add or
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

The scorecard freezes the daily top-10 and grades it against SPY — wins and losses both
stay up. Honest status: it currently trails SPY. Small sample, and I'm leaving it public
regardless. Entries are not re-ranked or deleted, and the corrections I've made are dated.

Not advice, no buy/sell calls — descriptive analytics you verify yourself. About 11,500 US stocks
and ETFs, on prices delayed about 15 minutes. The daily Top 10 and the scorecard are public (per-day entries on a 7-day delay) — no account, no card.

Genuine question for the sub: would you trust a score more if you could read what goes into
it, or is the obscurity doing useful work? (links in a comment)
```

---

## Product Hunt
**Schedule:** Tuesday, 12:01 AM PT. Line up 5–10 friends to upvote in hour 1.
**Tagline:** "Stock scanner that shows its work — and keeps its receipts."

**First comment (post immediately):**
```
Hey all — Christian, founder.

I got tired of every commercial scanner hiding its method and its track record, so
Tapeline publishes both:
· One 0–100 score per US ticker from six published factors (weight ordering public, exact
  numbers not)
· One plain-English sentence why, on every row
· A public scorecard that freezes the daily top-10 vs SPY — losing days kept

Honest note: the record currently trails SPY, and it's all on the page. The product is the
transparency and the time saved, not a promise of returns.

The published record needs no account at all. The 30-day Premium trial takes a card, charges
$0 today, first charge day 30, cancels in one click. AMA.
Feedback I'd love: is /how-it-works clear, and would you share a /t/[ticker] page?
```

---

## IndieHackers — /launches/new
**Title:** "After years of stock scanners, I built one that shows its work"
```
TL;DR: Tapeline scores about 11,500 US stocks and ETFs with a published 6-factor methodology, writes
a one-line why, and publishes a scorecard that back-checks the daily top-10 vs SPY — losses
kept. tapeline.io · the published record is free with no account · 30-day Premium trial, card
required ($0 today, first charge day 30).

Every prosumer scanner I tried fails the same way: black-box score, no track record, and a
free tier crippled to upgrade-trap you. So I built the opposite — a published factor set and
weight ordering, a public scorecard that keeps its losing days (it currently trails SPY;
that's the honest data, and it stays up), and a record anyone can read with no account at all.

Founding pricing while it earns a track record: Pro $8.25/mo annual, Premium $16.58/mo annual (adds per-ticker
insider Form 4 filings, unlimited alerts, API). Stack: FastAPI + Postgres + Next.js;
Massive for prices, Finnhub for fundamentals, SEC EDGAR for Form 4, FRED for macro.

It's descriptive research tooling, not advice — no buy/sell calls. Kick the tires and tell
me what's broken.
```

---

## Email — supporters / waitlist
```
Subject: Tapeline is live (please beat it up)

Tapeline is live at tapeline.io. The short version:
· 6-factor score on about 11,500 US stocks and ETFs, one-sentence why per row
· A public scorecard that keeps its losing days (honest: it currently trails SPY)
· The published record is free and needs no account; the 30-day Premium trial takes a card
  ($0 today, first charge day 30, one-click cancel)

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
