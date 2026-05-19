# Fintwit playbook — 30 days, copy-paste ready

A self-contained pre-launch distribution kit for daily X / LinkedIn posting.
Every tweet is built around something Tapeline can prove — usually the public
`/scorecard` (which is the moat).

**Principles.** No one cares about your product. They care about: (a) being
right, (b) not feeling dumb, (c) edge they can copy. Every post here is one
of those three.

**Founder voice.** Tight, declarative, never salesy. Lead with the receipt,
not the claim. If a stranger reads it and learns nothing, rewrite it.

**Cadence.** 1 short post per day, 1 thread per week, 5 personalised DMs
per day. 30 days minimum before judging traction.

---

## Part 1 — 15 short tweets (use any day)

Copy-paste, fill in the bracketed scorecard data when you post.

### Receipt tweets — these are the engine

> **1.**
> Tapeline picked these 10 names at Friday's close:
> [paste top-10 with scores from /scorecard]
> Here's how they did Monday:
> [paste 1d performance + alpha vs SPY]
> Hit rate beating SPY: [X]/10.
> Same back-check every day → tapeline.io/scorecard

> **2.**
> 30-day Tapeline scorecard:
> · [X] days tracked
> · [Y]% hit rate beating SPY
> · median 1D alpha: [Z]%
> No edits, no deletions, no "AI predicts." Just the receipt.
> tapeline.io/scorecard

> **3.**
> [TICKER] was a HIGH CONVICTION call on Tapeline at [DATE].
> Score: [N]/100. Reason at the time: "[paste the score reason]."
> Next day: [+X% vs SPY's Y%].
> Receipt: tapeline.io/scorecard/[ticker]

> **4.**
> The screenshot most stock-Twitter accounts don't post:
> a calendar of every call they made, color-coded by hit/miss.
> Here's mine. [embed scorecard image]
> 26 days tracked, [X]% beat SPY. That's the bar.

> **5.**
> Most "stock scanner" products won't show you their picks from
> 14 days ago. Tapeline auto-publishes every top-10 ranking with the
> next-day return vs SPY. tapeline.io/scorecard
> Build in public or don't bother.

### Methodology tweets — earn the quant crowd

> **6.**
> The Tapeline Score is one number per ticker, 0-100. Formula:
> 0.25·trend + 0.20·rs + 0.15·fundamentals + 0.15·smart_money + 0.15·macro + 0.10·momentum
> Weights are published. Sub-scores visible per ticker.
> The whole thing fits in a tweet.

> **7.**
> Why six factors and not 60?
> 60-factor models look impressive in a deck. They overfit on the back-test
> and degrade silently in live trading.
> Six well-chosen factors with published weights you can verify >
> 60 factors weighted by "proprietary."

> **8.**
> Smart-money signal in Tapeline = Congressional trades (House + Senate
> disclosures) + live SEC Form 4 insider activity.
> Not "guru picks." Not whisper numbers.
> Actual disclosed trades by people whose disclosures are legally required.

> **9.**
> Tapeline's regime factor flips RISING / FALLING / SIDEWAYS based on the
> 10Y yield's last 30 obs from FRED.
> A 15% weight in the score reacts when macro shifts.
> A scanner that ignores macro will tell you to buy growth in a 5% rate cycle.

> **10.**
> Three things I will never do with Tapeline:
> 1. Edit historical scorecard entries
> 2. Hide picks that didn't work
> 3. Change the published weights without a public changelog
> If any of those happen, the moat is gone.

### Anti-marketing tweets — work because everyone else is salesy

> **11.**
> Tapeline isn't going to make you a better trader if you're already
> not one. It's faster ranking + a public record of when the ranking was
> right or wrong.
> If you're losing money buying based on hunches, a scanner doesn't fix
> that. Process does.

> **12.**
> The Tapeline Free tier shows the top 20 tickers with 24-hour delayed
> data. That's the entire free product.
> No "free for 7 days then $99/mo." No card required for the trial.
> No marketing pop-ups. The product is the funnel.

> **13.**
> Best feedback I've gotten this week: "Your scorecard makes me trust
> the score even when it's wrong."
> Right — that's the point. A wrong score with the reasoning intact is
> 10x more useful than a "correct" score with no audit trail.

> **14.**
> Six months in. One paying customer. Tapeline isn't profitable.
> Posting this because every "I went from 0 to $10K MRR in 30 days"
> thread you read on here is either lying or the exception.
> Real number: 80 visitors a week. Building anyway. /1

> **15.**
> Pricing test: Tapeline Pro is $24.99/mo annual ($299.99/yr).
> Premium is $39.99/mo annual ($479.99/yr) and includes the full
> live universe + Congressional trades + insider Form 4.
> Both have a 14-day Premium trial. No card.
> tapeline.io/pricing

---

## Part 2 — 3 weekly threads (use one per week)

### Thread A — "Six factors, in the open"

(Six-tweet thread explaining the formula. Designed to anchor Tapeline as
the transparent option in a category where most products hide the formula.)

> **1/** Every stock scanner has a ranking system. Almost none publish
> the formula. Here's Tapeline's six-factor model in six tweets.
>
> Weights:
> · Trend 25%
> · Relative Strength 20%
> · Fundamentals 15%
> · Smart Money 15%
> · Macro 15%
> · Momentum 10%

> **2/** Trend (25%) — the heaviest factor because nothing matters
> if the ticker is in a downtrend. We compute it from price relative
> to its own 50/200-day moving averages plus the slope of those averages.
> A ticker bleeding under its 200dma can never score high.

> **3/** Relative Strength (20%) — how the ticker has performed vs SPY
> over the last 1m / 3m / 6m windows. Rewards outperformance vs the
> market regardless of direction. A ticker up 5% in a market down 10%
> scores higher than one up 2% in a market up 8%.

> **4/** Fundamentals (15%) — five-metric composite: P/E vs sector,
> revenue growth YoY, gross margin trajectory, ROE, debt-to-equity.
> Deliberately small. A 60-metric fundamental composite over-engineers
> noise into the score.

> **5/** Smart Money (15%) — Congressional trades (House + Senate
> disclosures) + live SEC Form 4 insider activity. Officers and directors
> trading their own stock is real signal. Politicians' disclosed trades
> are less consistent but worth a factor weight.

> **6/** Macro (15%) — 10Y yield direction (FRED), VIX regime, DXY trend.
> Composite tilts the score against equities when macro turns hostile.
> Momentum (10%) — recent breakouts + volume confirmation, the lightest
> weight because it's the noisiest.
>
> Whole formula here: tapeline.io/how-it-works

### Thread B — "What I'd build differently if I started over"

(Founder-vulnerability thread. High engagement format. Make it specific
to Tapeline so it doesn't read as generic "lessons learned" content.)

> **1/** Six months building Tapeline. Five things I'd do differently.
> Posting these because there are 50 people out there about to make the
> same mistakes — and one of you is going to actually ship.

> **2/** Mistake one: building the scanner before the scorecard.
> The scanner is the product. The scorecard is the moat. I spent three
> months on the scanner before publishing a single back-check.
> Should have shipped the scorecard week one and let it accumulate.

> **3/** Mistake two: 14-day trial without a card. Sounds founder-friendly,
> but at low traffic volume it just means trial users vanish silently at
> day 14. If I'd required a card with auto-cancel-anytime, I'd have caught
> more conversion data by now.
> [if you change your mind on this later, this tweet ages]

> **4/** Mistake three: not picking a single SEO long-tail to dominate
> in month one. I tried to rank for "stock scanner" (impossible) when I
> could have owned "Tapeline alternative to Finviz" in a week. Pick the
> niche that's two layers deep before the big one.

> **5/** Mistake four: building three notification channels (email,
> browser, Telegram) before launch. Should have built one. The optionality
> compounds support burden; the marginal email-vs-Telegram converter doesn't
> exist at < 1,000 users.

> **6/** Mistake five: announcing too late. I'm only writing this thread
> now, after the conversion machine is built. The honest order would be:
> announce, watch the funnel break, fix what's actually broken, announce
> again. Iterating in public > polishing in private.
>
> Anything you'd do differently in your build? Reply, I'm reading.

### Thread C — "Why the formula is public" (positioning thread)

> **1/** The whole Tapeline Score formula fits in a tweet. Weights:
> 0.25·trend + 0.20·rs + 0.15·fundamentals + 0.15·smart_money +
> 0.15·macro + 0.10·momentum.
> Half of fintwit thinks I've sabotaged my own moat. Here's why I haven't.

> **2/** The formula isn't the moat. The execution is. Any of you can
> rebuild this in a spreadsheet. Almost none of you will. The ones who
> do will discover the data acquisition, the scoring throughput, the
> back-check infrastructure is 80% of the work — the formula is 5%.

> **3/** Hidden weights breed superstition. "BUY signal" without the
> weights is a coin flip you're trusting because someone in a hoodie
> says trust them. Tapeline isn't that.
>
> A 0-100 score with the formula attached is auditable. Auditable beats
> magical every time once you've been burned.

> **4/** The biggest competitor in this space is the "Smart Score" from
> a $250M-valued fintech. They publish a number, they don't publish the
> weights. They have eight digit revenue. So why share?
>
> Different bet. They monetised opacity. I'm betting trust compounds
> faster long-term.

> **5/** If you find a flaw in the formula, tell me and I'll fix it. If
> the fix changes the score, the scorecard's prior entries stay frozen
> with the old version noted. Methodology changes are themselves logged
> publicly. Reputational integrity > looking smart on any single update.

---

## Part 3 — DM templates (5 personas)

Each template is < 200 chars. Personalise the bracketed parts. Send 5/day
for 30 days; expect ~10% reply rate, ~10% of replies converting to signups.
That's ~15 signups over 30 days from outreach alone — at zero cost.

### Day-trader persona

> Hey [name], saw your [post about TSLA squeeze last week]. Built a
> scanner that flags exactly that kind of setup early — would love 60
> seconds of your honest take. No pitch. tapeline.io/scorecard for the
> back-checks before you click anything.

### Swing-trader persona

> [name] — I see you trade [setup type]. I built Tapeline (stock scanner
> with a public scorecard, every pick back-checked vs SPY). 30-day hit
> rate is at [X]%. Curious if you'd find the regime + smart-money factors
> useful. No card trial, link in bio.

### Quant-curious / engineer persona

> Saw your thread on factor models. Built Tapeline — six-factor composite
> score, weights published in a tweet, every daily top-10 logged with
> next-day SPY-relative move. Would love your eyes on the methodology
> page. tapeline.io/how-it-works

### Ex-prop / institutional persona

> [name], retail-side scanner with a 6-factor composite + public per-pick
> back-check vs SPY. Inspired by [equivalent institutional tool / e.g. AQR
> factor model / Bloomberg model]. Would love your take on what the
> retail version is missing.

### Newsletter / fintwit creator persona

> [name] — I read your [newsletter / thread]. I built Tapeline, the
> scanner with a public scorecard. Would you want a free Premium account
> in exchange for a candid review (positive or negative)? No edits, no
> approval needed.

---

## Part 4 — Daily cadence (the 30-day routine)

**Morning (15 min):**
- Open `/scorecard` — note yesterday's hit rate vs SPY
- Pick today's tweet from Part 1 (rotate, don't repeat in the same week)
- Post by 8am ET (US market opens at 9:30am ET; ride the pre-market
  attention spike)

**Midday (10 min):**
- Reply to 3 fintwit threads with substance (no plugs)
- Quote-tweet 1 of your own scorecard entries with a fresh observation

**Afternoon (20 min):**
- Send 5 personalised DMs from Part 3
- Maintain a spreadsheet: name, persona, sent date, replied y/n, signed
  up y/n

**Weekly (Sundays, 30 min):**
- Post one thread from Part 2
- Write next week's pinned-tweet copy
- Review which Part 1 tweet got the most engagement; lean into that
  pattern next week

---

## Part 5 — What to skip

- **Engagement pods** — fake amplification, instantly readable as such,
  destroys credibility
- **Generic "trade idea" tweets** — fintwit is saturated with these; the
  marginal contribution is zero
- **Repeat-posting the same tweet across the week** — the algorithm
  notices and downweights repeat content
- **Replying to massive accounts you haven't engaged with for 60+ days**
  — reads as opportunistic, often gets you blocked
- **Posting losses without context** — "lost on TSLA today" without the
  size, setup, and learning is just noise. Show the framework, not the
  P/L.

---

## Tracking

Spreadsheet template at `docs/launch/FINTWIT_TRACKING.csv` (create on
first day):

| date | format | tweet_link | impressions | replies | profile_clicks | signups_attrib |
| --- | --- | --- | --- | --- | --- | --- |

Attribution: tag every CTA link with `?utm_source=twitter&utm_campaign=
[tweet_id_short]&utm_medium=organic`. PostHog will then segment signups
by source. After 30 days, the data tells you which tweet templates
actually convert vs just get likes.

---

**Last reviewed:** 2026-05-19
**Next review:** after 30 days of posting cadence — compare actual
signups attributed via UTM vs. the projected 15-50 range.
