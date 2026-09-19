/**
 * Gaps, corrections and known limitations of the public record — the data
 * behind `KnownLimitations.tsx` on /scorecard.
 *
 * Integrity wave approved by the founder on 2026-09-14 (tickets T-05, T-29).
 * Before that date none of the following was stated on /scorecard:
 *   - the 15 June 2026 cap of recorded scores above 100 (all 190 entries from
 *     18 May – 12 June now read 100; which of them changed is unknown),
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

/**
 * The day the list below was last verified against production, as it is
 * printed in copy ("When we checked on …"). Update it together with
 * VERIFIED_MISSING_SESSIONS so a count and its date cannot drift apart.
 */
export const VERIFIED_MISSING_SESSIONS_CHECKED_ON = "14 September 2026";

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

/**
 * The verified missing sessions as one phrase, e.g. "31 August, 2 September,
 * 4 September and 9 September 2026". For copy outside /scorecard that has to
 * name the gaps where it describes the daily list (#842 follow-up,
 * 2026-09-17). Derived from the list above so the two cannot disagree; the
 * year is printed once when every date shares it.
 */
export function verifiedMissingSessionsLabel(
  sessions: readonly MissingSession[] = VERIFIED_MISSING_SESSIONS,
): string {
  const dates = sessions.map((s) => new Date(`${s.date}T00:00:00Z`));
  const oneYear = new Set(dates.map((d) => d.getUTCFullYear())).size === 1;
  const parts = dates.map((d) =>
    d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "long",
      ...(oneYear ? {} : { year: "numeric" }),
      timeZone: "UTC",
    }),
  );
  const joined =
    parts.length <= 1 ? parts.join("") : `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
  return oneYear && dates.length > 0 ? `${joined} ${dates[0].getUTCFullYear()}` : joined;
}

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
      "A database change set every recorded score above 100 to 100 and kept no copy of the originals. All 190 entries from 18 May to 12 June 2026 now read 100. Scores of 120 to 137 had been verified in entries from 22 May to 5 June, and until a fix on 9 June 2026 the daily top 10 could be ranked on such scores. Because the originals were not kept, we cannot tell which of the 190 entries were changed or by how much. The lists were not re-ranked. This was not disclosed until 14 September 2026.",
  },
  {
    date: "2026-08-25",
    label: "25 August 2026",
    body:
      "Recorded prices were restated on 684 of the 688 entries for sessions up to 21 August 2026, because they had been taken from after-hours trades instead of the official close. The other 4 were left as first recorded. The list for 24 August 2026 was not part of this restatement and still uses the after-hours prices (see below). See the restatement note above.",
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
    date: "2026-06-23",
    period: "The list for 23 June 2026",
    body:
      "One listed name is not a common stock. BHFAO is Brighthouse Financial's 6.75% non-cumulative preferred depositary shares, and it was listed fourth. Preferred shares, notes and similar listings are scored on the same six factors as common stock, and nothing made one ineligible to be listed. Checked on 17 September 2026 across all 439 symbols ever listed; it is the only one. Stated, not corrected: the list stands as recorded. From 19 September 2026 (#875), listings detected as not common stock (notes, preferred and depositary shares, warrants, rights and units) can no longer be listed. Detection is by name and symbol and does not catch every one. Three preferred listings stay eligible on purpose, PBR.A, CIG and BBD, each its company's main traded share; exchange-traded notes, which are held as funds, are not covered.",
  },
  {
    date: "2026-08-23",
    period: "Lists recorded before 24 August 2026",
    body:
      "After each restart of our system, tickers not covered by our scoring spreadsheet were scored from random placeholder factor values until the daily data pass ran. A list from this period could include names scored that way, and our stored data cannot show whether any was. Fixed on 23 August 2026.",
  },
  {
    date: "2026-08-25",
    period: "The list for 24 August 2026",
    body:
      "This list was recorded shortly before we switched to official closing prices, and it was not included in the 25 August 2026 restatement. Its prices at flag still come from the last trade including after-hours trading. For 7 of its 10 entries that price differs from the official close, by 0.08% to 1.36%, so their results are not on the official-close basis either. Not corrected.",
  },
  {
    date: "2026-09-06",
    period: "All lists to date",
    body:
      "When measured on 6 September 2026, 5,697 of 7,417 scored tickers (77%) had no reading for two of the six factors (fundamentals and insider activity), which then counted as neutral, so the listed names were drawn mostly from the tickers that did have readings. Changes merged on 6 September 2026 (#762) and 7 September 2026 (#775). Coverage is still incomplete: on 14 September 2026, 6,092 of 11,649 scored tickers had neither reading.",
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
  {
    date: "2026-09-14",
    period: "Entries from 24 August to 11 September 2026 (16 entries)",
    body:
      "16 entries were ranked while the ticker held a Smart Money value with no SEC Form 4 filing on file: BBH on 24, 25, 26 and 28 August and 1, 3 and 8 September; BBP on 25, 26 and 28 August and 1 September; BIB on 26 August and 1 September; PLX on 8, 10 and 11 September. The same tickers appear in 7 earlier entries (BBH on 19 and 21 August, BBP on 20 August, BIB on 7, 12, 13 and 20 August), where whether they held such a value cannot be checked. At 13:30 UTC on 14 September 2026, 856 tickers held such a value: 629 ETFs, 222 stocks and 5 commodity futures contracts. 42 of those values were below 10 or above 90, which the Form 4 calculation cannot produce. Where the values came from has not been established. From 14 September 2026 (#824) an empty Form 4 answer removes the value, unless a filing we already hold from that source records a transaction in the last 80 days, and such tickers become due for a re-check at the next daily run, ahead of other Smart Money re-checks (#833). Lists not changed.",
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
