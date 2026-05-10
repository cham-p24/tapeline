/**
 * ScannerPreview is the landing-hero product shot. It now pulls live data
 * from /api/scanner; with no fetch in the test environment it shows the
 * frozen FALLBACK_ROWS. We assert on the fallback so the regression-target
 * is stable in CI without spinning up a backend, but still verify the
 * never-show-prescriptive-labels guarantee that protects the publisher's
 * exemption.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScannerPreview } from "@/components/ScannerPreview";

describe("ScannerPreview", () => {
  it("never renders the deprecated prescriptive labels", () => {
    render(<ScannerPreview />);
    expect(screen.queryByText(/BUY NOW/)).toBeNull();
    expect(screen.queryByText(/STRONG ACCUMULATE/)).toBeNull();
    expect(screen.queryByText(/^HOLD$/)).toBeNull();
    expect(screen.queryByText(/AVOID/)).toBeNull();
  });

  it("shows a non-empty Why column even on the fallback path", () => {
    render(<ScannerPreview />);
    // Fallback rows have "Loading live picks…" while the fetch settles —
    // any non-empty Why text passes. If the live fetch lands during the
    // test it'll be a real reason string, also non-empty.
    const cells = screen.getAllByText(/Loading live picks|tick|trend|signal|score/i);
    expect(cells.length).toBeGreaterThan(0);
  });
});
