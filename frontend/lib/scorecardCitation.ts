/**
 * The one-sentence citable form of the public scorecard summary.
 *
 * WHY THIS EXISTS: a real converting Premium-trial signup arrived referred by
 * Microsoft Copilot, and the AI answer engines behind that channel (GPTBot,
 * PerplexityBot, OAI-SearchBot, bingbot) do not execute JavaScript. The
 * scorecard's headline facts were fetched client-side, so the single most
 * quotable fact about Tapeline — the N-day, M-entry public record — was
 * invisible to every one of them. This helper produces the plain-text
 * sentence the server component renders into static HTML.
 *
 * COMPLIANCE
 *   - Rule 3: the vs-SPY figure is permitted in body text / data sections
 *     with the sample disclosed — never in the H1, <title> or meta
 *     description. Callers must keep the sentence in body copy.
 *   - Wording is descriptive ("beat SPY the next session" names the metric's
 *     definition — the share of entries whose next-day return exceeded
 *     SPY's), states the sample, and claims nothing forward-looking.
 *   - Formatting is deterministic (no locale-dependent APIs) so the server
 *     render is stable across environments.
 */

export type CitableSummary = {
  days_tracked: number;
  entries_scored: number;
  entries_excluded_outliers: number;
  median_alpha_vs_spy: number | null;
  hit_rate_beat_spy: number | null;
  first_tracked_date?: string | null;
};

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

/** "2026-05-12" → "12 May 2026". Null for anything that isn't a plain ISO date. */
export function formatTrackedSince(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return null;
  const month = Number(m[2]);
  const day = Number(m[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  return `${day} ${MONTHS[month - 1]} ${m[1]}`;
}

/**
 * "Across 610 logged top-10 picks over 62 market days since 12 May 2026,
 * 51.3% beat SPY the next session."
 *
 * Null when the record has nothing back-checked yet — the caller renders
 * nothing rather than an empty claim.
 */
export function citableSentence(summary: CitableSummary): string | null {
  const { days_tracked, entries_scored, hit_rate_beat_spy } = summary;
  if (!days_tracked || !entries_scored || hit_rate_beat_spy == null) return null;
  const since = formatTrackedSince(summary.first_tracked_date);
  const sinceClause = since ? ` since ${since}` : "";
  return (
    `Across ${entries_scored} logged top-10 picks over ${days_tracked} market days${sinceClause}, ` +
    `${hit_rate_beat_spy.toFixed(1)}% beat SPY the next session.`
  );
}
