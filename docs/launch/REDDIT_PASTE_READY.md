> ⚠️ **SUPERSEDED (2026-07-26) — use [`FIRE_NOW.md`](FIRE_NOW.md) instead. Do not paste from this file.**
> The prices here ($9.99/$19.99) are still correct, but the **Free-tier
> description below is wrong** — Free is the top-10 rows and 12 look-ups/day,
> not "top 20, 24h delayed" — and the scorecard numbers are first-week
> placeholders. `FIRE_NOW.md` has the corrected, current paste-ready posts.
>
> **Updated 2026-09-15:** false lines below (congressional trades, "~2,500",
> "sub-60 seconds", "live", "unedited", a card at sign-in) were corrected in
> place so a stray paste does less harm. Every plan's prices are delayed about
> 15 minutes. Check `docs/COPY_FACTS.md` before posting anything.

# Reddit paste-ready — Tue 19 May launch week

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

Three subs, three posts. Reddit + MCP-blocked, so the agent can't drive
the submit form — paste these into the browser yourself.

**Premium smart-money surface**: "Elite 13F holdings (Buffett, Burry, Ackman,
etc.)" was stripped from marketing in PR #74 (Quiver Trader-tier TOS
"No Commercial Use Rights") and the adapter has since been deleted. The
Premium smart-money surface is **per-ticker SEC Form 4 insider filings**. (It
used to say "plus Congressional trades"; there has never been a real source for
those, and #820 removed the claim on 2026-09-14.)

---

## 1. r/stocks — Tue 19 May, 9 AM ET (= 23:00 AEST tonight)

URL: https://www.reddit.com/r/stocks/submit

**Title (~85 chars):**
```
Built a free stock score tool — every call back-checked vs SPY next day, record public
```

**Body:**
```
I got annoyed at every "AI stock recommendation" service refusing to show its track record. So I built Tapeline. The record is public — no account needed to read it.

What's free:
- One 0-100 score per stock with a plain-English why
- Public scorecard of the daily top 10 it records, back-checked against SPY the next day
- 5-ticker watchlist

What costs $9.99/mo (Pro):
- Every row of the scan (about 11,500 US stocks and ETFs)
- Smart watchlist alerts when scores move
- IPOs / earnings / news calendar

What costs $19.99/mo (Premium):
- + API access
- + Recent insider buys (SEC Form 4) across the active universe

30-day Premium trial — a card starts it, $0 charged that day, first charge on day 30, cancel in one click before then. Signing up itself takes only an email and a password. The daily Top 10 and the public scorecard (per-day entries on a 7-day delay) are readable with no account.

Try it on any ticker you like — tapeline.io/t/AAPL, tapeline.io/t/NVDA, whatever. Drop your favorite ticker in comments and I'll post its current score + the breakdown.

Tell me what's missing. Roast the methodology at /how-it-works.
```

---

## 2. r/algotrading — Thu 21 May, 10 AM ET

URL: https://www.reddit.com/r/algotrading/submit

**Title:**
```
I built a 6-factor composite stock score with a public daily back-check vs SPY
```

**Body:** (mirrors LAUNCH_PLAYBOOK.md — already mentions Form 4)
```
Three months ago I started Tapeline (tapeline.io) because every screener I tried either showed me raw filters (Finviz) or hid its methodology behind an "AI score" black box (Simply Wall St). I wanted something that picks a single number, tells me what's driving it, and lets me audit every call against SPY the next day.

Here's what I shipped:

**The methodology** (version-controlled, changelogged). Six factors — Trend and Relative Strength carry the most weight, Momentum the least (the exact weights stay internal):

- Trend — the ticker's multi-month price change, and where the latest price sits inside its own 52-week range
- Relative Strength — the ticker's price change minus a broad-market benchmark's, over three horizons; not sector-adjusted
- Fundamentals — reported margin, return on equity, EPS and revenue growth, and an earnings multiple
- Smart Money — disclosed SEC Form 4 insider transactions, netted over a recent window — *not* 13F
- Macro — a single market-wide regime classification; the same reading for every ticker on a tick
- Momentum — a momentum-quality reading plus a short-horizon return, deliberately the lightest factor

**The accountability layer**

Each trading day I freeze the top 10 composite scores. The next day I log each name's actual return vs SPY. The history lives at /scorecard (per-day entries on a 7-day delay without a paid plan) with no survivor bias filtering — losers stay on the page, and corrections and days with no list are dated. Win-rate / avg alpha / beat-SPY rate columns fill in after each session resolves.

**What I'd like feedback on**

1. Smart Money via Form 4 — is net-90-day buying the right window, or should I weight by insider role (CEO > director)?
2. Should momentum carry even less weight than it does, given it's already inside trend + RS?
3. What factor would you add to make this defensible for a 1Y horizon vs the current 1D back-check?

Roast it. The methodology is the part I want to harden.
```

---

## 3. r/SecurityAnalysis — Tue 26 May, 9 AM ET

URL: https://www.reddit.com/r/SecurityAnalysis/submit

**Title:**
```
Tapeline — synthesises 6 factor signals into one score, plain-English Why per ticker, public daily scorecard
```

**Body:** (corrections — "Congress / 13F" → "SEC Form 4"; cadence and delay per `docs/COPY_FACTS.md`)
```
At tapeline.io. Built it because I wanted to stop manually weighing trend / RS / fundamentals / insider activity every time I screened.

The Fundamentals factor reads five reported figures:
- Revenue growth between reported periods
- EPS growth between reported periods
- Profit margin, as reported
- Return on equity, as reported
- An earnings multiple — lower moves the reading up

Scores are recalculated about every 60 seconds during US market hours on prices delayed about 15 minutes (Massive, formerly Polygon). Most inputs are daily readings (fundamentals, SEC Form 4 filings, FRED macro), so a score usually changes about once a day.

Concrete example a SecurityAnalysis crowd might find useful: filter to /sector/financials and the score will give you a 0-100 read on every financial. Click any ticker → /t/$X → see the six-factor breakdown so you can drill into which factor is dragging or pulling.

Free tier covers everything I'd want as a generalist (score + scorecard + 5-ticker watchlist). Pro $9.99 unlocks the full universe. Premium $19.99 adds per-ticker SEC Form 4 filings.

Happy to take fundamentals-specific critique — especially on the fact that the same bands are applied to every company regardless of sector, so a bank, a biotech and a software name land on one scale.
```

---

## Posting playbook (per LAUNCH_PLAYBOOK.md §2)

- One sub per week. Reddit's spam filter shadowbans cross-posts.
- Post body links only to FREE public pages (/scorecard, /how-it-works) —
  let the pricing page sell itself.
- Hang around the first 60 min answering every comment.
- Don't reply defensively to "shilling" accusations — link to /scorecard.
- Don't post in r/wallstreetbets — they burn SaaS founders alive.
