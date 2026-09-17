/**
 * Data freshness — what the copy is allowed to SAY about how fresh the data is.
 *
 * One place, the way lib/trial.ts holds the trial length. Mirrors
 * backend/app/services/freshness.py, and the two are pinned together by
 * backend/tests/test_freshness_constants_agree.py (backend side) and
 * __tests__/freshnessConstants.test.tsx (frontend side).
 *
 * WHY THIS EXISTS (integrity wave, founder-approved 14 Sep 2026)
 * --------------------------------------------------------------
 * The site said "sub-60-second refresh", "real-time", "live, not delayed" and
 * "every minute" on ~170 surfaces. Measured during the US session on
 * Mon 14 Sep 2026:
 *   - The price vendor plan is 15-minute delayed. At 13:59 UTC the AAPL
 *     snapshot's `updated` was 899 s old and the newest minute bar 961 s old,
 *     with no lastTrade/lastQuote (not entitled). A second session measured
 *     15.0 minutes for SPY, AAPL, NVDA and MSFT at 13:41 UTC.
 *   - The worker re-reads every covered stock and ETF once per pass. Before
 *     #843 passes landed 69.7 to 74.3 s apart (the tick plus a 60 s sleep).
 *     Since #843 (merged 14 Sep 18:34 UTC) the loop is fixed-rate: 22 gaps
 *     measured 59.99 to 60.02 s during the US session (18:45-19:12 UTC).
 *     A deploy or restart still leaves a gap of several minutes.
 *   - Only ~38 of ~11,546 scores changed in 2.5 minutes while ~4,161 prices
 *     did: score inputs are daily readings.
 *   - Public pages are cached snapshots (s-maxage 1800-3600 with a year of
 *     stale-while-revalidate): the heatmap showcase was served ~60 minutes
 *     old and /t/AAPL's price data ~50 minutes old.
 *
 * Never write these numbers into copy. Interpolate them from here. And never
 * write "real-time", "live data", "not delayed", "sub-60s", "every minute" or
 * a "Live" badge about the data — scripts/lint-copy-compliance.mjs blocks it.
 *
 * Whether a paid vendor upgrade to real-time prices happens is a founder
 * decision. Until it does, nothing here may assume it.
 */

/** Vendor price delay, in minutes (Massive/Polygon Stocks Starter plan). */
export const PRICE_DELAY_MINUTES = 15;

/** "delayed about 15 minutes", for interpolation into a sentence. */
export const PRICE_DELAY_PHRASE = `delayed about ${PRICE_DELAY_MINUTES} minutes`;

/** The short visible note, used wherever a price is shown or a plan is sold. */
export const PRICE_DELAY_NOTE = `Prices ${PRICE_DELAY_PHRASE}`;

/**
 * The note for a server-reported delay (`data_delayed_minutes` on
 * /api/scanner). Falls back to the constant when the value is missing or
 * reads below the vendor delay, which no caller can actually get.
 */
export function priceDelayNote(minutes?: number | null): string {
  const m =
    typeof minutes === "number" && Number.isFinite(minutes) && minutes >= PRICE_DELAY_MINUTES
      ? Math.round(minutes)
      : PRICE_DELAY_MINUTES;
  return `Prices delayed about ${m} minutes`;
}

/**
 * How often the worker re-reads every covered stock and ETF, as a phrase that
 * held across every steady-state pass measured after #843 (59.99-60.02 s,
 * 14 Sep 2026 18:45-19:12 UTC). Gaps are longer around deploys, which the long
 * sentences say.
 */
export const PASS_INTERVAL_SECONDS = 60;

/** "60s", for a compact counter. */
export const PASS_INTERVAL_SHORT = `${PASS_INTERVAL_SECONDS}s`;

export const PASS_CADENCE_PHRASE = `about every ${PASS_INTERVAL_SECONDS} seconds`;

/** The combined price-freshness sentence. */
export const PRICE_FRESHNESS_SENTENCE =
  `Prices are ${PRICE_DELAY_PHRASE}. Tapeline re-reads them for every covered ` +
  `stock and ETF ${PASS_CADENCE_PHRASE} during US market hours, and less often ` +
  `around deploys.`;

/** What a score's cadence really is. */
export const SCORE_CADENCE_SENTENCE =
  "Scores are recalculated on each pass, but their inputs (daily price bars and " +
  "the macro regime, plus fundamentals and SEC Form 4 filings, which update less " +
  "often) change at most about once a day, so a score usually changes about once a day.";

/** Crypto is daily for both price and score. */
export const CRYPTO_CADENCE_SENTENCE =
  "Crypto prices and scores update once a day.";

/**
 * Public pages are cached snapshots. Their age is bounded by the next visit
 * after the cache expires, not by the revalidate setting, so "up to an hour"
 * is not a safe upper bound.
 */
export const PUBLIC_SNAPSHOT_SENTENCE =
  "This page is a saved snapshot and can be an hour old or more; open the app for current numbers.";

/** Footer line for public list pages (signal, sector, sectors, best-stocks-for, stocks). */
export const PUBLIC_SNAPSHOT_FOOTER =
  `Saved snapshot; can be an hour old or more. Prices ${PRICE_DELAY_PHRASE}.`;

/** In-app pages do not update themselves (the push channel never reached the browser). */
export const IN_APP_REFRESH_SENTENCE =
  "The page shows the latest data when you open it or change a filter; reload to see newer numbers.";
