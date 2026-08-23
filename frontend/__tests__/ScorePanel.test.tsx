/**
 * The score panel — the top of the ticker page.
 *
 * What these tests protect is the difference between a fact and a decision
 * aid. "Trend 88" is a fact. "Trend 88 — 91st percentile of Health Care
 * (n=612), weight 25" is a decision aid, because a reader can see how much it
 * counts and what it was measured against. Every assertion below is about
 * keeping one of those three companions attached to the number: the weight,
 * the peer group, and the denominator.
 *
 * The other half is the refusals. Where we cannot rank honestly the panel must
 * SAY SO in words — a blank cell would be indistinguishable from a bug, and a
 * percentile computed over a handful of rows would be worse than either.
 */
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { ScorePanel } from "@/components/ScorePanel";

const BREAKDOWN = {
  trend: { value: 88, weight: 25, label: "Trend" },
  rs: { value: 81, weight: 20, label: "Relative strength" },
  fundamentals: { value: 34, weight: 15, label: "Fundamentals" },
  smart_money: { value: 52, weight: 15, label: "Smart money" },
  macro: { value: 61, weight: 15, label: "Macro" },
  momentum: { value: 70, weight: 10, label: "Momentum" },
};

const PERCENTILES = {
  score: { percentile: 84, n: 763, peer_group: "Health Care" },
  trend: { percentile: 91, n: 612, peer_group: "Health Care" },
  rs: { percentile: 84, n: 640, peer_group: "Health Care" },
  // Fundamentals coverage is ~15% of the universe: in a real sector this is
  // exactly where the peer count runs out.
  fundamentals: { percentile: 22, n: 11, peer_group: "Health Care" },
  smart_money: null,
  macro: { percentile: 66, n: 601, peer_group: "Health Care" },
  momentum: { percentile: 71, n: 612, peer_group: "Health Care" },
};

function renderPanel(overrides: Partial<React.ComponentProps<typeof ScorePanel>> = {}) {
  return render(
    <ScorePanel
      symbol="ABC"
      score={71}
      signal="STRONG SETUP"
      confidencePct={82}
      breakdown={BREAKDOWN}
      percentiles={PERCENTILES}
      {...overrides}
    />,
  );
}

/** The <tr> whose row header is this factor. */
function factorRow(label: string): HTMLElement {
  return screen.getByRole("rowheader", { name: label }).closest("tr") as HTMLElement;
}

describe("ScorePanel", () => {
  it("prints the composite with its peer group and denominator", () => {
    renderPanel();
    expect(screen.getByTestId("composite-ranking").textContent).toBe(
      "84th percentile of Health Care (n=763)",
    );
  });

  it("shows all six factors with their published weights", () => {
    renderPanel();
    for (const [label, weight] of [
      ["Trend", "25"],
      ["Relative strength", "20"],
      ["Fundamentals", "15"],
      ["Smart money", "15"],
      ["Macro", "15"],
      ["Momentum", "10"],
    ] as const) {
      const cells = within(factorRow(label)).getAllByRole("cell");
      // [score, weight, ranking]
      expect(cells[1].textContent).toBe(weight);
    }
  });

  it("attaches the peer group and n to every factor percentile it prints", () => {
    renderPanel();
    expect(within(factorRow("Trend")).getAllByRole("cell")[2].textContent).toBe(
      "91st percentile of Health Care (n=612)",
    );
    expect(within(factorRow("Macro")).getAllByRole("cell")[2].textContent).toBe(
      "66th percentile of Health Care (n=601)",
    );
  });

  it("refuses to rank on a thin peer group, and says why", () => {
    renderPanel();
    // n=11 covered peers — a single row would move the figure by 9 points.
    const cell = within(factorRow("Fundamentals")).getAllByRole("cell")[2];
    expect(cell.textContent).toBe("not enough covered peers to rank");
    expect(cell.textContent).not.toMatch(/\d+(st|nd|rd|th)/);
  });

  it("prints a reason rather than a blank when a factor has no ranking at all", () => {
    renderPanel();
    expect(within(factorRow("Smart money")).getAllByRole("cell")[2].textContent).toBe(
      "no peer ranking available",
    );
  });

  it("renders every factor row even when the percentile block is missing entirely", () => {
    // A frontend deploy ahead of the backend.
    renderPanel({ percentiles: undefined });
    for (const label of ["Trend", "Relative strength", "Fundamentals", "Smart money", "Macro", "Momentum"]) {
      expect(within(factorRow(label)).getAllByRole("cell")[2].textContent).toBe(
        "no peer ranking available",
      );
    }
    expect(screen.getByTestId("composite-ranking").textContent).toBe(
      "no peer ranking available",
    );
  });

  it("never substitutes 0 for a sub-score we do not hold", () => {
    renderPanel({
      breakdown: { ...BREAKDOWN, fundamentals: { value: null, weight: 15, label: "Fundamentals" } },
    });
    expect(within(factorRow("Fundamentals")).getAllByRole("cell")[0].textContent).toBe("—");
  });

  it("carries the one-sentence read, built only from the percentile payload", () => {
    renderPanel();
    const read = screen.getByTestId("ticker-read").textContent ?? "";
    expect(read).toContain("Score 71.0/100 — 84th percentile of Health Care (n=763).");
    expect(read).toContain("Trend 91st (n=612)");
    // Fundamentals was refused a ranking, so it cannot be the "lowest" —
    // the read may only cite what was actually ranked.
    expect(read).not.toContain("Fundamentals");
  });

  it("discloses the minimum peer count and the weight rule in the footnote", () => {
    const { container } = renderPanel();
    expect(container.textContent).toMatch(/at least 30 of them/i);
    expect(container.textContent).toMatch(/sum to 100/i);
  });

  it("uses a real table with row headers, inside its own scroll container", () => {
    const { container } = renderPanel();
    const table = container.querySelector("table");
    expect(table).not.toBeNull();
    expect(table!.querySelector("caption")).not.toBeNull();
    expect(table!.parentElement!.className).toContain("overflow-x-auto");
    expect(container.querySelectorAll("th[scope='row']")).toHaveLength(6);
    expect(container.querySelectorAll("th[scope='col']")).toHaveLength(4);
  });

  it("stays descriptive — no advice, target, or performance claim anywhere", () => {
    const { container } = renderPanel();
    expect(container.textContent ?? "").not.toMatch(
      /\bbuy\b|\bsell\b|recommend|price target|fair value|undervalued|overvalued|outperform|beat the market/i,
    );
  });
});
