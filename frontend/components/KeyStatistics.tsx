"use client";

import { userLocale } from "@/lib/datetime";

/**
 * Key statistics — the market fields, after the score panel and the record.
 *
 * WHAT CHANGED, AND WHY
 * ---------------------
 * This block used to be a flat grid of twelve equally-weighted figures. A
 * competitor study of Yahoo, StockAnalysis, Simply Wall St, WallStreetZen,
 * Koyfin, Stock Rover, Zacks, TipRanks and Morningstar landed on one finding:
 * a number helps someone decide only when it is LOCATABLE. A figure with
 * nothing to locate it against is not a decision aid, it is furniture. So the
 * block is now ranked rather than flat:
 *
 *   • RELATIVE VOLUME IS THE HEADLINE. "Volume 51,847,301" and "Avg. volume
 *     48,213,004" as two equal figures answer nothing; the question a reader
 *     actually has is "is today unusual?", which is the ratio. The ratio is
 *     printed first and the two raws are demoted to a quiet line beneath —
 *     kept, not deleted, because the ratio must be checkable.
 *
 *   • OPEN, PREVIOUS CLOSE AND DAY'S RANGE ARE ONE QUIET LINE. They restate
 *     what "price, change, as-of" already says at the top of the page. They
 *     are microstructure for a reader about to transact, and we have no
 *     level-1 feed for that reader.
 *
 *   • BETA, P/E AND EPS SIT IN THEIR OWN DEMOTED GROUP. A valuation multiple
 *     with no percentile beside it is unjudgeable — "P/E 32.9" is a fact,
 *     "P/E 32.9, 71st percentile of Semiconductors (n=142)" is a decision aid,
 *     and we cannot print the second one yet: those columns are still filling,
 *     so ranking on them would mean ranking on almost nothing. They keep
 *     rendering (as em-dashes today) but they are not presented as headline
 *     judgements.
 *
 *   • DIVIDEND YIELD RENDERS ONLY WHEN IT IS NON-ZERO. "0.00%" on every
 *     non-payer is noise, and a dashed row for a company that simply pays no
 *     dividend is worse — it implies a missing feed. Payers get the row;
 *     nobody else does.
 *
 * Every value here comes from a feed we already pull and pay for: the Massive
 * snapshot (previous close / open), the 365-day daily bars (ranges + 30-day
 * average volume), Finnhub `metric=all` (beta / EPS / P/E / dividend yield) and
 * the earnings calendar. See the column ownership comment on `Ticker` in
 * backend/app/models/ticker.py.
 *
 * THE ONE RULE: a value we do not hold renders as an em-dash. Never 0, never
 * "N/A", never a derived stand-in. ~72% of the universe has no price or volume
 * read at all, so a mostly-blank block is the NORMAL render for a long-tail
 * ticker, not a failure — hence the coverage note under the heading, which is
 * what makes the blanks read as deliberate rather than broken.
 *
 * Relative volume is the one computed figure in the block. It is a ratio of two
 * values we hold and print immediately below it, so it is arithmetic on
 * disclosed inputs rather than a new number: when either input is missing the
 * ratio is an em-dash, and it is never approximated from one side.
 *
 * Deliberately absent: bid/ask (no level-1 quote feed) and the 1-year analyst
 * price target (not on our Finnhub plan). A row with nothing honest behind it
 * is worse than no row.
 *
 * Compliance (docs/COMPLIANCE_COPY_RULES.md): descriptive only — these are
 * reported facts about the instrument, so no colour-coding, no framing, and no
 * copy suggesting what any of them means for a decision.
 */

/**
 * The key-statistics slice of the ticker payload.
 *
 * Field names mirror the `tickers` columns 1:1 so the block reads straight off
 * the API response with no remapping. Every field is optional AND nullable:
 * optional because a frontend deploy can land ahead of the backend that serves
 * the keys, nullable because the column genuinely has no value for most rows.
 * Both cases render the same em-dash, which is why nothing here needs a
 * loading or error state.
 */
export type KeyStats = {
  previous_close?: number | null;
  day_open?: number | null;
  day_high?: number | null;
  day_low?: number | null;
  week52_high?: number | null;
  week52_low?: number | null;
  volume?: number | null;
  avg_volume_30d?: number | null;
  market_cap?: number | null;
  beta?: number | null;
  pe_ttm?: number | null;
  eps_ttm?: number | null;
  next_earnings_date?: string | null;
  /** Indicated annual yield as a PERCENT (Finnhub's units: 0.43 → "0.43%"). */
  dividend_yield?: number | null;
  ex_dividend_date?: string | null;
};

/** The single, deliberate rendering of "we do not hold this value". */
const EMPTY = "—";

export function KeyStatistics({ stats }: { stats: KeyStats }) {
  // Payers only. A null yield is omitted for the same reason a 0.00% one is:
  // a dashed dividend row on a company that pays no dividend reads as a broken
  // feed rather than as "there is no dividend here".
  const paysDividend =
    stats.dividend_yield != null &&
    !Number.isNaN(stats.dividend_yield) &&
    stats.dividend_yield > 0;

  return (
    <section className="card" aria-labelledby="key-statistics-heading">
      <div className="border-b border-border p-4">
        <h2 id="key-statistics-heading" className="font-semibold">
          Key statistics
        </h2>
        <p className="mt-0.5 text-xs text-muted">
          Market fields as reported. An em-dash means we hold no value for this
          ticker &mdash; most of the universe has no daily price or volume read.
        </p>
      </div>

      {/* Overflow container: the grid reflows to one column on a phone and no
          value wraps, so this should never engage — it's here so a freak long
          value scrolls inside the card instead of pushing the page sideways. */}
      <div className="overflow-x-auto p-4">
        {/* Definition list, one <div> per pair — same dt/dd shape the squeeze
            panel on this page already uses. Row-flow grid, so the DOM order IS
            the reading order at every breakpoint. */}
        <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2 lg:grid-cols-3">
          {/* The one figure here that answers a question rather than reporting
              a level: is today's participation unusual for this ticker? */}
          <Stat
            label="Relative volume"
            value={fmtRelVolume(stats.volume, stats.avg_volume_30d)}
          />
          <Stat label="52-week range" value={fmtRange(stats.week52_low, stats.week52_high)} />
          <Stat label="Market cap" value={fmtUsdCompact(stats.market_cap)} />
          <Stat label="Earnings date" value={fmtDate(stats.next_earnings_date)} />
          {paysDividend && (
            <Stat label="Dividend yield" value={fmtPct(stats.dividend_yield)} />
          )}
          {/* No ex-dividend date row. The field exists on the API and stays null:
              Finnhub /stock/metric does not carry it and /stock/dividend is a
              premium endpoint we are not on. A row that can NEVER populate reads
              as "we have this data and this ticker lacks it", which is untrue for
              every ticker — the same reason bid/ask and the analyst price target
              are absent rather than dashed. Add the row back the day the feed
              actually carries it. */}
        </dl>

        {/* The demoted raws. Still a definition list — they are label/value
            pairs and a reader auditing the ratio above needs both sides — but
            typographically quiet, on one wrapping line. */}
        <dl className="mt-4 flex flex-wrap gap-x-5 gap-y-1 border-t border-border pt-3 text-xs text-muted">
          <Quiet label="Volume" value={fmtCount(stats.volume)} />
          <Quiet label="Avg. volume (30d)" value={fmtCount(stats.avg_volume_30d)} />
        </dl>

        {/* Session microstructure. One quiet line: these restate the price and
            change already stamped at the top of the page. */}
        <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
          <Quiet label="Open" value={fmtPrice(stats.day_open)} />
          <Quiet label="Previous close" value={fmtPrice(stats.previous_close)} />
          <Quiet label="Day's range" value={fmtRange(stats.day_low, stats.day_high)} />
        </dl>

        {/* Unjudged group. These render, but they are not presented as
            headline figures, because a multiple with nothing to locate it
            against cannot be judged — see the block comment above. */}
        <div className="mt-4 border-t border-border pt-3">
          <p className="text-xs text-subtle">
            Shown without a peer ranking &mdash; we hold no percentile for these
            yet, so there is nothing here to locate them against.
          </p>
          <dl className="mt-2 grid grid-cols-1 gap-x-8 sm:grid-cols-3">
            <Stat label="Beta" value={fmtRatio(stats.beta)} />
            <Stat label="P/E (TTM)" value={fmtRatio(stats.pe_ttm)} />
            <Stat label="EPS (TTM)" value={fmtRatio(stats.eps_ttm)} />
          </dl>
        </div>
      </div>
    </section>
  );
}

/**
 * One label/value pair. `nums` gives tabular figures so the values line up
 * down each column, and the value is pinned right against the next column's
 * gutter — this block is scanned, not read.
 */
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border py-2">
      <dt className="min-w-0 text-sm text-muted">{label}</dt>
      <dd className="nums whitespace-nowrap text-sm font-medium">{value}</dd>
    </div>
  );
}

/** A demoted pair, inline on one wrapping line. Same dt/dd semantics. */
function Quiet({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <dt>{label}</dt>
      <dd className="nums whitespace-nowrap text-fg">{value}</dd>
    </div>
  );
}

/** Share price to the cent. No "$" — the page header already sets the unit,
 *  and a bare number keeps the ranges below compact. */
function fmtPrice(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return EMPTY;
  return v.toFixed(2);
}

/**
 * "196.21 – 260.10". A range needs BOTH ends to mean anything, so a half-known
 * range is reported as unknown rather than as an open-ended one — showing
 * "— – 260.10" would invite the reader to fill in the missing side themselves.
 */
function fmtRange(low: number | null | undefined, high: number | null | undefined): string {
  if (low == null || high == null || Number.isNaN(low) || Number.isNaN(high)) return EMPTY;
  return `${low.toFixed(2)} – ${high.toFixed(2)}`;
}

/**
 * "1.08× 30-day average" — today's volume against this ticker's own recent
 * norm, which is the question the two raw figures were failing to answer.
 *
 * Both sides are required and the denominator must be positive: a ratio taken
 * against a zero or absent average is not a small number, it is no number.
 * Two decimals because the interesting range is roughly 0.3× to 5× and the
 * second digit is where "quiet" separates from "normal".
 */
function fmtRelVolume(
  volume: number | null | undefined,
  avg: number | null | undefined,
): string {
  if (volume == null || avg == null) return EMPTY;
  if (Number.isNaN(volume) || Number.isNaN(avg)) return EMPTY;
  if (avg <= 0) return EMPTY;
  return `${(volume / avg).toFixed(2)}× 30-day average`;
}

/**
 * Share counts in full, with thousands separators ("51,847,301") — an average
 * volume is compared against the day's volume, and rounding both to "51.85M"
 * throws away the comparison.
 *
 * Grouping is pinned to en-US rather than the visitor's locale because this
 * component renders on the server too: a locale-dependent separator would
 * differ between the SSR pass and hydration.
 */
function fmtCount(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return EMPTY;
  return Math.round(v).toLocaleString("en-US");
}

/**
 * Ratios and per-share dollar figures to 2dp. Nothing is normalised away: a
 * negative EPS keeps its minus sign, and a negative P/E is reported as it
 * stands rather than blanked, because it is a real reading of a real company.
 * No leading "+" — these are levels, not changes.
 */
function fmtRatio(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return EMPTY;
  return v.toFixed(2);
}

/** Indicated annual dividend yield, already a percent upstream. */
function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return EMPTY;
  return `${v.toFixed(2)}%`;
}

/** Absolute market cap. Mirrors the scanner's "Mkt Cap" column exactly. */
function fmtUsdCompact(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return EMPTY;
  if (v >= 1e12) return "$" + (v / 1e12).toFixed(2) + "T";
  if (v >= 1e9) return "$" + (v / 1e9).toFixed(2) + "B";
  if (v >= 1e6) return "$" + (v / 1e6).toFixed(2) + "M";
  if (v >= 1e3) return "$" + (v / 1e3).toFixed(1) + "K";
  return "$" + String(v);
}

/**
 * "22 Aug 2026" from a bare YYYY-MM-DD calendar date.
 *
 * Parsed part-by-part into a LOCAL date, the same way daysUntilEarnings does
 * in lib/useEarningsCalendar: `new Date("2026-08-22")` is midnight UTC, which
 * renders as the 21st for every reader west of Greenwich. Locale comes from
 * lib/datetime so the day/month order matches the rest of the app.
 */
function fmtDate(v: string | null | undefined): string {
  if (!v) return EMPTY;
  const parts = v.slice(0, 10).split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return EMPTY;
  const [y, m, d] = parts;
  const parsed = new Date(y, m - 1, d);
  if (Number.isNaN(parsed.getTime())) return EMPTY;
  return parsed.toLocaleDateString(userLocale(), {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
