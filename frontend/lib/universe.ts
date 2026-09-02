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
 * and confirm ACTIVE_UNIVERSE_SIZE in backend/app/services/universe.py.
 */

/**
 * Mirrors backend `ACTIVE_UNIVERSE_SIZE`. The number that belongs in copy.
 * If the backend constant moves, move this with it.
 */
export const ACTIVE_SCORED_TICKERS = 2500;

/** Rows in `tickers`, scored or merely tracked. Rounded down from 11,815. */
export const TRACKED_TICKERS = 11800;

/** Display form for the number that belongs in copy, e.g. "~2,500". */
export const activeScoredLabel = `~${ACTIVE_SCORED_TICKERS.toLocaleString("en-US")}`;
