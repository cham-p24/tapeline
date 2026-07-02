# Tapeline — 14-Day Tweet Schedule

Drafted 2026-05-13. Goal: drive trial signups by turning the public scorecard into daily, auditable content. Each tweet links to a page anyone can verify.

**Posting account**: @TapelineHQ (or founder's personal handle, posting as "Christian Piyatilaka — building Tapeline"). Pick one and stay with it for all 14 days; switching mid-cadence kills the audience-build.

**Time zones**: ET. 8:00 AM ET = US East Coast morning, pre-market open. 4:15 PM ET = 15 min after close, when the scorecard worker freezes top-10 and back-checks the previous day. Both are peak finance-Twitter hours.

**Cadence**: one tweet per US market day. Skip Saturdays, Sundays, and 2026-05-25 (Memorial Day, markets closed).

---

## Daily data refresh (one-liner)

Run this 5 min before the scheduled post to grab today's top-3 from the live scorecard.

**PowerShell** (Windows, your default):
```powershell
$d = irm "https://api.tapeline.io/api/scorecard?days=1"; $d.days.PSObject.Properties | select -First 1 -ExpandProperty Value | select -First 3 | % { "`$$($_.symbol) ($($_.score_at_flag))" }
```
Verified output today (2026-05-13): `$CBXY (82.3)` / `$XME (80.4)` / `$BELT (80.2)` — runs in < 1s against the live API.

**bash / WSL** (if you ever post from another machine):
```bash
curl -s "https://api.tapeline.io/api/scorecard?days=1" | jq -r '.days | to_entries[0].value[:3] | .[] | "$\(.symbol) (\(.score_at_flag))"'
```

Output is three lines like `$AIEQ (83.6)` ready to paste into the tweet. Verify the date matches what you expect before posting — the scorecard worker freezes at 4 PM ET, so before then this returns yesterday's freeze.

For "open" tweets that reference yesterday's freeze: same command. For sector-aggregate or hit-rate tweets, see notes inline below.

---

## The 14 tweets

Every tweet is ≤ 280 chars including the URL (Twitter counts every URL as 23 chars regardless of length). Each one is ready to paste — fill in the bracketed tickers/scores at post time.

---

### Day 1 — Thu 2026-05-14 · 4:15 PM ET · Top-3 close

```
Tapeline's top 3 scores at today's close: $[AAA] ([XX]) · $[BBB] ([XX]) · $[CCC] ([XX])

Each gets back-checked vs SPY at tomorrow's close. Wins and losses both stay on the page, no quiet edits.

https://tapeline.io/scorecard
```

**Screenshot**: open https://tapeline.io/scorecard, crop the top-10 table for today's date. Attach as image — Twitter rewards image tweets with ~30% more impressions.

---

### Day 2 — Fri 2026-05-15 · 8:00 AM ET · Formula transparency

```
Every Tapeline score is the same recipe:

Trend 25%
Relative Strength 20%
Fundamentals 15%
Smart Money 15%
Macro 15%
Momentum 10%

Same weights for every ticker. If they ever change, there's a changelog entry on the page.

https://tapeline.io/how-it-works
```

**Screenshot**: the "How the score is built" section of /how-it-works showing the six-factor pie or weight table. No live data, so this tweet is publish-ready as-is.

---

### Day 3 — Mon 2026-05-18 · 8:00 AM ET · Top-3 open (Friday's freeze)

```
Open question for today: Tapeline flagged $[AAA] · $[BBB] · $[CCC] as the top 3 at Friday's close.

Did they beat SPY by 4 PM Monday? The 1-day back-check posts at today's close. No retroactive removal.

https://tapeline.io/scorecard
```

**Screenshot**: Friday's top-3 row from /scorecard (the back-check column will still be blank Monday morning — that's the point, the post is asking the question).

---

### Day 4 — Tue 2026-05-19 · 4:15 PM ET · Top-3 close

```
Top 3 at today's close: $[AAA] ([XX]) · $[BBB] ([XX]) · $[CCC] ([XX])

Tomorrow's close gets the 1-day return vs SPY for each. Wins go in green, misses go in red. Everything stays on the page.

https://tapeline.io/scorecard
```

**Screenshot**: today's top-3 row with back-check column blank, plus the prior day's row showing filled-in green/red back-checks (so the reader sees what's coming).

---

### Day 5 — Wed 2026-05-20 · 8:00 AM ET · Mega-cap breakdown (NVDA)

```
NVDA on Tapeline right now: 63.4 composite, CONSTRUCTIVE.

Trend 64 · RS 46 · Fundamentals 79 · Smart Money 59 · Macro 66 · Momentum 78

RS is the drag. If it climbs back above 60, the composite goes ~70 and the label flips to STRONG SETUP.

https://tapeline.io/t/NVDA
```

**Pre-post check**: 5 min before posting, run `curl -s "https://api.tapeline.io/api/ticker/NVDA"` and confirm the breakdown numbers in the tweet still match. If they've moved >2 pts on any factor, update the tweet before posting. If the composite has crossed a label boundary (CONSTRUCTIVE → STRONG SETUP at 70), rewrite the second paragraph to fit the new label.

**Screenshot**: /t/NVDA page showing the six-factor radial chart and composite score.

---

### Day 6 — Thu 2026-05-21 · 4:15 PM ET · Top-3 close

```
Top 3 at today's close: $[AAA] · $[BBB] · $[CCC]

24h back-check vs SPY rolls in at tomorrow's close. Every miss stays on the page — the point of a scorecard is the misses, not the wins.

https://tapeline.io/scorecard
```

**Screenshot**: today's top-3 row from /scorecard.

---

### Day 7 — Fri 2026-05-22 · 8:00 AM ET · Smart-Money differentiator

```
Where Tapeline's scoring tends to disagree with a fundamentals-only screen:

Smart Money (15%) is Form 4 insider buys, not 13F lag. Same ticker can score 75 here and 60 elsewhere because someone in the C-suite just bought.

Receipts: https://tapeline.io/how-it-works
```

**Screenshot**: the Smart Money section of /how-it-works, or a /t/[symbol] page showing the Smart Money factor highlighted in the breakdown. Publish-ready, no live data needed.

---

### Day 8 — Tue 2026-05-26 · 8:00 AM ET · Top-3 open (post-holiday)

```
Tapeline's top 3 from Friday: $[AAA] · $[BBB] · $[CCC]

How do they look vs SPY coming out of the long weekend? The 1-day back-check posts at today's close.

(Holidays don't break the scorecard — the worker pauses for closed sessions and resumes on the next trading day.)

https://tapeline.io/scorecard
```

**Screenshot**: Friday's top-3 row from /scorecard. Memorial Day shows no row.

---

### Day 9 — Wed 2026-05-27 · 4:15 PM ET · Mega-cap breakdown (CRWD)

```
CRWD on Tapeline today: 79.0 composite, STRONG SETUP.

Trend 89 · RS 94 · Fundamentals 66 · Smart Money 94 · Macro 59 · Momentum 51

Smart Money 94 = Congressional buys disclosed in the last 30 days. The disclosure feed is public — anyone can verify.

https://tapeline.io/t/CRWD
```

**Pre-post check**: 5 min before posting, run `curl -s "https://api.tapeline.io/api/ticker/CRWD"` and confirm the breakdown numbers still match. If the composite has crossed a label boundary (STRONG SETUP at 70, HIGH CONVICTION at 85), rewrite the label to fit. If Smart Money drops below 80, drop the Congressional-buys hook and swap in whichever factor is highest.

**Backup ticker** if CRWD's score has materially shifted: use any STRONG SETUP from `curl -s "https://api.tapeline.io/api/scanner?limit=10&sort=score&order=desc"` — preferably one with a recognizable name (CRWD, AMGN, PANW, etc., not an obscure ETF).

---

### Day 10 — Thu 2026-05-28 · 4:15 PM ET · Top-3 close

```
Top 3 scores at today's close: $[AAA] · $[BBB] · $[CCC]

Same drill: SPY-relative return at tomorrow's close. Public page. No edits after the fact.

https://tapeline.io/scorecard
```

**Screenshot**: today's top-3 row.

---

### Day 11 — Fri 2026-05-29 · 8:00 AM ET · Top-3 open + 30-day hint

```
Yesterday's top 3 from Tapeline: $[AAA] · $[BBB] · $[CCC]

Will they hold up into Friday's close vs SPY? Watch the back-check column on /scorecard tonight.

The rolling 30-day hit rate column is the one that matters.

https://tapeline.io/scorecard
```

**Screenshot**: yesterday's top-3 with the back-check column visible (some filled, some blank from the most recent close).

---

### Day 12 — Mon 2026-06-01 · 8:00 AM ET · Two-week honesty post

```
Two weeks of Tapeline top-10 picks now on the public page.

Some beat SPY. Some lost. None got quietly removed. Every day, every ticker, every back-check.

Built that way deliberately. The honesty is the product, not the marketing.

https://tapeline.io/scorecard
```

**Screenshot**: scroll the /scorecard page from top to bottom showing the 14+ daily rows. Crop the scroll to a single tall image (use a screenshotting tool that captures full-page). This is the most visual tweet in the schedule — make it count.

---

### Day 13 — Tue 2026-06-02 · 4:15 PM ET · Hit rate, current state

```
Tapeline scorecard, current state:

[X] of [XXX] top-10 picks beat SPY in their next-day back-check ([XX]% hit rate).
Average alpha: [±X.X]% per pick.

Updates every market close. Misses stay.

https://tapeline.io/scorecard
```

**Pre-post data pull**: 5 min before posting, run
```powershell
$s = (irm "https://api.tapeline.io/api/scorecard?days=30").summary; if ($null -eq $s.hit_rate_beat_spy) { "Not enough data yet: $($s.entries_scored) entries scored — defer this tweet" } else { "scored=$($s.entries_scored), hit_rate=$([math]::Round($s.hit_rate_beat_spy))%, avg_alpha=$([math]::Round($s.avg_alpha_vs_spy,2))%" }
```
Paste the numbers into the bracketed fields. If the command says "Not enough data yet" (which it does today, 2026-05-13 — only 2 days of scorecard freezes are in and neither has a 1-day back-check yet), **swap this tweet for another mega-cap breakdown (Day 5 / Day 9 pattern)** and post the hit-rate tweet on the first day the data is real. If `hit_rate < 50%`, **post anyway** — the honesty is the whole point. The conversion lever is "we publish the misses too," not "we always win."

**Screenshot**: the summary box at the top of /scorecard showing the same numbers, so the tweet and the page agree.

---

### Day 14 — Wed 2026-06-03 · 8:00 AM ET · Try-it CTA

```
Every other stock scanner gives you 47 filters and a blank stare.

Tapeline gives you one number, one plain-English why, and a public track record you can audit before you pay.

Free tier covers top 20 tickers (24h delayed). Pro is full live for $9.99/mo. 14-day Premium trial, no card.

https://tapeline.io
```

**Screenshot**: a clean shot of the /app/scanner page showing the score + signal + reason column. Or the /pricing page comparison table. Pick one — the cleaner the image, the better the click-through.

---

## Posting rules (every tweet, all 14)

- **Real cashtags only** ($AAPL, $NVDA) — not hashtags (#stocks). FinTwit reads cashtags as signal; hashtags read as spam.
- **No emojis** in the tweet body. They cap perceived seriousness; this account is selling a methodology, not a vibe.
- **Image attached** to every tweet that ships a screenshot reference above. Twitter's algorithm boosts image tweets by ~30% in impressions.
- **No tagging** of other accounts in the tweet body unless you're directly replying to one of their tweets. Tagging in a fresh tweet looks like spam outreach.
- **Founder voice** — first person, no "we". This is one person building one product. The single-founder honesty IS the differentiator.
- **No engagement bait** — no "RT if you agree," no polls unless the poll itself is genuinely useful (e.g., "which factor should I weight more, drop one in the replies"). 

## Reply playbook (when a tweet gets traction)

Triggers any tweet posted above hits ≥ 10 likes or ≥ 1,000 impressions in the first 60 min:

1. **Reply to every comment** within 2 hours. The Twitter algorithm cares about conversation depth as much as raw engagement.
2. **Link to /scorecard in one of your first 3 replies**, not in every reply. Spamming the same URL gets the tweet de-prioritized.
3. **If someone names a ticker**: reply with that ticker's current score + one-line reason, plus the /t/[symbol] link. Run `curl -s https://api.tapeline.io/api/ticker/[SYMBOL]` to get the live numbers in 2 seconds.
4. **If someone challenges the methodology**: don't get defensive. Link to /how-it-works and say "the formula is right there, what would you change?" Treat it as user research, not an attack.
5. **If someone asks "where's the back-test"**: "Walk-forward back-test on 2024-2025 in progress. The /scorecard page is the live forward-test — that's the one that counts for trust. Day-by-day, every ticker, no cherry-picking."

## What to do if a tweet flops

Defined as < 3 likes and < 200 impressions in the first 2 hours.

- **Don't delete it**. Account history matters more than per-tweet performance.
- **Don't bump it** with replies or self-quotes.
- **Don't change the schedule** for the next tweet — finish all 14, then look at the engagement data in aggregate.
- **Do note the type** that flopped. If "top-3 close" tweets average flat but "mega-cap breakdown" tweets all hit, the next 14-day schedule should weight more breakdowns.

## What to do if a tweet pops (> 50 likes in first hour)

- **Pin the tweet**. Replace the prior pinned tweet (currently the launch thread per LAUNCH_PLAYBOOK.md item 3).
- **Reply with a follow-up tweet** within 4 hours: "Yesterday's $[AAA] back-check vs SPY: $[AAA] +X.X%, SPY +Y.Y%, alpha +Z.Z%. /scorecard has the full history." That turns one viral tweet into a thread, which Twitter's algorithm treats as continued engagement.
- **DM new followers** who follow within 1 hour of the pop with a personal note. NOT a sales pitch — "hey, saw you followed during the $[AAA] tweet, thanks. If you want the breakdown for any ticker, drop one in DMs." Founder-personal voice always.

## Measurement (lightweight, no dashboards)

After all 14 days, log the following in a simple notes file:

- Total impressions across 14 tweets
- Tweet with highest engagement (likes / retweets / replies)
- New trial signups from `?utm_source=twitter&utm_campaign=tweet_schedule_v1` (founder appends to every link before scheduling)
- Conversion rate trial → paid for the cohort that signed up via twitter UTMs

The metric that matters: **trial signups per 1,000 impressions**. Anything > 5 is excellent for B2C SaaS prosumer pricing. Anything < 1 means the tweets need rewriting or the audience is wrong.

## UTM tags

Before posting, append to every /scorecard, /how-it-works, /t/[symbol], and tapeline.io link in the schedule:

```
?utm_source=twitter&utm_campaign=tweet_schedule_v1&utm_content=day_[N]
```

Example: `https://tapeline.io/scorecard?utm_source=twitter&utm_campaign=tweet_schedule_v1&utm_content=day_1`

Vercel Analytics already captures UTMs — no extra plumbing needed.

---

## Open questions (resolve before posting Day 1)

1. **Which handle posts these?** @TapelineHQ (brand) or founder personal? Brand reads more enterprise; founder personal reads more authentic. For a single-founder pre-launch, founder personal usually wins.
2. **Are the current scorecard tickers recognizable enough?** Today's top 3 (2026-05-12) was $CBXY $XME $BELT. XME (S&P Metals & Mining ETF) is fine. CBXY and BELT are obscure. If the schedule lands on a day with three obscure names, the engagement risk is real — the reader can't anchor on the names. **Mitigation**: on those days, swap in a "mega-cap breakdown" tweet from Day 5 / Day 9 type instead of "top-3 close." The schedule has 5 ticker-specific tweets and 6 top-3 templates — plenty of swap room.
3. **Should there be a tweet about Congressional trades?** Currently no. Adding one to Day 7 or Day 14 could lift Premium-tier interest. Saved for a v2 schedule once the v1 engagement data is in.
