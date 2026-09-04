# LinkedIn posts #4-15 — drafts ready to schedule

> **WHERE THE CARD SITS — updated 2026-09-05. Check every claim below against `docs/PRICING.md` before posting.**
>
> **Signing up takes an email and a password.** The account it makes lands on
> the Free plan and opens the live scanner — the top ten scored rows of any
> scan, one saved screen. **A card is what starts the 14-day Premium trial**
> (Stripe Checkout, $0 charged that day, first charge on day 14, one click to
> cancel before then), and the trial is what turns on every matching row rather
> than the first ten, plus alerts, CSV export and the Congressional and insider
> feeds.
>
> The **published record is free with no account at all**: the daily Top 10, the
> complete scorecard, a page per scored ticker, and the raw CSV/JSON export.
>
> So: **no line in this file may attach the card to the ACCOUNT or to SIGNING
> IN.** Attach it to the TRIAL, which genuinely requires one. Three layers, in
> this order: the record needs no account; signing up takes an email and a
> password; a card starts the trial.
>
> _History, because this block said the OPPOSITE until today, and that is the
> whole reason it is being rewritten: #548 (2026-08-22) put a card wall in front
> of the logged-in product, and #683 (2026-08-30) removed it. #686 corrected 79
> claims across 42 files — but not this one, because `docs/**` sits outside the
> copy linter's include globs. So this file kept instructing its own reader to
> write the false claim, and every line of paste-ready copy below it was
> generated from that instruction. Audited 2026-09-05: seven of the thirteen
> files in this directory still carried the retired block._
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

## Post #5 — The six factors, and the order they're weighted in

```
Tapeline scores every US stock on six factors, and the ordering is public:

Trend carries the most, then Relative Strength, then Fundamentals / Smart Money / Macro, with Momentum the lightest.

The weights aren't equal. The exact numbers stay internal; the ordering doesn't, and it doesn't change without a changelog entry.

Trend carries the most because price is the lowest-lag input available. The other five describe conditions around it.

Momentum is deliberately the lightest: short-horizon rate of change reverses often, and one of its two inputs is an approximation rather than a direct measurement. Weighting it least keeps the noisiest input from dominating.

Most quant services won't even tell you what's in the score. Anyone who thinks I've got the ordering wrong can argue it in public on the methodology page.
```

Char count: ~840. Add `tapeline.io/how-it-works` in first comment.

---

## Post #6 — What "Smart Money" actually means in our score

```
"Smart Money" is the most-overloaded term in finance. People mean different things by it. So Tapeline pins down exactly what the factor reads:

SEC Form 4 insider transactions — officers and directors trading their own company's stock, filed within 2 business days — netted by direction and dollar value over a recent window. That is the whole input.

Two things it is not. It isn't 13F: a quarterly snapshot filed up to 45 days after the quarter ends is old news by the time you see it, so Tapeline doesn't score it at all. And it isn't Congressional disclosure: Tapeline ingests STOCK Act filings and publishes them as their own feed in the product, but they are not folded into this sub-score, and the methodology page says so.

"Smart Money" is also deliberately a mid-weighted factor, not a top one. Lagged data shouldn't dominate the score, and a filing records that a transaction happened, never why. Still better than vibes.
```

Char count: ~900. Add `tapeline.io/how-it-works` in first comment.

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

## Post #8 — Why I publish the methodology even though competitors don't

```
A retail trader asked me last week why I publish Tapeline's scoring methodology. "Doesn't that let competitors copy it?"

Three answers:

1. Naming the factors isn't the moat. Six named factors with a published weight ordering — and a public per-pick record — is the entry ticket to being credible. The moat is the operations: the data pipelines, the back-check infrastructure, the scorecard accountability layer. Anyone can build a six-factor composite in a weekend. The infrastructure took six months.

2. The customer can't trust a black box. Finviz, Zacks, TipRanks, Simply Wall St all hide their scoring methodology entirely. That's not a competitive advantage; it's a trust deficit. If I don't tell you what the score is even made of, why should you act on it?

3. If the methodology is wrong, I want to know. Publishing it invites every quant on the internet to argue with me. Some of them will be right. The model gets better when it's audited in public.

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

3. The hardest part wasn't the scoring formula — it was the data plumbing. Polygon (now Massive) for prices, Finnhub for fundamentals + insider Form 4 + news, FRED for macro indicators, SEC EDGAR for 8-K filings. Each one has its own auth pattern, rate limits, and failure modes. Half the codebase is reconciling sources.

4. There's no support team to fall back on. Every bug is mine. Every customer email is mine. Every regulatory decision is mine. That's the trade for not having a co-founder yet.

Tapeline.io if you want to see what 9 months of solo work looks like.
```

Char count: ~1,360 (within LinkedIn's 3000 cap). Add nothing in comments.

---

## Post #11 — Why "Free" shows the real product, not a crippled demo

```
The Tapeline free surface doesn't show a feature-stripped demo. It shows the actual product, live.

Most SaaS free tiers cripple core functionality — fewer rows, no exports, no filters. The idea is to frustrate users into upgrading. That's the wrong incentive: it teaches users that the product is annoying.

The published record needs no account at all: the daily Top 10, a page per scored ticker, the complete scorecard, and the raw CSV/JSON export. A free account adds the top 10 scanner rows, live, with 12 ticker look-ups a day — each with the full 6-factor breakdown and the full reason sentence. The gate is breadth and volume, not freshness.

If ten names a day is enough, that's the right tier. If you want to scan the full ~2,500-ticker universe live, Pro ($8.25/month annual) opens it up.

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
| Thu 2026-05-28 | #8 (why publish the methodology) |
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
- Free-tier breadth (top-10 rows and 12 look-ups a day — deliberately)

We win on:
- Public factor set and weight ordering, plus a public per-pick record
  (not "proprietary algorithm")
- Daily back-checked picks vs SPY, append-only, every loser still on
  the page
- One-click cancel, a T-3 reminder email before the first charge, and
  30-day money back

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

A lot of Form 4 activity isn't a directional trade at all. What
to check before reading anything into one:

1. The transaction code. P is an open-market buy, S an open-market
   sale. Grants, vestings, withholdings and exercises
   — those are HR paperwork, not decisions about the stock.

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

And the catch that applies to all of it: the 2-day filing deadline
means that by the time you see a Form 4, the trade is already up to
48 hours old.

Where Tapeline sits on this, plainly. Smart Money is one of the six
factors in the composite, and it nets every disclosed transaction in
a recent window by direction and dollar value. It does not strip out
10b5-1 sales, exercises or withholdings — they get netted like
anything else. The filing records that a transaction happened, never
why, and no amount of scoring fixes that. It's stated as a limitation
on the methodology page rather than buried.
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
   Right answer: the factor set and their weighting order,
   published, with a changelog on any change. Vague answer:
   "proprietary algorithm developed over X years."

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
| Thu 2026-05-28 | #8 (why publish the methodology) |
| Sat 2026-05-30 | #9 (a scanner that publishes misses) |
| Tue 2026-06-02 | #10 (building solo from Melbourne) |
| Thu 2026-06-04 | #11 (free tier philosophy) |
| Sat 2026-06-06 | #12 (roadmap) |
| **Tue 2026-06-09** | **#13 (honest scanner comparison)** |
| **Thu 2026-06-11** | **#14 (Form 4 field guide)** |
| **Sat 2026-06-13** | **#15 (5-test scanner checklist)** |

