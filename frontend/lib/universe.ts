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
 * Copy says ~2,500 because that is the configured, defensible floor of what the
 * worker scores every tick. Every mega-cap (AAPL, MSFT, NVDA, TSLA, SPY, QQQ)
 * is in it with live volume — spot-checked the same day.
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
 * Still 2,500 pending measurement. That understates the product today and is
 * expected to move up materially; understating is the safe direction to be
 * wrong in while the number is unverified.
 */
export const ACTIVE_SCORED_TICKERS = 2500;

/** Rows in `tickers`, scored or merely tracked. Rounded down from 11,815. */
export const TRACKED_TICKERS = 11800;

/** Display form for the number that belongs in copy, e.g. "~2,500". */
export const activeScoredLabel = `~${ACTIVE_SCORED_TICKERS.toLocaleString("en-US")}`;
