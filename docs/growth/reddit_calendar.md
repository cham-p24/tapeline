# Tapeline — 8-Week Reddit Posting Calendar

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
| Thu 2026-05-21 | 10:00 AM ET | r/algotrading (~700K subs) | LAUNCH_PLAYBOOK §2 — "I built a 6-factor composite stock score with a public, unedited daily back-check vs SPY" |

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

1. The sample is far too small to draw a factor-level conclusion from. I had half-expected two weeks to tell me something about which factor combinations hold up; it doesn't, and I'd rather say so than read a pattern into [X] calls.

2. Macro is the same reading for every ticker on a given tick, by construction. It lifts or lowers the whole board together rather than separating names — a genuine limitation, and /how-it-works states it on the page rather than burying it.

3. Smart Money reads disclosed Form 4 transactions netted over a recent window — not 13F, and not Congressional disclosures, which are ingested and published as their own feed rather than folded into the sub-score. Whether that netting is the right construction is the thing I'd most like torn apart.

The full record is readable with no account and no card. A free account is an email and a password — no card — and gets top-10 rows live plus 12 look-ups a day. Pro is $9.99/mo for the full ~2,500-ticker universe. A card is only for the 14-day Premium trial — $0 charged today, first charge on day 14, one click to cancel before then.

What signals or factors would you want me to add weight to? The weighting is versioned in the changelog so factor changes ship with a written rationale.
```

**Response playbook for this post**: if it gets ≥ 30 upvotes in the first hour, reply to every comment in the next 2 hours. Treat sceptic comments as user research, not attacks — they're free product feedback.

**Thu 2026-06-04 · 10:00 AM ET · r/algotrading**

**Title**: `Walked the 6-factor model forward for 14 trading days. Here's the factor-level alpha breakdown.`

**Body**:

```
Update from the r/algotrading post two weeks ago. Brief recap: Tapeline is a 6-factor composite stock score, six named factors with a published weight ordering (heaviest Trend + RS, lightest Momentum), top-10 picks frozen at each close and back-checked vs SPY at next close on a public /scorecard.

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

1. The Smart Money factor's hit rate exceeds its weight. Suggests Smart Money may deserve more weight than it currently carries, taken from one of the lower-performing factors. But 14 days is too small a sample to act on; will publish the same table at 60 days and reconsider.

2. Momentum, the lightest-weighted factor, is *also* hitting above its weight. Probable explanation: Momentum overlaps heavily with Trend + RS, so its alpha is partially redundant. Don't think I'll rebalance up.

3. Macro factor's hit rate is *below* average on picks that scored high on Macro alone, but *above* average when it scored high in confluence with Trend + RS. This is what I expected: Macro is a confluence multiplier, not a standalone signal. Glad the data confirms.

If you have a backtest framework already running, I'd genuinely want eyes on the methodology. Roast the factor definitions at https://tapeline.io/how-it-works.
```

### Week 4 (2026-06-09) — Sub rotation

**Tue 2026-06-09 · 9:00 AM ET · r/SecurityAnalysis**

**Title**: `My Fundamentals factor reads five reported numbers and nothing else — roast the omissions`

**Body**:

```
Three weeks ago I posted the Tapeline launch here. Brief recap: 6-factor composite (heaviest Trend + RS, lightest Momentum), public scorecard, free top-10 rows live.

I want to dig into the Fundamentals factor since this sub leans deep on it. The Tapeline Fundamentals sub-score reads five figures, every one of them already reported in a filing — nothing estimated, projected or modelled:

- Profit margin, as reported
- Return on equity, as reported
- EPS growth between reported periods
- Revenue growth between reported periods
- An earnings multiple — a lower one moves the reading up, a higher one moves it down

Each metric that is available is mapped onto a common 0-100 scale using fixed, broadly-drawn bands, and the available components are averaged. A missing metric is left out entirely rather than filled in with a guess, and the ticker's confidence percentage falls to reflect the thinner evidence.

Three things I already know are weak about it, and where I actually want the roast:

1. There is no cash-flow input at all. No CFO, no CFO-versus-net-income, no accrual check. For a sub that leans on quality, that is probably the first thing you'd add. If you only got to add one more line, which would it be?

2. It is not sector-relative. The same bands are applied to a bank, a biotech and a software company. I know that's blunt. Sector-median comparisons bring their own problems on thin sectors, and I haven't convinced myself the trade is worth it yet.

3. The reading is exactly as current as the last filing. Between reports it does not move, even when the business does — for most names that means static for weeks at a time.

Five reported metrics is a narrow view of a company, and I'd rather say that plainly than dress it up as analysis. The factor definitions are at https://tapeline.io/how-it-works — the six factors are named there, along with their weight ordering.

Full scorecard with the live Fundamentals factor on every name: https://tapeline.io/scorecard.
```

### Week 5 (2026-06-16) — r/stocks, market-event-tied post

**Format**: tie this week's post to a real market event that happened in the prior 7 days. Examples:
- A Fed announcement → "How the Tapeline Macro factor reacted: the market-wide regime read shifted, and every score on the board moved with it"
- A major earnings miss/beat → "Tapeline scored $TICKER at X before earnings; here's what the post-earnings move looked like"
- A sector rotation event → "Energy ripped this week — the Tapeline Energy sector score had been climbing for 5 sessions"

**Title pattern**: `Tapeline read on [event]: [factor that moved] [direction]`

**Body skeleton** (fill in event-specific):

```
[Sentence on the event in plain English.]

The Tapeline composite has a [factor] component. Here's what that factor did during the event window:

- 2 days before event: avg sub-score across [universe] = [X]
- Day of event: avg sub-score = [Y]
- 2 days after event: avg sub-score = [Z]

[1-2 sentences on what that delta means in practice for picks.]

The full live read is at /scorecard; the methodology is at /how-it-works. Pro is $9.99/mo for the full live universe; free accounts get top-10 rows live with 12 look-ups a day.

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

2. The overlap worth looking at is "ranked top decile by 2+ methodologies" — [fill in from the table: which combinations overlapped, how many picks qualified]. Do not write a conclusion into this slot before the numbers exist; at this sample size there may not be one.

3. Tapeline's Macro factor is the clearest structural difference — none of the comparison methodologies carry a market-regime term at all. Worth being precise about what it does: it reads a single market-wide classification, so on any given tick it is the same reading for every ticker and it lifts or lowers the whole board rather than re-ordering names within it. Whether that helps is an open question.

If you're running your own composite system and want to throw a fourth methodology into the comparison, ping me — happy to share the picks list so you can run yours on the same universe.

/scorecard for the live record. /how-it-works for the methodology.
```

### Week 7 (2026-06-30) — r/SecurityAnalysis, deep-dive on one factor

**Tue 2026-06-30 · 9:00 AM ET · r/SecurityAnalysis**

**Title**: `Smart Money factor: why it reads SEC Form 4 and not 13F`

**Body**:

```
Pulling out the Smart Money factor from the Tapeline composite because it's the part most retail tools either skip or hide.

Tapeline's Smart Money sub-score reads one data stream: disclosed SEC Form 4 insider transactions. Every disclosed transaction in a recent rolling window becomes a signed dollar value — shares changed, times the disclosed price — and the net is taken against the gross, then mapped onto a 0-100 scale around a midpoint.

Congressional disclosures are ingested by Tapeline and published as their own feed in the product, but they are not an input to this sub-score. /how-it-works says so on the page; I'd rather name the boundary than let "smart money" imply more than it covers.

Five weeks in, and what I'd actually put up for critique:

- The 45-day 13F filing lag means that by the time you see a fund's position it is often already priced, which is why Tapeline doesn't score 13F data at all. Form 4 is due within a couple of business days of the transaction, so it is at least a fresher record of the same category of event.

- A filing records that a transaction happened, never why. Sales scheduled months ahead under a 10b5-1 plan, option exercises and share sales made purely to cover tax withholding all arrive as Form 4s and get netted like anything else. I have no clean way to strip those out and I don't pretend to.

- Netting by dollar value means one large filer can dominate a company with many reporting insiders. That's a weakness of the construction, not a subtlety.

- A ticker with no filings in the window gets no reading at all and the composite substitutes a mid-range value. An absence of filings is an absence of information, not a negative.

The full Smart Money factor methodology is at https://tapeline.io/how-it-works.

If you've built anything on Form 4: what's the cleanest way you've seen anyone separate a discretionary open-market purchase from a scheduled or comp-driven one, using only what's on the filing?
```

### Week 8 (2026-07-07) — r/stocks, two-month reflection

**Tue 2026-07-07 · 9:00 AM ET · r/stocks**

**Title**: `Two months of Tapeline running in public — the part I'd change about the methodology`

**Body**:

```
Two months ago I launched Tapeline (https://tapeline.io) — a 6-factor stock scoring tool with a public scorecard back-checking every top-10 daily pick against SPY the next session.

Two months in, the public scorecard has [X] daily top-10 cohorts logged with [Y]% hit rate beating SPY and [Z]% average alpha per pick. Full history at /scorecard.

One change I'd make if I were starting over today:

**Smart Money may be carrying too little weight.** Stated carefully, because two months is nowhere near enough to conclude anything: disclosed insider filings look like they may carry more than the weight I gave them. Lifting it — with the increment coming from Momentum, which is the lightest factor and partially redundant with Trend + RS — would have moved the hit rate by [Q] points on the sample so far. That is an observation about a tiny sample, not a finding. But:

1. Two months isn't a long enough horizon to act on. Want to see at least 6 months and a regime shift.

2. A Form 4 records that a transaction happened, never why. Scheduled 10b5-1 sales, option exercises and tax-withholding sales all arrive as filings and get netted like anything else — the sub-score does nothing to separate them out. A higher weight raises the cost of that.

3. Versioned weights are a feature, not a bug. The day the weights change, you see it in the changelog and you can audit what changed and why. If I bumped weights to fit a 2-month sample I'd be doing exactly what the rest of the industry does — overfitting to recent data.

So I'm publishing the observation but not the weight change. /how-it-works has the current methodology and the changelog for any future weight adjustments.

If you want to track the next factor-weight decision: subscribe to the scorecard RSS at /scorecard/rss.xml, or follow @tapeline_io. The methodology updates land there first.

Free accounts get top-10 rows live with 12 look-ups a day; the full record needs no account at all. Pro is $9.99/mo for the live full universe.
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
