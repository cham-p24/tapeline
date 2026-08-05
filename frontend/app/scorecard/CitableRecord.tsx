import { citableSentence, type CitableSummary } from "@/lib/scorecardCitation";

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
export function CitableRecord({ summary }: { summary: CitableSummary }) {
  const sentence = citableSentence(summary);
  if (!sentence) return null;

  // The denominator the aggregates were computed over — scored rows minus
  // data-quality exclusions. Disclosed inline, same as the summary table.
  const n = Math.max(summary.entries_scored - summary.entries_excluded_outliers, 0);
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
      <dl className="mt-3 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
        <div className="flex justify-between gap-4 sm:justify-start">
          <dt className="text-muted">Market days tracked</dt>
          <dd className="nums font-medium text-fg">{summary.days_tracked}</dd>
        </div>
        <div className="flex justify-between gap-4 sm:justify-start">
          <dt className="text-muted">Entries logged</dt>
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
      <p className="mt-3 text-xs text-subtle">
        Descriptive measures of the raw archive below — not a return, a forecast, or the result of
        any investable strategy. At this sample size they do not distinguish the ranking from
        chance. Raw CSV and JSON are linked further down so the arithmetic is checkable off-site.
      </p>
    </section>
  );
}
