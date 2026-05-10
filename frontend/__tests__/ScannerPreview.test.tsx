/**
 * ScannerPreview is the landing-hero product shot. It must show the new
 * descriptive signal labels (HIGH CONVICTION etc.), not the deprecated
 * prescriptive ones (BUY NOW etc.) that we replaced for legal posture.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScannerPreview } from "@/components/ScannerPreview";

describe("ScannerPreview", () => {
  it("uses descriptive signal labels, not prescriptive ones", () => {
    render(<ScannerPreview />);
    // Sample of the new labels
    expect(screen.getAllByText("HIGH CONVICTION").length).toBeGreaterThan(0);
    // These prescriptive labels are forbidden — fail loudly if any reappear
    expect(screen.queryByText(/BUY NOW/)).toBeNull();
    expect(screen.queryByText(/STRONG ACCUMULATE/)).toBeNull();
    expect(screen.queryByText(/^HOLD$/)).toBeNull();
  });

  it("renders a Why column with non-empty text", () => {
    render(<ScannerPreview />);
    // Why-column copy has been refactored several times; assert on the
    // stable "uptrend" token that consistently appears in at least one
    // sample row's reasoning rather than a specific phrase.
    expect(screen.getAllByText(/uptrend/i).length).toBeGreaterThan(0);
  });
});
