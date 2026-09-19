/**
 * How big the scored universe actually is — and why the big number is wrong.
 *
 * READ THIS BEFORE "CORRECTING" ANY TICKER COUNT IN COPY.
 *
 * `SELECT count(*) FROM tickers` returns ~11,800 and `WHERE score IS NOT NULL`
 * returns ~6,700. Neither is the marketing number, and reaching for one of them
 * is an easy, confident mistake — it was made on 2026-09-01, shipped to five
 * live SEO pages as "6,600+ scored tickers", and reverted the same day.
 *
 * There are TWO write paths into `tickers.score`:
 *
 *   1. The scoring worker, which scores exactly `ACTIVE_UNIVERSE_SIZE`
 *      (backend/app/services/universe.py — 2,500, not overridden in prod) by
 *      daily dollar-volume, and writes real price AND volume for those.
 *   2. `services/sheet_feed.py`, which upserts a price and a score from the
 *      Google Sheet for names OUTSIDE that top-N and has no volume column.
 *
 * So ~3,600 rows carry a score with `volume IS NULL`. They are tracked for
 * watchlists, news and per-ticker pages — they are not what "actively scored"
 * means, and counting them inflates the claim. See
 * docs/FEED_COVERAGE_AUDIT_2026-08-19.md, which reaches the same conclusion
 * and argues 2,500 is the right cut for the ICP.
 *
 * ── 2026-09-07: THE PARAGRAPH ABOVE HAS THE CAUSATION BACKWARDS ─────────────
 *
 * Those rows were not scoreless-of-volume because they are marginal. They had
 * `volume IS NULL` because they were never SNAPSHOTTED, and a snapshot is the
 * only thing that writes `volume`. The active-universe selector ranked by
 * `coalesce(volume * price, -1)` and took the top 2,500, so a row without a
 * volume reading sorted last, fell below the cut, got no snapshot, and could
 * never acquire the reading that would have lifted it. A closed loop.
 *
 * The set was therefore not a tail of illiquid names. It contained TSM,
 * Toyota, Sony, Mitsubishi UFJ, HubSpot and Qiagen — 1,389 companies above
 * $2B. Searching "TSM" returned nothing. Asked directly, the provider had
 * complete data for every one of them.
 *
 * So "counting them inflates the claim" was true only while the bug made them
 * uncountable. The fix (#763) lets the snapshot reach everything we score, and
 * once it has run these rows carry real volume like any other.
 *
 * ACTIVE_SCORED_TICKERS is deliberately NOT bumped in that PR. The new
 * ACTIVE_UNIVERSE_SIZE (12,000) is a snapshot CEILING chosen to sit above the
 * whole table — it is not a count of anything, and putting it in copy would
 * claim thousands of tickers we do not score. The honest number has to be
 * MEASURED after the fix has run, with the query at the bottom of this
 * comment, and only then written here.
 *
 * The honest split, verified 2026-09-01:
 *   11,815  rows in `tickers`            -> TRACKED_TICKERS
 *    6,713  score IS NOT NULL            -> NOT a marketing number
 *    3,051  score AND volume (worker)    -> the real active set
 *    2,500  ACTIVE_UNIVERSE_SIZE         -> ACTIVE_SCORED_TICKERS
 *
 * Copy said ~2,500 because that was the configured floor of what the worker
 * snapshotted every tick.
 *
 * ── SUPERSEDED 2026-09-07 ───────────────────────────────────────────────────
 *
 * That figure was never a count of anything a user could see. A row with no
 * snapshot has no `change_pct_1d`, and every ranked surface requires one, so
 * the knob silently became a cap on what could be SERVED — stranding 3,633
 * scored tickers including TSM, Toyota, Sony and HubSpot. Searching "TSM"
 * returned nothing. Fixed in #763/#765/#772: the universe was never small, we
 * were hiding two thirds of it and advertising the smaller number.
 *
 * The split below is re-measured: 11,852 tracked, 7,513 scored, 6,994 returned
 * by an unfiltered scan, 79 crypto in a separate bucket.
 *
 * RE-CHECK (read-only):
 *   SELECT count(*) FROM tickers;
 *   SELECT count(*) FROM tickers WHERE score IS NOT NULL AND volume > 0;
 *
 * Better still, count what a user can actually screen — the same predicate
 * every ranked surface applies (backend/app/services/ticker_freshness.py):
 *   score IS NOT NULL AND score <= 100 AND symbol NOT LIKE '% %'
 *   AND (non-null sub_* count) >= 2 AND change_pct_1d IS NOT NULL
 *   AND confidence_pct IS NOT NULL AND asset_class is a clean ASCII token
 *   AND updated_at >= (latest scored refresh - 7 days)
 * and confirm ACTIVE_UNIVERSE_SIZE in backend/app/services/universe.py.
 *
 * ── RE-MEASURED 2026-09-13 22:33 UTC (read-only) ────────────────────────────
 *
 * Production database:
 *   11,918  rows in `tickers`
 *   11,546  score IS NOT NULL, asset_class <> 'crypto' (5,906 equity, 5,613
 *           etf, 27 future_commodity), every one updated in the last 2 days
 *      103  crypto rows with a score (106 crypto rows in total)
 * Public API, anonymous:
 *   /api/scanner?min_dollar_volume=0&include_leveraged=true   total_matched 11,501
 *   /api/scanner?min_dollar_volume=0                          total_matched 10,714
 *   /api/scanner?asset_class=crypto                           total_matched 103
 *
 * So an unfiltered scan (liquidity floor and leveraged-fund exclusion both
 * switched off) returns 11,501, rounded down to 11,500. That is also the figure
 * in the founder-approved September product update email ("about 11,500
 * stocks and ETFs", "100 pairs"), so the site and the email now agree.
 */

/**
 * The number that belongs in copy: how many tickers we actively score.
 *
 * This used to mirror backend `ACTIVE_UNIVERSE_SIZE` exactly. It no longer
 * can, because that constant stopped being a count: it is now a snapshot
 * ceiling set above the whole table (see the 2026-09-07 note above). The
 * invariant that survives is one-directional — this may never EXCEED the
 * backend ceiling, because we cannot score more than we snapshot — and that
 * is what universeSizeIsSingleSourced.test.ts now asserts.
 *
 * MEASURED and rounded DOWN, never estimated and never rounded up.
 * 2026-09-07: `/api/scanner?limit=200&min_dollar_volume=0` returned 6,994.
 * 2026-09-13 22:33 UTC: `/api/scanner?limit=1&min_dollar_volume=0&include_leveraged=true`
 * returned total_matched = 11,501 — the same query a reader can run in ten
 * seconds.
 *
 * Not 11,852 (rows we merely TRACK, most of them unscored) and not 5,130 (the
 * DEFAULT view, which applies a $1M/day liquidity floor the user can switch
 * off). The claimable number is what an unfiltered scan actually returns.
 *
 * SINCE 2026-09-19 (#875) the default view also leaves out listings that are
 * not common stock (notes, preferreds, warrants, rights, units: 118 scored on
 * 2026-09-18), so the unfiltered scan needs a third switch:
 * `/api/scanner?limit=1&min_dollar_volume=0&include_leveraged=true&include_non_common=true`.
 * The 11,501 above was measured before that exclusion existed and counts them.
 * Re-measure with all three switches before changing this number.
 */
export const ACTIVE_SCORED_TICKERS = 11500;

/** Rows in `tickers`, scored or merely tracked. Rounded down from 11,918 (2026-09-13). */
export const TRACKED_TICKERS = 11900;

/**
 * Crypto pairs, in their own bucket. Rounded down from 103 (measured
 * 2026-09-13 22:33 UTC via the same endpoint with `asset_class=crypto`; it was
 * 79 on 2026-09-07).
 *
 * Deliberately a SEPARATE number, never added to ACTIVE_SCORED_TICKERS. A coin
 * and a stock scoring 70 do not mean the same thing: company fundamentals and
 * insider filings cannot exist for a token, so a coin's score is built from
 * four readings where a stock's is built from six. Summing them into one
 * headline would imply a comparison the arithmetic does not support — and it
 * is the same conflation that put a token's price on four real companies'
 * pages on 2026-09-03.
 *
 * Crypto also updates DAILY, not sub-60s: the vendor's real-time crypto feed
 * is not on the current plan. Any copy stating a refresh rate must say so.
 */
export const CRYPTO_PAIRS = 100;

/** Display form, e.g. "100". */
export const cryptoPairsLabel = CRYPTO_PAIRS.toLocaleString("en-US");

/** Display form for the number that belongs in copy, e.g. "~11,500". */
export const activeScoredLabel = `~${ACTIVE_SCORED_TICKERS.toLocaleString("en-US")}`;
