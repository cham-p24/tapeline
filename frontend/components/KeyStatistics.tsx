"use client";

import { userLocale } from "@/lib/datetime";

/**
 * Key statistics — the summary block a reader expects at the top of a ticker
 * page (previous close, day/52-week ranges, volume, market cap, beta, P/E,
 * EPS, earnings and dividend dates).
 *
 * Every value here comes from a feed we already pull and pay for: the Massive
 * snapshot (previous close / open), the 365-day daily bars (ranges + 30-day
 * average volume), Finnhub `metric=all` (beta / EPS / P/E / dividend yield /
 * ex-dividend date) and the earnings calendar. See the column ownership
 * comment on `Ticker` in backend/app/models/ticker.py.
 *
 * THE ONE RULE: a value we do not hold renders as an em-dash. Never 0, never
 * "N/A", never a derived stand-in. ~72% of the universe has no price or volume
 * read at all, so a mostly-blank block is the NORMAL render for a long-tail
 * ticker, not a failure — hence the coverage note under the heading, which is
 * what makes the blanks read as deliberate rather than broken.
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
  return (
    <section className="card" aria-labelledby="key-statistics-heading">
      <div className="border-b border-border p-4">
        <h2 id="key-statistics-heading" className="font-semibold">
          Key statistics
        </h2>
        <p className="text-xs text-muted">
          An em-dash means we hold no value for this ticker — most of the
          universe has no daily price or volume read.
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
          <Stat label="Previous close" value={fmtPrice(stats.previous_close)} />
          <Stat label="Open" value={fmtPrice(stats.day_open)} />
          <Stat label="Day's range" value={fmtRange(stats.day_low, stats.day_high)} />
          <Stat label="52-week range" value={fmtRange(stats.week52_low, stats.week52_high)} />
          <Stat label="Volume" value={fmtCount(stats.volume)} />
          <Stat label="Avg. volume (30d)" value={fmtCount(stats.avg_volume_30d)} />
          <Stat label="Market cap" value={fmtUsdCompact(stats.market_cap)} />
          <Stat label="Beta" value={fmtRatio(stats.beta)} />
          <Stat label="P/E (TTM)" value={fmtRatio(stats.pe_ttm)} />
          <Stat label="EPS (TTM)" value={fmtRatio(stats.eps_ttm)} />
          <Stat label="Earnings date" value={fmtDate(stats.next_earnings_date)} />
          <Stat label="Dividend yield" value={fmtPct(stats.dividend_yield)} />
          {/* No ex-dividend date row. The field exists on the API and stays null:
              Finnhub /stock/metric does not carry it and /stock/dividend is a
              premium endpoint we are not on. A row that can NEVER populate reads
              as "we have this data and this ticker lacks it", which is untrue for
              every ticker — the same reason bid/ask and the analyst price target
              are absent rather than dashed. Add the row back the day the feed
              actually carries it. */}
        </dl>
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
