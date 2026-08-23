/**
 * "On our record" — the per-ticker flag history.
 *
 * Three behaviours are load-bearing and all three are easy to break by
 * accident:
 *
 *   1. NEVER-FLAGGED IS A FIRST-CLASS STATE. ~8,400 of ~8,900 scored symbols
 *      have never been flagged. That render must read as a calm statement of
 *      fact, not as an empty table or an error.
 *
 *   2. AN ABSENT RECORD BLOCK IS NOT "NEVER FLAGGED". If the payload never
 *      carried a record we have not been told anything, and printing "never
 *      flagged" would manufacture a fact out of a deploy skew.
 *
 *   3. LOSSES ARE NEVER FILTERED, and the horizon is stated. The outcome is
 *      the NEXT SESSION only; a reader who assumes a longer horizon has been
 *      misled by omission.
 */
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { TickerRecord, normalizeRecord } from "@/components/TickerRecord";

const ROWS = [
  {
    as_of: "2026-07-02",
    rank: 4,
    score_at_flag: 88.4,
    price_at_flag: 101.2,
    price_next_day: 99.1,
    change_pct_1d_after: -2.08,
    spy_change_pct_1d: 0.31,
    alpha_vs_spy: -2.39,
  },
  {
    as_of: "2026-08-14",
    score_at_flag: 91.2,
    price_at_flag: 118.4,
    price_next_day: 121.0,
    change_pct_1d_after: 2.2,
    spy_change_pct_1d: 0.4,
    alpha_vs_spy: 1.8,
  },
  {
    as_of: "2026-08-21",
    score_at_flag: 89.0,
    price_at_flag: 124.5,
    price_next_day: null,
    change_pct_1d_after: null,
    spy_change_pct_1d: null,
    alpha_vs_spy: null,
  },
];

/**
 * The `flag_record` block exactly as routers/ticker.py `_flag_record_payload`
 * emits it: flat counts, the row list under `flags`, and the disclosure fields
 * that say what the row list is not showing.
 */
const RECORD = {
  horizon: "next_session",
  horizon_label: "next trading session",
  flag_count: 3,
  resolved_count: 2,
  beat_spy_count: 1,
  median_alpha_vs_spy: -0.3,
  suspect_outlier_count: 0,
  suspect_outlier_threshold_pct: 50,
  first_flagged_on: "2026-07-02",
  last_flagged_on: "2026-08-21",
  flags: ROWS,
  flags_delay_days: 0,
  flags_hidden_recent: 0,
  flags_truncated: false,
};

/** Read the <dd> paired with a given headline <dt>. */
function headline(label: string): string {
  const dt = screen.getByText(label);
  const pair = dt.parentElement as HTMLElement;
  return within(pair).getByText((_, el) => el?.tagName === "DD").textContent ?? "";
}

describe("TickerRecord", () => {
  it("renders NOTHING when the payload carries no record block", () => {
    // Not being told is not the same as being told there are no flags.
    const { container } = render(<TickerRecord symbol="ABC" record={undefined} />);
    expect(container.textContent).toBe("");
    expect(render(<TickerRecord symbol="ABC" record={null} />).container.textContent).toBe("");
    expect(render(<TickerRecord symbol="ABC" record={{}} />).container.textContent).toBe("");
  });

  it("states plainly that a ticker has never been flagged", () => {
    // ~8,400 of 8,879 scored symbols land here — the ordinary case.
    render(
      <TickerRecord
        symbol="ABC"
        record={{ flag_count: 0, resolved_count: 0, beat_spy_count: 0, median_alpha_vs_spy: null, flags: [] }}
      />,
    );
    expect(screen.getByText("Tapeline has never flagged ABC.")).toBeInTheDocument();
    // The common case, so it must not look like a failure: no table, no
    // pending rows, no warning tone.
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByText(/ordinary answer for most tickers/i)).toBeInTheDocument();
  });

  it("summarises the record from the API's own counts", () => {
    render(<TickerRecord symbol="ABC" record={RECORD} />);
    expect(headline("Times flagged")).toBe("3");
    expect(headline("Resolved")).toBe("2");
    // "1 of 2", not "50%": the live payload carries the two counts and no
    // rate, and a rate computed from them here would be a derived statistic
    // the API never published.
    expect(headline("Beat SPY next session")).toBe("1 of 2");
    expect(headline("Median alpha vs SPY")).toBe("-0.30%");
  });

  it("appends a hit rate only when the API actually sends one", () => {
    render(
      <TickerRecord symbol="ABC" record={{ ...RECORD, hit_rate_beat_spy: 50 }} />,
    );
    expect(headline("Beat SPY next session")).toBe("1 of 2 (50%)");
  });

  it("never back-derives a count the summary did not give", () => {
    // Rows are tier-delayed and can be capped, so counting them would publish
    // a number nobody counted.
    render(
      <TickerRecord
        symbol="ABC"
        record={{ flag_count: 3, resolved_count: 2, flags: ROWS }}
      />,
    );
    expect(headline("Beat SPY next session")).toBe("—");
    expect(headline("Median alpha vs SPY")).toBe("—");
  });

  it("says what the row list is not showing rather than looking empty", () => {
    const { container } = render(
      <TickerRecord
        symbol="ABC"
        record={{
          ...RECORD,
          flags: [],
          flags_delay_days: 30,
          flags_hidden_recent: 3,
        }}
      />,
    );
    // The counts stay, because the summary is not delayed — only the rows are.
    expect(headline("Times flagged")).toBe("3");
    expect(container.textContent).toMatch(/held back 30 days/);
    expect(container.textContent).toMatch(/hides the 3 most recent/);
    // And it is emphatically not the never-flagged state.
    expect(container.textContent).not.toMatch(/never flagged/);
  });

  it("discloses suspect vendor prints instead of dropping them", () => {
    const { container } = render(
      <TickerRecord
        symbol="ABC"
        record={{ ...RECORD, suspect_outlier_count: 1, suspect_outlier_threshold_pct: 50 }}
      />,
    );
    expect(container.textContent).toMatch(/1 resolved session moves more than 50%/);
    expect(container.textContent).toMatch(/counted in the figures above and listed below rather than removed/);
  });

  it("lists every flag, most recent first, losses included", () => {
    render(<TickerRecord symbol="ABC" record={RECORD} />);
    const bodyRows = screen.getAllByRole("row").slice(1); // drop the header row
    expect(bodyRows).toHaveLength(3);
    // Sorted here rather than trusted from the payload: ROWS arrives unsorted.
    const dates = bodyRows.map((r) => within(r).getByRole("rowheader").textContent);
    expect(dates[0]).toMatch(/21/);
    expect(dates[1]).toMatch(/14/);
    expect(dates[2]).toMatch(/2/);
    // The losing session is present and carries its real, signed figure.
    expect(bodyRows[2].textContent).toContain("-2.08%");
    expect(bodyRows[2].textContent).toContain("-2.39%");
  });

  it("styles a losing session with the same type size and weight as a winner", () => {
    render(<TickerRecord symbol="ABC" record={RECORD} />);
    const bodyRows = screen.getAllByRole("row").slice(1);
    const winnerAlpha = within(bodyRows[1]).getAllByRole("cell").at(-1)!;
    const loserAlpha = within(bodyRows[2]).getAllByRole("cell").at(-1)!;
    const strip = (c: string) => c.replace(/text-(up|down)/, "").trim();
    expect(strip(loserAlpha.className)).toBe(strip(winnerAlpha.className));
  });

  it("shows an unresolved flag as pending rather than as a zero return", () => {
    render(<TickerRecord symbol="ABC" record={RECORD} />);
    const newest = screen.getAllByRole("row")[1];
    expect(newest.textContent).toContain("pending");
    expect(newest.textContent).not.toContain("+0.00%");
  });

  it("is explicit that the horizon is a single session", () => {
    const { container } = render(<TickerRecord symbol="ABC" record={RECORD} />);
    expect(container.textContent).toMatch(/The horizon is one session\./);
    expect(container.textContent).toMatch(/Nothing here tracks what happened a week or a month later/);
    expect(container.textContent).toMatch(/Every flag is listed below, including the ones that lost/);
  });

  it("does not claim a complete list when the delay is withholding rows", () => {
    const { container } = render(
      <TickerRecord
        symbol="ABC"
        record={{ ...RECORD, flags: [], flags_delay_days: 30, flags_hidden_recent: 3 }}
      />,
    );
    expect(container.textContent).not.toMatch(/Every flag is listed below/);
    expect(container.textContent).toMatch(/No flag is filtered out for having lost/);
  });

  it("keeps the vs-SPY figure out of the heading", () => {
    render(<TickerRecord symbol="ABC" record={RECORD} />);
    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading.textContent).toBe("On our record");
    expect(heading.textContent).not.toMatch(/\d/);
  });

  it("links to the public scorecard so the record can be checked", () => {
    render(<TickerRecord symbol="ABC" record={RECORD} />);
    const link = screen.getByRole("link", { name: /ABC on the public scorecard/ });
    expect(link.getAttribute("href")).toBe("/scorecard/ABC");
  });

  it("puts the wide table in its own scroll container", () => {
    const { container } = render(<TickerRecord symbol="ABC" record={RECORD} />);
    const table = container.querySelector("table")!;
    expect(table.parentElement!.className).toContain("overflow-x-auto");
    expect(table.querySelector("caption")).not.toBeNull();
  });

  it("stays descriptive — no advice or performance claim", () => {
    const { container } = render(<TickerRecord symbol="ABC" record={RECORD} />);
    expect(container.textContent ?? "").not.toMatch(
      /\bbuy\b|\bsell\b|recommend|price target|outperform|beat the market|winning (stocks|picks)/i,
    );
  });
});

describe("normalizeRecord", () => {
  it("parses the live flat block", () => {
    const parsed = normalizeRecord(RECORD)!;
    expect(parsed.summary.flags).toBe(3);
    expect(parsed.summary.resolved).toBe(2);
    expect(parsed.summary.beatSpy).toBe(1);
    expect(parsed.summary.medianAlpha).toBe(-0.3);
    expect(parsed.rows).toHaveLength(3);
  });

  it("parses a nested summary block just as readily", () => {
    const parsed = normalizeRecord({
      summary: { appearances: 7, appearances_scored: 6, hit_rate_beat_spy: 50 },
      rows: ROWS,
    })!;
    expect(parsed.summary.flags).toBe(7);
    expect(parsed.summary.resolved).toBe(6);
    expect(parsed.summary.hitRate).toBe(50);
  });

  it("does not mistake the `flags` row array for a flag count", () => {
    // `flags` is the row list in the live payload and a count in none of them.
    const parsed = normalizeRecord({ flag_count: 3, flags: ROWS })!;
    expect(parsed.summary.flags).toBe(3);
    expect(parsed.rows).toHaveLength(3);
  });

  it("returns null when there is neither a count nor a row to report", () => {
    expect(normalizeRecord({})).toBeNull();
    expect(normalizeRecord({ summary: {} })).toBeNull();
    expect(normalizeRecord("nope")).toBeNull();
    expect(normalizeRecord(undefined)).toBeNull();
  });

  it("drops rows with no session date rather than dating them itself", () => {
    const parsed = normalizeRecord({ flag_count: 2, flags: [...ROWS, { score_at_flag: 50 }] })!;
    expect(parsed.rows).toHaveLength(3);
  });
});
