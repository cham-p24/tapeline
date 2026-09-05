> ⚠️ **SUPERSEDED (2026-07-26) — use [`FIRE_NOW.md`](FIRE_NOW.md) instead.**
> The prices here ($9.99/$19.99) are still correct, but the **Free-tier
> description below is wrong** — Free is now *live* (12 look-ups/day, top-10
> rows), not "top 20, 24h delayed" — and the scorecard numbers are first-week
> placeholders. `FIRE_NOW.md` has the corrected, current paste-ready posts.

# Reddit paste-ready — Tue 19 May launch week

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

Three subs, three posts. Reddit + MCP-blocked, so the agent can't drive
the submit form — paste these into the browser yourself.

**Premium smart-money surface**: "Elite 13F holdings (Buffett, Burry, Ackman,
etc.)" was stripped from marketing in PR #74 (Quiver Trader-tier TOS
"No Commercial Use Rights") and the adapter has since been deleted. The
Premium smart-money surface is **Recent insider buys (SEC Form 4)** plus
Congressional trades. Both this file and LAUNCH_PLAYBOOK.md now say so.

---

## 1. r/stocks — Tue 19 May, 9 AM ET (= 23:00 AEST tonight)

URL: https://www.reddit.com/r/stocks/submit

**Title (~85 chars):**
```
Built a free stock score tool — every call back-checked vs SPY next day, full history public
```

**Body:**
```
I got annoyed at every "AI stock recommendation" service refusing to show its track record. So I built Tapeline. The whole record is public — no account needed to read it.

What's free:
- One 0-100 score per stock with a plain-English why
- Public scorecard tracking every top-10 pick I make, back-checked against SPY the next day
- 5-ticker watchlist

What costs $9.99/mo (Pro):
- Full ~2,500 ticker live scan
- Smart watchlist alerts when scores move
- IPOs / earnings / news calendar

What costs $19.99/mo (Premium):
- + Congress trades feed (House + Senate disclosed)
- + Recent insider buys (SEC Form 4) across the active universe

30-day Premium trial — a new account adds a card at first sign-in, $0 charged that day, first charge on day 30, cancel in one click before then. The daily Top 10 and the full public scorecard are readable with no account.

Try it on any ticker you like — tapeline.io/t/AAPL, tapeline.io/t/NVDA, whatever. Drop your favorite ticker in comments and I'll post its current score + the breakdown.

Tell me what's missing. Roast the methodology at /how-it-works.
```

---

## 2. r/algotrading — Thu 21 May, 10 AM ET

URL: https://www.reddit.com/r/algotrading/submit

**Title:**
```
I built a 6-factor composite stock score with a public, unedited daily back-check vs SPY
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

Every market day I freeze the top 10 composite scores. The next day I log each name's actual return vs SPY. The full history lives at /scorecard with no survivor bias filtering — losers stay on the page. Win-rate / avg alpha / beat-SPY rate columns fill in 24h after each close.

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

**Body:** (one correction — "Congress / 13F" → "Congress / Form 4")
```
Live at tapeline.io. Built it because I wanted to stop manually weighing trend / RS / fundamentals / insider activity every time I screened.

The Fundamentals factor reads five reported figures:
- Revenue growth between reported periods
- EPS growth between reported periods
- Profit margin, as reported
- Return on equity, as reported
- An earnings multiple — lower moves the reading up

Score is recomputed sub-60 seconds during market hours from a live data feed (Polygon/Massive for prices, Finnhub for fundamentals + Form 4, FRED for macro).

Concrete example a SecurityAnalysis crowd might find useful: filter to /sector/financials and the score will give you a 0-100 read on every financial. Click any ticker → /t/$X → see the six-factor breakdown so you can drill into which factor is dragging or pulling.

Free tier covers everything I'd want as a generalist (score + scorecard + 5-ticker watchlist). Pro $9.99 unlocks the full universe. Premium $19.99 adds Congress / SEC Form 4.

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
