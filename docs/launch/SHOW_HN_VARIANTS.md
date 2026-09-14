> ⚠️ **SUPERSEDED (2026-07-26) — use [`FIRE_NOW.md`](FIRE_NOW.md) instead. Do not paste from this file.**
> The scorecard numbers in these variants ("first week", "35 clean entries",
> "-0.7% alpha") are stale — pull current figures from `/api/scorecard`. The
> Free-tier "top 20, 24h delay" line is also outdated (Free is the top-10 rows
> and 12 look-ups/day). `FIRE_NOW.md` has the corrected Show HN post.
>
> **Updated 2026-09-15:** false lines below (congressional trades, "live",
> "nothing gets quietly removed", a card at sign-in) were corrected in place.
> Every plan's prices are delayed about 15 minutes. Check `docs/COPY_FACTS.md`
> before posting anything.

# Show HN — alternative variants

> **WHERE THE CARD SITS — updated 2026-09-15. Check every claim below against `docs/COPY_FACTS.md` and `docs/PRICING.md` before posting.**
>
> **WHAT CHANGED ON 14 SEPTEMBER 2026 — read before posting anything below.**
> The founder approved an integrity wave on 14 September 2026 that corrected the
> product and the site. Drafts below were written before it. False lines found
> on 15 September 2026 were corrected in place, but check each one against
> `docs/COPY_FACTS.md`, which has the measurements and times:
>
> - **Prices are delayed about 15 minutes.** Tapeline re-reads them for every
>   covered stock and ETF about every 70 to 80 seconds during US market hours,
>   and a score usually changes about once a day. Do not call anything live,
>   real-time, sub-60s or "every minute".
> - **Coverage** is about 11,500 US stocks and ETFs, plus about 100 crypto pairs
>   updated once a day. Not ~2,500.
> - **Congressional trades and squeeze detection do not exist today.** Do not
>   offer either as a feature, a Premium benefit or a score input.
> - **The record:** entries are not re-ranked or deleted. We have corrected
>   recorded values twice, and said so: prices on 25 August 2026, and scores from
>   18 May to 12 June capped on 15 June 2026. No top 10 was recorded for
>   31 August, 2 September, 4 September or 9 September 2026.
> - **The pre-charge email** goes about 7 days before the first charge.
>
> **Signing up takes an email and a password.** The account it makes lands on
> the Free plan and opens the scanner — the top ten scored rows of any
> scan, one saved screen. **A card is what starts the 30-day Premium trial**
> (Stripe Checkout, $0 charged that day, first charge on day 30, one click to
> cancel before then), and the trial is what turns on every matching row rather
> than the first ten, plus alerts, CSV export and per-ticker SEC Form 4
> filings.
>
> The **published record is free with no account at all**: the daily Top 10, the
> complete scorecard, a page per scored ticker, and the raw CSV/JSON export.
>
> So: **no line in this file may attach the card to the ACCOUNT or to SIGNING
> IN.** Attach it to the TRIAL, which genuinely requires one. Three layers, in
> this order: the record needs no account; signing up takes an email and a
> password; a card starts the trial.
>
> _History: until 15 September 2026 this block was headed "CARD GATE —
> 2026-08-22" and described the card wall on new accounts, and told writers
> that no line may call an account free. That was true only while the wall
> ran (#548, 2026-08-22, to #683, 2026-08-30)._
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

`LAUNCH_PLAYBOOK.md` §1 has the primary draft (focus: public methodology +
public scorecard, 30-day trial mention). This file holds two alternate angles in
case the primary doesn't feel right on Tuesday morning. All three are
**post-as-Text-with-`https://tapeline.io`-in-URL-field** format.

Same posting rules apply (8 AM ET, weekday, ≥30-karma account, hang around
for 60 min answering every comment).

---

## Variant A — "the back-check is the product" angle

### Title (78 chars)

> **Show HN: A stock scanner that back-checks every top-10 pick against SPY**

### Text

```
I built Tapeline (https://tapeline.io) because every stock scanner I'd ever paid for had the same dishonest pattern: they show you a leaderboard of picks but never show you what happened next.

So Tapeline does the opposite. Each trading day at close, we freeze the top 10 ranked tickers. Next day at close, we record each name's actual return vs SPY and the result goes on /scorecard. Wins stay. Losses stay. Entries are not re-ranked or deleted, and the two corrections we made to recorded values are dated on the page.

The score itself is a 6-factor composite — Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum — weighted most toward Trend and Relative Strength and least toward Momentum. The factor set and ordering are on /how-it-works and don't change without a changelog entry. Every score comes with one plain-English sentence explaining what's driving it (the "Why" column).

The scorecard is the part I want HN to tear apart. It's the only thing I've ever seen in this space that's auditable from day one. Currently in its first week of forward-testing — early data on /scorecard shows median 1D alpha around -0.7% on 35 clean entries (4 vendor-data outliers excluded; the filter logic is in the public Python source). I expect those numbers to swing both directions as the sample grows. The transparency is the point, not the early hit rate.

Free tier: top-10 rows, 12 ticker look-ups a day, 5-name watchlist.
Pro $8.25/mo billed annually: every row of the scan (about 11,500 US stocks and ETFs) + alerts.
Premium $19.99/mo: + per-ticker SEC Form 4 filings.
Prices are delayed about 15 minutes.
30-day Premium trial — a card starts it, $0 charged that day, first charge on day 30, cancel in one click before then. The daily Top 10 and the full public scorecard are readable with no account.

Built solo over the last few months from Melbourne. Genuinely interested in what HN finds wrong with the methodology — and what factors I'm under-weighting.
```

### Why this variant

Leans harder into the accountability angle than the primary. Concedes weak
early back-check numbers upfront (the median alpha is honestly mediocre at
5 days), which HN respects more than "look how great we are." Self-flagellation
inoculates against the predictable "your scorecard only has 5 days" comment.

---

## Variant B — "what a Bloomberg refugee built on weekends" angle

### Title (76 chars)

> **Show HN: Tapeline – the stock scanner I wanted Bloomberg to be (public record)**

### Text

```
I've worked alongside retail traders for years and watched the same dynamic play out: they pay $30-60/month for screeners that won't tell you what's in the score and never publish a track record. Bloomberg's $24K/year terminal has the data but is built for an institutional workflow nobody under 40 actually uses.

So I built Tapeline (https://tapeline.io). One composite score per US ticker (0-100), six named factors, plain-English sentence on every row, and a public scorecard that back-checks each daily top-10 against SPY the next day. The whole product is "show your work, every step."

The methodology is on /how-it-works — six factors, listed with the heaviest-weighted first — Trend and Relative Strength carry the most weight, Momentum the least:
- Trend — the ticker's multi-month price change, and where the latest price sits inside its own 52-week range
- Relative Strength — the ticker's price change minus a broad-market benchmark's, over three horizons; not sector-adjusted
- Fundamentals — reported margin, return on equity, EPS and revenue growth, and an earnings multiple
- Smart Money — disclosed SEC Form 4 insider transactions, netted over a recent window. Not 13F
- Macro — a single market-wide regime classification; the same reading for every ticker on a tick
- Momentum — a momentum-quality reading plus a short-horizon return, deliberately the lightest factor

The scoring is version-controlled, so a change is a change on the record. /scorecard is uneditable history. /changelog logs every methodology revision.

Stack: Next.js 16 + FastAPI + Massive (formerly Polygon) + Finnhub + FRED, deployed on Fly.io. The methodology — the six factors, what each measures, and their weight ordering — is published on /how-it-works; the exact weights and the parameter recipe are not.

Free tier: top-10 rows, 12 ticker look-ups a day. Pro $8.25/mo annual. Premium $16.58/mo annual. 30-day Premium trial takes a card — $0 today, first charge on day 30, one click to cancel.

What I want HN to break: the methodology. The Smart Money sub-score in particular — it reads SEC Form 4 insider transactions and doesn't score 13F at all, because the 45-day filing lag means the position is usually already priced by the time you see it. I'd love to be argued out of that.
```

### Why this variant

Leans into the "Bloomberg too expensive, Finviz too raw" positioning. Names
the competitors explicitly (which the primary draft is more cautious about).
Invites methodology critique on a specific factor (Smart Money) which gives
commenters a concrete handle to engage with — more upvotes than "what do
you think overall."

Risk: directly invoking Bloomberg might attract a "this is nothing like
Bloomberg" pile-on. Use only if you're comfortable engaging that thread.

---

## Decision rubric — which variant to pick

| Situation | Pick |
|---|---|
| Want the safest, broadest-appeal angle | Primary draft in `LAUNCH_PLAYBOOK.md §1` |
| Want to lean into the back-check / scorecard differentiator | Variant A |
| Want to position against Bloomberg + Finviz explicitly | Variant B |
| Posting on a Monday or Wednesday (low traffic) | Variant A (more substance per word) |
| Posting on a Tuesday or Thursday (peak traffic) | Primary or Variant B |

All three end with a question / invitation to break the methodology — that's
the comment-engagement hook. Don't skip the "what I want HN to break" line.
