/**
 * Gaps, corrections and known limitations of the public record — the data
 * behind `KnownLimitations.tsx` on /scorecard.
 *
 * Integrity wave approved by the founder on 2026-09-14 (tickets T-05, T-29).
 * Before that date none of the following was stated on /scorecard:
 *   - the 15 June 2026 overwrite of 190 recorded scores (18 May – 12 June),
 *   - the four US trading days with no top 10,
 *   - the placeholder-factor defect, the inflated spreadsheet scores and the
 *     6–10 September factor refresh stall.
 *
 * RULES
 * 1. Every entry is dated and verified against the repository history or the
 *    production database. If something is not known (a cause, a start date),
 *    say it is not known. Never soften, never guess.
 * 2. Do not delete an entry because it is old. A limitation of past lists stays
 *    true of those lists.
 * 3. Missing sessions listed here are the ones VERIFIED on 2026-09-14. The
 *    page also merges the list the API computes from the rows
 *    (`summary.missing_sessions`), so a new gap appears without editing this
 *    file; a gap with no entry here is shown as "cause not yet documented".
 * 4. Keep in step with KNOWN_LIMITATIONS and RESTATEMENTS in
 *    backend/app/services/scorecard_export.py, which carry the same facts into
 *    the CSV/JSON download.
 */

export type MissingSession = {
  /** ISO date of the US trading session with no top 10. */
  date: string;
  /** What is known about why. */
  cause: string;
};

export const VERIFIED_MISSING_SESSIONS: MissingSession[] = [
  {
    date: "2026-08-31",
    cause: "Cause not established.",
  },
  {
    date: "2026-09-02",
    cause: "Cause not established.",
  },
  {
    date: "2026-09-04",
    cause: "Cause not established.",
  },
  {
    date: "2026-09-09",
    cause:
      "Our system stopped writing data at 15:36 UTC that day and did not recover before the daily list was due.",
  },
];

export type Correction = {
  /** Date the recorded values were changed (ISO). */
  date: string;
  /** Human date for the heading. */
  label: string;
  body: string;
};

/** Changes to values already recorded. Oldest first. */
export const CORRECTIONS: Correction[] = [
  {
    date: "2026-06-15",
    label: "15 June 2026",
    body:
      "Scores recorded for the 190 entries from 18 May to 12 June 2026 were capped at 100. A bug had stored values above 100, and each of those days' top 10 was ranked on those faulty values. The original values were not kept, so every score in that window now reads 100. The lists were not re-ranked. This was not disclosed until 14 September 2026.",
  },
  {
    date: "2026-08-25",
    label: "25 August 2026",
    body:
      "Recorded prices were restated on 684 of 688 entries, because they had been taken from after-hours trades instead of the official close. See the restatement note above.",
  },
];

export type Limitation = {
  /** Date the condition ended or was found (ISO). */
  date: string;
  period: string;
  body: string;
};

/** Conditions that affected past lists without changing any stored value. */
export const LIMITATIONS: Limitation[] = [
  {
    date: "2026-08-23",
    period: "Lists recorded before 24 August 2026",
    body:
      "After each restart of our system, tickers not covered by our scoring spreadsheet were scored from random placeholder factor values until the daily data pass ran. A list from this period could include names scored that way, and our stored data cannot show whether any was. Fixed on 23 August 2026.",
  },
  {
    date: "2026-09-06",
    period: "Lists recorded before 6 September 2026",
    body:
      "When measured on 6 September 2026, 77% of scored tickers had no reading for two of the six factors (fundamentals and insider activity), which then counted as neutral. The listed names were therefore drawn mostly from the tickers that did have readings.",
  },
  {
    date: "2026-09-07",
    period: "Lists recorded before 7 September 2026, from at least 24 August 2026",
    body:
      "Three renamed columns in our scoring spreadsheet were read as missing and scored as neutral, which made many spreadsheet-based scores too high. Corrected on 7 September 2026. Our stored score history starts on 24 August 2026, so the start of the problem is not known.",
  },
  {
    date: "2026-09-10",
    period: "6 to 10 September 2026",
    body:
      "The refresh of the trend, relative-strength and momentum inputs stalled, so those factors kept using price data fetched on 6 September. The list for 8 September 2026 was ranked while this was happening. Whether it had caught up before the 10 September list was recorded was not verified. Fixed on 10 September 2026.",
  },
  {
    date: "2026-09-14",
    period: "Entries from 22 May to 10 July 2026",
    body:
      "As of 14 September 2026, 32 entries from this period have no next-session back-check. Their result columns are blank rather than estimated, and they are not in the summary figures.",
  },
];

/** "2026-09-09" -> "9 September 2026". Deterministic, no locale APIs. */
export function formatIsoDate(iso: string): string {
  const MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ];
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
}

/**
 * The verified list merged with whatever the API computed from the rows.
 * Oldest first, no duplicates; an API-only date gets an honest placeholder
 * cause rather than a guessed one. Anything that is not a plain ISO date is
 * ignored.
 */
export function mergeMissingSessions(live: readonly string[] | null | undefined): MissingSession[] {
  const byDate = new Map<string, MissingSession>();
  for (const s of VERIFIED_MISSING_SESSIONS) byDate.set(s.date, s);
  for (const d of live ?? []) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d) || byDate.has(d)) continue;
    byDate.set(d, { date: d, cause: "Cause not yet documented." });
  }
  return [...byDate.values()].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}
