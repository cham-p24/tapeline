# LinkedIn posts #4-15 — drafts ready to schedule

> Filename still says `_4_to_12` for git-blame continuity — file now
> covers posts #4–15 (latest three added 2026-05-22 in PR #166).

Drafts continue from posts #1-3 (already LIVE on
linkedin.com/in/christian-piyatilaka-16192a40a). Each post follows the
same posture: factual, no hype, methodology-first, founder voice.
URLs go in the FIRST COMMENT under the post (LinkedIn down-ranks
links in the body).

Cadence target: Tue / Thu / Sat at 09:00 AEST. Don't post all on the
same day — rhythm matters more than throughput.

---

## Post #4 — Why the scorecard has a regulatory disclaimer now

```
A week ago Tapeline's public scorecard was showing average returns of +648%.

It wasn't a fraud. It was a vendor-data bug. Four tickers had unadjusted-for-split closes flow into the back-check. The arithmetic mean got dragged into nonsense by four outliers in a 50-row dataset.

I shipped three fixes the same day:
1. Median primary, mean as a transparency footnote.
2. Filter out any row with a 1-day move >50% (vanishingly rare in real markets, common in vendor data errors).
3. A permanent regulatory disclaimer — "general information only, not personal advice, past performance does not predict future results."

The scorecard now reads -0.73% median 1-day alpha on 35 clean entries. Mediocre by design. Five sessions in, the sample is too small to mean anything — and saying that publicly is the entire point.

I'd rather show -0.73% honestly than the +648% the bug was producing.
```

Char count: ~990. Add `tapeline.io/scorecard` in first comment.

---

## Post #5 — The 6 factors, in order of how much they actually predict

```
Tapeline scores every US stock on six factors. The weights are public:

Trend          25%
Relative Strength  20%
Fundamentals     15%
Smart Money    15%
Macro            15%
Momentum     10%

The weights aren't equal — they reflect what predicts forward performance vs SPY, not what's most "rigorous" or "fundamental."

Trend dominates because price action is the cleanest, fastest signal you can compute. The other five factors all argue for or against the trend's persistence.

Momentum is intentionally only 10%. Pure momentum factors over-fit to the recent regime. Weighting it lower forces the composite to wait for confirmation across other dimensions before tagging a name as high-conviction.

Most quant services hide their weights. Anyone arguing my weights are wrong can argue them in public on the methodology page — that's the whole point of publishing them.
```

Char count: ~880. Add `tapeline.io/how-it-works` in first comment.

---

## Post #6 — What "Smart Money" actually means in our score

```
"Smart Money" is the most-overloaded term in finance. People mean different things by it. So Tapeline pins down exactly which three signals make up its 15% weight:

1. Congressional disclosures (STOCK Act filings, ~1-3 month lag). 8% of the 15%.

2. SEC Form 4 insider trades (officers and directors trading their own company's stock, 2-business-day filing window). 5%.

3. Curated 13F holdings from 8 named managers — Buffett, Burry, Tepper, Ackman, Druckenmiller, Laffont, Coleman, Singer. 45-day lag. 2%.

Notice the weights inside the weight. Form 4 carries more weight than 13F even though 13F gets more financial-media airtime. The reason is the lag: 45-day-old 13F data has had its alpha eaten before you see it.

The whole "Smart Money" factor is intentionally only 15% of the composite. Lagged data shouldn't dominate a forward-looking score. But it's still better than vibes.
```

Char count: ~1,030. Add `tapeline.io/how-it-works` in first comment.

---

## Post #7 — What 7 days of live forward-testing actually looks like

```
The Tapeline scorecard has been freezing top-10 picks at every market close for a week.

Here's the honest read:
— 35 clean entries (4 vendor-data outliers excluded; full list on the page)
— Median 1-day alpha: -0.73% vs SPY
— Beat-SPY rate: 37% (1 in 3 calls)
— Best day's alpha: +6.4% on a single name. Worst: -8.1%

That's bad. Or it's noise. With 35 data points it's impossible to tell which.

I'm publishing it anyway. The point of /scorecard isn't to show off — it's to make the model auditable from day one, including when the early weeks look like this.

In 60-90 days, when the sample is large enough to mean something, the page will say either "the model holds up" or "the model needs work." Either way the data is there.

That's worth more than the +648% the bug was producing.
```

Char count: ~960. Add `tapeline.io/scorecard` in first comment.

---

## Post #8 — Why I publish the formula even though competitors don't

```
A retail trader asked me last week why I publish Tapeline's scoring formula. "Doesn't that let competitors copy it?"

Three answers:

1. The formula isn't the moat. Six published factors with published weights is the entry ticket to being credible. The moat is the operations — the data pipelines, the back-check infrastructure, the scorecard accountability layer. Anyone can build the formula in a weekend. The infrastructure took six months.

2. The customer can't trust a black box. Finviz, Zacks, TipRanks, Simply Wall St all hide their scoring methodology. That's not a competitive advantage; it's a trust deficit. If I don't tell you how the score is built, why should you act on it?

3. If the formula is wrong, I want to know. Publishing it invites every quant on the internet to argue with me. Some of them will be right. The model gets better when it's audited in public.

Tapeline.io/how-it-works has the full breakdown.
```

Char count: ~1,030. Add nothing in comments (URL is in the body itself, no separate destination).

---

## Post #9 — A scanner that publishes its misses

```
The Tapeline scorecard logged a -4.2% alpha day this week.

The pick was a high-conviction call. The next session it underperformed SPY by 4.2 percentage points.

Most stock scanner services would never show you this. They'd quietly update the methodology, retroactively adjust the weights, or just not back-check at all. The marketing keeps saying their "AI" or "proprietary algorithm" is winning.

I built /scorecard to be different. Every miss stays on the page. Every win stays on the page. Nothing gets edited. The /changelog tracks any methodology change in version-controlled markdown — if the formula ever changes, the change has to be argued for in writing first.

The point of doing it this way isn't that Tapeline never misses. It's that when Tapeline misses, you'll see it.
```

Char count: ~880. Add `tapeline.io/scorecard` in first comment.

---

## Post #10 — Building a fintech alone, from Melbourne

```
A few things I've learned building Tapeline solo from Melbourne over the last few months:

1. Australia treats fintech compliance very differently to the US. The Australian publisher exemption from AFSL requirements means I can publish quantitative analysis on US stocks without holding a financial services licence — provided I'm "general information only, not personal advice." That language is now on every scoring page.

2. The time zone is a feature, not a bug. The US market closes at 6 AM AEST. I wake up to a fully back-checked scorecard with overnight data already populated. By the time US-East-Coast traders are at their desks, the next day's picks are already frozen.

3. The hardest part wasn't the scoring formula — it was the data plumbing. Polygon (now Massive) for prices, Finnhub for fundamentals + insider Form 4, FRED for macro indicators, Benzinga for news, SEC EDGAR for 8-K filings. Each one has its own auth pattern, rate limits, and failure modes. Half the codebase is reconciling sources.

4. There's no support team to fall back on. Every bug is mine. Every customer email is mine. Every regulatory decision is mine. That's the trade for not having a co-founder yet.

Tapeline.io if you want to see what 9 months of solo work looks like.
```

Char count: ~1,360 (within LinkedIn's 3000 cap). Add nothing in comments.

---

## Post #11 — Why "Free" tier shows the real product, just delayed

```
The Tapeline Free tier doesn't show a feature-stripped demo. It shows the actual product, 24 hours delayed.

Most SaaS free tiers cripple core functionality — fewer rows, no exports, no filters. The idea is to frustrate users into upgrading. That's the wrong incentive: it teaches users that the product is annoying.

Tapeline's free tier instead shows the top 20 tickers from yesterday's close, with the full 6-factor breakdown, the full reason sentence, and the full scorecard. The only difference vs Pro is the 24-hour delay.

If you can act on day-old data, the free tier is the right tier. If you can't, the Pro tier ($24.99/month annual) gives you the same data live.

I'd rather a user understand what Tapeline does for free, decide it doesn't fit their workflow, and not pay, than have someone upgrade because the free tier was deliberately annoying and then churn in week two.

Both outcomes end at the same place. The first is honest.
```

Char count: ~1,080. Add `tapeline.io/pricing` in first comment.

---

## Post #12 — What's next on the Tapeline roadmap

```
A short version of what's shipping next:

1. Walk-forward back-test for 2024-2025 — the live /scorecard is the forward test; the walk-forward is the historical version. Lots of caveats about how walk-forward back-tests can be gamed, all documented on the page.

2. Multi-watchlist support — themed buckets like "Tech compounders" / "AI plays" / "Core 10" rather than one big undifferentiated list. Pro gets 5 lists, Premium 20. (Just shipped this week — try it on /app/watchlist.)

3. Saved scanner presets — save a filter combo (sector + min score + sort) and recall it with one click. Pro gets 10 presets, Premium 100.

4. Apple Sign-In + Microsoft OAuth — deferred until 50+ paying users specifically ask. Most of you sign in with Google.

5. A public API — Premium tier gets 1,000 requests/day once it ships. Building to actual demand, not the marketing copy promise.

Anything you'd add? I'm picking the next sprint by reply count.
```

Char count: ~1,040. Add `tapeline.io/roadmap` in first comment.

---

## Posting schedule

Spread these across ~3 weeks so the LinkedIn algorithm doesn't see a
spam pattern. Mix in engagement (comments on other people's posts)
between your own posts.

| Date | Post |
|---|---|
| Tue 2026-05-19 | #4 (scorecard fix) — high-relevance day-of |
| Thu 2026-05-21 | #5 (factors in order) |
| Sat 2026-05-23 | #6 (Smart Money breakdown) |
| Tue 2026-05-26 | #7 (7 days of forward-testing) — needs the number refreshed at post time |
| Thu 2026-05-28 | #8 (why publish the formula) |
| Sat 2026-05-30 | #9 (a scanner that publishes misses) |
| Tue 2026-06-02 | #10 (building solo from Melbourne) |
| Thu 2026-06-04 | #11 (free tier philosophy) |
| Sat 2026-06-06 | #12 (roadmap) |

After post #12, re-audit: are there topics from reader comments / Show
HN feedback / podcast interviews that are worth a #13-#20 batch?

---

## Posts #13-15 — amplify the 2026-05-20 blog cluster

Three new long-form posts shipped 2026-05-20/21 in PR #165 targeting
commercial-investigation SERP queries:

  /blog/best-stock-scanner-under-30
  /blog/how-to-read-sec-form-4
  /blog/how-to-evaluate-a-stock-scanner-track-record

Each gets a paired LinkedIn post in the same factual / methodology-first
voice. URL in the FIRST COMMENT (LinkedIn down-ranks links in body).

---

### Post #13 — Honest scanner-comparison framing

```
I wrote a "best stock scanner under $30/month" comparison this week.

I'm running one of the four products in the comparison (Tapeline). The
post is 1,200 words of honest cost-quality matrix vs Finviz Elite,
Stock Rover Essentials, Zacks Premium — and it explicitly calls out
the rows where Tapeline loses to each of them.

We lose on:
- Raw filter breadth (Finviz has 70+ filters; we don't try to)
- Portfolio analytics (Stock Rover does this better)
- Earnings + analyst-rating depth (Zacks is the reference)
- Free-tier data freshness (ours is 24-hour delayed — deliberately)

We win on:
- Public formula with exact weights (not "proprietary algorithm")
- Daily back-checked picks vs SPY, append-only, every loser still on
  the page
- One-click cancel, no-card trial

The reason most "best scanner" articles are useless is that they're
affiliate-fee farms. Every product gets 9/10, the criteria are
gamed, the conclusion is always "they're all great." If you've
read more than two, you know the pattern.

This isn't that. I tried to write the post I wish I'd read before
buying my first scanner — the one that tells you to rule us out
cleanly if we don't fit.
```

Char count: ~1,140. First comment: `tapeline.io/blog/best-stock-scanner-under-30`

Why this works: signals confidence (calling out own weaknesses), keys
into "affiliate farm" frustration B2B operators recognise, ends with
soft pitch tied to discomfort with industry-standard fluff.

---

### Post #14 — Form 4 field guide

```
Most retail traders see a Form 4 filing — the SEC paperwork every
corporate insider files within 2 business days of trading their
company's stock — and assume any large purchase is bullish.

90% of Form 4 activity is noise. Here's what I filter out before
the data hits Tapeline's Smart Money sub-score:

1. Anything that isn't transaction code P (open-market buy) or S
   (open-market sale). Grants, vestings, withholdings, exercises
   — those are HR paperwork, not directional trades.

2. 10b5-1 plan sales. These are pre-arranged schedules executives
   use to sell systematically. A CFO who set up a 10b5-1 in March
   selling 10k shares every quarter isn't reacting to current
   information.

3. Tiny purchases relative to existing holdings. A director who
   owns 500k shares buying 100 more is rounding error in their own
   portfolio.

4. Director purchases at companies with mandatory ownership rules.
   New board appointees are often just complying with the policy,
   not expressing a view.

What's left after that filter is the 10% that actually predicts
something. Cluster buying (CEO + CFO + ≥1 director, same direction,
30-day window) is the cleanest signal in the data. The 2-day filing
lag is the catch — by the time you see it, the trade is up to 48
hours old.

Smart Money is 15% of the Tapeline composite. The 90% filter runs
automatically; the result is one number, scored against the
universe.
```

Char count: ~1,310. First comment: `tapeline.io/blog/how-to-read-sec-form-4`

Why this works: technical credibility (mentions specific filing codes,
real 2-day lag), useful even if reader never visits Tapeline, ends on
"we do this filtering for you" pitch that's earned not begged.

---

### Post #15 — The 5-test scanner checklist

```
Choosing a stock scanner is mostly an exercise in detecting what
isn't said.

The five tests I'd run before paying for any of them — and what
the vague answer to each one tells you:

1. Can you see every pick, including the losers?
   Right answer: a URL to the daily picks log, append-only, losers
   visible. Vague answer: "67% win rate based on internal testing"
   with no link.

2. Is the benchmark named?
   Right answer: "vs SPY, same-day-pick to next-trading-day-close."
   Vague answer: "outperforms the market" with no index named.

3. Is the scoring methodology published?
   Right answer: exact factor weights, public, change-log
   announced. Vague answer: "proprietary algorithm developed
   over X years."

4. How fresh is the data?
   Test it by checking the timestamp on a single quote against
   your broker feed.

5. What's the cancel friction?
   The dirtiest test but the most diagnostic. Products confident
   in their value make it trivial to leave. Products that depend
   on retention friction make it hard.

I scored Tapeline against this checklist in the post (linked in
first comment). We pass all five — but the checklist is
deliberately product-agnostic. Use it on any scanner before paying.

The one thing the checklist DOESN'T test: whether the product
matches your style. That's a separate question. Pass the
checklist first, then check the style fit.
```

Char count: ~1,260. First comment: `tapeline.io/blog/how-to-evaluate-a-stock-scanner-track-record`

Why this works: positioned as buyer's framework, not seller's pitch.
Useful even if reader never tries Tapeline. Last paragraph admits the
checklist's limit — that admission is the credibility move.

---

### Updated posting schedule

Posts #4–6 are past their scheduled dates — facts haven't changed,
so just post them at the next available Tue/Thu/Sat in sequence
rather than shifting the whole calendar.

| Date | Post |
|---|---|
| Catch-up (post in order, one per Tue/Thu/Sat) | #4 → #5 → #6 |
| Tue 2026-05-26 | #7 (7 days of forward-testing) — refresh the number at post time |
| Thu 2026-05-28 | #8 (why publish the formula) |
| Sat 2026-05-30 | #9 (a scanner that publishes misses) |
| Tue 2026-06-02 | #10 (building solo from Melbourne) |
| Thu 2026-06-04 | #11 (free tier philosophy) |
| Sat 2026-06-06 | #12 (roadmap) |
| **Tue 2026-06-09** | **#13 (honest scanner comparison)** |
| **Thu 2026-06-11** | **#14 (Form 4 field guide)** |
| **Sat 2026-06-13** | **#15 (5-test scanner checklist)** |

