# Tapeline — Podcast Pitch Drafts

> **WHAT CHANGED ON 14 SEPTEMBER 2026 — read before sending anything below.**
> The founder approved an integrity wave on 14 September 2026 that corrected the
> product and the site. Pitches below were written before it. False lines found
> on 15 and 18 September 2026 were corrected in place, but check each one against
> `docs/COPY_FACTS.md`, which has the measurements and times:
>
> - **Prices are delayed about 15 minutes.** Tapeline re-reads them for every
>   covered stock and ETF about every 60 seconds during US market hours (longer
>   around a deploy), and a score usually changes about once a day. Never call
>   the data live: not real-time, not sub-60s, not "every minute".
> - **Coverage** is about 11,500 US stocks and ETFs, plus about 100 crypto pairs
>   updated once a day. Not ~2,500.
> - **Congressional trades and squeeze detection do not exist today.** Do not
>   offer either as a feature, a Premium benefit or a score input.
> - **The record:** the day's top 10 is recorded at the close, public since May
>   2026. Entries are not re-ranked or deleted. We have corrected recorded values
>   twice, and said so: prices on 25 August 2026, and scores from 18 May to
>   12 June capped on 15 June 2026. No top 10 was recorded for 31 August,
>   2 September, 4 September or 9 September 2026. Non-subscribers see per-day
>   entries on a 7-day delay.
> - **No performance claim.** The recorded picks show no edge over SPY. Offer the
>   record as something to audit, never a hit rate or alpha as a result.

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

Pitching myself as a guest because Tapeline (tapeline.io) is the only consumer stock-scanning tool I know of that records its daily top 10 at the close and back-checks each name against SPY the next session on a public scorecard. Misses stay on the page, and corrections and the days with no list are dated. The opposite of how every retail-trader-targeted scoring tool runs.

What I'd bring to a CWT episode:

— A walkthrough of the 6-factor composite — Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum — and why they sit in the order they do: heaviest Trend and Relative Strength, lightest Momentum.

— The forward-test data since May 2026 — how often the recorded top-10 names beat SPY (so far the record trails it), where the biggest factor surprises came from, and one weight change I'd argue for (and the reason I haven't made it yet: the sample isn't long enough).

— A specific worked example: pull a ticker during the episode, decompose its score, show what the factor breakdown is saying that the composite hides.

— Tooling: how a single worker re-scores about 11,500 US stocks and ETFs about every 60 seconds on 15-minute-delayed prices, on Fly.io + Neon Postgres + Massive (formerly Polygon) data, the cost structure, where the engineering bottlenecks are.

I have built this solo, with the record public since May 2026. Background in trading-system development before this. The whole thing is a single-founder project with a public methodology and a public scorecard.

tapeline.io if you want to see what we're talking about. tapeline.io/scorecard is the receipt.

Happy to record any time and travel-flexible.

Christian Piyatilaka
```

## 2. Top Traders Unplugged

**Host**: Niels Kaastrup-Larsen.
**Audience**: ~1K Apple-podcasts reviews at 4.8/5; institutional-leaning. Trend-following + systematic / quant angle.
**Why a fit**: TTU's quant-systematic audience cares deeply about transparent methodology; Tapeline's published methodology + back-check is exactly that ethos.
**Contact**: info@toptradersunplugged.com

**Pitch** (subject: "Guest idea: a retail-facing 6-factor composite with a public forward-test"):

```
Niels — long-time TTU listener.

Pitching myself as a guest. Tapeline (tapeline.io) is a 6-factor composite stock score for the US universe, with:

— A published methodology: six named factors and their weight ordering, version-controlled, with a changelog entry and a written rationale the day anything changes. (The exact weights stay private; the ordering, the factor set and the record are all public.)

— A public scorecard that records the day's top 10 at the close and back-checks each name against SPY the next session. Misses stay on the page; corrections and days with no list are dated.

— A forward-test running since May 2026. The dataset is small but the methodology is the point — recording every miss, and dating every correction, is what most retail scoring tools refuse to do.

What I'd bring to a TTU episode:

— A walkthrough of how the composite handles the Smart Money factor: it reads disclosed SEC Form 4 insider transactions and nets them by direction and size over a recent rolling window. It does not read congressional disclosures; Tapeline has no source for them. This isn't a topic most retail tools think rigorously about; your audience does.

— The Macro factor: it reads a single market-wide regime classification, so on any given tick it is the same reading for every ticker on the board. What that does and does not add to a composite is a genuinely open question. The argument is that confluence beats single-signal, but only if the regime overlay is honest about being market-wide.

— The walk-forward back-test plan (2024-2025 sample, leave-one-out cross-validation by quarter) and why I'm running it AFTER the public live test, not before. Some discussion of why the live forward-test is more honest than any back-test could be.

Background: developed trading systems before this; built Tapeline solo, with the record public since May 2026. The whole product is one founder shipping in public.

tapeline.io · tapeline.io/scorecard · tapeline.io/how-it-works (the published methodology).

Happy to record at any time-zone-friendly slot.

Christian Piyatilaka
```

## 3. Flirting With Models

**Host**: Corey Hoffstein (Newfound Research).
**Audience**: Quant practitioners. Smaller audience but high signal — every listener is a portfolio manager or quant researcher.
**Why a fit**: Flirting with Models is the canonical quant-methodology podcast. Tapeline's methodology transparency + factor decomposition is exactly the conversation Corey runs.
**Contact**: thinknewfound.com → contact / corey [at] thinknewfound dot com.

**Pitch** (subject: "Guest idea: retail-facing factor model with versioned weights + public forward-test"):

```
Corey — Newfound podcast subscriber.

Pitching a Tapeline (tapeline.io) episode. The angle that's right for FwM: I built a 6-factor composite score for the retail universe with one design constraint that goes against every commercial scoring tool — publish the methodology, version the weights, and publish every miss.

The model — six factors, heaviest-weighted first — Trend and Relative Strength carry the most weight, Momentum the least (the exact weights stay private; the ordering does not):

— Trend: the ticker's multi-month price change, and where the latest price sits inside its own 52-week range.
— Relative Strength: the ticker's price change minus a broad-market benchmark's, over three horizons; not sector-adjusted.
— Fundamentals: reported margin, return on equity, EPS and revenue growth, and an earnings multiple.
— Smart Money: disclosed SEC Form 4 insider transactions, netted over a recent window. Not 13F and not congressional disclosures.
— Macro: a single market-wide regime classification; the same reading for every ticker on a tick.
— Momentum: a momentum-quality reading plus a short-horizon return, deliberately the lightest factor.

Questions that might make for a good episode arc:

1. **Should factor weights be versioned in public?** Tapeline's weights are version-controlled; the factor set and their ordering are published, the numbers aren't. The argument for: any change requires written rationale and the audience can audit. The argument against: it exposes overfitting moments before they're production-ready. I'd come down on the "publish" side but I want to hear the counter-argument from someone who's run live models longer than me.

2. **What's the right Bayesian prior on weight changes?** I'm currently planning to require 60 days minimum of live data before adjusting any weight by more than 2 percentage points. That's arbitrary — would value a discussion of how to actually calibrate this.

3. **Does the Macro factor add alpha or is it noise inside the regime distribution?** The data since May 2026 is too small to tell. My instinct is that it works as a confluence multiplier but is noisy in isolation; the per-factor decomposition can't settle that yet.

Background: trading-system engineering before this. Tapeline is a solo founder project, shipped publicly since May 2026. /scorecard is the back-check; /how-it-works is the math.

Happy to record any time.

Christian Piyatilaka
```

## 4. The Meb Faber Show

**Host**: Meb Faber (Cambria Investment Management).
**Audience**: ~100K weekly listeners. Mass-affluent retail; quant-aware but not deep-quant.
**Why a fit**: Meb runs systematic strategies and his audience is the exact buyer profile for Tapeline — retail traders who want signal beyond their gut. Meb's published-strategy ethos aligns with Tapeline's published-methodology ethos.
**Contact**: mebfaber.com → contact form.

**Pitch** (subject: "Guest idea: published-methodology stock scoring with a public forward-test"):

```
Meb — long-time listener; have run a couple of your tactical models in client portfolios.

Pitching myself as a guest. Tapeline (tapeline.io) is a 6-factor composite score on US stocks with a constraint your audience would actually appreciate: published methodology, versioned weights, public forward-test that records every miss.

Most retail scoring tools (Tipranks Smart Score, Zacks Rank, WallStreetZen Zen Rating) hide their methodology behind "proprietary blend" language. Tapeline's whole positioning is the opposite — the six factors and their weight ordering are on /how-it-works, the weights are version-controlled, and the daily top-10 cohort gets back-checked against SPY on a public /scorecard the next session.

Episode angle suggestions:

— **"The forward-test since May 2026 on a 6-factor model — what worked, what didn't, what I'd change."** The record so far trails SPY; factor-level decomposition, and why I'm not adjusting weights on a sample this small.

— **"Why publish the methodology?"** Your published-tactical-strategies argument applied to retail-facing scoring tools. Same logic, different audience. The moat isn't the factor list; the moat is the data spine and the accountability layer.

— **"How a solo founder ships a quant tool in 2026."** Stack: FastAPI + Neon Postgres + Fly.io + Vercel + Massive (Polygon) data, ~$200/mo all-in to score about 11,500 stocks and ETFs through the trading day. Engineering bottlenecks, where I'm Stuck, what I'd build next.

Background: trading-system developer before this. Solo project, public since May 2026. /scorecard is up; /how-it-works has the methodology; /pricing is the business model.

Happy to record.

Christian Piyatilaka
```

## 5. We Study Billionaires (Investor's Podcast Network)

**Host**: Trey Lockerbie + rotating guests (Stig Brodersen, Clay Finck).
**Audience**: ~300K weekly listeners. Long-horizon value-investor leaning.
**Why a fit**: TIP's audience reads 10-Ks and 13F filings; Tapeline's Smart Money factor (disclosed SEC Form 4 insider transactions) speaks directly to that workflow.
**Contact**: theinvestorspodcast.com → contact form.

**Pitch** (subject: "Guest idea: the Smart Money factor inside a 6-factor composite — why it reads Form 4 and not 13F"):

```
Trey / Stig / Clay — long-time listener (We Study Billionaires + Millennial Investing).

Pitching a TIP episode. Tapeline (tapeline.io) is a 6-factor composite stock score; the angle I think your audience cares about most is the Smart Money factor.

Most retail scoring tools hide where the smart-money signal comes from. Tapeline names it on /how-it-works: the Smart Money factor reads disclosed SEC Form 4 insider transactions and nets them by direction and size over a recent rolling window. It does not read congressional disclosures: Tapeline has no source for them.

The bit worth an episode is the statutory lag. Form 4 is due within a couple of business days of the transaction; a 13F is a quarterly snapshot filed up to 45 days after the quarter ends. Same phrase, "smart money", two very different vintages of information — and the filing records that a transaction happened, never why. Sales scheduled months ahead under a 10b5-1 plan, option exercises and tax-withholding sales all arrive as Form 4s and get netted like anything else.

Possible episode arcs:

— **"Why disclosed insider filings are a fresher input than 13F for retail traders."** The lag analysis is non-obvious; most retail tools just say "13F holdings" and don't address that the position was opened 30-90 days ago.

— **"What disclosed insider buying actually looks like."** We could walk through recent Form 4 filings and what the six-factor breakdown on each of those names says alongside them.

— **"The Berkshire AAPL question."** When a famous manager buys a stock everyone watches, the position is already crowded by the time the quarterly filing publishes. That lag is exactly why Tapeline scores Form 4 and doesn't score 13F at all. Stig's audience would appreciate the argument about survivorship in the source data.

Background: solo founder, trading-system development before this. Tapeline has been public since May 2026. /scorecard back-checks every logged call.

Happy to record.

Christian Piyatilaka
```

## 6. Animal Spirits (Ritholtz Wealth)

**Host**: Michael Batnick + Ben Carlson.
**Audience**: ~200K weekly listeners. Generalist wealth-advisor leaning, but with a strong methodology-curious bent.
**Why a fit**: Animal Spirits covers tools, methodology critiques, and the gap between "what retail traders think they should do" vs "what the data says." Tapeline's positioning fits.
**Contact**: animalspiritspod.com → animalspirits [at] ritholtzwealth dot com.

**Pitch** (subject: "Guest idea: a stock scanner with a public scorecard — what the misses look like since May 2026"):

```
Michael + Ben — long-time Animal Spirits listener; have referenced your "things I'm reading" segments in my own daily routine.

Pitching a Tapeline (tapeline.io) episode. The hook for the show: I built a retail stock-scanning tool with one mandate that everyone in the category refuses to do — publish every miss.

The /scorecard page records the daily top 10 and its next-day return vs SPY; four days (31 August, 2, 4 and 9 September 2026) have no list. Wins are recorded, misses are recorded; entries are not re-ranked or deleted, and the two corrections to recorded values are dated. Since May 2026 the record trails SPY. The misses are visible. The model gets things wrong on a real percentage of calls. That's the whole point of publishing.

Animal Spirits often covers "this tool says X" without auditing what the tool's track record actually is. I think your listeners would benefit from one episode that walks through:

— What a public scorecard actually looks like (and why almost no commercial tool publishes one).

— The data since May 2026: hit rate and average return vs SPY per pick (the record trails SPY), distribution of factor-level outcomes.

— Where the model is weakest by construction, which I can talk about without needing a big sample to justify it: Macro is a single market-wide reading applied identically to every ticker, Fundamentals is five reported numbers on bands that ignore sector, and Momentum's short-horizon input is an approximation rather than a measurement.

— Why methodology transparency matters more than methodology sophistication. Most retail scoring tools are similar inside; the meaningful differentiator is whether the scorecard exists.

Tapeline is a solo-founder project. Trading-system development background. Record public since May 2026. /scorecard / /how-it-works / /pricing.

Happy to record.

Christian Piyatilaka
```

## 7. Excess Returns

**Hosts**: Justin Carbonneau + Matt Zeigler.
**Audience**: Quant practitioners + sophisticated retail. Smaller (~5-10K per episode) but every listener is a methodology-buyer.
**Why a fit**: Excess Returns is explicitly about quant model design + walk-forward testing. Tapeline's published-methodology + forward-test format is exactly their show.
**Contact**: excessreturnspod.com → contact form.

**Pitch** (subject: "Guest idea: walk-forward forward-testing a 6-factor model in public"):

```
Justin / Matt — Excess Returns listener.

Pitching a Tapeline (tapeline.io) episode. The hook is the inverse of most quant podcast guests: I'm walking a 6-factor model forward in public, with the next-day back-check on a public page, instead of running a 10-year back-test and reporting the Sharpe.

Episode arc that I think works for your audience:

— **Walk-forward vs back-test: why I started with forward-test.** A back-test on 6 factors with versioned weights is trivially over-fittable. The forward-test commits the weights before any data is in. Cost: small sample, slow signal. Value: no overfit, no survivor bias, no "we removed the underperforming factor mid-test."

— **Factor decomposition since May 2026: does any factor earn its weight?** The sample is too small to say, and the record trails SPY overall. The question is how to read a small sample without overfitting.

— **The Bayesian prior on weight change.** My current rule is no weight change > 2 percentage points without 60 days of supporting data. That's arbitrary; would value a discussion of how Newfound, Two Sigma, etc. actually calibrate model-update cadence.

— **The Stripe-pricing-vs-Sharpe trade-off.** Most quant tools target the institutional buyer (retainer + outcome share). Tapeline is $9.99/mo retail. The conversation: how does a retail-priced quant tool sustain methodology rigor when the unit economics don't support a research team?

Background: solo founder. Trading-system development before this. tapeline.io / tapeline.io/scorecard / tapeline.io/how-it-works.

Happy to record.

Christian Piyatilaka
```

## 8. The Compounders Podcast

**Host**: Ben Claremon (Cove Street Capital).
**Audience**: ~2-5K per episode. Concentrated long-only value investors. Small but the right buyer profile for Premium-tier Tapeline.
**Why a fit**: Compounders' guest format is methodology-deep; Ben asks about how the guest actually decides what to own. Tapeline IS a decision framework. Tightest signal-to-audience match in the list.
**Contact**: covestreetcapital.com → ben [at] covestreetcapital dot com.

**Pitch** (subject: "Guest idea: a published-methodology scoring tool — what it scores for compounders vs the broader market"):

```
Ben — long-time Compounders listener.

Pitching a Tapeline (tapeline.io) episode. The hook is your audience-specific: compounder investors typically distrust scoring tools because the tools' formulas are short-horizon. Tapeline's 6-factor composite carries a mid-weighted Fundamentals factor, but Trend is the heaviest and dominates outputs in any 1-day-to-3-week timeframe. That's the tension.

What I'd bring to a Compounders episode:

— **The Trend-vs-Fundamentals tension for compounders.** Tapeline scores names like CMG, COST, KO that are obvious compounders, but the composite weights short-horizon factors more heavily. Your audience would want to know: should the composite carve out a "compounder mode" that puts Fundamentals ahead of Trend? My instinct is no — the composite is universal — but the discussion is interesting.

— **The Smart Money factor and filing lag for long-horizon holders.** Form 4 is due within a couple of business days of the transaction; a 13F is a quarterly snapshot filed up to 45 days after the quarter ends, slow enough that Tapeline doesn't score it at all. For compounders, though, a slow signal still confirms what the long-term holder was already thinking. How much should a score value confirmation vs freshness?

— **A specific worked example on a Compounders-coverage name** ($CMG, $COST, your pick). Pull the current 6-factor breakdown, decompose what the composite is saying, debate whether the weighting is appropriate for the compounder-investor lens.

— **Why I publish the methodology and not just the score.** The Compounders listener-base is the most likely audience to argue with the six factors and their ordering, which is exactly what naming them enables. Every methodology revision goes in the public /changelog, so a re-weighting is a change on the record rather than a silent one.

Background: solo founder, record public since May 2026. Trading-system development before this. /scorecard for the record.

Happy to record.

Christian Piyatilaka
```

---

## 9. The Rational Reminder

**Hosts**: Benjamin Felix, Cameron Passmore, Dan Bortolotti (PWL Capital, Canada).
**Audience**: factor-investing-curious retail + RIA advisors. Strongly evidence-based, academic-literature-aligned. Heavy Canadian/US overlap.
**Why a fit**: every Rational Reminder episode is structured around methodology transparency and replicable evidence. Tapeline's published-methodology + version-controlled-weights + public-scorecard is the consumer-software application of exactly that ethos. Same incentive structure, different surface area.
**Contact**: info@rationalreminder.ca (also listed for transcript corrections — primary inbox per their podcast page).
**Status**: Gmail draft queued 2026-05-15 from `christian@tapeline.io`. Awaiting founder review + Send.

**Pitch** (subject: "Guest idea: a published-methodology factor scoring tool for US retail"):

```
Ben, Cameron, Dan — long-time Rational Reminder listener.

Pitching myself for a guest spot. Tapeline (tapeline.io) is a 6-factor composite score for the US stock universe whose factor set and weight ordering are public, with every methodology revision logged in a public changelog and a public forward-test that logs every miss the model makes.

The angle that's right for RR:

— Factor decomposition done in retail-accessible language. The 6 factors map to academic literature your audience already knows — Asness defensive-quality, Fama-French momentum, regime-aware risk scaling — expressed as a single 0-100 number with a plain-English "why" sentence per row. The transparency of a factor product, without the factor-product framing.

— Why a forward-test is more honest than any back-test. The /scorecard records the day's top 10 at the close and back-checks each against SPY the next session. Running since May 2026; days with no list are dated. Misses stay on the page, corrections are dated. The sample is small but the methodology stays.

— A specific worked example: take a name, decompose the score, show where the composite agrees and disagrees with the underlying factor signals. The disagreements are usually more interesting than the agreements.

— The evidence-based-software conversation, retail edition. Tapeline is $9.99/mo Pro, $19.99/mo Premium — competing against $500-$5,000/yr scoring tools that don't publish their methodology. What "evidence-based" means for retail-facing software, not just for portfolio construction.

Background: built Tapeline solo, record public since May 2026. Trading-system developer for ~10 years before this. Melbourne-based, time-zone-flexible.

tapeline.io · tapeline.io/scorecard · tapeline.io/how-it-works

Christian Piyatilaka
```

## 10. The Acquirers Podcast

**Host**: Tobias Carlisle (Acquirers Funds, author of The Acquirer's Multiple + Deep Value).
**Audience**: deep-value / quant-value practitioners, methodology-curious. Smaller but high-signal — every listener has run the multiple themselves.
**Why a fit**: Acquirers Funds publishes the multiple's formula openly and audits it against the market every month. Tapeline does the consumer-software equivalent — a published six-factor methodology (the factors and their weight ordering; the exact numbers stay in-house) and a public forward-test. The conversation-fit is the transparency-of-methodology question that Tobias asks every guest.
**Contact**: tobias@acquirersfunds.com (direct, public on acquirersfunds.com). Alternative: Twitter @Greenbackd.
**Status**: Gmail draft queued 2026-05-15 from `christian@tapeline.io`. Awaiting founder review + Send.

**Pitch** (subject: "Guest idea: a 6-factor composite with an audited Smart Money factor"):

```
Tobias — Acquirer's Multiple reader since the original book in 2014; have run the multiple across the Australian small-cap universe for the last two years.

Pitching myself for an Acquirers Podcast spot. Tapeline (tapeline.io) is a 6-factor composite score for the US universe with one constraint that's deeply Acquirers-aligned: the methodology is fully published (the six factors and their weight ordering), the weights are version-controlled, and every miss is logged on a public forward-test scorecard.

The angle that's right for Acquirers:

— A breakdown of how the Smart Money factor is wired: disclosed SEC Form 4 insider transactions, netted by direction and size over a recent window. Not congressional disclosures. Smart Money is deliberately a corroborating factor, not a standalone one. Worth discussing what the published research says about the lag on statutory disclosure.

— The Fundamentals factor: reported margin, return on equity, EPS and revenue growth, and an earnings multiple — five reported numbers on fixed bands, not sector-adjusted. Why it carries less weight than a deep-value playbook would suggest, and the forward-test result that's making me reconsider.

— A specific worked example: take a deep-value name (Acquirer's Funds holding or otherwise) and decompose the Tapeline score. Where the 6-factor view agrees with the deep-value framing and where it diverges. The disagreements are usually more interesting than the agreements.

— Operating economics. One worker re-scoring about 11,500 US stocks and ETFs about every 60 seconds on Fly.io + Neon Postgres + Massive (formerly Polygon). The cost-per-paid-user math and where the operational moat actually is (transparent forward-test, not the factor list).

Background: trading-system developer for ~10 years; built Tapeline solo, record public since May 2026. Melbourne-based.

tapeline.io · tapeline.io/scorecard · tapeline.io/how-it-works

Christian Piyatilaka
```

## 11. The Long View (Morningstar)

**Hosts**: Christine Benz, Amy Arnott, Ben Johnson (Morningstar).
**Audience**: planning/retirement-leaning retail + RIAs. Methodology-first investing audience built around Morningstar's "show the framework behind every rating" ethos.
**Why a fit**: Morningstar built a research business on publishing the methodology behind every rating. Tapeline is the consumer-software version of that — published six-factor methodology (factors named, weight ordering stated), every revision logged in a public changelog, back-checked public scorecard. Same standard, different surface area.
**Contact**: TheLongView@morningstar.com (official guest-pitch inbox). Alternative direct: christine.benz@morningstar.com.
**Status**: Gmail draft queued 2026-05-15 from `christian@tapeline.io`. Awaiting founder review + Send.

**Pitch** (subject: "Guest idea: a published-methodology scoring tool with a public back-checked scorecard"):

```
Christine, Amy, Ben — long-time Long View listener.

Pitching myself for a guest spot. Tapeline (tapeline.io) is a 6-factor composite scoring tool for the US stock universe with one design constraint that's directly Morningstar-aligned: the methodology is fully published (the six factors and their weight ordering), the weights are version-controlled, and every miss is logged on a public forward-test scorecard.

The angle that's right for The Long View:

— What methodology transparency means in retail-facing investing software. Morningstar built a research business on showing the methodology behind every rating; Tapeline applies the same standard to scoring software. The 0-100 composite is decomposed into 6 factor sub-scores on every ticker page with a plain-English "why" sentence.

— A back-checked forward-test, not a back-test. The /scorecard records the day's top 10 at the close and back-checks each against SPY the next session. Public since May 2026; days with no list are dated. Misses stay on the page. Discussion of why publishing the wins-and-misses log changes the incentives versus a quarterly fund factsheet.

— The retail-price conversation. Tapeline is $9.99/mo Pro, $19.99/mo Premium. The competitive set is $500-$5,000/yr scoring tools that don't publish their methodology. Why "evidence-based" software at retail price points is a structurally different conversation than evidence-based portfolio management.

— A specific worked example: take a name your audience knows, decompose the Tapeline score, show what the 6-factor breakdown is communicating that the composite hides.

Background: built Tapeline solo, record public since May 2026. Trading-system developer for ~10 years before this. Melbourne-based, time-zone-flexible.

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
