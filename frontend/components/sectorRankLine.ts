/**
 * The public ticker page's one-sentence peer-rank line.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * /t/[symbol] used to derive its "ranks #X out of Y {sector} stocks" line from
 * the related-tickers pool: an ANONYMOUS SSR call to /api/scanner asking for 60
 * rows. Anonymous callers are clamped to the Free row cap (10 rows), so the
 * pool was the GLOBAL top-10 by score, filtered in memory to the page's sector
 * — almost always zero rows. The ticker itself was then pushed into the empty
 * pool and the page printed "ranks #1 out of 1 information technology stocks"
 * in production: a confident-looking rank computed over one row, violating the
 * MIN_PEERS=30 rule the rest of the product enforces (see
 * backend/app/services/percentile.py and components/percentiles.ts).
 *
 * The honest source already exists: the ticker endpoint's `peer_percentiles`
 * block, which is computed over the FULL peer group server-side, refuses to
 * rank below MIN_PEERS=30, and always carries the denominator it used. This
 * module is the ONLY way the public page may render a rank line, and it goes
 * through `toRanking` — which re-applies the n >= 30 floor client-side — so no
 * arrangement of inputs can ever print a rank with a denominator under 30.
 * When the ranking is refused the line is suppressed entirely: no number is
 * better than a number computed over a handful of rows.
 *
 * Compliance (docs/COMPLIANCE_COPY_RULES.md): descriptive only. The sentence
 * states where the composite sits and against how many covered peers; no
 * verdict, no forecast, no instruction.
 */
import { normalizePercentiles, ordinal, type Ranking } from "@/components/percentiles";

/**
 * Build the rank sentence from the raw `peer_percentiles` payload, or refuse.
 *
 * Returns null whenever the composite ranking cannot be printed honestly —
 * missing payload, no peer group, fewer than 30 covered peers, or no composite
 * value of our own. The caller renders nothing in that case; there is no
 * fallback arithmetic and no second source of rank on the page.
 */
export function sectorRankLine(symbol: string, peerPercentiles: unknown): string | null {
  const ranking: Ranking = normalizePercentiles(peerPercentiles).score;
  if (ranking.kind !== "ranked") return null;
  const n = ranking.n.toLocaleString("en-US");
  return (
    `${symbol} scores in the ${ordinal(ranking.percentile)} percentile of ` +
    `${ranking.peerGroup} by composite score (n=${n} covered peers) this session.`
  );
}
