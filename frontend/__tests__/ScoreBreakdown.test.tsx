/**
 * ScoreBreakdown renders the six factor sub-scores on the scanner hovercard
 * and the ticker page. It must disclose data provenance honestly: only
 * Fundamentals (plus the Price/Volume inputs) is sourced from live data today;
 * the other five sub-scores are placeholders pending their live source, per
 * backend/app/services/polygon_feed.py fetch_snapshots.
 *
 * These assertions lock in that disclosure so a future edit cannot quietly
 * drop the beta tags and let the five placeholders read as live data.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";

const ALL_FACTORS = {
  trend: 72,
  rs: 61,
  fundamentals: 55,
  momentum: 40,
  macro: 48,
  smart_money: 66,
};

describe("ScoreBreakdown provenance disclosure", () => {
  it("renders all six named factors", () => {
    render(<ScoreBreakdown {...ALL_FACTORS} />);
    for (const label of [
      "Trend",
      "Relative strength",
      "Fundamentals",
      "Smart money",
      "Macro",
      "Momentum",
    ]) {
      // Fundamentals also appears in the provenance footnote, so allow >1.
      expect(screen.getAllByText(new RegExp(label, "i")).length).toBeGreaterThan(0);
    }
  });

  it("tags exactly the five not-yet-live factors as beta", () => {
    render(<ScoreBreakdown {...ALL_FACTORS} />);
    // The tooltip is the stable handle for a beta tag. Five factors are
    // placeholders today; Fundamentals is the only live sub-score.
    const tags = screen.getAllByTitle(/not yet powered by live data/i);
    expect(tags).toHaveLength(5);
  });

  it("names Fundamentals (plus Price/Volume) as the live data today", () => {
    render(<ScoreBreakdown {...ALL_FACTORS} />);
    const note = screen.getByText(/live data today/i);
    expect(note.textContent).toMatch(/Fundamentals/);
    expect(note.textContent).toMatch(/Price/);
    expect(note.textContent).toMatch(/Volume/);
  });

  it("keeps the disclosure descriptive — no prescriptive or performance language", () => {
    const { container } = render(<ScoreBreakdown {...ALL_FACTORS} />);
    expect(container.textContent ?? "").not.toMatch(
      /buy|sell|recommend|should|guaranteed|beat the market/i,
    );
  });

  it("renders in compact (hovercard) mode too", () => {
    render(<ScoreBreakdown {...ALL_FACTORS} compact />);
    expect(screen.getAllByTitle(/not yet powered by live data/i)).toHaveLength(5);
    expect(screen.getByText(/live data today/i)).toBeInTheDocument();
  });
});
