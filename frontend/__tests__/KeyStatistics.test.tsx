/**
 * Key statistics block on the ticker page.
 *
 * Two load-bearing properties:
 *
 *   1. HONESTY ABOUT ABSENCE. ~72% of the universe has no price or volume
 *      read, so a value we don't hold must render as an em-dash — never 0,
 *      never "N/A", never a derived stand-in.
 *
 *   2. RANKED, NOT FLAT. The block was a grid of twelve equal figures; a
 *      figure with nothing to locate it against is furniture. Relative volume
 *      is now the headline (it answers "is today unusual?", which the two raw
 *      volumes never did), the raws and the session microstructure are demoted
 *      to quiet lines, beta/P-E/EPS sit in an explicitly unranked group, and
 *      dividend yield renders for payers only.
 *
 * These tests pin both, plus the human formatting (grouped volume, abbreviated
 * market cap, "low – high" ranges, readable dates, signed EPS) and the
 * definition-list semantics.
 */
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { KeyStatistics, type KeyStats } from "@/components/KeyStatistics";

const EM_DASH = "—";

/** The promoted figures — the ones a reader is meant to land on first. */
const PRIMARY_LABELS = [
  "Relative volume",
  "52-week range",
  "Market cap",
  "Earnings date",
];

/** Demoted, but still present and still auditable. */
const QUIET_LABELS = [
  "Volume",
  "Avg. volume (30d)",
  "Open",
  "Previous close",
  "Day's range",
];

/** Rendered, but explicitly not presented as judgements. */
const UNRANKED_LABELS = ["Beta", "P/E (TTM)", "EPS (TTM)"];

/** A fully-populated ticker — the mega-cap case, where every feed has a read. */
const FULL: KeyStats = {
  previous_close: 212.34,
  day_open: 213.5,
  day_high: 216.02,
  day_low: 211.87,
  week52_high: 260.1,
  week52_low: 196.21,
  volume: 51847301,
  avg_volume_30d: 48213004,
  market_cap: 8485000000,
  beta: 1.24,
  pe_ttm: 31.07,
  eps_ttm: 6.84,
  next_earnings_date: "2026-10-29",
  dividend_yield: 0.43,
  ex_dividend_date: "2026-09-08",
};

/** Read the <dd> paired with a given <dt> label. */
function valueFor(label: string): string {
  const dt = screen.getByText(label);
  const pair = dt.parentElement as HTMLElement;
  const dd = within(pair).getByText((_, el) => el?.tagName === "DD");
  return dd.textContent ?? "";
}

describe("KeyStatistics", () => {
  it("renders every promised label", () => {
    render(<KeyStatistics stats={FULL} />);
    for (const label of [...PRIMARY_LABELS, ...QUIET_LABELS, ...UNRANKED_LABELS]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    // Payer, so the yield row is present too.
    expect(screen.getByText("Dividend yield")).toBeInTheDocument();
  });

  it("uses definition-list semantics rather than a grid of divs", () => {
    const { container } = render(<KeyStatistics stats={FULL} />);
    const dts = container.querySelectorAll("dt");
    const dds = container.querySelectorAll("dd");
    // 4 primary + dividend + 5 quiet + 3 unranked.
    expect(dts).toHaveLength(13);
    expect(dds).toHaveLength(13);
    // Every pair lives inside a <dl>, not a bare div.
    for (const dt of Array.from(dts)) {
      expect(dt.closest("dl")).not.toBeNull();
    }
  });

  it("leads with relative volume, the figure that answers a question", () => {
    render(<KeyStatistics stats={FULL} />);
    // 51,847,301 / 48,213,004 = 1.0753… → "1.08×".
    expect(valueFor("Relative volume")).toBe("1.08× 30-day average");
    // The raws are still there to check the ratio against.
    expect(valueFor("Volume")).toBe("51,847,301");
    expect(valueFor("Avg. volume (30d)")).toBe("48,213,004");
  });

  it("refuses a relative volume it cannot compute, rather than approximating", () => {
    render(<KeyStatistics stats={{ ...FULL, avg_volume_30d: null }} />);
    expect(valueFor("Relative volume")).toBe(EM_DASH);
  });

  it("never divides by a zero average volume", () => {
    render(<KeyStatistics stats={{ ...FULL, avg_volume_30d: 0 }} />);
    // Not "Infinity×", not "0.00×" — no number at all.
    expect(valueFor("Relative volume")).toBe(EM_DASH);
  });

  it("formats prices, ranges and market cap for a human", () => {
    render(<KeyStatistics stats={FULL} />);
    expect(valueFor("Previous close")).toBe("212.34");
    expect(valueFor("Open")).toBe("213.50");
    // "low – high", low first regardless of prop order.
    expect(valueFor("Day's range")).toBe("211.87 – 216.02");
    expect(valueFor("52-week range")).toBe("196.21 – 260.10");
    // 2dp, matching the scanner's "Mkt Cap" column exactly so the same
    // company reads identically on both surfaces. (8.485 is not exactly
    // representable in binary floating point and rounds down, hence .48.)
    expect(valueFor("Market cap")).toBe("$8.48B");
    expect(valueFor("Beta")).toBe("1.24");
    expect(valueFor("P/E (TTM)")).toBe("31.07");
    expect(valueFor("Dividend yield")).toBe("0.43%");
  });

  it("says plainly that beta and P/E carry no peer ranking", () => {
    const { container } = render(<KeyStatistics stats={FULL} />);
    expect(container.textContent).toMatch(/Shown without a peer ranking/i);
  });

  it("renders dividend yield only for a payer", () => {
    // A non-payer reports 0.00%, which is noise on every non-dividend stock.
    render(<KeyStatistics stats={{ ...FULL, dividend_yield: 0 }} />);
    expect(screen.queryByText("Dividend yield")).toBeNull();
  });

  it("omits the dividend row when we hold no yield at all", () => {
    // A dashed yield row reads as a broken feed rather than "no dividend".
    render(<KeyStatistics stats={{ ...FULL, dividend_yield: null }} />);
    expect(screen.queryByText("Dividend yield")).toBeNull();
  });

  it("renders dates as a readable day, not the raw ISO string", () => {
    render(<KeyStatistics stats={FULL} />);
    // Locale is resolved at runtime, so assert on the parts rather than one
    // fixed ordering — the point is that "2026-10-29" is not shown verbatim.
    const earnings = valueFor("Earnings date");
    expect(earnings).not.toBe("2026-10-29");
    expect(earnings).toMatch(/Oct/);
    expect(earnings).toMatch(/29/);
    expect(earnings).toMatch(/2026/);
    // Off-by-one guard: a bare YYYY-MM-DD parsed as UTC midnight renders as
    // the previous day west of Greenwich. Must stay on the 29th.
    expect(earnings).not.toMatch(/28/);
    // Ex-dividend date is deliberately NOT rendered: /stock/dividend is a
    // premium endpoint we are not on, so it could never populate for ANY
    // ticker, and a permanent em-dash would imply otherwise.
    expect(screen.queryByText("Ex-dividend date")).toBeNull();
  });

  it("keeps the sign on a negative EPS", () => {
    render(<KeyStatistics stats={{ ...FULL, eps_ttm: -1.37 }} />);
    expect(valueFor("EPS (TTM)")).toBe("-1.37");
  });

  it("renders an em-dash for a null field, never 0 or N/A", () => {
    render(<KeyStatistics stats={{ ...FULL, beta: null, market_cap: null }} />);
    expect(valueFor("Beta")).toBe(EM_DASH);
    expect(valueFor("Market cap")).toBe(EM_DASH);
    // The populated neighbours are untouched — one missing feed doesn't blank
    // the block.
    expect(valueFor("Previous close")).toBe("212.34");
  });

  it("renders an em-dash for a half-known range rather than an open-ended one", () => {
    render(<KeyStatistics stats={{ ...FULL, week52_low: null }} />);
    expect(valueFor("52-week range")).toBe(EM_DASH);
  });

  it("does not crash when the whole block is null, and shows only em-dashes", () => {
    const empty = Object.fromEntries(
      Object.keys(FULL).map((k) => [k, null]),
    ) as KeyStats;
    const { container } = render(<KeyStatistics stats={empty} />);
    for (const label of [...PRIMARY_LABELS, ...QUIET_LABELS, ...UNRANKED_LABELS]) {
      expect(valueFor(label)).toBe(EM_DASH);
    }
    // Nothing fabricated slipped in anywhere in the block.
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\bN\/A\b/);
    expect(text).not.toMatch(/\bNaN\b/);
    expect(text).not.toMatch(/undefined|null/);
    expect(text).not.toMatch(/Infinity/);
  });

  it("does not crash when the payload carries no key-stats keys at all", () => {
    // A frontend deploy that lands ahead of the backend: the fields are absent
    // rather than null. Same render, no throw.
    const { container } = render(<KeyStatistics stats={{}} />);
    // 12 pairs — the dividend row is absent along with the yield.
    expect(container.querySelectorAll("dd")).toHaveLength(12);
    for (const label of [...PRIMARY_LABELS, ...QUIET_LABELS, ...UNRANKED_LABELS]) {
      expect(valueFor(label)).toBe(EM_DASH);
    }
  });

  it("stays descriptive — no prescriptive or performance language", () => {
    const { container } = render(<KeyStatistics stats={FULL} />);
    expect(container.textContent ?? "").not.toMatch(
      /buy|sell|recommend|should|outperform|beat the market/i,
    );
  });
});
