import {
  citableSentence,
  formatTrackedSince,
  loggedCount,
  type CitableSummary,
} from "@/lib/scorecardCitation";

/**
 * The headline stats of the archive as STATIC server-rendered HTML.
 *
 * This is the block AI answer engines actually read. GPTBot, PerplexityBot,
 * OAI-SearchBot and bingbot (Copilot) do not execute JavaScript, so anything
 * fetched client-side does not exist for them. The page's server component
 * fetches the summary at build/revalidate time and renders it here as plain
 * text — one citable sentence plus a compact definition list.
 *
 * COMPLIANCE
 *   - Rule 3: the vs-SPY figure appears in body text and a neutral data list
 *     with the sample size disclosed — never in the H1, <title> or meta
 *     description (those live in layout.tsx and stay mechanism-only). No
 *     colour, no arrow, no hero-stat framing; a losing number would render
 *     at identical weight and size.
 *   - Rule 4: every value is a raw count or a plain central-tendency measure
 *     of raw rows. Nothing derived, compounded or annualised.
 */
/**
 * The /api/scorecard summary as this page reads it: the citable fields plus
 * the disclosure fields added 2026-09-14. All optional, because a cached
 * response from before they existed will not carry them.
 */
export type ScorecardSummary = CitableSummary & {
  /** US trading days in the record's range with no top 10 (ISO dates). */
  missing_sessions?: string[] | null;
  /** Newest session the public CSV/JSON download includes (ISO date). */
  export_cutoff?: string | null;
  /** How many of the n rows behind the figures are newer than the download. */
  entries_scored_after_export_cutoff?: number | null;
};

/**
 * T-06: the figures here are computed over every back-checked entry, but the
 * download stops at the publication-delay cutoff. Without this line a reader
 * who recomputes the share from the CSV gets a different n and a different
 * percentage and reasonably concludes the page is wrong. Null when there is
 * no difference to explain or the API did not say.
 */
export function downloadDifferenceNote(summary: ScorecardSummary, n: number): string | null {
  const k = summary.entries_scored_after_export_cutoff;
  const cutoff = summary.export_cutoff;
  if (typeof k !== "number" || k <= 0 || !cutoff) return null;
  const since = formatTrackedSince(cutoff) ?? cutoff;
  return (
    `These figures include ${k} back-checked ${k === 1 ? "entry" : "entries"} newer than the download ` +
    `(which runs to sessions on or before ${since}), so recomputing them from the download uses n = ${Math.max(n - k, 0)}, ` +
    `not ${n}.`
  );
}

export function CitableRecord({ summary }: { summary: ScorecardSummary }) {
  const sentence = citableSentence(summary);
  if (!sentence) return null;

  // The denominator the aggregates were computed over — scored rows minus
  // data-quality exclusions. Disclosed inline, same as the summary table.
  const n = Math.max(summary.entries_scored - summary.entries_excluded_outliers, 0);
  const downloadNote = downloadDifferenceNote(summary, n);
  const logged = loggedCount(summary);
  const median =
    summary.median_alpha_vs_spy == null
      ? "—"
      : `${summary.median_alpha_vs_spy >= 0 ? "+" : ""}${summary.median_alpha_vs_spy.toFixed(2)}%`;
  const hit = summary.hit_rate_beat_spy == null ? "—" : `${summary.hit_rate_beat_spy.toFixed(1)}%`;

  return (
    <section className="mt-8 rounded-lg border border-border bg-panel/40 p-5">
      <h2 className="text-sm font-medium uppercase tracking-wide text-muted">
        The record so far
      </h2>
      <p className="mt-2 max-w-3xl text-sm leading-relaxed text-fg">{sentence}</p>
      {/* Order: h2, citable sentence, THEN this sample-size caveat, THEN the
          numbers. The qualifier has to frame the vs-SPY figures rather than
          trail them: at this sample size they do not distinguish the ranking
          from chance, so the reader meets the caveat before the values, not
          after. Nothing is hidden, softened or rounded — the same values
          follow, unrounded, at the same weight. */}
      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">
        Descriptive measures of the raw archive below — not a return, a forecast, or the result of
        any investable strategy. At this sample size they do not distinguish the ranking from
        chance. Raw CSV and JSON are linked further down so the arithmetic is checkable off-site.
      </p>
      <dl className="mt-3 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
        <div className="flex justify-between gap-4 sm:justify-start">
          <dt className="text-muted">Market days tracked</dt>
          <dd className="nums font-medium text-fg">{summary.days_tracked}</dd>
        </div>
        {/* Two rows, not one. The old single "Entries logged" row printed
            entries_scored — the back-checked subset — so the count shown was
            smaller than the number of picks actually published. */}
        {logged != null && logged > summary.entries_scored && (
          <div className="flex justify-between gap-4 sm:justify-start">
            <dt className="text-muted">Entries logged</dt>
            <dd className="nums font-medium text-fg">{logged}</dd>
          </div>
        )}
        <div className="flex justify-between gap-4 sm:justify-start">
          <dt className="text-muted">Entries back-checked</dt>
          <dd className="nums font-medium text-fg">{summary.entries_scored}</dd>
        </div>
        <div className="flex justify-between gap-4 sm:justify-start">
          <dt className="text-muted">Share that beat SPY next session (n = {n})</dt>
          <dd className="nums font-medium text-fg">{hit}</dd>
        </div>
        <div className="flex justify-between gap-4 sm:justify-start">
          <dt className="text-muted">Median 1-day change minus SPY (n = {n})</dt>
          <dd className="nums font-medium text-fg">{median}</dd>
        </div>
      </dl>
      {downloadNote && (
        <p className="mt-3 max-w-3xl text-xs leading-relaxed text-muted">{downloadNote}</p>
      )}
    </section>
  );
}
