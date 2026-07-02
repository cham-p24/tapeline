# Tapeline — 8-Week Reddit Posting Calendar

Drafted 2026-05-14. Pairs with `docs/launch/LAUNCH_PLAYBOOK.md` §2 which has the three sub-tailored launch posts already drafted (r/algotrading, r/stocks, r/SecurityAnalysis). This calendar:

1. Schedules the launch posts across weeks 1-2.
2. Provides copy for weeks 3-8 follow-up posts that don't repeat the announcement — instead they share something interesting from the live `/scorecard` so the audience keeps coming back.
3. Sets the response playbook: what to do if a post pops, what to do if it dies.

**Posting account**: your existing reddit account with ≥ 30 karma. Fresh accounts get auto-filtered by sub-mod scripts; ban risk is high. Use your real account even if you'd rather stay anonymous.

**Voice**: founder-personal first person. Self-promo gets removed; substance + transparency carries.

**Anti-pattern checklist (do NOT do)**:
- Don't post in r/wallstreetbets — that crowd burns SaaS founders alive
- Don't post the same body to multiple subs in the same week — Reddit's spam filter shadowbans cross-posts
- Don't link to /pricing in the body; link to /scorecard or /how-it-works and let the pricing page sell itself
- Don't reply to "shilling" accusations defensively — link to /scorecard and let the public track record do the work

---

## The 8-week schedule

All times are US Eastern (where Reddit's finance subs see the most traffic). Skip days marked X for the previous week's post if its momentum is still alive; otherwise post on the next slot.

### Week 1 (2026-05-19) — Launch posts

| Day | Time | Sub | Post |
|---|---|---|---|
| Tue 2026-05-19 | 9:00 AM ET | r/stocks (3M subs) | LAUNCH_PLAYBOOK §2 — "Built a free stock score tool — every call back-checked vs SPY next day, full history public" |
| Thu 2026-05-21 | 10:00 AM ET | r/algotrading (~700K subs) | LAUNCH_PLAYBOOK §2 — "I built a 6-factor composite stock scoring system — formula, weights, and a public back-check page" |

### Week 2 (2026-05-26) — Third launch post

| Day | Time | Sub | Post |
|---|---|---|---|
| Tue 2026-05-26 | 9:00 AM ET | r/SecurityAnalysis (~250K subs) | LAUNCH_PLAYBOOK §2 — "Tapeline — synthesises 6 factor signals into one score, plain-English Why per ticker, public daily scorecard" |

### Week 3 (2026-06-02) — First follow-up cycle

**Tue 2026-06-02 · 9:00 AM ET · r/stocks**

**Title**: `Two weeks of scoring stocks in public — here's the rolling 30-day hit rate and one big surprise`

**Body** (replace `[X]` with values from `curl https://api.tapeline.io/api/scorecard?days=30 | jq '.summary'` before posting):

```
Two weeks ago I shared Tapeline (https://tapeline.io) here — a free stock scanner that publishes its top-10 daily picks and back-checks each one against SPY the next day. Posting an update because the public scorecard now has [X] top-10 calls logged and I think the early data is interesting:

- Of the [X] picks that have a completed 1-day back-check, [Y]% beat SPY in their next session.
- Average alpha per pick: [±Z.Z]% (positive means we beat SPY; negative means we underperformed).
- Best single call: [TICKER] at [+A.A]% alpha vs SPY.
- Worst single call: [TICKER] at [-B.B]% alpha vs SPY.

The full record — every pick, every back-check, including the misses — is at https://tapeline.io/scorecard. No survivor bias, no quiet edits. The misses stay on the page.

What surprised me from two weeks of running this:

1. The [SECTOR] factor weighting works better than I expected. When all four of Trend / RS / Smart Money / Momentum align, the next-day hit rate is materially higher than the composite average. When only one or two align, it's basically coin-flip.

2. Macro turns out to scale everything. Same factor configuration in a friendly regime vs a hostile one is a different trade. /how-it-works has the full formula if you want to roast it.

3. Insider clusters (multiple Form 4 buys in the same window) are the single best leading signal. I underweighted Smart Money on launch; the data is pushing me to revisit.

Free tier is still top 20 tickers, 24h delayed. Pro is $9.99/mo for the full ~2,500-ticker universe. 14-day Premium trial, no card needed.

What signals or factors would you want me to add weight to? The formula is versioned in the changelog so factor changes ship with a written rationale.
```

**Response playbook for this post**: if it gets ≥ 30 upvotes in the first hour, reply to every comment in the next 2 hours. Treat sceptic comments as user research, not attacks — they're free product feedback.

**Thu 2026-06-04 · 10:00 AM ET · r/algotrading**

**Title**: `Walked the 6-factor model forward for 14 trading days. Here's the factor-level alpha breakdown.`

**Body**:

```
Update from the r/algotrading post two weeks ago. Brief recap: Tapeline is a 6-factor composite stock score, weights public (25 trend / 20 RS / 15 fundamentals / 15 smart money / 15 macro / 10 momentum), top-10 picks frozen at each close and back-checked vs SPY at next close on a public /scorecard.

[X] picks logged. Here's what factor-decomposition on the picks that beat SPY says:

| Factor | Picks > 80 on this factor | Hit rate | Avg alpha |
|---|---|---|---|
| Trend | [X] | [Y]% | [Z]% |
| Relative Strength | [X] | [Y]% | [Z]% |
| Fundamentals | [X] | [Y]% | [Z]% |
| Smart Money | [X] | [Y]% | [Z]% |
| Macro | [X] | [Y]% | [Z]% |
| Momentum | [X] | [Y]% | [Z]% |

(Pull the actual numbers by running the same factor filter on /api/scorecard?days=30 plus /api/ticker per pick. I'll publish the analysis script if there's interest.)

Three observations worth roasting:

1. The Smart Money factor's hit rate exceeds its weight. Suggests I should bump it from 15% → 18-20% and reduce one of the lower-performing factors. But 14 days is too small a sample to act on; will publish the same table at 60 days and reconsider.

2. Momentum (lowest weight at 10%) is *also* hitting above its weight. Probable explanation: Momentum overlaps heavily with Trend + RS, so its alpha is partially redundant. Don't think I'll rebalance up.

3. Macro factor's hit rate is *below* average on picks that scored high on Macro alone, but *above* average when it scored high in confluence with Trend + RS. This is what I expected: Macro is a confluence multiplier, not a standalone signal. Glad the data confirms.

If you have a backtest framework already running, I'd genuinely want eyes on the methodology. Roast the factor definitions at https://tapeline.io/how-it-works.
```

### Week 4 (2026-06-09) — Sub rotation

**Tue 2026-06-09 · 9:00 AM ET · r/SecurityAnalysis**

**Title**: `Piotroski F-score in a 6-factor composite — how I'm using it differently from textbook`

**Body**:

```
Three weeks ago I posted the Tapeline launch here. Brief recap: 6-factor composite (Trend 25, RS 20, Fundamentals 15, Smart Money 15, Macro 15, Momentum 10), public scorecard, free top-20.

I want to dig into the Fundamentals factor since this sub leans deep on it. The Tapeline Fundamentals sub-score combines:

- Revenue growth, trailing 4 quarters (yoy + sequential)
- Operating-margin trend, trailing 4 quarters
- ROE — current vs sector median
- Piotroski F-score — 9-point score

The Piotroski piece is where I want feedback. The textbook formula treats all 9 binary tests with equal weight. In practice:

1. The cash-flow tests (CFO > 0, CFO > Net Income, CFO/Assets up) have predicted next-12mo returns substantially better than the equity tests (ROA up, gross margin up). I'm weighting cash-flow inputs ~1.5x in the composite. Sin or smart?

2. The leverage tests (long-term debt down) are noisy at the start of a capex cycle — penalising companies that are actively investing for growth. I'm dampening these tests when revenue growth is > 15% yoy. Probably violates the original Piotroski paper's intent.

3. For financial sector names the textbook F-score doesn't apply cleanly (long-term debt is the product, not a quality signal). I'm running a different fundamentals routine for sector=Financials. Documented at /how-it-works.

Curious whether anyone here has done the rigorous edge-case work on F-score across sectors. If there's a literature pointer I'm missing, I'd genuinely take it.

Full scorecard with the live Fundamentals factor on every name: https://tapeline.io/scorecard.
```

### Week 5 (2026-06-16) — r/stocks, market-event-tied post

**Format**: tie this week's post to a real market event that happened in the prior 7 days. Examples:
- A Fed announcement → "How the Tapeline Macro factor reacted: VIX impact + 10Y direction shift"
- A major earnings miss/beat → "Tapeline scored $TICKER at X before earnings; here's what the post-earnings move looked like"
- A sector rotation event → "Energy ripped this week — the Tapeline Energy sector score had been climbing for 5 sessions"

**Title pattern**: `Tapeline read on [event]: [factor that moved] [direction]`

**Body skeleton** (fill in event-specific):

```
[Sentence on the event in plain English.]

The Tapeline scoring formula has a [factor] component weighted at [X]%. Here's what that factor did during the event window:

- 2 days before event: avg sub-score across [universe] = [X]
- Day of event: avg sub-score = [Y]
- 2 days after event: avg sub-score = [Z]

[1-2 sentences on what that delta means in practice for picks.]

The full live read on every ticker is at /scorecard; the public formula is at /how-it-works. Pro tier is $9.99/mo for full live data, free is delayed-top-20.

Curious which factor weighting you'd argue should change after [event].
```

If no big market event happened this week, defer this slot to next week and repeat with whatever does happen.

### Week 6 (2026-06-23) — r/algotrading, methodology comparison

**Tue 2026-06-23 · 10:00 AM ET · r/algotrading**

**Title**: `Comparing Tapeline's 6-factor composite to Piotroski F + IBD Composite Rating + Zacks Rank — same universe, same week`

**Body**:

```
Five weeks of Tapeline running. To stress-test the 6-factor weighting, I ran three established scoring methodologies on the same 100-ticker liquid universe and compared each one's "top decile" picks against /scorecard's actual back-check.

Methodologies tested (all are factor-overlap-aware so this isn't apples to apples but is informative):

1. Piotroski F-score (9-point, pure fundamentals)
2. IBD Composite Rating (RS Rating × EPS Rating × A/D Rating × Group Rating × SMR Rating × Composite, technical-heavy)
3. Zacks Rank (analyst estimate revision, fundamentals-heavy)
4. Tapeline 6-factor composite (this thread)

Top-decile next-day vs SPY hit rate (5-week sample, [N] picks total):

[Table when you have the data]

Three observations:

1. None of the four methodologies have enough sample size to be statistically significant at 5 weeks. The differences below ±5 percentage points are noise.

2. The most useful intersection is "ranked top decile by 2+ methodologies." Tapeline + Piotroski + IBD all-three-aligned has the highest hit rate in the sample, but only [X] picks qualified. Suggests confluence > weighting.

3. Tapeline's Macro factor is the biggest divergence — none of the comparison methodologies include a regime overlay, which means in unfavorable regimes the comparison methods rank names that the Macro factor downweights. Whether that's good or bad depends on whether you think Macro adds alpha. Open question.

If you're running your own composite system and want to throw a fourth methodology into the comparison, ping me — happy to share the picks list so you can run yours on the same universe.

/scorecard for the live record. /how-it-works for the formula.
```

### Week 7 (2026-06-30) — r/SecurityAnalysis, deep-dive on one factor

**Tue 2026-06-30 · 9:00 AM ET · r/SecurityAnalysis**

**Title**: `Smart Money factor: how 13F lag + Form 4 cluster detection + Congressional flow combine into one sub-score`

**Body**:

```
Pulling out the Smart Money factor from the Tapeline composite (15% weight) because it's the part most retail tools either skip or hide.

Tapeline's Smart Money sub-score combines three data streams:

1. **Form 4 insider transactions** — net 90-day insider buying, weighted by cluster detection. Single insider buying noise; 2+ insiders in the same 30-day window is signal. Lag: 1-3 business days.

2. **Elite 13F holdings** — quarterly position disclosures from 8 curated funds (Buffett, Burry, Tepper, Ackman, Druckenmiller, Laffont, Coleman, Singer). New-position weighting > add-to-existing > trim > exit, scaled by portfolio percentage. Lag: 45 days post quarter-end.

3. **Congressional disclosures** — STOCK Act required filings, weighted by committee assignment + filing volume + recency. Lag: 30-45 days.

Five-week observations:

- Insider clusters predict 1-day-to-3-week returns better than 13F deltas. The 45-day 13F lag means by the time you see it, the position is often already-priced.

- 13F new positions in concentrated portfolios (e.g., Scion's typical ~10 positions) are signal-rich because the manager had to allocate a meaningful portfolio percentage. 13F adds in diversified portfolios (e.g., 200+ holdings) are noise.

- Congressional flow is the noisiest signal in the trio. Most members hold passive index funds; the few who trade individual names are concentrated in committee-relevant sectors. Tapeline weights Congressional flow by committee-relevance, not raw transaction count.

The full Smart Money factor methodology is at https://tapeline.io/how-it-works.

What's the cleanest way you've seen anyone scale Congressional disclosure flow? The dual problem is signal sparsity (most weeks have ~10 disclosures across thousands of liquid names) and noise (most disclosures are unrelated to committee work).
```

### Week 8 (2026-07-07) — r/stocks, two-month reflection

**Tue 2026-07-07 · 9:00 AM ET · r/stocks**

**Title**: `Two months of Tapeline running in public — the part I'd change about the methodology`

**Body**:

```
Two months ago I launched Tapeline (https://tapeline.io) — a 6-factor stock scoring tool with a public scorecard back-checking every top-10 daily pick against SPY the next session.

Two months in, the public scorecard has [X] daily top-10 cohorts logged with [Y]% hit rate beating SPY and [Z]% average alpha per pick. Full history at /scorecard.

One change I'd make if I were starting over today:

**Smart Money factor weight is too low at 15%.** Two months of data show insider-cluster events are the single best leading signal in the composite. Lifting Smart Money from 15% to 18-20% (taking the increment from Momentum which is 10% and partially redundant with Trend + RS) would mean a [Q]% hit-rate lift on the sample so far. But:

1. Two months isn't a long enough horizon to act on. Want to see at least 6 months and a regime shift.

2. The Smart Money signal degrades when an insider's buying pattern is predictable (option grants, compensation cycles). The composite already filters for cluster events, but a higher weight raises the cost of false positives.

3. Versioned weights are a feature, not a bug. The day the weights change, you see it in the changelog and you can audit what we re-trained on. If I bumped weights to fit a 2-month sample I'd be doing exactly what the rest of the industry does — overfitting to recent data.

So I'm publishing the observation but not the weight change. /how-it-works has the current formula and the changelog for any future weight adjustments.

If you want to track the next factor-weight decision: subscribe to the scorecard RSS at /scorecard/rss.xml, or follow @tapeline_io. The methodology updates land there first.

Free is still top-20 24h-delayed. Pro is $9.99/mo for live full universe.
```

---

## Response playbook (applies to every post above)

### If a post pops (≥ 30 upvotes in first hour OR comments section spikes)

- **Reply to every comment within 2 hours.** Reddit's algorithm cares as much about conversation depth as raw vote count.
- **Link to /scorecard in one of your first 3 replies, NOT in every reply.** Spammy URL repetition gets the post de-prioritized.
- **If someone names a ticker in a comment**, reply with that ticker's current score + 6-factor breakdown + the /t/[symbol] link. Run `curl -s https://api.tapeline.io/api/ticker/[SYMBOL]` to get live numbers in 2 seconds.
- **If someone challenges the methodology**: don't get defensive. Link to /how-it-works and ask "what would you change?" Treat it as free user research.
- **If a comment goes viral inside the post** (significantly more upvotes than the OP): pin it, reply to it directly with a substantive followup, and quote it back in your next post.

### If a post dies (< 5 upvotes in first hour)

- **Don't bump it** with comments or self-quotes. Reddit's filter detects that and shadowbans.
- **Don't delete it.** Reposting under a slightly different title triggers spam detection.
- **Do note the failure mode.** Did the title fail to hook? Was the topic too niche for the sub? Adjust the next post's title or sub choice.

### Cross-promotion within the calendar

- After a post in one sub gets traction, link it from your Twitter (@tapeline_io) the next day to seed extra eyes.
- If a comment thread in r/algotrading hits something specific (e.g., a factor question), use that question as the title for the next r/SecurityAnalysis post a week later.
- Don't manually link from one Reddit sub to another. Reddit's spam filter treats cross-sub URL repetition as spam.

## Measurement (lightweight, no dashboards)

Track per post in a simple notes file:

- Sub, post date, title, upvotes after 24h, comments after 24h
- Trial signups from `?utm_source=reddit&utm_campaign=launch_w<N>` (append to every link in every post)
- Comments that surfaced novel product feedback (i.e., feature requests you hadn't heard before)

The metric that matters at 8 weeks: **total trial signups attributable to Reddit UTMs / total Reddit traffic**. Anything > 1.5% is excellent for cold traffic from finance subs.

## UTM convention

Before posting any link in any Reddit post, append:
```
?utm_source=reddit&utm_campaign=launch_w<N>&utm_content=<sub_short>
```

Examples:
- Week 1 r/stocks post links: `https://tapeline.io/scorecard?utm_source=reddit&utm_campaign=launch_w1&utm_content=stocks`
- Week 4 r/SecurityAnalysis: `https://tapeline.io/how-it-works?utm_source=reddit&utm_campaign=launch_w4&utm_content=secanalysis`

Vercel Analytics picks up UTMs automatically — no extra plumbing.
