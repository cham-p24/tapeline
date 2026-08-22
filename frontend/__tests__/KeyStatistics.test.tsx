/**
 * Key statistics block on the ticker page.
 *
 * The load-bearing property is honesty about absence: ~72% of the universe has
 * no price or volume read, so a value we don't hold must render as an em-dash
 * — never 0, never "N/A", never a derived stand-in. These tests pin that, plus
 * the human formatting (grouped volume, abbreviated market cap, "low – high"
 * ranges, readable dates, signed EPS) and the definition-list semantics.
 */
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { KeyStatistics, type KeyStats } from "@/components/KeyStatistics";

const EM_DASH = "—";

/** Every label the block promises to show, in render order. */
const LABELS = [
  "Previous close",
  "Open",
  "Day's range",
  "52-week range",
  "Volume",
  "Avg. volume (30d)",
  "Market cap",
  "Beta",
  "P/E (TTM)",
  "EPS (TTM)",
  "Earnings date",
  "Dividend yield",
];

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
    for (const label of LABELS) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("uses definition-list semantics rather than a grid of divs", () => {
    const { container } = render(<KeyStatistics stats={FULL} />);
    expect(container.querySelector("dl")).not.toBeNull();
    expect(container.querySelectorAll("dt")).toHaveLength(LABELS.length);
    expect(container.querySelectorAll("dd")).toHaveLength(LABELS.length);
  });

  it("formats prices, ranges, volume and market cap for a human", () => {
    render(<KeyStatistics stats={FULL} />);
    expect(valueFor("Previous close")).toBe("212.34");
    expect(valueFor("Open")).toBe("213.50");
    // "low – high", low first regardless of prop order.
    expect(valueFor("Day's range")).toBe("211.87 – 216.02");
    expect(valueFor("52-week range")).toBe("196.21 – 260.10");
    // Thousands separators, not a rounded "51.85M" — volume is compared
    // against average volume and the rounding would destroy the comparison.
    expect(valueFor("Volume")).toBe("51,847,301");
    expect(valueFor("Avg. volume (30d)")).toBe("48,213,004");
    // 2dp, matching the scanner's "Mkt Cap" column exactly so the same
    // company reads identically on both surfaces. (8.485 is not exactly
    // representable in binary floating point and rounds down, hence .48.)
    expect(valueFor("Market cap")).toBe("$8.48B");
    expect(valueFor("Beta")).toBe("1.24");
    expect(valueFor("P/E (TTM)")).toBe("31.07");
    expect(valueFor("Dividend yield")).toBe("0.43%");
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
    // the previous day west of Greenwich. Must stay on the 8th.
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
    for (const label of LABELS) {
      expect(valueFor(label)).toBe(EM_DASH);
    }
    // Nothing fabricated slipped in anywhere in the block.
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\bN\/A\b/);
    expect(text).not.toMatch(/\bNaN\b/);
    expect(text).not.toMatch(/undefined|null/);
  });

  it("does not crash when the payload carries no key-stats keys at all", () => {
    // A frontend deploy that lands ahead of the backend: the fields are absent
    // rather than null. Same render, no throw.
    const { container } = render(<KeyStatistics stats={{}} />);
    expect(container.querySelectorAll("dd")).toHaveLength(LABELS.length);
    for (const label of LABELS) {
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
