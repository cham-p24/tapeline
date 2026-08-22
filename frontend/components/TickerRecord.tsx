"use client";

import Link from "next/link";
import { userLocale } from "@/lib/datetime";

/**
 * "On our record" — every time Tapeline has flagged this ticker, and what
 * happened next.
 *
 * WHY THIS BLOCK EXISTS
 * ---------------------
 * Yahoo, StockAnalysis, Simply Wall St, WallStreetZen, Koyfin, Stock Rover,
 * Zacks, TipRanks and Morningstar all converge on the same grammar — a number,
 * located against a peer group. Not one of them publishes what its own calls
 * did next. That is the only thing on this page a rival cannot copy by adding
 * a data feed, so it sits directly under the score rather than at the bottom.
 *
 * WHAT A "FLAG" IS, EXACTLY
 * -------------------------
 * A session on which this ticker appeared in our published daily top-10. The
 * row is frozen when it is written and never edited afterwards, which is what
 * makes the archive auditable. The outcome attached to it is the NEXT SESSION
 * ONLY — the single trading day after the flag — measured against SPY over the
 * same day. Nothing here tracks a longer horizon, and the copy says so in as
 * many words, because a reader who assumes otherwise is being misled by
 * omission.
 *
 * THE THREE STATES, AND WHY THE THIRD IS NOT AN ERROR
 * --------------------------------------------------
 *   1. flags > 0        → the summary line plus the full table.
 *   2. flags === 0      → "Tapeline has never flagged {SYMBOL}." This is the
 *                         COMMON case: roughly 408 of ~8,900 scored symbols
 *                         have ever been flagged, so ~8,400 land here. It is
 *                         rendered as a first-class, calm statement — no warning
 *                         colour, no empty-table skeleton, nothing that reads
 *                         as breakage.
 *   3. no record block  → renders NOTHING AT ALL. If the payload never carried
 *                         a record we have not been told this ticker was never
 *                         flagged; printing "never flagged" would be inventing
 *                         a fact from an absence. Silence is the only honest
 *                         render, and it is also what keeps the page correct
 *                         during a frontend-ahead-of-backend deploy.
 *
 * LOSSES ARE NEVER FILTERED. Every flag we hold is listed, most recent first,
 * including the ones that lost, and a losing row gets the same type size and
 * weight as a winning one (docs/COMPLIANCE_COPY_RULES.md Rule 3 — the record
 * is presented as a neutral data table with n disclosed, never hero-statted).
 * Rule 3 also forbids the vs-SPY figure in any headline slot, so the heading
 * here carries no number and there is no cumulative-return chart anywhere.
 *
 * NOTHING IS DERIVED. The counts come from the API's own summary. Where the
 * summary omits one it renders as an em-dash — it is never recomputed from the
 * rows, because the rows can be delayed or truncated by tier and a count taken
 * from a partial list would be a fabricated statistic (Rule 4).
 */

/** The single, deliberate rendering of "we do not hold this value". */
const EMPTY = "—";

/** One frozen flag. Mirrors the public scorecard's row shape. */
export type TickerRecordRow = {
  as_of: string;
  score_at_flag: number | null;
  price_at_flag: number | null;
  price_next_day: number | null;
  change_pct_1d_after: number | null;
  spy_change_pct_1d: number | null;
  alpha_vs_spy: number | null;
};

/** What the block prints above the table, after normalisation. */
export type TickerRecordSummary = {
  flags: number | null;
  resolved: number | null;
  beatSpy: number | null;
  hitRate: number | null;
  medianAlpha: number | null;
  /** 0 = this viewer sees live rows. >0 = rows are held back that many days. */
  delayDays: number | null;
  /** How many recent flags the delay is withholding from the row list. */
  hiddenRecent: number | null;
  /** True when the row list is capped rather than complete. */
  truncated: boolean;
  /**
   * Resolved rows whose 1-day move is large enough that we ourselves treat the
   * vendor close as suspect (unadjusted splits produce market-impossible
   * moves). Counted and disclosed rather than dropped — this block's whole
   * claim is that nothing is filtered out of it.
   */
  suspectOutliers: number | null;
  suspectThresholdPct: number | null;
};

function isRecordObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function num(src: Record<string, unknown>, keys: string[]): number | null {
  for (const k of keys) {
    const v = src[k];
    if (typeof v === "number" && Number.isFinite(v)) return v;
  }
  return null;
}

/**
 * The API's record block → summary + rows, or null when there is no block.
 *
 * Field aliases are accepted for the same reason components/percentiles.ts
 * accepts them: this block and the page were built in the same change, and a
 * rename must degrade to "render nothing" rather than to a confident wrong
 * statement. A flat block (counts at the top level) and a nested one
 * (`summary: {...}`) both parse.
 */
export function normalizeRecord(
  raw: unknown,
): { summary: TickerRecordSummary; rows: TickerRecordRow[] } | null {
  if (!isRecordObj(raw)) return null;
  const s = isRecordObj(raw.summary) ? raw.summary : raw;

  const rawRows =
    (Array.isArray(raw.rows) && raw.rows) ||
    (Array.isArray(raw.flags) && raw.flags) ||
    (Array.isArray(raw.entries) && raw.entries) ||
    (Array.isArray(raw.items) && raw.items) ||
    [];

  const rows: TickerRecordRow[] = rawRows
    .filter(isRecordObj)
    .map((r) => ({
      as_of: typeof r.as_of === "string" ? r.as_of : typeof r.date === "string" ? r.date : "",
      score_at_flag: num(r, ["score_at_flag", "score"]),
      price_at_flag: num(r, ["price_at_flag", "price"]),
      price_next_day: num(r, ["price_next_day"]),
      change_pct_1d_after: num(r, ["change_pct_1d_after", "return_pct_1d"]),
      spy_change_pct_1d: num(r, ["spy_change_pct_1d", "spy_return_pct_1d"]),
      alpha_vs_spy: num(r, ["alpha_vs_spy", "alpha"]),
    }))
    .filter((r) => r.as_of !== "")
    // Most recent first. Sorted here rather than trusted from the payload so
    // the reading order is the same whatever order the API happens to send.
    .sort((a, b) => (a.as_of < b.as_of ? 1 : a.as_of > b.as_of ? -1 : 0));

  const summary: TickerRecordSummary = {
    flags: num(s, ["flag_count", "flags_count", "appearances", "times_flagged", "count"]),
    resolved: num(s, [
      "resolved_count",
      "resolved",
      "appearances_scored",
      "entries_scored",
      "scored",
    ]),
    beatSpy: num(s, ["beat_spy_count", "beat_spy", "beats", "wins"]),
    hitRate: num(s, ["hit_rate_beat_spy", "beat_spy_rate", "hit_rate"]),
    medianAlpha: num(s, ["median_alpha_vs_spy", "median_alpha"]),
    delayDays: num(s, ["flags_delay_days", "delay_days"]),
    hiddenRecent: num(s, ["flags_hidden_recent", "hidden_recent"]),
    truncated: s.flags_truncated === true,
    suspectOutliers: num(s, ["suspect_outlier_count"]),
    suspectThresholdPct: num(s, ["suspect_outlier_threshold_pct"]),
  };

  // No count AND no rows: we have been told nothing about this ticker's
  // record, which is not the same as being told it has none.
  if (summary.flags == null && rows.length === 0) return null;

  return { summary, rows };
}

export function TickerRecord({ symbol, record }: { symbol: string; record: unknown }) {
  const parsed = normalizeRecord(record);
  if (!parsed) return null;

  const { summary, rows } = parsed;
  const neverFlagged = summary.flags === 0 && rows.length === 0;

  return (
    <section className="card" aria-labelledby="ticker-record-heading">
      <div className="border-b border-border p-4">
        <h2 id="ticker-record-heading" className="font-semibold">
          On our record
        </h2>
        <p className="mt-0.5 text-xs text-muted">
          Every session {symbol} has appeared in our published daily top-10, and
          what the next session did. Rows are frozen when written and never
          edited.
        </p>
      </div>

      {neverFlagged ? (
        <div className="p-4">
          <p className="text-sm font-medium">
            Tapeline has never flagged {symbol}.
          </p>
          <p className="mt-2 max-w-2xl text-sm text-muted">
            A flag is a day this ticker appeared in the published daily top-10.
            Only a few hundred of the ~8,900 symbols we score have ever appeared,
            so this is the ordinary answer for most tickers &mdash; it does not
            mean anything is missing. {symbol} still carries a live score and
            factor breakdown above.
          </p>
          <p className="mt-3 text-sm">
            <Link href="/scorecard" className="text-accent hover:underline">
              See the tickers we have flagged
            </Link>
          </p>
        </div>
      ) : (
        <>
          <div className="p-4">
            {/* Headline counts. Definition list: these are label/value pairs,
                not a table. */}
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
              <Headline label="Times flagged" value={fmtCount(summary.flags)} />
              <Headline label="Resolved" value={fmtCount(summary.resolved)} />
              <Headline label="Beat SPY next session" value={fmtBeat(summary)} />
              <Headline
                label="Median alpha vs SPY"
                value={fmtSignedPct(summary.medianAlpha)}
              />
            </dl>
            <p className="mt-3 max-w-3xl text-xs text-muted">
              &ldquo;Resolved&rdquo; means the next session has closed and its
              return is known; the rest are still pending. Alpha is that single
              next session&rsquo;s return minus SPY&rsquo;s over the same day.{" "}
              <strong className="font-medium text-fg">
                The horizon is one session.
              </strong>{" "}
              Nothing here tracks what happened a week or a month later.{" "}
              {/* Only claim completeness when the list actually is complete —
                  the delay and the cap are disclosed on their own lines
                  below, and this sentence must not contradict them. */}
              {listIsComplete(summary)
                ? "Every flag is listed below, including the ones that lost."
                : "No flag is filtered out for having lost; the note below says which are held back."}
            </p>
            {/* What the row list below is NOT showing, stated rather than
                left to look like an empty record. The counts above always
                cover every flag; only the row list is held back. */}
            {summary.delayDays != null && summary.delayDays > 0 && (
              <p className="mt-3 text-xs text-muted">
                Rows below are held back {summary.delayDays} days on your plan
                {summary.hiddenRecent != null && summary.hiddenRecent > 0
                  ? `, which hides the ${summary.hiddenRecent} most recent`
                  : ""}
                . The counts above cover every flag, held-back ones included.{" "}
                <Link href="/pricing" className="text-accent hover:underline">
                  Compare plans
                </Link>
              </p>
            )}
            {summary.truncated && (
              <p className="mt-2 text-xs text-muted">
                Only the most recent flags are listed here.{" "}
                <Link
                  href={`/scorecard/${encodeURIComponent(symbol)}`}
                  className="text-accent hover:underline"
                >
                  The full history is on the scorecard
                </Link>
                .
              </p>
            )}
            {/* Suspect prints are COUNTED, never dropped. A reader deserves to
                know when a figure leans on a close we ourselves distrust. */}
            {summary.suspectOutliers != null && summary.suspectOutliers > 0 && (
              <p className="mt-2 text-xs text-muted">
                {summary.suspectOutliers} resolved{" "}
                {summary.suspectOutliers === 1 ? "session moves" : "sessions move"}{" "}
                more than{" "}
                {summary.suspectThresholdPct != null
                  ? `${summary.suspectThresholdPct}%`
                  : "our review threshold"}{" "}
                in a day, which usually means an unadjusted vendor close rather
                than a real move. They are counted in the figures above and
                listed below rather than removed.
              </p>
            )}
          </div>

          {/* Wide content scrolls inside its own container so the page never
              scrolls sideways. */}
          <div className="overflow-x-auto border-t border-border">
            <table className="w-full min-w-[36rem] text-sm">
              <caption className="sr-only">
                Every session {symbol} was flagged, most recent first, with the
                next session&rsquo;s return against SPY
              </caption>
              <thead>
                <tr className="text-xs uppercase tracking-wide text-muted">
                  <th scope="col" className="px-4 py-2 text-left font-normal">
                    Session flagged
                  </th>
                  <th scope="col" className="px-4 py-2 text-right font-normal">
                    Score
                  </th>
                  <th scope="col" className="px-4 py-2 text-right font-normal">
                    Price
                  </th>
                  <th scope="col" className="px-4 py-2 text-right font-normal">
                    Next session
                  </th>
                  <th scope="col" className="px-4 py-2 text-right font-normal">
                    SPY
                  </th>
                  <th scope="col" className="px-4 py-2 text-right font-normal">
                    Alpha
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr className="border-t border-border/60">
                    <td colSpan={6} className="px-4 py-3 text-sm text-muted">
                      No individual rows are available to show.
                    </td>
                  </tr>
                )}
                {rows.map((r) => (
                  <tr key={r.as_of} className="border-t border-border/60">
                    <th
                      scope="row"
                      className="whitespace-nowrap px-4 py-2 text-left font-normal text-muted"
                    >
                      {fmtDate(r.as_of)}
                    </th>
                    <td className="nums px-4 py-2 text-right">
                      {r.score_at_flag != null ? r.score_at_flag.toFixed(1) : EMPTY}
                    </td>
                    <td className="nums px-4 py-2 text-right text-muted">
                      {r.price_at_flag != null ? `$${r.price_at_flag.toFixed(2)}` : EMPTY}
                    </td>
                    {/* Winning and losing sessions get identical type size and
                        weight; only the hue differs, and it is applied
                        symmetrically. Rule 3. */}
                    <td className={`nums px-4 py-2 text-right ${tone(r.change_pct_1d_after)}`}>
                      {r.change_pct_1d_after != null
                        ? fmtSignedPct(r.change_pct_1d_after)
                        : "pending"}
                    </td>
                    <td className="nums px-4 py-2 text-right text-muted">
                      {r.spy_change_pct_1d != null ? fmtSignedPct(r.spy_change_pct_1d) : EMPTY}
                    </td>
                    <td className={`nums px-4 py-2 text-right ${tone(r.alpha_vs_spy)}`}>
                      {fmtSignedPct(r.alpha_vs_spy)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="border-t border-border p-4 text-xs text-subtle">
            <Link
              href={`/scorecard/${encodeURIComponent(symbol)}`}
              className="text-accent hover:underline"
            >
              {symbol} on the public scorecard
            </Link>{" "}
            &middot;{" "}
            <Link href="/scorecard" className="text-accent hover:underline">
              The whole published record
            </Link>
          </p>
        </>
      )}
    </section>
  );
}

/**
 * True when the row list below really is every flag we hold — nothing withheld
 * by the tier delay and nothing cut by the serialisation cap. Only then may
 * the copy claim completeness.
 */
function listIsComplete(s: TickerRecordSummary): boolean {
  if (s.truncated) return false;
  if (s.hiddenRecent != null && s.hiddenRecent > 0) return false;
  if (s.delayDays != null && s.delayDays > 0) return false;
  return true;
}

function Headline({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="nums mt-0.5 text-lg font-semibold">{value}</dd>
    </div>
  );
}

/** Equal-prominence hue for a signed figure. Never a weight or size change. */
function tone(v: number | null): string {
  if (v == null) return "text-muted";
  return v > 0 ? "text-up" : v < 0 ? "text-down" : "";
}

function fmtCount(v: number | null): string {
  if (v == null) return EMPTY;
  return Math.round(v).toLocaleString("en-US");
}

/** "+0.42%" / "-0.42%". Signed, because the sign IS the information. */
function fmtSignedPct(v: number | null): string {
  if (v == null) return EMPTY;
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

/**
 * "3 of 6" when both counts are given; the rate alone when only the rate is.
 * Never the count back-derived from the rate — rounding a rate into a count
 * would publish a number nobody counted.
 */
function fmtBeat(s: TickerRecordSummary): string {
  if (s.beatSpy != null && s.resolved != null) {
    const pct = s.hitRate != null ? ` (${s.hitRate.toFixed(0)}%)` : "";
    return `${fmtCount(s.beatSpy)} of ${fmtCount(s.resolved)}${pct}`;
  }
  if (s.hitRate != null && s.resolved != null) {
    return `${s.hitRate.toFixed(0)}% of ${fmtCount(s.resolved)}`;
  }
  if (s.hitRate != null) return `${s.hitRate.toFixed(0)}%`;
  if (s.beatSpy != null) return fmtCount(s.beatSpy);
  return EMPTY;
}

/**
 * "14 Aug 2026" from a bare YYYY-MM-DD. Parsed part-by-part into a LOCAL date:
 * `new Date("2026-08-14")` is midnight UTC and renders as the 13th for every
 * reader west of Greenwich. Same treatment as KeyStatistics.fmtDate.
 */
function fmtDate(v: string): string {
  const parts = v.slice(0, 10).split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return v;
  const [y, m, d] = parts;
  const parsed = new Date(y, m - 1, d);
  if (Number.isNaN(parsed.getTime())) return v;
  return parsed.toLocaleDateString(userLocale(), {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
