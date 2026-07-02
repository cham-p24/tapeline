# Tapeline — Launch posts (compliant, ready to fire)

Corrected 2026-06-26 to the **locked positioning** (process + honesty + time-saving,
**never performance**) and the **current product**. The prior version of this file was
stale and non-compliant (it claimed "+0.4% above SPY", described the old 20-ticker/24h
free tier, and pitched the removed Quiver/13F feature) — all removed.

## Hard rules (do not undo)
- **No performance claims.** The public scorecard currently trails SPY (~42% hit-rate).
  Any "beat the market / +X% vs SPY" line is false AND a Google/FTC/ASIC violation. The
  hook is the honesty: *"Most scanners show you the wins. We show the whole record —
  losses included."*
- **Current facts:** ~2,500 US-listed tickers scored every minute · public 6-factor
  formula · one-sentence "why" per ticker · public scorecard freezes each daily top-10 and
  back-checks vs SPY, keeping the losing days · **Free forever:** live scores, top-10
  scanner rows, 5 look-ups/day, 3-ticker watchlist, full public scorecard · 14-day Premium
  trial, no card · **Pro** $9.99/mo ($8.25/mo annual) · **Premium** $19.99/mo
  ($16.58/mo annual, founding pricing — locked in for early subscribers) adds Congressional-trades feed, recent insider buys (SEC Form 4),
  unlimited Telegram + email alerts, public API. (No 13F/Quiver — removed.)

---

## X / Twitter — launch tweet (pin it)

**Variant A — anti-hype:**
```
Most stock scanners show you a highlight reel.

Tapeline publishes the whole tape: one 0–100 score on every US stock from a public
6-factor formula, and a scorecard that freezes every daily top-10 and grades it against
the S&P — losing days kept on the page.

14-day trial, no card. tapeline.io
```

**Variant B — origin:**
```
For years I cancelled every stock scanner within a month — they all hide the formula and
bury their losers.

So I built one that publishes both: the exact 6-factor math, and a public scorecard that
keeps its losing days. Not tips. A transparent screen. tapeline.io
```

**Reply 5 min later (the formula):**
```
The formula, public on /how-it-works:

score = 0.25·trend + 0.20·relative_strength + 0.15·fundamentals
      + 0.15·smart_money + 0.15·macro + 0.10·momentum

The day it stops working, you'll be able to see it and leave.
```

---

## Show HN
**Title:** Show HN: Tapeline – a stock scanner that publishes its formula and its losing days
```
I built Tapeline. It scores every US-listed stock (~2,500) every minute on one public
6-factor formula (trend, relative strength, fundamentals, smart-money, macro, momentum —
exact weights on /how-it-works) and writes a one-sentence plain-English "why" per ticker.

The part I care about: it freezes each day's top-10 and back-checks them against SPY on a
public scorecard that keeps the losing days. Honest status — the record currently trails
SPY. I leave it up exactly as-is; the whole point is you can check my work instead of
trusting a screenshot.

It is NOT a tip service — no buy/sell calls. It's a fast, transparent screen; you see how
each score is built and decide for yourself.

Free tier is usable forever (live scores, top-10, 5 look-ups/day); 14-day Premium trial,
no card. I'd love the methodology torn apart — what factor would you add or drop?
tapeline.io
```

---

## Reddit (r/algotrading, r/stocks, r/investing, r/SecurityAnalysis)
> Needs account karma/age or it's auto-removed. Comment helpfully for a few days first.
> Lead with the idea; link low/in a comment. One sub, no same-day cross-posting.

**Title:** I built a stock scanner and made it publish its own losing days. Here's the record.
```
Almost no prosumer scanner publishes its scoring formula or its track record, for two
honest reasons: publish the formula and users can audit it (and leave the day it stops
working); publish the record and you eat your losers in public.

I did both anyway. The formula:
score = 0.25·trend + 0.20·rs + 0.15·fundamentals + 0.15·smart_money + 0.15·macro + 0.10·momentum

The scorecard freezes each day's top-10 and grades it against SPY — wins and losses both
stay up. Honest status: it currently trails SPY. Small sample, and I'm leaving it public
regardless — editing it would defeat the point.

Not advice, no buy/sell calls — descriptive analytics you verify yourself. ~2,500 US names
scored every minute. Free tier shows live scores with no card.

Genuine question for the sub: would you trust a score more if you could read its formula,
or is the obscurity doing useful work? (links in a comment)
```

---

## Product Hunt
**Schedule:** Tuesday, 12:01 AM PT. Line up 5–10 friends to upvote in hour 1.
**Tagline:** "Live stock scanner that shows its work — and keeps its receipts."

**First comment (post immediately):**
```
Hey all — Christian, founder.

I got tired of every commercial scanner hiding its formula and its track record, so
Tapeline publishes both:
· One 0–100 score per US ticker, 6 factors, public weights
· One plain-English sentence why, on every row
· A public scorecard that freezes each day's top-10 vs SPY — losing days kept

Honest note: the record currently trails SPY, and it's all on the page. The product is the
transparency and the time saved, not a promise of returns.

Free forever tier (live scores, 5 look-ups/day); 14-day Premium trial, no card. AMA.
Feedback I'd love: is /how-it-works clear, and would you share a /t/[ticker] page?
```

---

## IndieHackers — /launches/new
**Title:** "After years of stock scanners, I built one that shows its work"
```
TL;DR: Tapeline scores every US ticker (~2,500) with a public 6-factor formula, writes a
one-line why, and publishes a scorecard that back-checks each day's top-10 vs SPY — losses
kept. tapeline.io · free forever tier · 14-day Premium trial, no card.

Every prosumer scanner I tried fails the same way: black-box score, no track record, and a
free tier crippled to upgrade-trap you. So I built the opposite — public weights, a public
scorecard that keeps its losing days (it currently trails SPY; that's the honest data, and
it stays up), and a free tier that's a real, usable product.

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
· Free forever tier; 14-day Premium trial, no card

Two things I'd love feedback on:
1. /how-it-works — is the formula clear to a non-technical trader?
2. Set up a 3-ticker watchlist for 24h — are the alerts actually useful?

Reply with anything broken — I read every one. — Christian
```

---

## Posting order + what NOT to do
**Order:** your X (pin) → IndieHackers → one Reddit sub → Show HN (only if the tweet got
traction) → Product Hunt (Tue) → 10 warm DMs to traders you respect. One channel/day.
**Never:** claim returns or "beats the market" · post to r/wallstreetbets · email-blast a
cold list · run paid ads in week one. Descriptive labels only.
