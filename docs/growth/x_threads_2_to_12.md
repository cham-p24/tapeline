# X threads #2-12 — drafts ready to post

Thread #1 launched 2026-05-13 on @tapeline_io and was extended with
tweets 4+5+URL on 2026-05-18. These threads carry the cadence
forward.

Posting rules:
- Use REPLY-CHAIN, not the X multi-post composer (the composer drops
  focus on long types via MCP — handover doc verified).
- Tweet character limits: 280 max, URLs always count as 23 chars
  regardless of length.
- Pin one new thread per week. The pinned thread is the visiting
  retail trader's first impression — make it the most current one.
- URLs in REPLY tweets, not in the original thread body (X downranks
  bodies with links).

---

## Thread #2 — Trend at 25%: what's actually in it

Target: Wed 2026-05-21, 10pm AEST = 8 AM ET.

**Tweet 1** (~270 chars):
```
"Trend 25%" is Tapeline's largest single factor.

Most quant services say "trend-following" and leave it there. We publish exactly what goes in:

– 20DMA vs 50DMA vs 200DMA stack (above/below)
– Slope of the 50DMA over the last 30 sessions
– Days the price has held above the 50DMA
```

**Tweet 2** (~250 chars):
```
Why 25% and not 30 or 20?

Price action is the lowest-lag signal you can compute. Every other factor — fundamentals, smart money, macro — argues for or against the trend continuing.

If the trend score is high but the others disagree, the composite stays moderate. Trend alone doesn't win.
```

**Tweet 3** (~230 chars):
```
A high Trend score with low Fundamentals means "momentum without quality" — the kind of move that snaps back hard.

A high Trend score with high Smart Money means "the trend has institutional cover" — much more likely to persist.

The composite weighs both.
```

**Tweet 4** (~250 chars):
```
What Trend specifically WON'T catch:

– Regime breaks (that's Macro's job)
– Earnings surprises (that's Fundamentals)
– Insider selling into strength (that's Smart Money)
– 1-day spikes on news (that's Momentum)

Trend is structural, not tactical. It's measuring multi-month behaviour.
```

**URL reply** (~50 chars + URL):
```
Full methodology: https://tapeline.io/how-it-works
```

---

## Thread #3 — Smart Money done right: Form 4 over 13F

Target: Wed 2026-05-28, 8 AM ET.

**Tweet 1** (~270 chars):
```
Most "smart money" trackers in fintech are 13F-driven.

13F has a 45-day filing lag. That's almost 7 weeks of price action between when the fund traded and when you find out.

Tapeline weights Form 4 (officers/directors, 2-business-day lag) more than 13F. Here's the math.
```

**Tweet 2** (~260 chars):
```
Smart Money is 15% of the Tapeline composite. Inside that 15%:

– Congressional disclosures (STOCK Act): 8%
– SEC Form 4 insider buys: 5%
– Curated 13F (8 named funds): 2%

Form 4 has more weight than 13F because the lag math actually works.
```

**Tweet 3** (~260 chars):
```
The 13F lag isn't just slow — it's adversarially slow.

Big positions get scaled out of slowly. By the time the 13F shows the position, the manager has often unwound it. You're looking at last quarter's conviction, not this week's.

Form 4 is messier but fresher.
```

**Tweet 4** (~270 chars):
```
Caveat: Form 4 is noisy.

Officers sell for personal reasons all the time. A single insider sale isn't bearish.

What we score is the 90-day NET — total bought minus total sold, weighted by transaction size. That's harder to fake and captures cluster patterns better than any single filing.
```

**URL reply**:
```
The full Smart Money breakdown: https://tapeline.io/how-it-works
```

---

## Thread #4 — What 7 days of forward-testing actually looks like

Target: Mon 2026-05-26, 8 AM ET. Refresh the numbers from /api/scorecard at post time.

**Tweet 1** (~270 chars):
```
The Tapeline scorecard has been freezing top-10 picks at every US market close for a week.

I'm posting the live numbers because the point of /scorecard is that it's auditable. Even when the early weeks look mediocre.
```

**Tweet 2** (~270 chars — REFRESH NUMBERS BEFORE POSTING):
```
7 days. 35 clean entries (4 vendor-data outliers excluded, methodology on the page).

Median 1-day alpha: -0.73% vs SPY
Beat-SPY rate: 37%
Best day's alpha: +6.4%
Worst: -8.1%

A small sample with high variance. Means nothing yet. That's the point.
```

**Tweet 3** (~260 chars):
```
Most stock-scanner services would NEVER show numbers this rough.

They'd update the methodology silently, adjust the weights, or just stop publishing the back-check. The marketing keeps insisting their AI is winning.

The whole point of /scorecard is that you'll see when it isn't.
```

**Tweet 4** (~260 chars):
```
In 60-90 days the sample will mean something. The numbers will say either:

(a) the model holds up, or
(b) the model needs work

Either way the data is published. The /changelog tracks any methodology revision — no retroactive edits.
```

**URL reply**:
```
The full back-check, including every miss: https://tapeline.io/scorecard
```

---

## Thread #5 — Why Tapeline shows the real product on Free tier

Target: Wed 2026-06-04, 8 AM ET.

**Tweet 1** (~260 chars):
```
Most SaaS free tiers cripple core functionality. Fewer rows, no exports, no filters. The idea is to frustrate users into upgrading.

It teaches users the product is annoying.

Tapeline's free tier instead shows the real product, just 24 hours delayed.
```

**Tweet 2** (~270 chars):
```
The Free tier on Tapeline:

– Top 20 tickers from yesterday's close
– Full 6-factor breakdown on every row
– Full plain-English "Why" sentence
– Full scorecard
– Watchlist of 5 names

The ONLY difference vs Pro is the 24-hour delay on data.
```

**Tweet 3** (~260 chars):
```
If you can act on day-old data, the free tier IS the right tier. Stay there forever — that's fine.

If you need live data, Pro is $24.99/mo billed annually. Same scoring engine, same scorecard, no data delay, plus smart watchlist alerts.

That's the entire upgrade decision.
```

**Tweet 4** (~270 chars):
```
The 14-day Premium trial gives the full live universe + Congressional trades + insider Form 4 + Telegram unlimited. No card required.

I'd rather you understand what Tapeline does, decide it doesn't fit, and not pay than have you upgrade because the free tier was deliberately broken.
```

**URL reply**:
```
https://tapeline.io/pricing
```

---

## Thread #6 — How Tapeline's scorecard back-check actually works

Target: Wed 2026-06-11, 8 AM ET.

**Tweet 1** (~270 chars):
```
Every market day, Tapeline freezes the top-10 composite scores at close.

The next session's close gets recorded the next day, alongside the SPY close for the same dates.

Realised return - SPY return = alpha. That's the number on the public scorecard.

Wins stay. Losses stay.
```

**Tweet 2** (~270 chars):
```
What the back-check explicitly DOESN'T do:

– No retroactive picking (the top-10 at close is locked once recorded)
– No survivor bias filter (delisted tickers stay on the historical page)
– No methodology adjustment after the fact (changelog tracks every change in markdown)
```

**Tweet 3** (~260 chars):
```
What the back-check is BAD at:

– Small samples (5-30 days is mostly noise)
– Sector-rotation regimes (a quarter of bad calls in one sector can dominate)
– Holding-period assumptions — alpha is measured at 1-day, not 1-week or 1-month

All of this is documented on the methodology page.
```

**Tweet 4** (~250 chars):
```
The reason it's still worth running is that it's the only honest version of "did the model work."

Everything else in the SaaS scanner space is back-tests (gameable) or testimonials (cherry-picked). A live forward test, auditable from day one, is the actual control.
```

**URL reply**:
```
The full record so far: https://tapeline.io/scorecard
```

---

## Thread #7 — Why Tapeline's Macro factor matters

Target: Wed 2026-06-18, 8 AM ET.

**Tweet 1** (~270 chars):
```
Tapeline's Macro factor is 15% of every score.

That seems high to people new to the platform — "isn't macro noise?"

It's not noise. It's the regime overlay that gates whether the other 85% means anything.

Here's what goes in.
```

**Tweet 2** (~270 chars):
```
Inputs to the Macro factor:

– VIX percentile (last 252 sessions)
– NYSE advance/decline breadth
– 10-year Treasury yield direction (FRED)
– Composite regime score (bull/bear/transition)

Each gets a sub-weight. They aggregate into a 0-100 macro reading.
```

**Tweet 3** (~260 chars):
```
When Macro is high (60+):

A high Trend/Fundamentals composite is much more likely to persist.

When Macro is low (<40):

The same high Trend/Fundamentals score still triggers, but the composite gets dampened. The model says "right setup, wrong regime, wait."
```

**Tweet 4** (~260 chars):
```
Most retail-facing scanners don't model regime at all. You get the same "high conviction" signal in a benign tape as in a melt-down — and the marketing never tells you.

Tapeline's HIGH CONVICTION label requires the regime to AGREE. That's not a feature; it's the entry ticket.
```

**URL reply**:
```
The full Macro methodology: https://tapeline.io/how-it-works
```

---

## Thread #8 — Building solo from Melbourne

Target: Wed 2026-06-25, 8 AM ET.

**Tweet 1** (~260 chars):
```
Tapeline is a quant scanner for US stocks. The whole thing was built solo from Melbourne over the last few months.

Three things about that combo I wasn't expecting:
```

**Tweet 2** (~270 chars):
```
1. The Australian publisher exemption from AFSL is genuinely permissive.

I can publish quantitative analysis on US stocks without a financial services licence as long as it's "general information only, not personal advice." That language is on every scoring page now.
```

**Tweet 3** (~270 chars):
```
2. The time zone is a feature.

US markets close 6 AM AEST. I wake up to a fully back-checked scorecard with overnight data already populated. By the time East Coast traders are at their desks, the next picks are frozen.

This isn't a bug to work around — it's literally why it works.
```

**Tweet 4** (~270 chars):
```
3. Solo means every regulatory decision is mine.

No counsel-by-committee. Got the Holley Nethercote lawyers in Melbourne queued for a publisher-exemption consult; everything I publish until then is on the conservative side of "general info, not advice." It's annoying. It's also necessary.
```

**Tweet 5** (~250 chars):
```
The hard parts weren't the scoring formula. They were the data pipelines.

Polygon/Massive, Finnhub, FRED, Benzinga, SEC EDGAR. Each one's own auth, rate limits, failure modes. Half the codebase is reconciling sources when they disagree about a ticker's last close.
```

**URL reply**:
```
The result: https://tapeline.io
```

---

## Thread #9 — The 6-factor composite: full breakdown

Target: Wed 2026-07-02, 8 AM ET.

**Tweet 1** (~270 chars):
```
Tapeline's score is built from 6 factors with public weights:

Trend 25
Relative Strength 20
Fundamentals 15
Smart Money 15
Macro 15
Momentum 10

Sums to 100. Doesn't change retroactively. Open for arguing about on the methodology page.

Why these weights? Quick thread.
```

**Tweet 2** (~270 chars):
```
TREND (25%) — price action across 20/50/200 DMA stack + slope + days above 50DMA. Largest weight because it's the lowest-lag signal you can compute.

RELATIVE STRENGTH (20%) — Mansfield RS vs SPY, sector RS, 12-1 momentum. Filters out "everything's going up" markets.
```

**Tweet 3** (~270 chars):
```
FUNDAMENTALS (15%) — Piotroski-style F-score with a quality tilt. Revenue growth, margin trend, ROE, debt-to-equity.

Why 15 and not 20? Fundamentals are slow-moving and 1-day-alpha-irrelevant. Worth weighting but not dominating.
```

**Tweet 4** (~260 chars):
```
SMART MONEY (15%) — Congressional disclosures + Form 4 insider buys + curated 13F. Inside that 15%: Congress 8, Form 4 5, 13F 2. Lagged data, weighted lower than its media airtime suggests.

MACRO (15%) — VIX, breadth, 10Y, regime. The regime overlay that gates the other 85%.
```

**Tweet 5** (~260 chars):
```
MOMENTUM (10%) — 20-day rate-of-change, RSI position, accumulation/distribution. Lowest weight on purpose.

Pure momentum factors over-fit to the recent regime. Keeping it at 10% forces the composite to wait for confirmation across other dimensions before tagging high-conviction.
```

**URL reply**:
```
https://tapeline.io/how-it-works
```

---

## Thread #10 — Why the formula is public and the infrastructure isn't

Target: Wed 2026-07-09, 8 AM ET.

**Tweet 1** (~260 chars):
```
Tapeline publishes its scoring formula. Six factors, exact weights, on /how-it-works. The /changelog tracks every methodology change.

A retail trader asked: "doesn't that let competitors copy it?"

Three answers:
```

**Tweet 2** (~270 chars):
```
1. The formula isn't the moat.

Six published factors with weights is the ENTRY TICKET to being credible. The actual moat is operations: data pipelines from 6 vendors, the back-check infrastructure, the scorecard accountability layer.

The formula is a weekend. The infra was 9 months.
```

**Tweet 3** (~270 chars):
```
2. The customer can't trust a black box.

Finviz, Zacks, TipRanks, Simply Wall St — all hide their scoring methodology. That's not a competitive advantage; it's a trust deficit.

If a model doesn't tell you how it works, you can't act on it. You're just gambling on the brand.
```

**Tweet 4** (~270 chars):
```
3. If the formula is wrong, I want to know.

Publishing it invites every quant on Twitter to argue with me. Some of them will be right. The model gets better when it's audited in public.

The /changelog is markdown. You can read every methodology change since launch.
```

**URL reply**:
```
https://tapeline.io/how-it-works
```

---

## Thread #11 — Confidence pct: the column most people miss

Target: Wed 2026-07-16, 8 AM ET.

**Tweet 1** (~270 chars):
```
Every Tapeline ticker has a CONFIDENCE % alongside its composite score.

Most people skip it. It's the most useful column on the scanner.

Confidence isn't "how good is this signal?" — it's "how complete is the data behind it?" Big difference.
```

**Tweet 2** (~270 chars):
```
A mega-cap like AAPL or MSFT has full coverage across all 6 factor inputs. The confidence pct lands in the 88-96 range.

A small-cap or micro-cap has sparse Fundamentals + Smart Money coverage. Confidence drops to 45-70. The composite still ranks them — just with a louder caveat.
```

**Tweet 3** (~270 chars):
```
Why expose this rather than hide it?

Because "high score, low confidence" is genuinely different from "high score, high confidence."

A 78 composite with 92% confidence on a mega-cap is a different bet than a 78 with 51% confidence on a sub-$500M name.
```

**Tweet 4** (~250 chars):
```
The /app/scanner table sorts by score by default but lets you filter on confidence pct.

For position-sizing, that's the variable that should weight your exposure — not the composite alone.

It's the column most retail traders ignore. Don't.
```

**URL reply**:
```
See it live: https://tapeline.io/app/scanner
```

---

## Thread #12 — What's next, and how to vote on it

Target: Wed 2026-07-23, 8 AM ET.

**Tweet 1** (~260 chars):
```
A quick public roadmap thread for what's shipping next on Tapeline. Everything is on /roadmap — Premium users can vote, the order is updated by votes.
```

**Tweet 2** (~270 chars):
```
Shipping this month:

– Walk-forward back-test on 2024-2025 (historical version of /scorecard)
– Multi-watchlist support — themed buckets like "Tech compounders" / "AI plays" (just shipped)
– Saved scanner presets (just shipped)
```

**Tweet 3** (~270 chars):
```
Deferred until 50+ paying users specifically ask:

– Apple Sign-In (needs $99/yr Apple Dev membership for me)
– Microsoft OAuth (needs M365 Developer tenant)
– Public API endpoint (real-shaped 2-3 days of work; building to demand)
– Discord server
```

**Tweet 4** (~260 chars):
```
Closed-as-deferred (won't reopen without specific trigger):

– "Elite 13F holdings" — dropped from Premium because Quiver Trader-tier TOS says "No Commercial Use Rights." Reopen only with a commercial Quiver license or an alternative legally-clean vendor.
```

**Tweet 5** (~250 chars):
```
Anything you'd add? The /roadmap page has a voting widget for Premium users. Pick the items that matter most to you — that determines the next sprint.

I'm picking the next sprint by reply count + page votes.
```

**URL reply**:
```
https://tapeline.io/roadmap
```

---

## Cadence summary

| Date (Wed) | Thread |
|---|---|
| 2026-05-21 | #2 Trend deep-dive |
| 2026-05-28 | #3 Smart Money done right |
| 2026-06-04 | #5 Free tier philosophy |
| 2026-06-11 | #6 How the back-check works |
| 2026-06-18 | #7 Why Macro matters |
| 2026-06-25 | #8 Building solo from Melbourne |
| 2026-07-02 | #9 Six-factor breakdown |
| 2026-07-09 | #10 Why publish the formula |
| 2026-07-16 | #11 Confidence pct |
| 2026-07-23 | #12 What's next |

Thread #4 (forward-testing data) intentionally NOT on this calendar —
post that opportunistically when scorecard sample size or specific
numbers make it timely.

After thread #12, re-audit based on reader engagement, Show HN
comments, and any podcast/Reddit feedback that surfaces fresh angles
worth a #13-#20 batch.
