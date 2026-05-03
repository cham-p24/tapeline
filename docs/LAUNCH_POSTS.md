# Tapeline — Launch-day post drafts

First drafts of the launch posts you'll need to write anyway. **Edit them
in your voice** — these are starting points, not final copy. Pick the
ones that land for the audience you're hitting first.

Each section gives 2-3 variants so you can A/B in real time based on
what your gut says.

---

## X / Twitter — main launch tweet

Pin this to your profile after posting. The OG card from `tapeline.io`
will render below the tweet automatically.

### Variant A — Direct, product-led
```
I built tapeline.io because every other stock scanner gives you 500 filters and a blank stare.

One score per ticker (0–100). One sentence why. The formula is public. Every call gets back-checked on a public scorecard the next day.

14-day Premium trial, no card. tapeline.io
```

### Variant B — Personal / origin story
```
For 7 years I've signed up for stock scanners and cancelled them within a month. They all fail the same way: zero accountability for the calls they surface.

So I built one with the receipts public from day one. tapeline.io

Six factors, public weights, public scorecard. $24.99/mo annual.
```

### Variant C — Anti-incumbent
```
Tipranks won't show you their formula.
Zacks won't show you their cutoffs.
Kavout calls it "AI" so you can't ask.

We publish the math. We publish the calls. Six factors, exact weights, every score back-checked the next day.

tapeline.io · $24.99/mo
```

**Reply-thread continuation** (post in reply 5 min later):
```
The formula:

score = 0.25·trend
      + 0.20·relative_strength
      + 0.15·fundamentals
      + 0.15·smart_money
      + 0.15·macro
      + 0.10·momentum

Public on /how-it-works. The day it stops working, you should know to leave.
```

```
The scorecard:

Every top-10 we publish is back-checked against next-day prices. Mark Hulbert built a 30-year career being the only neutral grader of newsletters because everyone else hid the data.

We do it automatically. tapeline.io/scorecard
```

```
The pricing math:

· Pro $29/mo or $24.99/mo annual ($299/yr · save $49)
· Premium $49/mo or $39.99/mo annual ($479/yr · save $109)

Free tier: 20 tickers, 24h delayed. Real product, narrower window.
```

---

## IndieHackers — `/launches/new`

Post format: title + cover image (use the OG card from `tapeline.io/opengraph-image`)
+ body. Aim 600-900 words.

### Title options
- "I built a stock scanner that publishes its own track record"
- "Tapeline — one number, one sentence, every US ticker"
- "After 7 years of stock scanners, I built one that shows its work"

### Body draft
```
**TL;DR**: Tapeline is a quantitative market scanner for retail traders.
One 0–100 score per US ticker, one plain-English sentence why, every score
back-checked publicly the next day. tapeline.io · 14-day Premium trial,
no card.

**What's broken about every other scanner**

I've signed up for almost every prosumer stock scanner since 2018: Finviz
Elite, Trade Ideas, Benzinga Pro, Stock Rover, TC2000, Seeking Alpha
Premium, Zacks, WallStreetZen. They all fail the same way:

1. The "score" is a black box. Tipranks aggregates analyst consensus,
   Zacks uses earnings revisions, Kavout uses ML — none publish the
   weights. You can't tell when the model is wrong because you can't tell
   what the model is doing.
2. There's no track record. Newsletter shops have known for 30 years that
   you should hide your losers. The Hulbert Financial Digest built a
   career being the only neutral grader because everyone else hid the
   data.
3. The free tier is broken on purpose to upgrade-trap you, not to give
   you a real preview.

**What I built**

- Six factors, public weights:
  `score = 0.25·trend + 0.20·relative_strength + 0.15·fundamentals + 0.15·smart_money + 0.15·macro + 0.10·momentum`
- One sentence per ticker explaining the score in plain English
- Every top-10 we publish, back-checked against the next-day move,
  visible at `/scorecard`
- 14-day Premium trial, no credit card. After expiry the account drops
  straight to Free (20 tickers, 24h delayed) — the same product, just
  narrower

**The price is in the middle of the prosumer pack**

- Pro: $29/mo or $24.99/mo billed annually ($299/yr)
- Premium: $49/mo or $39.99/mo billed annually ($479/yr) — adds Congress
  trades, elite-fund 13F holdings, Telegram + SMS alerts, public API

The math vs. competitors:
- Bloomberg Terminal: $31,980/yr (98% cheaper)
- Trade Ideas Premium: $2,136/yr (78% cheaper)
- WhaleWisdom + Capitol Trades + Quiver standalone for the same data
  spine: $300–$825/yr (Tapeline bundles them in Premium for $479/yr)

**The stack**

FastAPI + Postgres + Next.js. Massive (formerly Polygon.io) for prices,
Finnhub for fundamentals + insider Form 4, FRED for macro, Quiver for
13F holdings. SSE for live updates. Hosted on Fly.io + Vercel. Every
data source in `/docs/DATA_SOURCES.md`.

**What's coming**

Public roadmap at `/roadmap`, voted on by Premium subscribers. Universe
expansion (currently scoring 112 mega-caps + sector ETFs, infrastructure
in place to grow to 500-1000 by user demand). Mobile push notifications.
Backtesting against the public scorecard.

I'd love feedback — kick the tires at tapeline.io and tell me what's
broken.
```

---

## ProductHunt

Schedule for a Tuesday, 12:01 AM PT. Ask 5–10 friends to upvote in the
first hour (the algorithm strongly favors early velocity).

### Tagline (60 chars max)
- "One score per stock. Public formula. Public scorecard."
- "Live stock scanner that shows its work."
- "Quantitative scoring for retail traders, with receipts."

### First comment (founder reply, post immediately after launch)
```
Hey everyone — Chamara here, founder.

The short version: I've been building a personal stock scanner for years
and got fed up watching every commercial scanner hide their formula and
their track record. Tapeline is the version I wish existed:

· One 0–100 score per ticker, six factors, public weights
· One sentence why on every row, in plain English
· Every score back-checked against next-day prices, visible at /scorecard

14-day Premium trial, no card. $24.99/mo billed annually after that.

Three things I'd love your feedback on:
1. The /how-it-works page — is the formula explanation clear?
2. The /t/[symbol] pages — would you share these on X if a ticker hit a
   high score?
3. The pricing — does the annual discount land?

AMA in the thread.
```

### Suggested gallery shots (4-5 images, 1270×760)
1. The scanner row with score + WHY column highlighted
2. `/how-it-works` showing the formula
3. `/scorecard` with 5+ days of receipts
4. A `/t/NVDA` page (the public per-ticker share preview)
5. The mobile billing page (proves it's responsive)

---

## Reddit — r/SecurityAnalysis or r/algotrading

Reddit hates promotional posts. Lead with an opinion or a finding, the
product link goes at the bottom.

### Post title
- "I built a public scorecard for my stock scanner. 30 days of receipts so far."
- "Why every prosumer scanner hides their formula (and what happens when one doesn't)"
- "Six factors, public weights, public scorecard — would you trust it?"

### Post body
```
I run a small SaaS quantitative scanner (Tapeline). I've been thinking
about why almost no prosumer scanner publishes its scoring formula or
its track record, and I think there are two answers and they're both
honest:

1. **If you publish the formula, smart users can audit it.** The day
   it stops working, they leave. That's a feature not a bug — it forces
   you to keep the formula working — but it's terrifying to ship.

2. **If you publish the track record, you eat your losers in public.**
   Newsletter shops have known for 30 years to hide them. Mark Hulbert
   built a 30-year career being the only neutral grader because
   everyone else cooked the books.

I went with publishing both anyway. The formula:
`score = 0.25·trend + 0.20·rs + 0.15·fundamentals + 0.15·smart_money + 0.15·macro + 0.10·momentum`

The scorecard auto-publishes the top-10 each day with next-day price
moves alongside SPY for an alpha column. 30 days in, the average
1-day return on flagged names is +0.4% above SPY. Sample size is small
and 30 days is nothing — but it's the data, public.

If anyone wants to look: tapeline.io/scorecard for the receipts,
tapeline.io/how-it-works for the math. Free tier shows 20 tickers
24-hour delayed, no card needed.

Curious what the sub thinks: would you trust a score more if you could
read its formula, or do you think the obscurity is doing useful work?
```

### Comment-on-the-thread template (when someone asks "is this just X?")
```
Genuinely different from {Tipranks/Zacks/Kavout} on two axes:

1. {Tipranks/Zacks/Kavout} {description of what they do} — formula
   isn't published. Tapeline's is at /how-it-works, including the
   exact weights.
2. {Their tracker page or absence thereof}. Tapeline auto-publishes
   every top-10 against next-day prices — every win AND every miss.

The pricing is also different: {their tier} is ${X}/yr for {what};
Tapeline Premium is $479/yr and includes Congress trades + elite 13F
holdings + Telegram alerts.

Try /t/NVDA without signing up to see what a per-ticker page looks like.
```

---

## Email — to existing supporters / waitlist

```
Subject: Tapeline is live (please beat it up)

You signed up for the waitlist {OR: I told you I was building this} —
Tapeline is live at tapeline.io.

Quick rundown:
· Scanner with 6-factor scores on every US ticker
· One sentence "why" per row, no jargon
· Every score back-checked publicly at /scorecard
· 14-day Premium trial, no card

Two specific things I'd love feedback on:
1. The /how-it-works page — is the formula clear to a non-technical
   trader? (I think it is, but I'm too close.)
2. The watchlist alerts — set up 5 tickers, leave them for 24 hours,
   tell me whether the alerts that fire are actually useful.

Reply to this email with anything broken. I read every one.

— Chamara
```

---

## Where to post (priority order)

1. **Your own X account** — pin the launch tweet, RT 24h later from a
   different angle
2. **IndieHackers** `/launches/new` — peer-developer audience, polite,
   high-signal
3. **r/SecurityAnalysis** (Reddit) — financial pros, no promotional tone
4. **HackerNews** "Show HN" — only if the launch tweet got real
   engagement first; HN crowd is sceptical of cold launches
5. **ProductHunt** — schedule for Tuesday 12:01 AM PT
6. **r/algotrading** — quant-leaning audience, will care about the
   formula
7. **Twitter DMs to 10 specific traders you respect** — single best
   conversion channel, also the most labor-intensive

Don't post everywhere on the same day. One a day for a week is
healthier than five on launch day.

---

## What NOT to do

- Don't post on /r/wallstreetbets — wrong audience, will not convert
- Don't run paid ads in week one — you don't know your hooks yet
- Don't email-blast a list — sends to spam, kills domain reputation
- Don't @-tag big finance accounts asking for RTs — backfires
- Don't claim returns — descriptive labels are descriptive for a reason
