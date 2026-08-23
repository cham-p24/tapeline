/**
 * Regime page + FinancialsTab: every metric LABEL must name what the code
 * actually computes.
 *
 * Three mislabels this pins down (audit 2026-08-24):
 *
 *   1. `breadth_pct` was labelled "% of S&P components above their 200-day
 *      moving average". Both writers compute a SAME-DAY advance/decline ratio
 *      — polygon_feed: 100 * advancers / len(moving) over change_pct_1d;
 *      sheet_feed._compute_breadth_pct: the same thing in SQL. Nothing in the
 *      system reads a 200-day moving average for this number, and the universe
 *      is ours, not the S&P. The tone/hint bands were also 200DMA bands
 *      (70/55/40/25); an A/D ratio is balanced at 50 by construction.
 *
 *   2. "Where this regime score comes from" described a four-input composite
 *      with 70/50/30 score bands. The running classifier is four raw VIX
 *      thresholds (<15 / <20 / <25 / else) and nothing else — the stated bands
 *      correspond to no variable in the system.
 *
 *   3. "Sector leaders" was labelled "top 3 GICS sectors by 5-day relative
 *      strength vs SPY". It is a top-3 by the mean of OUR OWN composite score.
 *
 * These assert on RENDERED OUTPUT, not on source text.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/useLiveStream", () => ({
  useLiveStream: () => ({ status: "live", lastUpdate: null }),
}));

// The page body is wrapped in <Paywall>, which returns null while the user
// context loads. Pass children through so we can assert on the real content.
vi.mock("@/components/Paywall", () => ({
  Paywall: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const regimeMock = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { regime: () => regimeMock() } };
});

import RegimePage from "@/app/app/regime/page";

function regimeFixture(overrides: Record<string, unknown> = {}) {
  return {
    regime: "NEUTRAL",
    vix: 17.26,
    dxy: 103.5,
    yield_10y: 4.47,
    rate_direction: "SIDEWAYS",
    breadth_pct: 57.4,
    sector_leaders: "Technology, Industrials, Financials",
    updated_at: null,
    ...overrides,
  };
}

beforeEach(() => {
  regimeMock.mockReset();
});

describe("regime page metric labels", () => {
  it("labels breadth_pct as a same-day advancer ratio, never as a 200DMA read", async () => {
    regimeMock.mockResolvedValue(regimeFixture());
    const { container } = render(<RegimePage />);

    await waitFor(() => {
      expect(
        screen.getByText("Advancers today (% of names that moved)"),
      ).toBeInTheDocument();
    });

    // The whole rendered page must not claim a moving-average breadth read.
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/200DMA/);
    expect(text).not.toMatch(/200-day moving average/i);
    // ...nor attribute our universe to an index we don't screen.
    expect(text).not.toMatch(/S&P 1500/);
    // The description must state the exclusion that makes the number readable:
    // unchanged names and names with no price read are out of the denominator.
    expect(text).toMatch(/advancers ÷ \(advancers \+ decliners\)/);
    expect(text).toMatch(/excluded/i);
  });

  it("bands the advancer hint around 50, not around 200DMA levels", async () => {
    // 50% is balanced for an A/D ratio. Under the old 200DMA bands this value
    // rendered "40-55% — narrow. Index masking weakness." — a bearish read of
    // a dead-even session.
    regimeMock.mockResolvedValue(regimeFixture({ breadth_pct: 50 }));
    const { container } = render(<RegimePage />);
    await waitFor(() => {
      expect(container.textContent).toMatch(/roughly balanced/i);
    });
    expect(container.textContent).not.toMatch(/masking weakness/i);
  });

  it("reads a heavy-down session as a decline, not as capitulation/bear territory", async () => {
    regimeMock.mockResolvedValue(regimeFixture({ breadth_pct: 22 }));
    const { container } = render(<RegimePage />);
    await waitFor(() => {
      expect(container.textContent).toMatch(/most moving names fell today/i);
    });
    // One session's A/D ratio is not a regime claim.
    expect(container.textContent).not.toMatch(/bear-market territory/i);
    expect(container.textContent).not.toMatch(/capitulation/i);
  });

  it("labels sector leaders as our own composite ranking, not relative strength vs SPY", async () => {
    regimeMock.mockResolvedValue(regimeFixture());
    const { container } = render(<RegimePage />);

    await waitFor(() => {
      expect(
        screen.getByText("Highest-scoring sectors (our composite)"),
      ).toBeInTheDocument();
    });
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/GICS/);
    // The old definition. The page may still say "NOT relative strength vs
    // SPY" as an explicit disclaimer — what must not survive is the claim
    // that the ranking IS one.
    expect(text).not.toMatch(/by 5-day relative strength/i);
    expect(text).toMatch(/not relative strength vs SPY/i);
    // Must state the sample the ranking is drawn from.
    expect(text).toMatch(/symbols we scored/i);
  });

  it("renders an em-dash when the sector ranking is absent", async () => {
    // The worker writes "—" when it could not rank sectors. An empty string
    // must not collapse into a blank cell either.
    regimeMock.mockResolvedValue(regimeFixture({ sector_leaders: "" }));
    render(<RegimePage />);
    await waitFor(() => {
      expect(
        screen.getByText("Highest-scoring sectors (our composite)"),
      ).toBeInTheDocument();
    });
    const label = screen.getByText("Highest-scoring sectors (our composite)");
    expect(label.nextElementSibling?.textContent).toBe("—");
  });

  it("states the real VIX ladder and drops the invented composite bands", async () => {
    regimeMock.mockResolvedValue(regimeFixture());
    const { container } = render(<RegimePage />);

    await waitFor(() => {
      expect(screen.getByText(/Where this regime label comes from/i)).toBeInTheDocument();
    });
    const text = container.textContent ?? "";

    // The four thresholds that actually run.
    expect(text).toMatch(/below 15 = BULL/i);
    expect(text).toMatch(/15–20 = NEUTRAL/i);
    expect(text).toMatch(/20–25 = CAUTIOUS/i);
    expect(text).toMatch(/25 or above = BEAR/i);
    expect(text).toMatch(/There is no composite/i);

    // The bands that correspond to no variable in the system.
    expect(text).not.toMatch(/composite > 70/i);
    expect(text).not.toMatch(/50-70 = NEUTRAL/i);
    expect(text).not.toMatch(/30-50 = CAUTIOUS/i);
    // VIX percentile vs a trailing 1-year distribution is not computed anywhere.
    expect(text).not.toMatch(/percentile/i);
  });

  it("says plainly that the other figures are context, not inputs to the label", async () => {
    regimeMock.mockResolvedValue(regimeFixture());
    const { container } = render(<RegimePage />);
    await waitFor(() => {
      expect(screen.getByText(/Where this regime label comes from/i)).toBeInTheDocument();
    });
    expect(container.textContent).toMatch(/None of them are inputs to the label/i);
  });

  it("keeps the copy descriptive — no directives, no performance claims", async () => {
    regimeMock.mockResolvedValue(regimeFixture({ regime: "CAUTIOUS" }));
    const { container } = render(<RegimePage />);
    await waitFor(() => {
      expect(screen.getByText("CAUTIOUS")).toBeInTheDocument();
    });
    const text = container.textContent ?? "";
    // The legend used to say "lighten size, tighten stops", "Cash is a
    // position", "Long bias favoured" — prescriptive trading directives.
    expect(text).not.toMatch(/tighten stops/i);
    expect(text).not.toMatch(/cash is a position/i);
    expect(text).not.toMatch(/long bias favoured/i);
    expect(text).not.toMatch(/beat the market/i);
  });
});
