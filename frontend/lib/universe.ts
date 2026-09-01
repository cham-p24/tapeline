/**
 * How big the scored universe actually is.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * "~2,500 tickers" was hardcoded as a string literal in ten places, including
 * JSON-LD served to search engines and AI assistants. It was correct when
 * written and then quietly stopped being true: the discovery/reconciliation
 * fixes of 2026-08-28 (PRs #654, #658) grew the live universe from 2,463 to
 * ~11,800 rows, and no marketing copy moved with it.
 *
 * Understating the product is not a safe error. `/best-finviz-alternatives`
 * was conceding "~2,500 actively scored ... not the full 9,000+ Finviz
 * indexes" — surrendering a comparison Tapeline no longer loses.
 *
 * So: one constant, one place, and the query that verifies it.
 *
 * HOW TO RE-CHECK (read-only):
 *   SELECT count(*) FROM tickers;                          -- UNIVERSE_TICKERS
 *   SELECT count(*) FROM tickers WHERE score IS NOT NULL;  -- SCORED_TICKERS
 *
 * Last verified 2026-09-01: 11,808 rows, 6,643 scored
 * (4,132 equities + 2,418 ETFs), 3,376 refreshed in the previous 24h.
 *
 * WHICH NUMBER TO PUT IN COPY
 * ---------------------------
 * `SCORED_TICKERS` — always. It is the smaller, defensible one, and it is the
 * one that matches the claim being made: a scanner is judged on what it
 * scores, not on what it lists. Both are rounded DOWN to a round number so
 * copy is never ahead of the database between refreshes.
 */

/** Rows in `tickers` carrying a composite score. Rounded down from 6,643. */
export const SCORED_TICKERS = 6600;

/** Total rows in `tickers`, scored or not. Rounded down from 11,808. */
export const UNIVERSE_TICKERS = 11800;

/** Display form for the number that belongs in copy, e.g. "6,600+". */
export const scoredTickersLabel = `${SCORED_TICKERS.toLocaleString("en-US")}+`;
