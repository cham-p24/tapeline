# Tapeline — Podcast Pitch Drafts

Drafted 2026-05-14, extended 2026-05-15. 11 podcasts where the Tapeline founder fits as a guest. Pitches 1-8 drafted from scratch on 2026-05-14; 7 of those sent that day from cpiyatilaka@gmail.com (all but Flirting With Models, blocked by reCAPTCHA). TTU declined; the other 6 pending reply. Pitches 9-11 drafted 2026-05-15 with verified contact emails and queued as Gmail drafts from `christian@tapeline.io` for founder review + Send.

**Pacing**: send one pitch per week. Two per week reads as bulk outreach; podcasts compare notes. One per week is what real authors / founders do.

**Slow payback caveat**: podcasts book 8-16 weeks out. Don't expect any episode air dates inside the launch window. The value is mid-term (Q3-Q4 2026) authority-build, not immediate signups.

---

## 1. Chat With Traders

**Host**: Tessa Dao and Ian Cox (took over from founder Aaron Fifield).
**Audience**: ~50K weekly listeners. Active retail + prop traders, methodology-curious.
**Why a fit**: every guest is a trader with a system; Tapeline IS a system, with a public scorecard. CWT's entire format is "show me how you actually make decisions."
**Contact**: chatwithtraders.com → guest application form (typeform).

**Pitch** (subject: "Show idea: a stock scanner that publishes its misses"):

```
Hi Tessa, hi Ian — long-time CWT listener.

Pitching myself as a guest because Tapeline (tapeline.io) is the only consumer stock-scanning tool I know of that auto-publishes its picks and their next-day returns vs SPY on a public page. Every miss stays on the page; nothing gets curated. The opposite of how every retail-trader-targeted scoring tool runs.

What I'd bring to a CWT episode:

— A walkthrough of the 6-factor composite formula (25 trend / 20 RS / 15 fundamentals / 15 smart money / 15 macro / 10 momentum) and why each factor is the weight it is.

— The five-month forward-test data — how often the top-10 daily picks beat SPY, where the biggest factor surprises came from, and one weight change I'd argue for (and the reason I haven't made it yet, because two months isn't a long enough sample).

— A specific worked example: pull a ticker live during the episode, decompose its score, show what the factor breakdown is saying that the composite hides.

— Tooling: how the live worker scores ~2,500 US tickers per minute on Fly.io + Neon Postgres + Massive (formerly Polygon) data, the cost structure, where the engineering bottlenecks are.

I built this solo over the last six months. Background in trading-system development before this. The whole thing is a single-founder project with a public formula and a public scorecard.

tapeline.io if you want to see what we're talking about. tapeline.io/scorecard is the receipt.

Happy to record any time and travel-flexible.

Christian Piyatilaka
```

## 2. Top Traders Unplugged

**Host**: Niels Kaastrup-Larsen.
**Audience**: ~1K Apple-podcasts reviews at 4.8/5; institutional-leaning. Trend-following + systematic / quant angle.
**Why a fit**: TTU's quant-systematic audience cares deeply about transparent methodology; Tapeline's published formula + back-check is exactly that ethos.
**Contact**: info@toptradersunplugged.com

**Pitch** (subject: "Guest idea: a retail-facing 6-factor composite with a public forward-test"):

```
Niels — long-time TTU listener.

Pitching myself as a guest. Tapeline (tapeline.io) is a 6-factor composite stock score for the US universe, with:

— A fully published formula and weights (25 trend / 20 RS / 15 fundamentals / 15 smart money / 15 macro / 10 momentum). The weights are version-controlled; the day they change there's a changelog entry with a written rationale.

— A public scorecard that freezes the top-10 daily picks at each market close and back-checks each name against SPY the next session. No survivor bias; misses stay on the page.

— A live forward-test that's currently in month 5. The dataset is small but the methodology is the point — the publisher's commitment to record every miss is what most retail scoring tools refuse to do.

What I'd bring to a TTU episode:

— A walkthrough of how the composite handles the Smart Money factor (Form 4 insider clusters + elite 13F + Congressional disclosure, each with its own lag and signal characteristic). This isn't a topic most retail tools think rigorously about; your audience does.

— The Macro factor implementation — VIX percentile + breadth + 10Y direction + regime score — and how it scales every other factor. The argument is that confluence beats single-signal, but only if the regime overlay is honest.

— The walk-forward back-test plan (2024-2025 sample, leave-one-out cross-validation by quarter) and why I'm running it AFTER the public live test, not before. Some discussion of why the live forward-test is more honest than any back-test could be.

Background: developed trading systems before this; built Tapeline solo over the last six months. The whole product is one founder shipping in public.

tapeline.io · tapeline.io/scorecard · tapeline.io/how-it-works (the published formula).

Happy to record at any time-zone-friendly slot.

Christian Piyatilaka
```

## 3. Flirting With Models

**Host**: Corey Hoffstein (Newfound Research).
**Audience**: Quant practitioners. Smaller audience but high signal — every listener is a portfolio manager or quant researcher.
**Why a fit**: Flirting with Models is the canonical quant-methodology podcast. Tapeline's formula transparency + factor decomposition is exactly the conversation Corey runs.
**Contact**: thinknewfound.com → contact / corey [at] thinknewfound dot com.

**Pitch** (subject: "Guest idea: retail-facing factor model with versioned weights + public forward-test"):

```
Corey — Newfound podcast subscriber.

Pitching a Tapeline (tapeline.io) episode. The angle that's right for FwM: I built a 6-factor composite score for the retail universe with one design constraint that goes against every commercial scoring tool — version the weights in public, publish every miss.

The model:

Composite = 0.25 × Trend + 0.20 × RS + 0.15 × Fundamentals + 0.15 × Smart Money + 0.15 × Macro + 0.10 × Momentum

— Trend: 20/50/200 DMA stack, slope, days above 50DMA.
— RS: Mansfield RS vs SPY, sector RS, 12-1 momentum.
— Fundamentals: revenue growth (TTM), operating-margin trend, ROE vs sector median, Piotroski F-score.
— Smart Money: Form 4 cluster (90-day net insider), elite 13F (8 curated funds), Congressional disclosure weighted by committee relevance.
— Macro: VIX percentile, breadth, 10Y direction, regime score.
— Momentum: 20-day RoC, RSI position, accumulation/distribution.

Questions that might make for a good episode arc:

1. **Should factor weights be versioned in public?** Tapeline's weights are version-controlled and published. The argument for: any change requires written rationale and the audience can audit. The argument against: it exposes overfitting moments before they're production-ready. I'd come down on the "publish" side but I want to hear the counter-argument from someone who's run live models longer than me.

2. **What's the right Bayesian prior on weight changes?** I'm currently planning to require 60 days minimum of live data before adjusting any weight by more than 2 percentage points. That's arbitrary — would value a discussion of how to actually calibrate this.

3. **Does the Macro factor add alpha or is it noise inside the regime distribution?** Five months of data is too small to tell. My instinct is that it works as a confluence multiplier but is noisy in isolation; that's what the per-factor decomposition is showing so far.

Background: trading-system engineering before this. Tapeline is a solo founder project shipped publicly over six months. /scorecard is the back-check; /how-it-works is the math.

Happy to record any time.

Christian Piyatilaka
```

## 4. The Meb Faber Show

**Host**: Meb Faber (Cambria Investment Management).
**Audience**: ~100K weekly listeners. Mass-affluent retail; quant-aware but not deep-quant.
**Why a fit**: Meb runs systematic strategies and his audience is the exact buyer profile for Tapeline — retail traders who want signal beyond their gut. Meb's published-strategy ethos aligns with Tapeline's published-formula ethos.
**Contact**: mebfaber.com → contact form.

**Pitch** (subject: "Guest idea: published-formula stock scoring with a public forward-test"):

```
Meb — long-time listener; have run a couple of your tactical models in client portfolios.

Pitching myself as a guest. Tapeline (tapeline.io) is a 6-factor composite score on US stocks with a constraint your audience would actually appreciate: published formula, versioned weights, public forward-test that records every miss.

Most retail scoring tools (Tipranks Smart Score, Zacks Rank, WallStreetZen Zen Rating) hide their methodology behind "proprietary blend" language. Tapeline's whole positioning is the opposite — formula is on /how-it-works, weights are version-controlled, the daily top-10 cohort gets back-checked against SPY on a public /scorecard the next session.

Episode angle suggestions:

— **"The five-month forward-test on a 6-factor model — what worked, what didn't, what I'd change."** Current hit rate vs SPY, factor-level decomposition, which factor's actual alpha exceeds its weight, why I'm not adjusting weights yet despite the data suggesting I could.

— **"Why publish the formula?"** Your published-tactical-strategies argument applied to retail-facing scoring tools. Same logic, different audience. The moat isn't the formula; the moat is the data spine and the accountability layer.

— **"How a solo founder ships a quant tool in 2026."** Stack: FastAPI + Neon Postgres + Fly.io + Vercel + Massive (Polygon) data, ~$200/mo all-in to score ~2,500 tickers per minute. Engineering bottlenecks, where I'm Stuck, what I'd build next.

Background: trading-system developer before this. Six-month solo project. /scorecard is live; /how-it-works has the formula; /pricing is the business model.

Happy to record.

Christian Piyatilaka
```

## 5. We Study Billionaires (Investor's Podcast Network)

**Host**: Trey Lockerbie + rotating guests (Stig Brodersen, Clay Finck).
**Audience**: ~300K weekly listeners. Long-horizon value-investor leaning.
**Why a fit**: TIP's audience reads 10-Ks and 13F filings; Tapeline's Smart Money factor (13F + Form 4 + Congress) speaks directly to that workflow.
**Contact**: theinvestorspodcast.com → contact form.

**Pitch** (subject: "Guest idea: the Smart Money factor inside a 6-factor composite — how 13F + Form 4 + Congress combine"):

```
Trey / Stig / Clay — long-time listener (We Study Billionaires + Millennial Investing).

Pitching a TIP episode. Tapeline (tapeline.io) is a 6-factor composite stock score; the angle I think your audience cares about most is the Smart Money factor.

Most retail scoring tools hide where the smart-money signal comes from. Tapeline's Smart Money factor (15% weight of the composite) is decomposed into three independent data streams, each with different lag and signal characteristics:

1. **Elite 13F holdings**: 8 curated funds (Buffett, Burry, Tepper, Ackman, Druckenmiller, Laffont, Coleman, Singer). New positions weight > add-to-existing > trim > exit, scaled by portfolio percentage. Lag: 45 days post quarter-end.

2. **Form 4 cluster detection**: 2+ insiders buying in the same 30-day window with no scheduled compensation event. Single-insider buys are deweighted (often comp-driven). Lag: 1-3 business days.

3. **Congressional disclosure**: STOCK Act required filings, weighted by committee assignment + recency. Lag: 30-45 days.

Possible episode arcs:

— **"Why insider clustering is a better leading signal than 13F for retail traders."** The lag analysis is non-obvious; most retail tools just say "13F holdings" and don't address that the position was opened 30-90 days ago.

— **"What the 8 elite funds got right and wrong over the last quarter."** I publish each fund's weighting changes; we could walk through the most concentrated positions and what the factor breakdown on each name says.

— **"The Berkshire AAPL question."** When Buffett buys a stock everyone watches, the position is already crowded by the time the filing publishes. Tapeline weights "new position in concentrated portfolio" > "add to existing in diversified portfolio." Stig's audience would appreciate the methodology around survivorship in the source data.

Background: solo founder, trading-system development before this. Tapeline has been live in public for six months. /scorecard back-checks every call.

Happy to record.

Christian Piyatilaka
```

## 6. Animal Spirits (Ritholtz Wealth)

**Host**: Michael Batnick + Ben Carlson.
**Audience**: ~200K weekly listeners. Generalist wealth-advisor leaning, but with a strong methodology-curious bent.
**Why a fit**: Animal Spirits covers tools, methodology critiques, and the gap between "what retail traders think they should do" vs "what the data says." Tapeline's positioning fits.
**Contact**: animalspiritspod.com → animalspirits [at] ritholtzwealth dot com.

**Pitch** (subject: "Guest idea: a stock scanner with a public scorecard — what the misses look like at 5 months"):

```
Michael + Ben — long-time Animal Spirits listener; have referenced your "things I'm reading" segments in my own daily routine.

Pitching a Tapeline (tapeline.io) episode. The hook for the show: I built a retail stock-scanning tool with one mandate that everyone in the category refuses to do — publish every miss.

The /scorecard page records every top-10 daily pick and its next-day return vs SPY. Wins are recorded, misses are recorded, nothing gets quietly removed. Five months in, the hit rate is real but humbling. The misses are visible. The model gets things wrong on a real percentage of calls. That's the whole point of publishing.

Animal Spirits often covers "this tool says X" without auditing what the tool's track record actually is. I think your listeners would benefit from one episode that walks through:

— What a public scorecard actually looks like (and why almost no commercial tool publishes one).

— The five-month data: hit rate, average alpha per pick, distribution of factor-level outcomes.

— Where the model is consistently wrong. Specifically: high-Macro-score names in hostile regimes underperform; insider-cluster-only signals without Trend confirmation underperform.

— Why methodology transparency matters more than methodology sophistication. Most retail scoring tools are similar inside; the meaningful differentiator is whether the scorecard exists.

Tapeline is a solo-founder project. Trading-system development background. Six months in. /scorecard / /how-it-works / /pricing.

Happy to record.

Christian Piyatilaka
```

## 7. Excess Returns

**Hosts**: Justin Carbonneau + Matt Zeigler.
**Audience**: Quant practitioners + sophisticated retail. Smaller (~5-10K per episode) but every listener is a methodology-buyer.
**Why a fit**: Excess Returns is explicitly about quant model design + walk-forward testing. Tapeline's published-formula + live-forward-test format is exactly their show.
**Contact**: excessreturnspod.com → contact form.

**Pitch** (subject: "Guest idea: walk-forward forward-testing a 6-factor model in public"):

```
Justin / Matt — Excess Returns listener.

Pitching a Tapeline (tapeline.io) episode. The hook is the inverse of most quant podcast guests: I'm walking a 6-factor model forward in public, with the next-day back-check on a public page, instead of running a 10-year back-test and reporting the Sharpe.

Episode arc that I think works for your audience:

— **Walk-forward vs back-test: why I started with forward-test.** A back-test on 6 factors with versioned weights is trivially over-fittable. The forward-test commits the weights before any data is in. Cost: small sample, slow signal. Value: no overfit, no survivor bias, no "we removed the underperforming factor mid-test."

— **Five-month decomposition: which factor's alpha actually exceeds its weight.** Both Smart Money and Momentum are hitting above weight; Macro is below weight in isolation but above weight when in confluence with Trend + RS. The question is how to act on that without overfitting.

— **The Bayesian prior on weight change.** My current rule is no weight change > 2 percentage points without 60 days of supporting data. That's arbitrary; would value a discussion of how Newfound, Two Sigma, etc. actually calibrate model-update cadence.

— **The Stripe-pricing-vs-Sharpe trade-off.** Most quant tools target the institutional buyer (retainer + outcome share). Tapeline is $24.99/mo retail. The conversation: how does a retail-priced quant tool sustain methodology rigor when the unit economics don't support a research team?

Background: solo founder. Trading-system development before this. tapeline.io / tapeline.io/scorecard / tapeline.io/how-it-works.

Happy to record.

Christian Piyatilaka
```

## 8. The Compounders Podcast

**Host**: Ben Claremon (Cove Street Capital).
**Audience**: ~2-5K per episode. Concentrated long-only value investors. Small but the right buyer profile for Premium-tier Tapeline.
**Why a fit**: Compounders' guest format is methodology-deep; Ben asks about how the guest actually decides what to own. Tapeline IS a decision framework. Tightest signal-to-audience match in the list.
**Contact**: covestreetcapital.com → ben [at] covestreetcapital dot com.

**Pitch** (subject: "Guest idea: a published-formula scoring tool — what it scores for compounders vs the broader market"):

```
Ben — long-time Compounders listener.

Pitching a Tapeline (tapeline.io) episode. The hook is your audience-specific: compounder investors typically distrust scoring tools because the tools' formulas are short-horizon. Tapeline's 6-factor composite has 15% weight on Fundamentals (Piotroski F + ROE-vs-sector + revenue growth) — but the Trend factor at 25% weight dominates outputs in any 1-day-to-3-week timeframe. That's the tension.

What I'd bring to a Compounders episode:

— **The Trend-vs-Fundamentals tension for compounders.** Tapeline scores names like CMG, COST, KO that are obvious compounders, but the composite weights short-horizon factors more heavily. Your audience would want to know: should the composite carve out a "compounder mode" that weighs Fundamentals at 30%+ and Trend at 10%? My instinct is no — the composite is universal — but the discussion is interesting.

— **The Smart Money factor and 13F lag for long-horizon holders.** Insider Form 4 clusters are fast signal (1-3 days lag), elite 13F is slow signal (45-day lag). For compounders, the 13F signal is often "already-known" by the time it publishes — but it still confirms what the long-term holder was already thinking. How should Tapeline weight that confirmation value vs leading-signal value?

— **A specific worked example on a Compounders-coverage name** ($CMG, $COST, your pick). Pull the live 6-factor breakdown, decompose what the composite is saying, debate whether the weighting is appropriate for the compounder-investor lens.

— **Why I publish the formula and not just the score.** The Compounders listener-base is the most likely audience to argue with the math, which is exactly what version-controlled weights enable. The next operator after me can argue for a different weighting if the data supports it.

Background: solo founder, six months in. Trading-system development before this. /scorecard for the live record.

Happy to record.

Christian Piyatilaka
```

---

## 9. The Rational Reminder

**Hosts**: Benjamin Felix, Cameron Passmore, Dan Bortolotti (PWL Capital, Canada).
**Audience**: factor-investing-curious retail + RIA advisors. Strongly evidence-based, academic-literature-aligned. Heavy Canadian/US overlap.
**Why a fit**: every Rational Reminder episode is structured around methodology transparency and replicable evidence. Tapeline's published-formula + version-controlled-weights + public-scorecard is the consumer-software application of exactly that ethos. Same incentive structure, different surface area.
**Contact**: info@rationalreminder.ca (also listed for transcript corrections — primary inbox per their podcast page).
**Status**: Gmail draft queued 2026-05-15 from `christian@tapeline.io`. Awaiting founder review + Send.

**Pitch** (subject: "Guest idea: a published-formula factor scoring tool for US retail"):

```
Ben, Cameron, Dan — long-time Rational Reminder listener.

Pitching myself for a guest spot. Tapeline (tapeline.io) is a 6-factor composite score for the US stock universe — Trend 25 / RS 20 / Fundamentals 15 / Smart Money 15 / Macro 15 / Momentum 10 — with one constraint that matches the RR ethos: the formula is fully public, the weights are version-controlled, and every miss the model makes is logged on a back-checked public scorecard.

The angle that's right for RR:

— Factor decomposition done in retail-accessible language. The 6 factors map to academic literature your audience already knows — Asness defensive-quality, Fama-French momentum, regime-aware risk scaling — expressed as a single 0-100 number with a plain-English "why" sentence per row. The transparency of a factor product, without the factor-product framing.

— Why the live forward-test is more honest than any back-test. The /scorecard freezes the top-10 daily picks at close and back-checks each against SPY the next session. Five months in. Misses stay on the page. The sample is small but the methodology stays.

— A specific worked example: take a name live, decompose the score, show where the composite agrees and disagrees with the underlying factor signals. The disagreements are usually more interesting than the agreements.

— The evidence-based-software conversation, retail edition. Tapeline is $24.99/mo Pro, $39.99/mo Premium — competing against $500-$5,000/yr scoring tools that don't publish their methodology. What "evidence-based" means for retail-facing software, not just for portfolio construction.

Background: built Tapeline solo over the last six months. Trading-system developer for ~10 years before this. Melbourne-based, time-zone-flexible.

tapeline.io · tapeline.io/scorecard · tapeline.io/how-it-works

Christian Piyatilaka
```

## 10. The Acquirers Podcast

**Host**: Tobias Carlisle (Acquirers Funds, author of The Acquirer's Multiple + Deep Value).
**Audience**: deep-value / quant-value practitioners, methodology-curious. Smaller but high-signal — every listener has run the multiple themselves.
**Why a fit**: Acquirers Funds publishes the multiple's formula openly and audits it against the market every month. Tapeline does the consumer-software equivalent — a fully published 6-factor composite with version-controlled weights and a public forward-test. The conversation-fit is the transparency-of-methodology question that Tobias asks every guest.
**Contact**: tobias@acquirersfunds.com (direct, public on acquirersfunds.com). Alternative: Twitter @Greenbackd.
**Status**: Gmail draft queued 2026-05-15 from `christian@tapeline.io`. Awaiting founder review + Send.

**Pitch** (subject: "Guest idea: a 6-factor composite with an audited Smart Money factor"):

```
Tobias — Acquirer's Multiple reader since the original book in 2014; have run the multiple across the Australian small-cap universe for the last two years.

Pitching myself for an Acquirers Podcast spot. Tapeline (tapeline.io) is a 6-factor composite score for the US universe with one constraint that's deeply Acquirers-aligned: the formula is fully published, the weights are version-controlled, and every miss is logged on a back-checked public scorecard.

The angle that's right for Acquirers:

— A breakdown of how the Smart Money factor is wired: Form 4 insider clusters + elite-fund 13F + Congressional disclosure, each sub-signal with its own decay function. The composite weight is intentionally only 15% — the argument being that smart-money is corroborating signal, not standalone. Worth discussing what the published research says about each sub-signal's lag.

— The Fundamentals factor (15% of composite): Piotroski F-score + earnings-revisions trend + balance-sheet quality. Why this is smaller than a deep-value playbook would suggest, and the live forward-test result that's making me reconsider the weight.

— A specific worked example: take a deep-value name (Acquirer's Funds holding or otherwise) and decompose the Tapeline score live. Where the 6-factor view agrees with the deep-value framing and where it diverges. The disagreements are usually more interesting than the agreements.

— Operating economics. Live worker scoring ~2,500 US tickers per minute on Fly.io + Neon Postgres + Massive (formerly Polygon). The cost-per-paid-user math and where the operational moat actually is (transparent forward-test, not the formula).

Background: trading-system developer for ~10 years; built Tapeline solo over six months. Melbourne-based.

tapeline.io · tapeline.io/scorecard · tapeline.io/how-it-works

Christian Piyatilaka
```

## 11. The Long View (Morningstar)

**Hosts**: Christine Benz, Amy Arnott, Ben Johnson (Morningstar).
**Audience**: planning/retirement-leaning retail + RIAs. Methodology-first investing audience built around Morningstar's "show the framework behind every rating" ethos.
**Why a fit**: Morningstar built a research business on publishing the methodology behind every rating. Tapeline is the consumer-software version of that — published 6-factor formula, version-controlled weights, back-checked public scorecard. Same standard, different surface area.
**Contact**: TheLongView@morningstar.com (official guest-pitch inbox). Alternative direct: christine.benz@morningstar.com.
**Status**: Gmail draft queued 2026-05-15 from `christian@tapeline.io`. Awaiting founder review + Send.

**Pitch** (subject: "Guest idea: a published-formula scoring tool with a public back-checked scorecard"):

```
Christine, Amy, Ben — long-time Long View listener.

Pitching myself for a guest spot. Tapeline (tapeline.io) is a 6-factor composite scoring tool for the US stock universe with one design constraint that's directly Morningstar-aligned: the formula is fully published, the weights are version-controlled, and every miss is logged on a back-checked public scorecard.

The angle that's right for The Long View:

— What methodology transparency means in retail-facing investing software. Morningstar built a research business on showing the methodology behind every rating; Tapeline applies the same standard to scoring software. The 0-100 composite is decomposed into 6 factor sub-scores on every ticker page with a plain-English "why" sentence.

— A back-checked forward-test, not a back-test. The /scorecard freezes the top-10 daily picks at close and back-checks each against SPY the next session. Five months in. Misses stay on the page. Discussion of why publishing the wins-and-misses log changes the incentives versus a quarterly fund factsheet.

— The retail-price conversation. Tapeline is $24.99/mo Pro, $39.99/mo Premium. The competitive set is $500-$5,000/yr scoring tools that don't publish their methodology. Why "evidence-based" software at retail price points is a structurally different conversation than evidence-based portfolio management.

— A specific worked example: take a name your audience knows, decompose the Tapeline score live, show what the 6-factor breakdown is communicating that the composite hides.

Background: built Tapeline solo over the last six months. Trading-system developer for ~10 years before this. Melbourne-based, time-zone-flexible.

tapeline.io · tapeline.io/scorecard · tapeline.io/how-it-works

Christian Piyatilaka
```

---

## What to do if a host books you

- **Lead time**: most podcasts record 4-8 weeks out from publish. Expect any signups attributable to the episode in Q3-Q4 2026, not the launch month.
- **Audio/video setup**: a basic Røde NT-USB or Shure MV7 + a quiet room is sufficient. Don't over-engineer for the first 3 episodes; the content matters more than the audio.
- **Show notes**: write a 4-bullet summary the host can paste into their show notes the day of release. Include links to /scorecard, /how-it-works, and the homepage with UTM tags: `?utm_source=podcast&utm_campaign=<show_short>`.
- **Promotion**: when the episode releases, post a clip + the show notes on X (@tapeline_io). Tag the host. The host will retweet 70%+ of the time, which carries.

## What to do if a host doesn't reply

One follow-up after 14 days. Subject: `Following up: Tapeline episode pitch`. Keep it 2 sentences:

```
Hi [Host] — circling back on the pitch from 14 days ago. Happy to send a 30-second voice memo intro if that helps you decide whether the topic angle fits. Otherwise I'll get out of your inbox.

Christian
```

If silence after that follow-up: don't pitch them again for 6 months. Move down the list.

## Tracking

After each send, append to a notes file:

```
2026-05-14 | Chat With Traders | sent via typeform | -
2026-05-21 | Top Traders Unplugged | sent to info@... | -
2026-05-28 | Flirting With Models | sent | reply 06-03: "thinking about it"
...
```

The metric that matters at 12 weeks: **bookings**. Anything > 1 confirmed booking out of 8 pitches is a strong response rate for cold-outreach to high-tier podcasts.

## UTM tags

Per podcast, before sending any URL:
```
?utm_source=podcast&utm_campaign=<show_short>
```

`<show_short>` mapping: `cwt`, `ttu`, `fwm`, `meb`, `tip`, `aspirits`, `excess`, `compounders`.
