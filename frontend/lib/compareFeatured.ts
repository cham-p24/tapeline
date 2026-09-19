import { canonicalMatchup } from "@/lib/comparePairs";
import {
  COMPARE_FACTORS,
  fetchCompareTicker,
  type CompareFactorKey,
  type CompareTickerData,
} from "@/lib/compareTicker";

/**
 * The /compare index's featured head-to-heads, read server-side from the same
 * ticker endpoint (and the same fetch cache entry) as /compare/[matchup].
 *
 * NO NUMBER HERE IS EVER MADE UP. A pair is featured only when BOTH tickers
 * came back from the API with a composite score; anything else — a transient
 * error, an unknown symbol, a null composite — drops the pair, and if every
 * pair drops the index renders no preview at all. A factor the API holds no
 * reading for stays null (rendered as an em-dash), never 0.
 */

/** Serialisable — handed from the server page to the client tabs. */
export type FeaturedSide = {
  symbol: string;
  name: string;
  sector: string | null;
  score: number;
  signal: string | null;
  factors: { key: CompareFactorKey; label: string; value: number | null }[];
};

export type FeaturedMatchup = { slug: string; a: FeaturedSide; b: FeaturedSide };

/** Classic within-theme head-to-heads, all in the curated list. */
export const FEATURED_PAIRS: [string, string][] = [
  ["AAPL", "MSFT"],
  ["AMD", "NVDA"],
  ["BAC", "JPM"],
  ["KO", "PEP"],
];

function finite(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function toSide(symbol: string, d: CompareTickerData): FeaturedSide | null {
  const score = finite(d.score);
  if (score == null) return null;
  return {
    symbol,
    name: d.name || symbol,
    sector: d.sector ?? null,
    score,
    signal: d.signal ?? null,
    factors: COMPARE_FACTORS.map(({ key, label }) => ({
      key,
      label,
      value: finite(d.breakdown?.[key]?.value),
    })),
  };
}

export async function loadFeaturedMatchups(
  pairs: [string, string][] = FEATURED_PAIRS,
): Promise<FeaturedMatchup[]> {
  const symbols = Array.from(new Set(pairs.flat().map((s) => s.toUpperCase())));
  const fetched = await Promise.all(symbols.map((s) => fetchCompareTicker(s)));
  const bySymbol = new Map(symbols.map((s, i) => [s, fetched[i]]));

  const out: FeaturedMatchup[] = [];
  for (const [x, y] of pairs) {
    // Canonical (alphabetical) sides — the same left/right the matchup page uses.
    const [a, b] = [x.toUpperCase(), y.toUpperCase()].sort();
    const fa = bySymbol.get(a);
    const fb = bySymbol.get(b);
    if (fa?.status !== "ok" || fb?.status !== "ok") continue;
    const sa = toSide(a, fa.data);
    const sb = toSide(b, fb.data);
    if (!sa || !sb) continue;
    out.push({ slug: canonicalMatchup(a, b), a: sa, b: sb });
  }
  return out;
}
