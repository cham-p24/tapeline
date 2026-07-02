/**
 * PricingProof — the /pricing public-record proof block (pattern ported
 * from the signup page). Three things matter:
 *   1. Shows days-on-record from /api/scorecard, linking to /scorecard
 *      so the claim is auditable in one click.
 *   2. Renders nothing when the record is empty (days_tracked = 0) — an
 *      empty proof block would be worse than none.
 *   3. Renders nothing when the API call fails (silent fallback).
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { PricingProof } from "@/app/pricing/PricingProof";

function mockScorecard(days_tracked: number) {
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ summary: { days_tracked }, days: {} }),
    }),
  ) as unknown as typeof fetch;
}

describe("PricingProof", () => {
  it("shows the days-on-record proof linking to /scorecard", async () => {
    mockScorecard(42);
    render(<PricingProof />);

    expect(await screen.findByText("42")).toBeInTheDocument();
    expect(screen.getByText(/days on the record/i)).toBeInTheDocument();
    expect(
      screen.getByText(/logged same-day, never edited/i),
    ).toBeInTheDocument();
    // The whole block is a link to the auditable record.
    expect(screen.getByRole("link")).toHaveAttribute("href", "/scorecard");
  });

  it("renders nothing when no days are logged yet", async () => {
    mockScorecard(0);
    const { container } = render(<PricingProof />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the scorecard call fails", async () => {
    global.fetch = vi.fn(() =>
      Promise.reject(new Error("network down")),
    ) as unknown as typeof fetch;
    const { container } = render(<PricingProof />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
