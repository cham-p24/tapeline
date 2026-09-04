# LinkedIn outreach — finance journalists, fintech operators, fund managers

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

Companion to `linkedin_posts_4_to_12.md` (founder-voice broadcast) and
`fintwit_outreach.md` (X public replies). This file is for **DMs to
specific named people** — slower volume, higher conversion per touch
than broadcast posts.

Posture: every DM is anchored on the public scorecard. Never lead with
"we built this." Lead with "here's a verifiable thing — would value
your read." If they're not interested they ignore the DM; if they are,
the conversation is already past the credentialing stage.

---

## Why this channel matters

Three audiences with very different conversion economics, all best
reached via LinkedIn DM:

1. **Finance journalists** — one positive write-up at a publication
   like Bloomberg / Barron's / The Verge / TechCrunch / FT Alphaville
   moves more traffic than 90 days of organic SEO. Conversion rate per
   DM is low (1-3%) but the upside per win is huge.

2. **Fintech operators** — founders + heads of product at adjacent
   tools (broker SaaS, charting tools, portfolio trackers). They
   become integration partners, podcast guests, or just public
   endorsers. The B2B network effect compounds.

3. **Fund managers / RIAs with public presence** — folks like
   @AltaFoxCapital or @AndrewRangeley on X who ALSO post on LinkedIn
   with more detail. A LinkedIn DM is less spammy than an X DM
   (closed-DMs problem) and the prose-format thesis is more credible.

---

## Outreach budget

**5 DMs per week. Hand-crafted each.**

Higher volume looks like a paste-spam campaign and gets flagged by
LinkedIn's anti-abuse heuristics. 5/wk × 4 weeks = 20 personalised
touches per month; assume 2-4 substantive replies, 1 real
relationship per month at sustained cadence.

Tracker: log each DM in this file (date / recipient / angle / response)
so we never DM the same person twice with the same opener.

---

## Cohort 1 — Finance journalists (priority 1, top of file)

### Targets

Hand-picked from publications that have run "build-in-public solo
SaaS finance founder" or "transparent stock scanner" stories in the
past 18 months. Verify each one's beat and recent bylines before
sending — the wrong-beat DM is the #1 reason these get ignored.

| Name | Publication | Beat | LinkedIn |
|---|---|---|---|
| _verify-first_ | _research before listing_ | retail-fintech, indie SaaS | search "[beat keyword]" + "journalist" on LinkedIn |

Founder action: before sending any DM in this cohort, run
`https://twitter.com/search?q="stock+scanner"+from%3A[handle]` to
confirm the journalist actually covers this space. A journalist who
last wrote about retail finance 18 months ago has likely moved beats.

### DM template — finance journalist

```
Subject: Public scorecard for a US-equity scoring SaaS — would value
         your read

Hi [first name],

I run Tapeline (tapeline.io) — a solo-built quantitative scanner
that scores every US ticker with a single 0-100 composite from a
published 6-factor methodology (the factors and their weight
ordering). The piece I'm proud of is the public
back-checked scorecard at tapeline.io/scorecard: every top-10
daily pick logged with next-day return vs SPY, append-only, every
miss still on the page.

I noticed you covered [specific recent article they wrote] — the
piece on [specific angle they took]. The angle that might be
worth your read on Tapeline: [pick one — "what happens when a
solo-built indie SaaS publishes its scorecard against the best
incumbents" / "the methodology-transparency posture vs the
'proprietary algorithm' industry standard" / "what 90 days of
forward-testing actually showed"].

Happy to send the back-check methodology details, the data-source
audit (LICENSE_AUDIT.md), and any composite breakdown for tickers
you're curious about. No press kit ask — just a heads-up that the
scorecard is the most verifiable thing in the space.

Christian
Founder, Tapeline
tapeline.io/scorecard
```

Customise the bracketed sections per recipient. If you can't fill
[specific recent article] with something specific, don't send the DM
— pick a different target.

---

## Cohort 2 — Fintech operators (priority 2)

### Targets

Founders + heads of product at adjacent retail-fintech tools.
Looking for: someone who already publishes thoughtfully, has a
~5-50k LinkedIn following, and runs a product where Tapeline could
plausibly integrate or cross-promote.

| Type | Why fit |
|---|---|
| Broker SaaS founders | They already serve retail traders; Tapeline scoring is complementary |
| Charting tool teams (TradingView competitors) | Same audience, non-overlapping product |
| Portfolio-tracker founders | Adjacent surface; could embed Tapeline scores |
| Stock newsletter operators | Cross-promotion |

### DM template — fintech operator

```
Hi [first name],

I run Tapeline (tapeline.io) — a US-equity scoring SaaS scoring every
US ticker via a public 6-factor composite. The scorecard
(tapeline.io/scorecard) is what I'd pitch you on: every top-10 pick
back-checked vs SPY, append-only, public methodology.

I noticed [their product] is building in [adjacent space]. Two angles
that might be useful:

1. Methodology comparison — if you've thought about how to score or
   rank inside [their product], the choice we made — six named factors
   ordered heaviest Trend and Relative Strength, lightest Momentum — is
   documented at /how-it-works with our reasoning. Happy to talk
   through what we'd do differently.

2. Possible cross-promotion — your users might benefit from a daily
   Tapeline read on their watchlist names, and our users might
   benefit from [whatever their product does]. Worth a short call
   to scope?

No urgency — happy to keep this as a "founder network" thread for
when something useful comes up.

Christian
Founder, Tapeline
```

Watch the framing — DON'T pitch "we should integrate." Pitch
"here's the methodology comparison; if you find it useful we can
talk about whether there's a structural fit." Operators recognise
the difference.

---

## Cohort 3 — Fund managers with public LinkedIn presence (priority 3)

### Targets

Same vibe as the fintwit playbook (PR #80) — verified-active accounts
whose investment style maps to Tapeline's factor weighting. LinkedIn is
quieter than X DMs and the prose-format thesis is more credible.

### DM template — fund manager

```
Hi [first name],

I've enjoyed your write-ups on [specific recent thesis they posted —
quote one sentence]. Wanted to share something you might find useful
to read against.

Tapeline (tapeline.io) scores every US ticker via a 6-factor composite
— published factor set and weight ordering, live free-tier scores.
Where it might be useful for your style: the Smart Money sub-score nets
disclosed SEC Form 4 transactions over a recent window — including the
scheduled and comp-driven ones, which it makes no attempt to strip out.
For the names you've written up recently, the composite read is at:

  tapeline.io/t/[SYMBOL_1]
  tapeline.io/t/[SYMBOL_2]
  tapeline.io/t/[SYMBOL_3]

(URLs are tagged with utm_source=linkedin_outreach so I can see what
worked.)

Not asking for anything — just a heads-up that the scorecard
(tapeline.io/scorecard) is back-checked against SPY every day, every
miss still on the page. Happy to send the methodology doc if you'd
find it useful for a future write-up.

Christian
```

The 3 ticker URLs are the conversion vector here. Pick names the
manager has *recently* posted about (last 30 days). Anything older
and the link doesn't read as personalised.

---

## Send / track template

Don't email these in batches. Send one, wait for reply (or 3 days),
send the next. Track in this table — append a row per DM sent.

| Date | Recipient | Cohort | Angle | Replied? | Notes |
|---|---|---|---|---|---|
| _ | _ | _ | _ | _ | _ |

---

## What to AVOID

- "I've been admiring your work" / "I'm a huge fan" — every paste-spam
  template uses this. Skip it.
- Pitching the trial up front. The scorecard is the proof — let it do
  the selling.
- Following up more than once per recipient. If they didn't bite the
  first time, the second message is just noise.
- Group-mentioning multiple recipients in one message. LinkedIn's
  anti-spam heuristics flag this.
- Sending on Sunday or after 8pm local. Tuesday-Thursday 09:00-11:00
  local time is the sweet spot.

---

## Tracking conversion

Every URL in these DMs carries `utm_source=linkedin_outreach&utm_medium=dm`
plus a per-recipient `utm_campaign=<surname>_<YYYYMMDD>`. When
visitors signed up via this channel land in the User table,
`users.signup_utm_*` columns capture the attribution. Run the
following SQL monthly against the prod DB to measure conversion:

```sql
SELECT
  signup_utm_campaign,
  COUNT(*) AS signups,
  SUM(CASE WHEN trial_ends_at IS NOT NULL THEN 1 ELSE 0 END) AS trials,
  SUM(CASE WHEN stripe_customer_id IS NOT NULL THEN 1 ELSE 0 END) AS paid
FROM users
WHERE signup_utm_source = 'linkedin_outreach'
GROUP BY signup_utm_campaign
ORDER BY signups DESC;
```

If the first 20 DMs produce zero conversions, the targets are wrong —
re-audit before continuing. If they produce 2+ trial signups and 1
paying user, the channel works; double the budget to 10/wk.
