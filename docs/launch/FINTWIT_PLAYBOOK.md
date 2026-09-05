# Fintwit playbook — 30 days, copy-paste ready

> **CARD GATE — 2026-08-22. Check every claim below against `docs/PRICING.md` before posting.**
>
> From 2026-08-22 a **new account must put a card on file at first sign-in**
> before it can use the logged-in product (Stripe Checkout, $0 charged that day,
> 30-day Premium trial, first charge on day 30, one click to cancel before then).
> Accounts created **before** that date are grandfathered: they keep the free
> access they signed up for and are never asked for a card.
>
> So: **no line in this file may say an account is free, that there is a free
> tier a new user can sign up for, or that signing up needs no card.** What is
> still true and should be said instead — the **published record is free with no
> account at all**: the daily Top 10, the complete scorecard, a page per scored
> ticker, and the raw CSV/JSON export.
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
> The Tapeline Score is one number per ticker, 0-100, from six named
> factors: trend, relative strength, fundamentals, smart money, macro,
> momentum. Weighted most toward trend and relative strength, least
> toward momentum. Sub-scores visible per ticker.

> **7.**
> Why six factors and not 60?
> 60-factor models look impressive in a deck. They overfit on the back-test
> and degrade silently in live trading.
> Six named factors with a published ordering and a public per-pick
> record you can verify > 60 factors weighted by "proprietary."

> **8.**
> The Smart Money factor in Tapeline reads live SEC Form 4 insider activity —
> disclosed trades, netted over a recent window. Congressional trades are
> published as their own Premium feed, not folded into that factor.
> Not "guru picks." Not whisper numbers.
> Actual disclosed trades by people whose disclosures are legally required.

> **9.**
> Tapeline's Macro factor reads a single market-wide regime classification —
> rising, sideways or falling — so the backdrop sits inside the score instead
> of being left to the reader. It's the same reading for every ticker on a tick.
> A scanner that ignores macro ranks a growth name identically in any rate cycle.

> **10.**
> Three things I will never do with Tapeline:
> 1. Edit historical scorecard entries
> 2. Hide picks that didn't work
> 3. Change the factor weighting without a public changelog
> If any of those happen, the moat is gone.

### Anti-marketing tweets — work because everyone else is salesy

> **11.**
> Tapeline isn't going to make you a better trader if you're already
> not one. It's faster ranking + a public record of when the ranking was
> right or wrong.
> If you're losing money buying based on hunches, a scanner doesn't fix
> that. Process does.

> **12.**
> The Tapeline Free tier shows the top 10 rows, live, plus 12 ticker
> look-ups a day and the full scorecard. That's the entire free product.
> No "free for 30 days then $99/mo." The published record has no clock and
> no card — no account needed at all. An account puts a card on file and
> starts the 30-day Premium trial: $0 that day, one click cancels.

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
> Pricing test: Tapeline Pro is $8.25/mo annual ($99/yr).
> Premium is $16.58/mo annual ($199/yr) and includes the full
> live universe + Congressional trades + insider Form 4.
> Both have a 30-day Premium trial. It takes a card — $0 charged
> today, first charge on day 30, one click to cancel.
> tapeline.io/pricing

---

## Part 2 — 3 weekly threads (use one per week)

### Thread A — "Six factors, in the open"

(Six-tweet thread explaining the methodology. Designed to anchor Tapeline as
the transparent option in a category where most products name nothing at all.)

> **1/** Every stock scanner has a ranking system. Almost none will even
> tell you what goes into it. Here's Tapeline's six-factor model in six
> tweets.
>
> Six factors, published ordering — heaviest Trend, then Relative
> Strength, then Fundamentals / Smart Money / Macro, lightest Momentum.

> **2/** Trend — the heaviest factor, because nothing matters
> if the ticker is in a downtrend. We read the ticker's multi-month price
> change and where the latest price sits inside its own 52-week range.
> Both describe price that has already happened. It's a description, not
> a forecast.

> **3/** Relative Strength — how the ticker has performed against a
> broad-market benchmark over three horizons. Not sector-adjusted.
> It reads the difference regardless of direction: a ticker up 5% in a
> market down 10% reads higher than one up 2% in a market up 8%.

> **4/** Fundamentals — a small composite: reported margin, return on
> equity, EPS and revenue growth, and an earnings multiple.
> Deliberately small. A 60-metric fundamental composite over-engineers
> noise into the score.

> **5/** Smart Money — disclosed SEC Form 4 insider transactions, netted
> by direction and size over a recent window. Officers and directors filing
> on their own stock, because the law makes them. Congressional trades are
> published in Tapeline as their own Premium feed, not folded into this factor.

> **6/** Macro — a single market-wide regime classification, the same
> reading for every ticker on a tick.
> Momentum — a momentum-quality reading plus a short-horizon return,
> the lightest factor because it's the noisiest.
>
> Full methodology here: tapeline.io/how-it-works

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

> **3/** Mistake two: I launched with a no-card trial. Sounds
> founder-friendly, but at low traffic volume it just means trial users
> vanish silently at day 14. Fixed in August — a card goes on file at
> first sign-in, $0 charged that day, auto-cancel-anytime in one click.
> Conversion data is finally readable.

> **4/** Mistake three: not picking a single SEO long-tail to dominate
> in month one. I tried to rank for "stock scanner" (impossible) when I
> could have owned "Tapeline alternative to Finviz" in a week. Pick the
> niche that's two layers deep before the big one.

> **5/** Mistake four: building three alert channels (email, browser push,
> Telegram) before launch. Should have built one. I've since retired the
> Telegram one — the optionality compounds support burden and the marginal
> extra-channel converter doesn't exist at < 1,000 users.

> **6/** Mistake five: announcing too late. I'm only writing this thread
> now, after the conversion machine is built. The honest order would be:
> announce, watch the funnel break, fix what's actually broken, announce
> again. Iterating in public > polishing in private.
>
> Anything you'd do differently in your build? Reply, I'm reading.

### Thread C — "Why the factor set is public but the exact recipe isn't" (positioning thread)

> **1/** The whole Tapeline Score is six named factors: trend, relative
> strength, fundamentals, smart money, macro, momentum — weighted most
> toward trend and relative strength, least toward momentum.
> Half of fintwit thinks naming them sabotages my own moat. Here's why
> it doesn't.

> **2/** The factor set isn't the moat. The execution is. Any of you can
> rebuild something like this in a spreadsheet. Almost none of you will.
> The ones who do will discover the data acquisition, the scoring
> throughput and the back-check infrastructure is 80% of the work.

> **3/** A black box breeds superstition. A "BUY signal" with nothing
> named behind it is a coin flip you're trusting because someone in a
> hoodie says trust them. Tapeline isn't that.
>
> A 0-100 score with a public, unedited record attached is auditable.
> Auditable beats magical every time once you've been burned.

> **4/** The biggest competitor in this space is the "Smart Score" from
> a $250M-valued fintech. They publish a number and won't tell you what's
> in it. They have eight digit revenue. So why share anything?
>
> Different bet. They monetised opacity. I'm betting trust compounds
> faster long-term.

> **5/** If you find a flaw in the methodology, tell me and I'll fix it. If
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
> useful. The full record is free to read with no account at all — link in bio.

### Quant-curious / engineer persona

> Saw your thread on factor models. Built Tapeline — six-factor composite
> score, all six factors named and ranked, every daily top-10 logged with
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
