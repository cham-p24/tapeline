# X threads #2-12 — drafts ready to post

> ## ⛔ HOLD — PENDING LEGAL. DO NOT POST FROM THIS FILE.
>
> Flagged 2026-09-05. This file contains a **first-person legal conclusion about
> the author's own licensing status** — see the line beginning "The Australian
> publisher exemption". Four live site pages assert the same exemption, but they
> assert it about *Tapeline*; these drafts assert it as *"I can publish ...
> without holding a financial services licence"*, in the founder's own voice.
>
> Two things make that worse than the site strings:
> 1. `docs/LEGAL_CHECKLIST.md` §2, the only written reasoning behind the claim,
>    argues entirely from **US** SEC and state investment-adviser law. The claim
>    made here is **Australian**. Those are different doctrines.
> 2. *ASIC v Scholz* [2022] FCA 1542 turned on the founder-persona channel. A
>    first-person claim from a named individual is the aggravating shape, not
>    the mitigating one.
>
> The claim has been sent to Holley Nethercote (2026-09-05, thread
> `1a06d461fe5712c4`) as part of the open consult. **Do not edit or soften the
> wording** — counsel needs the exact string that was drafted. Do not post any
> part of this file until that answer arrives; the rest of the file cannot be
> cherry-picked out, because posting from it is how the flagged line escapes.


> **WHERE THE CARD SITS — updated 2026-09-05. Check every claim below against `docs/PRICING.md` before posting.**
>
> **Signing up takes an email and a password.** The account it makes lands on
> the Free plan and opens the live scanner — the top ten scored rows of any
> scan, one saved screen. **A card is what starts the 30-day Premium trial**
> (Stripe Checkout, $0 charged that day, first charge on day 30, one click to
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

## Thread #2 — Trend is the heaviest factor: what's actually in it

Target: Wed 2026-05-21, 10pm AEST = 8 AM ET.

**Tweet 1** (~250 chars):
```
Trend is Tapeline's heaviest factor.

Most quant services say "trend-following" and leave it there. We at least tell you what it's reading:

– The ticker's own multi-month price change
– Where the latest price sits inside its own 52-week range

Both describe price that has already happened.
```

**Tweet 2** (~280 chars):
```
Why Trend and not fundamentals first?

Price action is the lowest-lag signal you can compute. Every other factor — fundamentals, smart money, macro — argues for or against the trend continuing.

If the trend score is high but the others disagree, the composite stays moderate. Trend alone doesn't win.
```

**Tweet 3** (~230 chars):
```
A high Trend score with low Fundamentals is a move without much reported quality behind it.

A high Trend score with high Smart Money means insiders were net disclosed buyers over the same stretch.

The composite weighs both. Neither reading is a forecast.
```

**Tweet 4** (~250 chars):
```
What Trend specifically WON'T catch:

– The market-wide regime (that's Macro)
– What the last filing reported (that's Fundamentals)
– Disclosed insider selling into strength (that's Smart Money)
– Shorter-horizon rate of change (that's Momentum)

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

Tapeline's Smart Money factor reads Form 4 (officers/directors, 2-business-day filing deadline). It doesn't read 13F at all. Here's why.
```

**Tweet 2** (~260 chars):
```
The Smart Money factor reads one disclosed-trade stream: SEC Form 4 insider transactions.

Congressional disclosures (STOCK Act) are ingested too and published as their own Premium feed — but they are not an input to this sub-score.

Form 4 lands in days; Congressional disclosures take weeks.
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

What we score is the NET over a recent window — total disclosed buying minus total disclosed selling, by transaction value. A single filing moves it very little on its own.
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

Tapeline's free tier instead shows the real product, live — just fewer rows and a daily look-up cap.
```

**Tweet 2** (~270 chars):
```
The Free tier on Tapeline:

– Top 10 rows, live
– 12 ticker look-ups a day
– Full 6-factor breakdown and "Why" sentence on every row
– Full scorecard
– Watchlist of 5 names

Pro adds the full ~2,500-ticker universe, unlimited look-ups, email alerts, CSV export and saved scans.
```

**Tweet 3** (~250 chars):
```
The published record is free to read with no account and no card at all — if that's all you need, stay there.

If you want live scanning across the full universe, Pro is $8.25/mo billed annually. Same scoring engine, same scorecard, plus smart watchlist alerts.
```

**Tweet 4** (~270 chars):
```
The 30-day Premium trial gives the full live universe + Congressional trades + insider Form 4. It takes a card, charges $0 today, and cancels in one click.

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
Tapeline's Macro factor is a full, named factor in every score.

That seems odd to people new to the platform — "isn't macro noise?"

It's a mid-weighted term in the composite: the market-wide backdrop gets a seat at the table instead of being left to the reader.

Here's what goes in.
```

**Tweet 2** (~270 chars):
```
Input to the Macro factor:

– A single market-wide regime classification, resolved into rising, sideways or falling.

That's the whole input. Nothing about the individual ticker enters this factor — no price, no filing, no company data.
```

**Tweet 3** (~260 chars):
```
Which means: on any given tick, Macro is the SAME reading for every ticker on the board.

It lifts or lowers the whole board together and never separates one name from another.

That is a real limitation, and the methodology page says so rather than burying it.
```

**Tweet 4** (~260 chars):
```
Most retail-facing scanners don't name a macro input at all. The label reads the same in a benign tape as in a melt-down, and the marketing never mentions it.

Tapeline doesn't solve that. It just puts the backdrop inside the score, named, where you can see what it did.
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

Polygon/Massive, Finnhub, FRED, SEC EDGAR. Each one's own auth, rate limits, failure modes. Half the codebase is reconciling sources when they disagree about a ticker's last close.
```

**URL reply**:
```
The result: https://tapeline.io
```

---

## Thread #9 — The 6-factor composite: full breakdown

Target: Wed 2026-07-02, 8 AM ET.

**Tweet 1** (~250 chars):
```
Tapeline's score is built from six named factors, in fixed weight order:

Trend
Relative Strength
Fundamentals
Smart Money
Macro
Momentum

Heaviest first, lightest last. It doesn't change retroactively. Open for arguing about on the methodology page.

Why this order? Quick thread.
```

**Tweet 2** (~260 chars):
```
TREND — the ticker's multi-month price change and where the latest price sits inside its own 52-week range. Heaviest factor because price is the lowest-lag input available.

RELATIVE STRENGTH — that same price change minus a broad-market benchmark's, over three horizons. Not sector-adjusted. Filters out "everything's going up" markets.
```

**Tweet 3** (~240 chars):
```
FUNDAMENTALS — reported margin, return on equity, EPS and revenue growth, and an earnings multiple.

Why mid-weighted rather than top? Reported figures are slow-moving and 1-day-alpha-irrelevant. Worth weighting, not worth dominating.
```

**Tweet 4** (~250 chars):
```
SMART MONEY — disclosed SEC Form 4 insider transactions, netted over a recent window. Lagged by statute, weighted lower than its media airtime suggests.

MACRO — a single market-wide regime classification. The same reading for every ticker on a tick.
```

**Tweet 5** (~260 chars):
```
MOMENTUM — a momentum-quality reading plus a short-horizon return. Lightest factor on purpose.

Pure momentum factors over-fit to the recent regime. Keeping it lightest stops the noisiest input from dominating the composite.
```

**URL reply**:
```
https://tapeline.io/how-it-works
```

---

## Thread #10 — Why the methodology is public and the infrastructure isn't

Target: Wed 2026-07-09, 8 AM ET.

**Tweet 1** (~270 chars):
```
Tapeline publishes its factor set and their weight ordering on /how-it-works — the exact weights and the parameter recipe stay private. The /changelog tracks every methodology change.

A retail trader asked: "doesn't that let competitors copy it?"

Three answers:
```

**Tweet 2** (~270 chars):
```
1. Naming the factors isn't the moat.

Six named factors with a published record is the ENTRY TICKET to being credible. The actual moat is operations: data pipelines from 6 vendors, the back-check infrastructure, the scorecard accountability layer.

The idea is a weekend. The infra was 9 months.
```

**Tweet 3** (~270 chars):
```
2. The customer can't trust a black box.

Finviz, Zacks, TipRanks, Simply Wall St — all hide their scoring methodology. That's not a competitive advantage; it's a trust deficit.

If a model doesn't tell you how it works, you can't act on it. You're just gambling on the brand.
```

**Tweet 4** (~270 chars):
```
3. If the methodology is wrong, I want to know.

Naming the factors and the record invites every quant on Twitter to argue with me. Some of them will be right. The model gets better when it's audited in public.

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
– Public API — live at /api/v1 for Premium, 1,000 requests/day, docs at /developers
```

**Tweet 3** (~250 chars):
```
Deferred until 50+ paying users specifically ask:

– Apple Sign-In (needs $99/yr Apple Dev membership for me)
– Microsoft OAuth (needs M365 Developer tenant)
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
| 2026-07-09 | #10 Why publish the methodology |
| 2026-07-16 | #11 Confidence pct |
| 2026-07-23 | #12 What's next |

Thread #4 (forward-testing data) intentionally NOT on this calendar —
post that opportunistically when scorecard sample size or specific
numbers make it timely.

After thread #12, re-audit based on reader engagement, Show HN
comments, and any podcast/Reddit feedback that surfaces fresh angles
worth a #13-#20 batch.
