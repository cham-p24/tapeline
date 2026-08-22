"use client";

import Link from "next/link";
import { ScoreRadial } from "@/components/ScoreRadial";
import {
  buildFactorRows,
  buildTickerRead,
  describeRanking,
  normalizePercentiles,
  ordinal,
  MIN_PEER_N,
  type FactorKey,
  type Ranking,
} from "@/components/percentiles";

/**
 * The score panel — the top of the ticker page.
 *
 * WHAT IT IS FOR
 * --------------
 * The reader arrives asking two questions: "what does this product think?" and
 * "can I check it?". This panel answers the first. It is deliberately the first
 * thing under the price, ahead of the quote grid, because a grid of raw fields
 * locatable against nothing is not what anyone came for.
 *
 * Every factor row carries four things and needs all four to be useful:
 *   • the factor's 0-100 value            — what we measured
 *   • its PUBLISHED weight                — how much that measurement counts
 *   • its percentile among covered peers  — where that value actually sits
 *   • the peer group and its size (n)     — what "sits" was measured against
 *
 * The weights are already public: the API returns them on every `breakdown`
 * entry and /how-it-works prints the whole formula. Showing them here is
 * disclosure, not a leak, and it is what lets a reader reconstruct the
 * composite instead of taking it on faith.
 *
 * WHAT IT WILL NOT DO
 * -------------------
 * It will not print a percentile without its denominator, will not rank on a
 * peer group thinner than MIN_PEER_N, will not treat "Uncategorized" as a peer
 * group, and will not substitute 0 for a value we do not hold. Those four
 * refusals live in components/percentiles.ts and are enforced by its types —
 * see the header there. Where a ranking is refused the cell prints the REASON
 * in words ("not enough covered peers to rank"), never a blank, because a
 * reader has to be able to tell a deliberate silence from a broken page.
 *
 * COMPLIANCE (docs/COMPLIANCE_COPY_RULES.md, binding)
 * ---------------------------------------------------
 * Descriptive only. This panel reports measurements and their position in a
 * named peer group and stops there. No buy/sell/hold, no price target, no fair
 * value, no forecast, no performance claim — none of which is derivable from a
 * percentile anyway. Rule 2 in particular: a factor is described by what it
 * MEASURED and where that reading ranks, never by an adjective about the
 * security.
 */

/** The single, deliberate rendering of "we do not hold this value". */
const EMPTY = "—";

export function ScorePanel({
  symbol,
  score,
  signal,
  confidencePct,
  breakdown,
  percentiles,
  reason,
  displayScore,
}: {
  symbol: string;
  score: number | null;
  signal: string | null;
  confidencePct: number | null;
  /** The API's `breakdown` block. Read structurally — see buildFactorRows. */
  breakdown: unknown;
  /** The API's `percentiles` block. Absent on an older build → all unranked. */
  percentiles: unknown;
  /** The API's own one-line note on the score. Rendered verbatim, or not at all. */
  reason?: string | null;
  /**
   * Optional pre-formatted composite, so the page can keep its count-up
   * animation. Presentation only: every decision below reads `score`.
   */
  displayScore?: string;
}) {
  const ranks = normalizePercentiles(percentiles);
  const rows = buildFactorRows(breakdown, ranks);
  const read = buildTickerRead({ symbol, score, composite: ranks.score, factors: rows });

  const big = displayScore ?? (score != null ? score.toFixed(1) : EMPTY);
  // Keyed lookup rather than positional: the radial's six props must not
  // silently reshuffle if FACTOR_ORDER is ever reordered.
  const sub = (key: FactorKey) => rows.find((r) => r.key === key)?.value ?? null;

  return (
    <section className="card" aria-labelledby="score-panel-heading">
      <div className="border-b border-border p-4">
        <h2 id="score-panel-heading" className="font-semibold">
          Tapeline Score
        </h2>
        <p className="mt-0.5 text-xs text-muted">
          Six factors, published weights, one 0&ndash;100 composite. Every
          percentile here names the peer group it was computed in and how many
          covered peers were in it.
        </p>
      </div>

      <div className="p-4">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-4">
          {/* Visual signature for the six sub-scores. Decorative alongside the
              table below, which carries the same numbers in text. */}
          <ScoreRadial
            trend={sub("trend")}
            rs={sub("rs")}
            fundamentals={sub("fundamentals")}
            smart_money={sub("smart_money")}
            macro={sub("macro")}
            momentum={sub("momentum")}
            score={score}
            size={104}
            showCenter={false}
            showLabels={false}
          />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="nums text-5xl font-bold leading-none">{big}</span>
              <span className="text-sm text-muted">/ 100</span>
              {signal && (
                <span className={`rounded px-2 py-0.5 text-xs ${signalTone(signal)}`}>
                  {signal}
                </span>
              )}
              {confidencePct != null && (
                <span className="nums text-xs text-muted" title={confidenceLabel(confidencePct)}>
                  data confidence {confidencePct.toFixed(0)}%
                </span>
              )}
            </div>
            <p className="mt-2 text-sm" data-testid="composite-ranking">
              <RankingText ranking={ranks.score} />
            </p>
          </div>
        </div>

        {/* The one-sentence read. Deterministic template, assembled only from
            the percentile payload — no model call, no per-render cost, and the
            same payload produces the same sentence on every render. */}
        <p
          data-testid="ticker-read"
          className="mt-4 border-l-2 border-border2 pl-3 text-sm text-fg"
        >
          {read}
        </p>

        {/* The API's own note on this score, verbatim. Kept beneath the read so
            it is clearly the payload speaking, not a second synthesis. */}
        {reason && <p className="mt-3 text-sm italic text-muted">&ldquo;{reason}&rdquo;</p>}
      </div>

      {/* Wide content gets its own scroll container so the page itself never
          scrolls sideways on a phone. */}
      <div className="overflow-x-auto border-t border-border">
        <table className="w-full min-w-[34rem] text-sm">
          <caption className="sr-only">
            {symbol} factor scores, their published weights, and where each sits
            among covered peers
          </caption>
          <thead>
            <tr className="text-xs uppercase tracking-wide text-muted">
              <th scope="col" className="px-4 py-2 text-left font-normal">
                Factor
              </th>
              <th scope="col" className="px-4 py-2 text-right font-normal">
                Score
              </th>
              <th scope="col" className="px-4 py-2 text-right font-normal">
                Weight
              </th>
              <th scope="col" className="px-4 py-2 text-left font-normal">
                Among covered peers
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className="border-t border-border/60">
                <th scope="row" className="px-4 py-2 text-left font-normal text-muted">
                  {r.label}
                </th>
                <td className="nums px-4 py-2 text-right font-medium">
                  {r.value != null ? r.value.toFixed(0) : EMPTY}
                </td>
                {/* The published weight, straight off the API response. */}
                <td className="nums px-4 py-2 text-right text-muted">{r.weight}</td>
                <td className="px-4 py-2 text-left">
                  <RankingText ranking={r.ranking} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="border-t border-border p-4 text-xs text-subtle">
        Weights are the published formula and sum to 100. A percentile is
        computed only over tickers we actually hold a value for, and only where
        that peer group has at least {MIN_PEER_N} of them &mdash; below that a
        single peer moves the figure by more than three points, so we print the
        reason instead of a number. Fundamentals and smart money are the two
        thinnest factors in our coverage today, so they are the two most often
        unranked.{" "}
        <Link href="/how-it-works" className="text-accent hover:underline">
          How the score is built
        </Link>
      </p>
    </section>
  );
}

/**
 * A ranking, or the reason there isn't one.
 *
 * The refusal is styled as muted body text rather than as an error: for a
 * thinly-covered factor "not enough covered peers to rank" is the correct,
 * expected answer, not a failure.
 */
function RankingText({ ranking }: { ranking: Ranking }) {
  if (ranking.kind === "unranked") {
    return <span className="text-muted">{describeRanking(ranking)}</span>;
  }
  return (
    <span>
      <span className="nums font-medium">{ordinal(ranking.percentile)}</span>{" "}
      <span className="text-muted">
        percentile of {ranking.peerGroup} (n={ranking.n.toLocaleString("en-US")})
      </span>
    </span>
  );
}

/**
 * What the confidence figure means, as a hover title. Confidence is a
 * statement about OUR DATA COVERAGE for this ticker — how many of the scoring
 * inputs we actually hold — not a statement about the security. Copy carried
 * over unchanged from the score card this panel replaces.
 */
function confidenceLabel(c: number): string {
  if (c >= 95) return "Full data on every signal feature";
  if (c >= 80) return "Most features present, missing 1–3 minor data points";
  if (c >= 60) return "Core scoring data and most fundamentals — typical liquid stock";
  if (c >= 40) return "Only basic price and trend data held";
  return "Sparse data — few scoring inputs held for this ticker";
}

/**
 * Band colouring for the signal chip. The six band NAMES are the published
 * taxonomy (see /how-it-works); the tint is the same one the scanner uses, so
 * a reader who has learned the colours on one surface reads them on the other.
 */
function signalTone(signal: string): string {
  switch (signal) {
    case "HIGH CONVICTION":
      return "text-up bg-up/20";
    case "STRONG SETUP":
      return "text-up bg-up/10";
    case "CONSTRUCTIVE":
      return "text-accent bg-accent/10";
    case "NEUTRAL":
      return "text-muted bg-muted/20";
    case "CAUTION":
      return "text-warn bg-warn/10";
    default:
      return "text-down bg-down/10";
  }
}
