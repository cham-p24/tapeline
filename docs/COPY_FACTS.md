# Copy facts: what is true to say about Tapeline

**Last checked:** 15 September 2026. **Why this exists:** the integrity wave the
founder approved on 14 September 2026 (#817, #818, #820, #821, #826, #827, #830)
corrected the product. The copy banks under `docs/` kept repeating the old claims,
because nothing checks them. This page is the one place a copy bank, an outreach
draft or a listing should be checked against. If a line in any other doc
disagrees with this page, this page wins until someone re-measures.

Every number here is dated. Re-measure before you quote a count in anything that
will be read after the date shown.

---

## 1. Prices and freshness

**Say:** "Prices are delayed about 15 minutes. During US market hours Tapeline
re-reads them for every covered stock and ETF about every 70 to 80 seconds."

- **Prices are delayed about 15 minutes.** The data plan is Massive (formerly
  Polygon) Stocks Starter, which is a 15-minute delayed plan. Measured on
  Monday 14 September 2026 during the US session: at 13:59:01 UTC the AAPL
  snapshot was 899 seconds old and its latest minute bar 961 seconds old, with
  no last-trade or last-quote data (not on the plan). A second check at
  13:41 UTC found SPY, AAPL, NVDA and MSFT 15.0 minutes old. A response
  timestamp that reads "0 seconds old" is the time of the response, not the
  time of the trade.
- **A pass takes about 70 to 80 seconds.** Each pass rewrites the price and score
  of every scored stock and ETF (about 11,500 rows, in about 5 seconds), then the
  worker sleeps. Gaps measured on 14 September 2026: 72.2, 71.1, 74.3 and 71.6
  seconds (13:49 to 13:54 UTC); 71, 73 and 71 seconds (14:02 to 14:07 UTC). A
  deploy stretched one gap to 98 seconds and a restart stretched another to
  about 6 minutes.
- **Scores usually change about once a day.** A score is recalculated on every
  pass, but most of its inputs (daily price bars for trend, relative strength
  and momentum; fundamentals; SEC Form 4 filings; the macro regime from a daily
  VIX close) are daily readings. In one 2.5-minute window about 38 of 11,546
  scores changed while about 4,161 prices did.
- **Crypto prices and scores update once a day**, from daily bars.
- **In-app pages do not update on their own today.** The scanner and the other
  `/app` pages load the latest data when you open them or change a filter.
  A 300-second capture of the browser stream on 14 September 2026 (14:02:11 to
  14:07:11 UTC) received 0 update events while the database was rewritten 4
  times. Do not write copy that promises pages refresh themselves.
- **Public pages are saved snapshots.** The heatmap showcase, signal and sector
  lists, ticker pages (`/t/...`), the homepage and similar pages are cached and
  can be an hour old or more. On 14 September 2026 at 14:09 UTC the heatmap page
  was serving a copy built before the 13:30 UTC open, and `/t/AAPL` showed price
  data 49 minutes 47 seconds old. For current numbers, point people at the app.

**Never write:** "real-time", "live data", "live prices", "live, not delayed",
"no delay", "not delayed", "streaming", "sub-60s", "under 60 seconds",
"every minute", "per minute", "60s cadence", "refreshed every 5 minutes",
or a "Live" badge. None of them held when measured.

Whether a paid data plan with real-time prices is bought is a founder decision.
Do not write copy that assumes it.

## 2. What is covered

- **About 11,500 US stocks and ETFs.** An unfiltered scan
  (`/api/scanner?min_dollar_volume=0&include_leveraged=true`) returned 11,501 on
  13 September 2026 at 22:33 UTC. The default view applies a liquidity floor
  (about $1M a day) that the user can switch off, so it shows fewer.
- **About 100 crypto pairs** (103 on the same date), in their own bucket,
  updated once a day, scored on four readings instead of six.
- **Not** "~2,500", "every US-listed stock", "~6,900" or "5,757". 2,500 was a
  configured snapshot size, never a count of what a user could screen.

## 3. The public record

**Say:** "Each trading day's top 10 goes on a public scorecard with its
next-session result against SPY, losses included. Entries are not re-ranked or
deleted. We have corrected recorded values twice, and said so: prices on
25 August 2026, and scores from 18 May to 12 June capped on 15 June 2026."

- **Two corrections.** On 25 August 2026 the record switched to official
  closing prices and past rows were recomputed (684 of 688 rows; 4 kept as first
  recorded because the vendor no longer returns prices for them; the
  24 August 2026 list was not rebased). On 15 June 2026 every recorded score
  above 100 was set to 100 and the originals were not kept: all 190 entries
  from 18 May to 12 June 2026 now read 100. That one was not disclosed until
  14 September 2026.
- **Four missing days.** No top 10 was recorded for 31 August, 2 September,
  4 September or 9 September 2026. None was filled in afterwards.
<!-- copy-compliance-allow record-never-edited -- this line lists the banned phrasings in order to ban them -->
- **Never write:** "never edited", "unedited", "no edits", "append-only", "immutable", "a record you can't edit", "nothing gets quietly removed", "every day" or "every session" about the record.
- **No performance claims.** The record trails SPY: just under half of entries
  beat SPY at the next session, and a check at one and three months on
  7 September 2026 came out worse, not better. Do not state a hit rate, return or alpha in copy that
  will outlive the day; link `/scorecard`, which carries the live figure and the
  sample size. "Beat SPY" is allowed when describing the measurement.
<!-- copy-compliance-allow performance-claim -- names the banned phrase in order to ban it -->
- **Banned everywhere:** "beat the market".
- **The formula.** The six factors and their weight order are public on
  `/how-it-works`. The exact weights are not (PR #342). Never write "published
  weights", "fully public formula" or "open formula".

## 4. Features that do not exist today

- **Congressional trades: not available.** There is no real source of
  congressional trade disclosures. Tapeline does not show any, and none feed the
  score. `/congressional-trades` and `/app/congress` say so. Do not list
  congressional trades as a feature, a Premium benefit or a score input.
- **Squeeze detection: not working.** No real squeeze data source is configured
  (the sheet URL was unset on the worker when checked on 14 September 2026). The
  squeeze pages show an empty state and squeeze alerts cannot fire (#818). Do not
  describe squeeze setups, Squeeze Watch or squeeze alerts as a feature.
- **Insider data** is SEC Form 4 filings, shown per ticker on Premium. Call it
  "public SEC filings" or "SEC Form 4 filings", never "insider trading tips".
  For how often it refreshes, use the wording on `/data-sources` (#827); do not
  invent a cadence.

## 5. Plans, trial and billing

- **Free:** signing up is free and needs no card. Top 10 scanner rows, 12 ticker
  look-ups per UTC day, a 5-ticker watchlist, 1 saved screen, no alert rules, and
  the full public scorecard.
- **Anonymous visitors are not metered** on ticker look-ups. Do not state a
  number for use without an account.
- **Pro:** $9.99 a month, or $99 a year ($8.25 a month billed annually). Up to
  1,000 scanner rows, 50-ticker watchlist, email alerts (10 a day), browser push
  alerts, CSV export.
- **Premium:** $19.99 a month, or $199 a year ($16.58 a month billed annually).
  Everything in Pro plus per-ticker SEC Form 4 filings, a 200-ticker watchlist,
  100 saved screens, effectively unlimited alerts and API access (1,000 requests
  a day).
- **Trial:** adding a card starts a **30-day** Premium trial. $0 that day, the
  first charge on day 30, one click cancels before then. The pre-charge email
  goes **about 7 days before** the first charge. Not "14-day", not "three days
  before", and a new account is not asked for a card at first sign-in (that gate
  ran from 22 to 30 August 2026 and was removed in #683).

## 6. Where these facts live in code

| Fact | Source of truth |
| --- | --- |
| Trial length | `backend/app/routers/billing.py` `TRIAL_DAYS`, `frontend/lib/trial.ts` |
| Pre-charge notice | `backend/app/services/precharge_notice.py`, `frontend/lib/trial.ts` `PRECHARGE_NOTICE_DAYS` |
| Prices, plan limits | `frontend/lib/pricing.ts`, `backend/app/services/tier.py` |
| Universe counts | `frontend/lib/universe.ts` (with the measuring queries) |
| Record corrections | `/changelog` entries dated 2026-08-25, 2026-06-15 and 2026-09-14; `/scorecard` "Gaps and known limitations" |
| Congress, squeeze | `backend/app/services/congress_integrity.py`, `backend/app/services/squeeze_integrity.py` |
