# FIRE NOW — the paste-ready launch pack (written 2026-07-26; false lines corrected 2026-09-15)

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

This supersedes `REDDIT_PASTE_READY.md` and `SHOW_HN_VARIANTS.md`. Those had two
things wrong that would have burned a launch: the **Free tier** was described as
"top 20, 24h delayed" (it is now the top 10 rows and 12 look-ups/day, on the same
15-minute-delayed prices as every plan), and the **scorecard numbers** were
first-week placeholders. The posts below were checked against the site on
2026-07-26 and corrected against `docs/COPY_FACTS.md` on 2026-09-15; the record
figures are now placeholders you fill in from `/api/scorecard` on the day.

**Why this matters:** the product is built and the funnel converts end to end.
The only thing between zero signups and the first paying customer is **traffic**,
and the cheapest traffic you can get right now is you posting these three times.
I can't post them — they need your own aged accounts (new accounts get
shadow-banned, and HN/Reddit karma-gate submissions). This is the 30-minute
version of "go get customers."

---

## The numbers everything below is locked to (verified 2026-07-26, corrected 2026-09-15)

| Thing | Current truth |
|---|---|
| **Free** | $0, no card · 12 ticker look-ups/day (unmetered first 24h) · top-10 scanner rows · watchlist (5) · 1 saved screen · public scorecard (per-day entries on a 7-day delay) |
| **Prices** | Delayed about 15 minutes on every plan; re-read about every 60 seconds during US market hours. Scores usually change about once a day. Never "live" or "no delay" |
| **Pro** | **$9.99/mo** or **$8.25/mo billed annually** ($99/yr) · every row of the scan (about 11,500 US stocks and ETFs) · alerts · calendars · CSV |
| **Premium** | **$19.99/mo** or **$16.58/mo billed annually** ($199/yr) · + per-ticker SEC Form 4 filings · + API 1,000/day |
| **Trial** | 30 days of Premium, **card required** ($0 charged today, first charge on day 30, an email about 7 days before it, one-click cancel before then). Signing up takes an email and a password. Adding a card is what starts the trial. The published record — daily Top 10, the public scorecard (per-day entries on a 7-day delay), per-ticker pages, CSV/JSON export (to 7 days ago) — needs no account and no card. |
| **Scorecard** | Pull `[DAYS]` and `[CALLS]` from `/api/scorecard` on the day you post. Do not put a hit rate in a post that stays up: link `/scorecard`, which carries the current figure and its sample size (`docs/COPY_FACTS.md` §3). For reference, on 2026-07-26 it was 52 days, 478 calls and ~47% beating SPY the next day. Entries are not re-ranked or deleted; recorded values were corrected twice (prices on 25 August 2026; scores from 18 May to 12 June capped on 15 June 2026); no top 10 was recorded for 31 August, 2, 4 or 9 September 2026. |
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
I built a stock scanner that logs each top-10 call vs SPY the next day — the record is public and free to read
```

**Body:**
```
I got tired of "AI stock pick" tools that never show you what happened after the call. So I built Tapeline. The published record is free to read with no account at all, and the track record is public — winners and losers, with any correction dated.

Free, no account and no card:
- The daily Top 10
- One 0-100 score per stock with a plain-English "why" sentence
- A page per scored ticker
- The public scorecard (without a paid plan, the last 7 days of entries are held back), plus the raw CSV/JSON export

The scorecard is the part I actually want you to attack. At the close I freeze the day's top 10 scores; the next day I log each name's real return vs SPY. [CALLS] calls logged over [DAYS] trading days. The share that beat SPY the next session is on the page with its sample size, whatever it says on the day you read this, along with the two corrections we made to recorded values and the four days with no list. The point is that it's auditable from day one, not that it's magic yet.

The score is a 6-factor composite — Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum — with the six factors and their weight ordering published at tapeline.io/how-it-works. "Smart Money" is SEC Form 4 insider buying, not 13F lag.

Prices are delayed about 15 minutes. Paid is $9.99/mo (every row of the scan, about 11,500 US stocks and ETFs, + alerts + calendars) and $19.99/mo (+ per-ticker SEC Form 4 filings + API). The public record needs no account and no card. Signing up takes an email and a password. A card starts the 30-day Premium trial — $0 until day 30, one click cancels.

Drop a ticker in the comments and I'll post its current score + the six-factor breakdown. And tell me what's wrong with the methodology — that's the part I want to harden.
```

---

## Post 2 — r/algotrading

**URL:** https://www.reddit.com/r/algotrading/submit (Text post)

**Title:**
```
I built a 6-factor composite stock score with a public daily back-check vs SPY — roast the methodology
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

The accountability layer: at the close I freeze the day's top 10 composite scores and log each name's next-day return vs SPY. No survivor-bias filtering — losers stay on the page, and corrections are dated. It's [DAYS] trading days deep now, [CALLS] calls, and the share that beat SPY is on /scorecard with its sample size. I'd rather publish the record as it is than hide the misses.

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

**Title (75 chars):**
```
Show HN: A stock scanner that records its daily top 10 and checks it vs SPY
```

**Text:**
```
I built Tapeline (https://tapeline.io) because every stock scanner I'd ever paid for had the same dishonest pattern: they show you a leaderboard of picks and never show you what happened next.

So Tapeline does the opposite. At the close it freezes the day's top 10 ranked tickers. The next day at close it records each name's actual return vs SPY, and the result goes on /scorecard. Wins stay. Losses stay. Entries are not re-ranked or deleted; we have corrected recorded values twice and dated both, and the four days with no list are listed on the page.

The score is a 6-factor composite — Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum — weighted most toward Trend and Relative Strength and least toward Momentum. The factor set and that ordering are on /how-it-works and don't change without a changelog entry. Every score ships with one plain-English sentence explaining what's driving it.

The scorecard is the part I want HN to tear apart. It's [DAYS] trading days and [CALLS] calls deep, and the share of picks that beat SPY the next session is on /scorecard with its sample size. The transparency is the product; the hit rate is not the pitch, and I expect it to move both directions as the sample grows.

The published record needs no account: the daily Top 10, a page per scored ticker, the public scorecard (per-day entries on a 7-day delay) and the raw CSV/JSON export. Prices are delayed about 15 minutes, and most score inputs are daily readings. Pro is $8.25/mo billed annually for every row of the scan (about 11,500 US stocks and ETFs) + alerts. Premium is $16.58/mo annually for + per-ticker SEC Form 4 filings + API. Signing up takes an email and a password. A card starts the 30-day Premium trial — $0 today, first charge on day 30, one click to cancel.

Built solo from Melbourne. Genuinely interested in what HN finds wrong with the methodology — and which factor I'm under-weighting.
```

---

## Only you can do these (I can't — accounts / cards / your identity)

1. **Post the three above** from your own aged Reddit + HN accounts (new accounts get shadow-banned; HN needs karma to submit). Public outreach identity is "Christian Piyatilaka."
2. **Answer comments in the first hour.** Keep the voice descriptive — never "buy/sell/should/recommend." If someone challenges the record, agree it's below coin-flip and point at /scorecard. That candor is what earns the upvotes.
3. **Reddit karma wall:** if either account is under ~30 comment-karma, spend a few days commenting genuinely in the sub first, or the post won't clear the filter.

## What's already done for you (so you don't redo it)
- Message-match landing headlines by traffic source (`?from=` wiring) — shipped, live.
- Google Ads: wasteful PMax paused, callouts + sitelinks added, RSA improved, conversion tracking fixed on the correct GA4 property.
- Pricing page, comparison table, trial flow, scorecard, /how-it-works — all live and price-correct at $9.99/$19.99.
