/**
 * Citation furniture for the public /t/[symbol] page.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * The ~3,500 per-ticker pages are the site's largest surface and produce no
 * unbranded AI citations at all; eleven /best-stocks-for/ pages produce all of
 * it. Looking at what the sources that DO get cited have in common, three
 * things were missing here and all three are cheap:
 *
 *   1. A dated restatement of the number in SENTENCE form. A model can quote a
 *      sentence. It cannot quote a table cell, and the score on this page lived
 *      only as a 6xl numeral next to a label.
 *   2. A visible "Updated <date>" alongside a machine-readable `dateModified`,
 *      so a reader and a crawler get the same freshness statement.
 *   3. The company NAME in the heading. The h1 was the bare ticker, which is
 *      close to unquotable — "AAPL" alone identifies nothing to a reader who
 *      arrived from a search for Apple.
 *
 * THE DATE IS THE SCORE'S OWN, NEVER RENDER TIME
 * ----------------------------------------------
 * Every function here takes `updatedAt` — `Ticker.updated_at`, the instant the
 * composite was last computed — and returns un-dated prose when it is absent.
 * `new Date()` would be a lie: this route is ISR'd hourly, so a render-time
 * stamp would tell a crawler each page was freshly measured when in fact only
 * the cache had turned over.
 *
 * COMPLIANCE (docs/COMPLIANCE_COPY_RULES.md)
 * ------------------------------------------
 * R1/R2: every sentence here states what was MEASURED and when. No adjective
 * is applied to the security, no expectation is expressed, nothing is implied
 * about what the price does next. The band names (HIGH CONVICTION, STRONG
 * SETUP, …) are score-range labels and are described as exactly that.
 */

/** The descriptive score bands, and the range each one names. */
const BANDS: Record<string, string> = {
  "HIGH CONVICTION": "85 to 100",
  "STRONG SETUP": "70 to 84",
  CONSTRUCTIVE: "55 to 69",
  NEUTRAL: "40 to 54",
  CAUTION: "25 to 39",
  WEAK: "0 to 24",
};

/**
 * "7 September 2026" — UTC, en-GB, day-month-year.
 *
 * Fixed locale and fixed time zone on purpose. This string is server-rendered
 * into a cached page that every visitor shares, so it must not depend on who
 * asked or where the renderer runs; and the whole product's day boundary is
 * UTC (the look-up meter's reset, the scorecard freeze, the news window).
 *
 * Returns null for a missing or unparseable stamp, which every caller treats
 * as "say nothing about freshness" rather than "substitute today".
 */
export function formatUpdatedDay(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(d);
}

/**
 * The page heading: company name plus ticker, or the bare ticker when the name
 * we hold is a placeholder.
 *
 * `_is_placeholder_name` on the backend fills `name` with the symbol itself for
 * tickers discovery has found but the profile backfill has not reached yet.
 * Rendering that verbatim would give "AAPL (AAPL)", so the symbol-equals-name
 * case falls back to the symbol alone.
 */
export function headingFor(symbol: string, name: string | null | undefined): string {
  const sym = symbol.toUpperCase();
  const trimmed = (name ?? "").trim();
  if (!trimmed || trimmed.toUpperCase() === sym) return sym;
  return `${trimmed} (${sym})`;
}

export type ScoreRestatementArgs = {
  symbol: string;
  name: string | null;
  score: number | null;
  signal: string | null;
  /** ISO-8601 `Ticker.updated_at`. Null → the prose carries no date. */
  updatedAt: string | null;
};

/**
 * The score, restated as prose a model can lift whole.
 *
 * Deliberately one self-contained passage: it names the company AND the ticker,
 * the number AND its denominator, the band AND the range that band means, and
 * the date the reading was taken. Quoted out of context it stays true and stays
 * attributable, which is the entire point of writing it as a sentence.
 */
export function buildScoreRestatement(a: ScoreRestatementArgs): string {
  const sym = a.symbol.toUpperCase();
  const subject = headingFor(sym, a.name);
  const day = formatUpdatedDay(a.updatedAt);
  const asOf = day ? `As of ${day}, ` : "";

  if (a.score == null) {
    const tail = day
      ? `Tapeline held no six-factor composite score for ${subject} when this page was last measured, on ${day}.`
      : `Tapeline holds no six-factor composite score for ${subject} right now.`;
    return `${tail} The six factors are trend, relative strength, fundamentals, smart money, macro and momentum; a score appears once enough of them have data for this ticker.`;
  }

  const value = a.score.toFixed(0);
  const label = (a.signal ?? "").trim();
  const range = BANDS[label.toUpperCase()];

  const first =
    label && range
      ? `${asOf}${subject} scores ${value} out of 100 on the Tapeline six-factor composite, which puts it in the ${label} band — the descriptive name for scores of ${range}.`
      : `${asOf}${subject} scores ${value} out of 100 on the Tapeline six-factor composite.`;

  const second =
    `The composite blends six named factors — trend, relative strength, fundamentals, smart money, ` +
    `macro and momentum — each normalised to 0-100. It records what those measurements read ` +
    `${day ? `on ${day}` : "at the most recent scoring tick"}, and it is not investment advice.`;

  return `${first} ${second}`;
}

/**
 * The Premium-gated counts the backend reports for this symbol.
 * Mirrors the `gated_counts` block in backend/app/routers/ticker.py.
 *
 * Null means the count read degraded — NOT "there is nothing". A present block
 * with 0 is the "we looked, there are none" case.
 */
export type GatedCounts = {
  insider_form4?: number | null;
  insider_form4_window_days?: number | null;
} | null;

export type CountedLock = { key: string; text: string };

/**
 * Turn the counts into the lines the page renders — one per dataset that
 * actually holds rows for this ticker.
 *
 * TWO RULES, BOTH LOAD-BEARING:
 *
 *   • A line is emitted ONLY where the count is above zero. "0 Form 4 filings
 *     — Premium" advertises an empty drawer, and a padlock over nothing is
 *     what made the old locked surfaces read as dishonest.
 *
 *   • These lines are NEVER a substitute for a factor's em-dash. Two of the six
 *     factors are unfilled for most tickers (docs/TODO.md 9e/9f) and that dash
 *     means MISSING DATA. Dressing a data gap as a paywall would claim we hold
 *     something we do not. The caller renders these in their own block, well
 *     away from the factor table.
 *
 * There is deliberately no congressional line: `congress_trades` in production
 * is a fabricated backlog (see workers/signal_publisher.py), so the backend
 * does not publish a count for it and neither does this.
 */
export function countedLocks(counts: GatedCounts): CountedLock[] {
  if (!counts) return [];
  const out: CountedLock[] = [];
  const form4 = counts.insider_form4;
  const window = counts.insider_form4_window_days;
  if (typeof form4 === "number" && form4 > 0 && typeof window === "number" && window > 0) {
    out.push({
      key: "insider_form4",
      text: `${form4.toLocaleString("en-US")} SEC Form 4 insider filing${form4 === 1 ? "" : "s"} in the last ${window} days`,
    });
  }
  return out;
}
