/**
 * LandingCta — the shared above-the-fold conversion block used across the
 * high-traffic "front door" marketing pages (/best-stock-scanners,
 * /best-stocks-for/*, /best-finviz-alternatives, /compare/*).
 *
 * These pages were ~50% of all site traffic and converted nothing because
 * the only signup CTA sat at the very bottom of a long article. This block is
 * the fix, so its contract is load-bearing:
 *   1. A primary CTA linking to /signup?from=<slug> with the scanner-forward
 *      "no card" copy — and it must only ever use a slug the signup page
 *      actually personalises on (finviz | screener | scorecard | compare).
 *   2. The offer must be legible at the point of interest: free-forever tier,
 *      the founding Pro price (from lib/pricing.ts, never hardcoded), and the
 *      30-day money-back guarantee.
 *   3. The live scanner preview (product proof) renders by default and can be
 *      suppressed on pages that already show a data table above the fold.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { LandingCta } from "@/components/LandingCta";
import { PRICING, usd } from "@/lib/pricing";

// ScannerPreview is an async server component (it fetches the real anonymous
// top-10 on the server). RTL/jsdom can't render async components inline, so
// stub it — its own contract (real data, truthful labels, sample fallback)
// is covered in ScannerPreview.test.tsx. Here we only verify LandingCta's
// show/hide wiring.
vi.mock("@/components/ScannerPreview", () => ({
  ScannerPreview: () =>
    require("react").createElement("div", { "data-testid": "scanner-preview" }),
}));

describe("LandingCta", () => {
  it("renders a primary signup CTA with the scanner-forward, no-card copy", () => {
    render(<LandingCta from="screener" showPreview={false} />);
    const primary = screen.getByRole("link", { name: /try the live scanner free — no card/i });
    expect(primary).toBeInTheDocument();
    expect(primary).toHaveAttribute("href", "/signup?from=screener");
  });

  it("message-matches the signup page via the ?from= slug", () => {
    const { rerender } = render(<LandingCta from="finviz" showPreview={false} />);
    expect(
      screen.getByRole("link", { name: /try the live scanner free/i }),
    ).toHaveAttribute("href", "/signup?from=finviz");

    rerender(<LandingCta from="compare" showPreview={false} />);
    expect(
      screen.getByRole("link", { name: /try the live scanner free/i }),
    ).toHaveAttribute("href", "/signup?from=compare");
  });

  it("makes the offer clear: free forever tier, founding price, money-back", () => {
    render(<LandingCta from="screener" showPreview={false} />);
    expect(screen.getByText(/free forever tier/i)).toBeInTheDocument();
    expect(screen.getByText(/30-day money-back guarantee/i)).toBeInTheDocument();
    // Founding Pro price is read from the single source of truth, not
    // hardcoded. The price sits in its own <li> split across text nodes
    // ("Pro from", "$9.99", "/mo · ", "$99.00", "/yr"), so match on the
    // list item's combined textContent rather than a single text node.
    const offerStrip = screen.getByRole("list", { name: /pricing and guarantee/i });
    const text = offerStrip.textContent ?? "";
    expect(text).toContain(`Pro from ${usd(PRICING.pro.monthly)}`);
    expect(text).toContain(usd(PRICING.pro.annual));
  });

  it("links the secondary CTA to the public scorecard by default", () => {
    render(<LandingCta from="screener" showPreview={false} />);
    expect(
      screen.getByRole("link", { name: /see the public scorecard/i }),
    ).toHaveAttribute("href", "/scorecard");
  });

  it("shows the scanner preview (product proof) by default", () => {
    render(<LandingCta from="screener" />);
    expect(screen.getByTestId("scanner-preview")).toBeInTheDocument();
    expect(screen.getByText(/a live preview of the tapeline scanner/i)).toBeInTheDocument();
  });

  it("suppresses the preview when showPreview is false", () => {
    render(<LandingCta from="compare" showPreview={false} />);
    expect(screen.queryByTestId("scanner-preview")).toBeNull();
    // The CTA + offer strip still render.
    expect(
      screen.getByRole("link", { name: /try the live scanner free/i }),
    ).toBeInTheDocument();
  });
});
