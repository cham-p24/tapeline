/**
 * RegimeLabel surfaces the market-wide regime that every score is computed
 * under. It must:
 *   - render a descriptive "Regime: <Bull|Neutral|...>" pill once the value
 *     lands, title-casing the backend's all-caps string
 *   - link to the regime detail page
 *   - never use prescriptive language
 *   - render nothing if the regime fetch fails
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

// Mock the api client so we control what regime() resolves to per test.
const regimeMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { regime: () => regimeMock() },
}));

import { RegimeLabel } from "@/components/RegimeLabel";

beforeEach(() => {
  regimeMock.mockReset();
});

describe("RegimeLabel", () => {
  it("renders a descriptive, title-cased regime pill linking to /app/regime", async () => {
    regimeMock.mockResolvedValue({ regime: "BULL" });
    render(<RegimeLabel />);

    await waitFor(() => {
      expect(screen.getByText("Bull")).toBeInTheDocument();
    });
    expect(screen.getByText(/Regime:/)).toBeInTheDocument();
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/app/regime");
    // Descriptive, not prescriptive.
    expect(link.textContent ?? "").not.toMatch(/buy|sell|recommend|should/i);
  });

  it("title-cases other regime values", async () => {
    regimeMock.mockResolvedValue({ regime: "CAUTIOUS" });
    render(<RegimeLabel />);
    await waitFor(() => {
      expect(screen.getByText("Cautious")).toBeInTheDocument();
    });
  });

  it("renders nothing when the regime fetch fails", async () => {
    regimeMock.mockRejectedValue(new Error("boom"));
    const { container } = render(<RegimeLabel />);
    // Give the rejected promise a tick to settle.
    await Promise.resolve();
    expect(container).toBeEmptyDOMElement();
  });
});
