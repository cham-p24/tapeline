# Show HN — alternative variants

`LAUNCH_PLAYBOOK.md` §1 has the primary draft (focus: public formula + public
scorecard, 14-day trial mention). This file holds two alternate angles in
case the primary doesn't feel right on Tuesday morning. All three are
**post-as-Text-with-`https://tapeline.io`-in-URL-field** format.

Same posting rules apply (8 AM ET, weekday, ≥30-karma account, hang around
for 60 min answering every comment).

---

## Variant A — "the back-check is the product" angle

### Title (78 chars)

> **Show HN: A stock scanner that back-checks every top-10 pick against SPY**

### Text

```
I built Tapeline (https://tapeline.io) because every stock scanner I'd ever paid for had the same dishonest pattern: they show you a leaderboard of picks but never show you what happened next.

So Tapeline does the opposite. Every market day at close, we freeze the top 10 ranked tickers. Next day at close, we record each name's actual return vs SPY and the result goes on /scorecard. Wins stay. Losses stay. Nothing gets quietly removed when a pick goes badly.

The score itself is a public 6-factor composite — Trend 25%, Relative Strength 20%, Fundamentals 15%, Smart Money 15%, Macro 15%, Momentum 10%. Weights live on /how-it-works and don't change without a changelog entry. Every score comes with one plain-English sentence explaining what's driving it (the "Why" column).

The scorecard is the part I want HN to tear apart. It's the only thing I've ever seen in this space that's auditable from day one. Currently in its first week of forward-testing — early data on /scorecard shows median 1D alpha around -0.7% on 35 clean entries (4 vendor-data outliers excluded; the filter logic is in the public Python source). I expect those numbers to swing both directions as the sample grows. The transparency is the point, not the early hit rate.

Free tier: top 20 tickers, 24h delay, 5-name watchlist.
Pro $24.99/mo billed annually: full live universe + smart alerts.
Premium $39.99/mo: + Congress trades + SEC Form 4 + Telegram.
14-day Premium trial, no card.

Built solo over the last few months from Melbourne. Genuinely interested in what HN finds wrong with the methodology — and what factors I'm under-weighting.
```

### Why this variant

Leans harder into the accountability angle than the primary. Concedes weak
early back-check numbers upfront (the median alpha is honestly mediocre at
5 days), which HN respects more than "look how great we are." Self-flagellation
inoculates against the predictable "your scorecard only has 5 days" comment.

---

## Variant B — "what a Bloomberg refugee built on weekends" angle

### Title (76 chars)

> **Show HN: Tapeline – the stock scanner I wanted Bloomberg to be (open formula)**

### Text

```
I've worked alongside retail traders for years and watched the same dynamic play out: they pay $30-60/month for screeners that hide the formula and never publish a track record. Bloomberg's $24K/year terminal has the data but is built for an institutional workflow nobody under 40 actually uses.

So I built Tapeline (https://tapeline.io). One composite score per US ticker (0-100), six published factors, plain-English sentence on every row, and a public scorecard that back-checks each daily top-10 against SPY the next day. The whole product is "show your work, every step."

The formula is on /how-it-works:
- Trend 25% — DMA stack, slope, days above 50DMA
- Relative Strength 20% — Mansfield RS vs SPY, sector RS, 12-1 momentum
- Fundamentals 15% — revenue growth, margin trend, ROE, Piotroski F-score
- Smart Money 15% — SEC Form 4 insider transactions (90-day net), NOT 13F lag
- Macro 15% — VIX percentile, breadth, 10Y direction, regime score
- Momentum 10% — RSI position, ROC, A/D

Weights are version-controlled. /scorecard is uneditable history. /changelog logs every methodology revision.

Stack: Next.js 16 + FastAPI + Polygon/Massive + Finnhub + FRED, deployed on Vercel + Fly.io. Source for the scoring formula and the scorecard back-check service is open on /how-it-works in pseudocode form (the production code is closed but mirror-able from the published spec).

Free tier: top 20 tickers, 24h delay. Pro $24.99/mo annual. Premium $39.99/mo annual. 14-day trial, no card.

What I want HN to break: the methodology. The Smart Money sub-score in particular — I weight Form 4 over 13F because the lag math kills 13F-driven signals, but I'd love to be argued out of it.
```

### Why this variant

Leans into the "Bloomberg too expensive, Finviz too raw" positioning. Names
the competitors explicitly (which the primary draft is more cautious about).
Invites methodology critique on a specific factor (Smart Money) which gives
commenters a concrete handle to engage with — more upvotes than "what do
you think overall."

Risk: directly invoking Bloomberg might attract a "this is nothing like
Bloomberg" pile-on. Use only if you're comfortable engaging that thread.

---

## Decision rubric — which variant to pick

| Situation | Pick |
|---|---|
| Want the safest, broadest-appeal angle | Primary draft in `LAUNCH_PLAYBOOK.md §1` |
| Want to lean into the back-check / scorecard differentiator | Variant A |
| Want to position against Bloomberg + Finviz explicitly | Variant B |
| Posting on a Monday or Wednesday (low traffic) | Variant A (more substance per word) |
| Posting on a Tuesday or Thursday (peak traffic) | Primary or Variant B |

All three end with a question / invitation to break the methodology — that's
the comment-engagement hook. Don't skip the "what I want HN to break" line.
