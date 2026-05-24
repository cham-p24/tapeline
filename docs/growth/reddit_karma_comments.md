# Reddit karma comment library

**Drafted 2026-05-23. Purpose:** unblock the r/stocks posting wall. Account currently fails the r/stocks karma threshold for new posts. Build the karma via substantive comments on existing threads — no Tapeline mentions, no link drops, no self-promo. Pure value.

**Rules:**
1. **Never mention Tapeline or tapeline.io in these comments.** Detection of self-promo via comment history is what gets accounts shadowbanned. We earn karma now, post the launch thread once we cross the threshold.
2. **Match the thread you're replying to.** Don't paste a generic ticker breakdown into a methodology thread; don't paste a methodology essay into a "what's everyone buying" thread.
3. **One comment per thread per day max.** Multiple replies on the same thread = spam-detected.
4. **Spread across subs:** r/stocks (60%), r/algotrading (25%), r/SecurityAnalysis (15%).
5. **Target:** 50 comment karma in 7-10 days. r/stocks posting wall typically lifts at ~30-50 karma + 7+ day account age.

---

## How to use this file

Pick a comment that matches a thread you've actually read. Paste, hit submit. Track which ones you've used by adding `✓ 2026-05-XX` after the heading. Don't burn the same comment on different threads (Reddit's spam filter will catch repeated copy-paste).

If a thread has a specific ticker question, prefer the **ticker-discussion comments**. If it's a methodology / "what tools do you use" thread, prefer the **methodology comments**.

---

## Methodology / "what do you use" comments

### M1 — `r/stocks` / `r/algotrading` — "what do you actually look at when picking stocks"

> The thing that finally clicked for me was treating "factor confluence" as the real signal, not any single factor. A trend score on its own is noisy. A trend score that lines up with rising relative strength AND a positive fundamentals delta is way more reliable, even though each input is mediocre alone.
>
> Practical version of this — for any ticker I'm considering, I write down whether each of these is positive: 200DMA slope, RS vs SPY (3M and 6M), revenue trend YoY, operating margin trend, and insider 90-day net buying. If 4+ of those 5 are positive in the same window, it's worth a position. If only 1-2 line up, even with a "perfect" chart, I skip. Cuts my watchlist by 80% and my win rate has been measurably better.
>
> What I'd really like is for someone to do the work of weighting these properly across regimes — same factor mix probably needs different weights in a BULL vs CAUTIOUS market — but I haven't found anyone publishing the actual numbers.

---

### M2 — `r/SecurityAnalysis` — F-score / Piotroski / quality-scoring threads

> One thing worth flagging on the Piotroski F-score: the 9 binary tests have very different predictive weight in practice, even though the textbook treats them as equal.
>
> The three cash-flow tests (CFO > 0, CFO > Net Income, CFO/Assets up) carry materially more signal than the equity-side tests in the data I've looked at. The leverage tests (long-term debt down) are especially noisy because they punish companies investing into a capex cycle, which is often exactly when you want to own them.
>
> A modified F-score that weights cash-flow inputs ~1.5x and dampens the leverage tests when revenue growth > 15% YoY backtests noticeably better, though obviously the sample I've run on is small and over-fit risk is real. The textbook 9-point version is still the right starting point if you're new to it — just don't take a perfect 9 as gospel and a 4 as automatic disqualification.

---

### M3 — `r/algotrading` — "how do you handle regime detection"

> Two things that helped me a lot here:
>
> 1. Use breadth, not VIX, as the primary regime input. VIX captures fear *intensity* but not market *participation*. % of S&P 1500 above 200DMA is the cleanest single read — when it crosses below ~50% from a higher level, almost everything stops working regardless of what VIX is doing. Above 60% and most setups continue to follow through.
>
> 2. Don't gate trades on the regime, scale them. Position size 100% in BULL, 60% in NEUTRAL, 30% in CAUTIOUS, 0-10% in BEAR. Going binary on regime (trade / don't trade) means you sit out the regime transitions, which is where the new leadership is forming.
>
> The hardest part isn't detecting the regime, it's not flipping bias on every CAUTIOUS-to-NEUTRAL whipsaw. Run the classifier on a daily close, not intraday — saves you from chasing your tail.

---

### M4 — `r/stocks` — "smart money / insider trades / how do you use them"

> Most retail "smart money" tools either dump 13F lag in your lap (45-day stale, signal already priced in) or chase Reddit/Twitter sentiment (negative alpha most of the time).
>
> What actually works for me:
>
> - **SEC Form 4 cluster detection** — single insider buying is noise, 2+ insiders in the same 30-day window is signal. Form 4 lag is only 2 business days so the data is fresh.
> - **Congressional disclosures filtered by committee** — most of the noise is from members holding passive index funds. Filtering for "trade in a sector related to a committee assignment" cuts the dataset by ~90% and what's left has real signal.
> - **Avoid 13F entirely for active trades** — useful for narrative ("Burry is short housing again") but not for entries. The 45-day window kills it.
>
> The free SEC EDGAR APIs cover all three. Anyone selling you "smart money flow" is repackaging public data; you can build it yourself in a weekend.

---

## Ticker-discussion comments

### T1 — generic mega-cap thread reply (NVDA / AAPL / MSFT / TSLA / META)

> The factor I'd watch on $NVDA right now isn't earnings — it's customer concentration. Last 10-Q had ~46% of revenue from four customers (the hyperscalers). Their capex commentary on the next round of earnings calls is the leading indicator. If MSFT / GOOGL / AMZN / META all guide capex flat or down, the multiple compresses fast even if NVDA themselves beat. If they all guide up, the AI cycle continues.
>
> The hard part is the data center capex is real but the timing is lumpy — H100 → H200 → Blackwell ramp means each quarter's number depends on which generation is shipping vs which is being lapped. Don't read sequential decline as a thesis break unless it's coupled with hyperscaler capex cuts.

(Adapt to whichever mega-cap the thread is about — the "customer concentration / supplier dependency / second-order signal" framework works for AAPL→TSMC, TSLA→battery cell suppliers, META→reality-labs spend, etc.)

---

### T2 — "what do you think of [smaller cap]" / "is X a buy" thread

> Honest answer is "depends on your time horizon and what's in the rest of your book."
>
> For any single-name pitch I want to see:
> 1. Why now — what changed in the last 30/60 days that makes this the entry vs. waiting 6 months
> 2. What kills the thesis — name 2-3 things that would make you sell. If you can't, you're not actually trading the name, you're holding it
> 3. What's the position size relative to your max — adding a 10% position is a very different decision from a 2% position
>
> Without those three I'd just point at the chart and the last 4 quarters of revenue/margin trend and let you draw your own conclusion. Cult-of-the-CEO buys are how people lose money.

---

### T3 — "I bought / I sold" personal-trade thread

> Genuine question — what's your stop? Not trying to be a jerk, that's just the question I wish someone had asked me on every trade I made in my first 5 years.
>
> If your answer is "I'll hold long term" that's fine but it's a different decision from "this is a 6-month trade". The mental model that helped me most was writing the exit BEFORE the entry: at what price do I add, at what price do I take profits, at what price do I sit on my hands, at what price am I wrong. Three of the four are usually obvious from the chart. The "wrong" line is the hardest one and the most important.

---

### T4 — sector rotation / "what's working / what's not" thread

> The thing about sector rotation that took me embarrassingly long to internalise: leadership changes are slow but ROTATION between two specific sectors is usually fast. So you can wait until you actually see Tech → Industrials handoff in the price action (Industrials' 5-day RS vs SPY crosses positive while Tech crosses negative) instead of trying to time it from macro narrative.
>
> Top 3 sectors by 5-day relative strength is the simplest leadership indicator. If those three are Tech / Discretionary / Industrials you're in a risk-on regime; if they're Staples / Utilities / Health Care you're in risk-off. Watch for shifts in that top 3 — they usually precede the headline news by 1-3 weeks.

---

## Question / curiosity comments (lowest effort, lowest karma per post, but volume-friendly)

### Q1 — any methodology thread

> Curious how you weight the Smart Money factor relative to the price factors — do you cap its influence so a single insider buy can't dominate the score, or let it through unmediated? I've been wrestling with the same question and would love to hear how others have landed on it.

---

### Q2 — any backtest results thread

> Two questions on the methodology:
>
> 1. Walk-forward vs single-period split — which one are you running here, and if walk-forward, what's the re-train cadence?
> 2. What's your slippage assumption? Backtest results that show >1% annualised alpha disappear pretty fast at realistic slippage on small-cap names.
>
> Not trying to nit-pick, the results look interesting — just calibrating how to read them.

---

### Q3 — any "I made $X" / "I lost $X" thread

> What did the win rate look like for the trades that contributed most to the result? A few big wins covering a lot of small losses reads very differently from steady grind. Curious because it's the difference between "this is a real strategy" and "got lucky on the tail".

---

## Tracking

| Date | Sub | Comment ID | Karma after 24h | Notes |
|------|-----|------------|-----------------|-------|
|      |     |            |                 |       |

(Fill this in as you go. Once you cross 50 karma in this table, retry the r/stocks launch post from docs/launch/LAUNCH_PLAYBOOK.md §2.)

---

## Anti-pattern checklist

Don't do any of these:

- ❌ Mention Tapeline, tapeline.io, or the scorecard
- ❌ Link to anything (even non-Tapeline URLs — looks promotional)
- ❌ Cross-post the same comment to multiple threads in the same week
- ❌ Reply to the same OP twice in one thread
- ❌ Reply to threads older than 7 days (low visibility, looks like karma-farming)
- ❌ Reply within 60 seconds of another commenter — Reddit treats fast-replies as bots
- ❌ Use emoji bullet lists (Reddit comment culture is anti-emoji)
- ❌ Sign off with anything that looks like a handle ("— Christian", "Cheers!") — Reddit norms reject branded sign-offs
