# X thread #1 — tweets 4 + 5 + URL reply

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

Continues the @tapeline_io launch thread from May 13. Tweets 1-3 are already
live (hook + black-box reveal + "we publish them"). This file holds the
agent-drafted continuation so the founder can copy-paste-post when ready.

Posting order:
1. Open the LAST tweet in the existing chain on @tapeline_io
2. Click Reply, paste Tweet 4
3. From Tweet 4 → Reply, paste Tweet 5
4. From Tweet 5 → Reply, paste the URL reply

All tweets verified ≤ 280 chars (Twitter counts URLs as 23 chars regardless).

---

## Tweet 4 (~190 chars)

```
And every top-10 pick gets back-checked vs SPY the next day. Wins AND losses both stay on the page, corrections dated, no survivor bias. The current median alpha and its sample size are on tapeline.io/scorecard.
```

**Why this works:** it points at the live figure instead of baking in a
number that goes stale (the original draft quoted a 5-session median alpha).
Corrections to recorded values are dated on /scorecard and /changelog (updated
15 September 2026).
The "wins AND losses both stay on the page" line is the trust-builder.
Self-skeptical tone matches the rest of the thread.

---

## Tweet 5 (~275 chars)

```
The full record is free to read, no account. Pro $8.25/mo billed annually = the full ~11,500 stocks & ETFs + alerts. Premium $19.99 adds SEC Form 4 filings. Sign-up is email + password; a card starts the 30-day trial, $0 today. Built solo from Melbourne.
```

**Why this works:** transparent pricing with the genuinely card-free surface as
the hook — the published record needs no account at all — and the trial's terms
stated rather than buried. "Built solo
from Melbourne" adds founder context without being self-promotional. No CTA
verb — the URL reply that follows IS the CTA.

---

## URL reply (~95 chars including 2 URL allowances)

```
The record so far: https://tapeline.io/scorecard
The product: https://tapeline.io
```

**Why this works:** two distinct destinations — `/scorecard` is the proof
surface, `/` is the product entry. URL-only replies on X get treated
differently by the algorithm than text-with-URL — sometimes better, sometimes
worse. We err on the side of "let them click through to verify."

---

## Alternative Tweet 4 + 5 (if Option A doesn't feel right)

Drafted as a fallback before Option A was picked. The six-factor breakdown
angle:

**Tweet 4:**
```
The six factors, heaviest-weighted first (Trend and Relative Strength most, Momentum least):

Trend
Relative Strength
Fundamentals
Smart Money
Macro
Momentum

Heaviest Trend and RS, lightest Momentum. The ordering is fixed and public, and it doesn't change retroactively. Argue with it on /how-it-works.
```

**Tweet 5:**
```
The published record is complete and needs no account. Free accounts get top-10 rows and 12 look-ups a day, no card. Pro $8.25/mo annual = all ~11,500 stocks & ETFs + alerts. Premium $19.99/mo adds SEC Form 4 filings. Prices delayed ~15 min.
```

**URL reply:** `https://tapeline.io`

Skipped because it rehashes the methodology content already in tweets 2/3.
Kept here in case the founder prefers to lead with the factor list.
