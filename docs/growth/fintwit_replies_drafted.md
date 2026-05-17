# Fintwit public replies — drafted 2026-05-17

Round 1 of PR #80's pivot from cold DMs to substantive public replies. Drafted
against each account's most recent substantive tweet, anchored on live
Tapeline composite scores from `api.tapeline.io/api/ticker/{symbol}` (24h-delayed
feed, free-tier — same data anyone visiting `tapeline.io/t/SYMBOL` would see).

Founder reviews each draft, opens the target tweet, hits Reply, posts. Avatar
+ banner are now live on @tapeline_io so this no longer looks like a 0-asset
bot account.

---

## 1. @JohnHuber72 (49.1K followers · Saber Capital)

**Target tweet** (May 14): "Morgan Stanley says April was 'the best month for
stock picking hedge funds since December 1999.' And funds quadrupled their
allocation to semis in the last year — went from 5.5% of HF portfolios on net
last year to 20% at present, per Morgan Stanley."

**Reply draft:**

> HFs are loaded, but the tape's already softening — NVDA 52, AVGO 47, AMD 56
> on our composite. Momentum sub-scores 23 / 50 / 25 across the three; NVDA's
> read is literally "thrust fading on lighter volume." Crowd quadrupling
> allocation while leadership thins is a classic late-cycle pattern.

**Char count:** 277 · fits.

**Why this works:** John posts cycle-history threads (his SNDK/GLW 1999→phoenix
post on May 7); a "1999 vs today" parallel + concrete sub-scores lands in his
register. No promo. Reader who's curious clicks the @tapeline_io profile.

---

## 2. @HaydenCapital — Fred Liu (Hayden Capital, concentrated growth)

**Target tweet** (repost May 4): David Senra's thread about Adam Foroughi
($APP) borrowing money to buy back $6B in stock at a 92% drawdown — bet that
went on to print $60B+. Fred also did a Drew Cohen podcast Apr 25 explicitly
on $APP and $SE as concentrated bets.

**Reply draft:**

> Notable footnote: $APP scores 64 CONSTRUCTIVE on our composite today —
> momentum 100, macro 85, smart-money 80, thrust signal triggered. The buyback
> Senra describes 18 months ago is still printing on the smart-money sub-score
> now. Compounding the comeback, not just recovering from it.

**Char count:** 287 · trim 7 chars. v2:

> $APP today on our composite: 64 CONSTRUCTIVE — momentum 100, macro 85,
> smart-money 80, thrust signal triggered. The buyback Senra describes 18
> months ago is still printing on the smart-money sub-score now. Compounding
> the comeback, not just recovering from it.

**Char count:** 270 · fits.

**Why this works:** Fred's whole brand is "emerging compounders," and the
smart-money sub-score is exactly the lens he uses (insider + institutional
flow). Quoting his investment thesis back with live tape data signals we
actually read his stuff.

---

## 3. @TidefallCapital — Trevor Scott ($CSU.TO bull)

**Target tweet** (10h ago): "When a university student realized AI won't
displace all software leaders. Software is more than code. $CSU.to"

**Reply draft:**

> Same widening gap in the US software comp: MSFT 58 CONSTRUCTIVE (uptrend
> intact, RS tilting up vs sector), CRM 40 NEUTRAL ("underperforming the
> sector on every timeframe"), ORCL 44 NEUTRAL ("breakdown from prior
> support, no reclaim"). The "more than code" moat is showing up as
> structural alpha between entrenched compounders and the long tail.

**Char count:** 343 · over by 63. Trim:

> US software comp echoes this: MSFT 58 CONSTRUCTIVE (uptrend intact, RS
> tilting up), CRM 40 NEUTRAL ("underperforming sector on every timeframe"),
> ORCL 44 NEUTRAL ("breakdown from prior support, no reclaim"). "More than
> code" is printing as a widening gap between compounders and the tail.

**Char count:** 282 · trim 2 more. v3:

> US software comp echoes it: MSFT 58 CONSTRUCTIVE (uptrend intact, RS
> tilting up), CRM 40 NEUTRAL ("underperforming sector every timeframe"),
> ORCL 44 NEUTRAL ("breakdown from prior support, no reclaim"). "More than
> code" is printing as a widening gap between compounders and the tail.

**Char count:** 278 · fits.

**Why this works:** CSU.TO isn't in our US-only universe, so we don't pretend
it is. Instead, we map his "software is more than code" thesis onto US tickers
he'd recognize and where we have signal. Validates the thesis with adjacent
data.

---

## 4. @TSOH_Investing — Alex Morris

**Target tweet** (May 16): chart of YoY Room Nights Growth for Airbnb vs
Booking Holdings.

**Reply draft:**

> Same divergence in our composite: ABNB 60 CONSTRUCTIVE (momentum at 6-month
> high, RS tilting up vs peers) vs BKNG 41 NEUTRAL ("breakdown from prior
> support, no reclaim," macro sub-score 19). Operational data and the tape
> are agreeing for once — usually they argue.

**Char count:** 269 · fits.

**Why this works:** Alex publishes weekly research roundups; he treats
fundamentals + price action as the same conversation. The "agreeing for once
— usually they argue" line is a fundamental-investor in-joke that lands.

---

## 5. @alluvialcapital — SKIP

Account dormant since November 19, 2023 — went inactive over content
moderation concerns. Marked `verified-inactive` in
`docs/growth/fintwit_list.csv` (was previously untagged).

---

## Posting order + cadence

PR #80 strategy: 5–10 substantive replies per week, hand-crafted, no
templating. For this batch:

1. **@JohnHuber72** first — highest follower count (49.1K), most likely to be
   re-engaged-with, most tape-friendly thesis.
2. **@TSOH_Investing** second — Alex actively replies to comments on his
   posts; the ABNB/BKNG data point is direct and on-topic.
3. **@HaydenCapital** third — the Senra repost is 13 days old, so engagement
   window is fading; still good context but not first-priority.
4. **@TidefallCapital** fourth — CSU.TO content is harder to anchor on US-only
   data; this is the weakest fit of the four.

Space them 30–60 minutes apart. Reply window: in the next 24 hours, before
the tweets fall off the algorithm.

## Re-audit notes for `fintwit_list.csv`

- `@HaydenCapital` — verified-active (recent posts May 4 repost, Apr 25 own)
- `@TidefallCapital` — verified-active (posts within last 24h, active replies)
- `@TSOH_Investing` — verified-active (daily posts, weekly roundup cadence)
- `@JohnHuber72` — verified-active (multiple posts within last week)
- `@alluvialcapital` — **verified-inactive** since Nov 2023 (update CSV)
