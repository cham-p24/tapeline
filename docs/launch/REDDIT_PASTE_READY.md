# Reddit paste-ready — Tue 19 May launch week

Three subs, three posts. Reddit + MCP-blocked, so the agent can't drive
the submit form — paste these into the browser yourself.

**Critical correction vs LAUNCH_PLAYBOOK.md**: the r/stocks Premium bullet
in that file still says "Elite 13F holdings (Buffett, Burry, Ackman, etc.)"
— that line was stripped from marketing in PR #74 (Quiver Trader-tier TOS
"No Commercial Use Rights"). The Premium smart-money surface is now
**Recent insider buys (SEC Form 4)**. The copy below is corrected.

---

## 1. r/stocks — Tue 19 May, 9 AM ET (= 23:00 AEST tonight)

URL: https://www.reddit.com/r/stocks/submit

**Title (~85 chars):**
```
Built a free stock score tool — every call back-checked vs SPY next day, full history public
```

**Body:**
```
I got annoyed at every "AI stock recommendation" service refusing to show its track record. So I built Tapeline (free tier covers the top 20 tickers).

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
- + Unlimited Telegram alerts

14-day Premium trial, no card.

Try it on any ticker you like — tapeline.io/t/AAPL, tapeline.io/t/NVDA, whatever. Drop your favorite ticker in comments and I'll post its current score + the breakdown.

Tell me what's missing. Roast the methodology at /how-it-works.
```

---

## 2. r/algotrading — Thu 21 May, 10 AM ET

URL: https://www.reddit.com/r/algotrading/submit

**Title:**
```
I built a 6-factor composite stock scoring system — formula, weights, and a public back-check page
```

**Body:** (no edits from LAUNCH_PLAYBOOK.md — already mentions Form 4)
```
Three months ago I started Tapeline (tapeline.io) because every screener I tried either showed me raw filters (Finviz) or hid its methodology behind an "AI score" black box (Simply Wall St). I wanted something that picks a single number, tells me what's driving it, and lets me audit every call against SPY the next day.

Here's what I shipped:

**The formula** (public, version-controlled, won't change without a changelog entry)

- Trend 25% — 20/50/200 DMA stack, slope, days above 50DMA
- Relative Strength 20% — Mansfield RS vs SPY, sector RS, 12-1 momentum
- Fundamentals 15% — revenue growth, margin trend, ROE, F-score
- Smart Money 15% — Form 4 insider transactions (net 90-day) — *not* 13F lag
- Macro 15% — composite of VIX percentile, breadth, 10Y, regime score
- Momentum 10% — 20-day rate-of-change, RSI position, accumulation/distribution

**The accountability layer**

Every market day I freeze the top 10 composite scores. The next day I log each name's actual return vs SPY. The full history lives at /scorecard with no survivor bias filtering — losers stay on the page. Win-rate / avg alpha / beat-SPY rate columns fill in 24h after each close.

**What I'd like feedback on**

1. Smart Money via Form 4 — is net-90-day buying the right window, or should I weight by insider role (CEO > director)?
2. Should momentum get less weight (currently 10%) given it's already inside trend + RS?
3. What factor would you add to make this defensible for a 1Y horizon vs the current 1D back-check?

Roast it. The formula is the part I want to harden.
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

The 15% Fundamentals factor breaks down into:
- Revenue growth (trailing 4 quarters)
- Operating margin trend
- ROE (current vs sector median)
- F-score (Piotroski 9-point)

Score is recomputed every ~30 sec during market hours from a live data feed (Polygon/Massive for prices, Finnhub for fundamentals + Form 4, FRED for macro).

Concrete example a SecurityAnalysis crowd might find useful: filter to /sector/financials and the score will give you a 0-100 read on every financial. Click any ticker → /t/$X → see the six-factor breakdown so you can drill into which factor is dragging or pulling.

Free tier covers everything I'd want as a generalist (score + scorecard + 5-ticker watchlist). Pro $9.99 unlocks the full universe. Premium $19.99 adds Congress / SEC Form 4 / Telegram alerts.

Happy to take fundamentals-specific critique. The Piotroski F-score implementation in particular — would love eyes on edge cases (financial vs non-financial scoring).
```

---

## Posting playbook (per LAUNCH_PLAYBOOK.md §2)

- One sub per week. Reddit's spam filter shadowbans cross-posts.
- Post body links only to FREE public pages (/scorecard, /how-it-works) —
  let the pricing page sell itself.
- Hang around the first 60 min answering every comment.
- Don't reply defensively to "shilling" accusations — link to /scorecard.
- Don't post in r/wallstreetbets — they burn SaaS founders alive.
