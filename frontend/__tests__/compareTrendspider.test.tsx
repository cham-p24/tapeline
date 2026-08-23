/**
 * /compare/trendspider — the paid-scanner comparison page for the tool the
 * engaged ICP (beginner-intermediate swing traders on $10-50k accounts)
 * actually cross-shops. Two things must stay true on this page:
 *   1. Competitor pricing is hedged AND dated — TrendSpider's list prices
 *      change often, so the page must never present them as guaranteed-
 *      current ("as of August 2026 … check their site").
 *   2. The copy stays inside the compliance boundary: descriptive only,
 *      no performance claims, no competitor rating-label vocabulary.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import VsTrendSpiderPage from "@/app/compare/trendspider/page";

describe("/compare/trendspider", () => {
  it("renders the comparison with an H1 naming both products", () => {
    render(<VsTrendSpiderPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /tapeline vs trendspider/i }),
    ).toBeInTheDocument();
  });

  it("hedges and dates competitor pricing instead of presenting it as current", () => {
    const { container } = render(<VsTrendSpiderPage />);
    const text = container.textContent || "";
    expect(text).toMatch(/as of August 2026/i);
    expect(text).toMatch(/check their site for current pricing/i);
  });

  it("states Tapeline founding pricing and the card-required trial", () => {
    const { container } = render(<VsTrendSpiderPage />);
    const text = container.textContent || "";
    expect(text).toMatch(/\$8\.25\/mo/);
    expect(text).toMatch(/\$16\.58\/mo/);
    // The trial takes a card from #548 onward; what stays card-free is reading
    // the record. Assert that split rather than a bare "no card".
    expect(text).toMatch(/14-day trial/i);
    expect(text).toMatch(/free to read — no account/i);
  });

  it("contains no banned performance-claim or rating-label phrases", () => {
    const { container } = render(<VsTrendSpiderPage />);
    const text = (container.textContent || "").toLowerCase();
    for (const banned of [
      "beat the market",
      "strong buy",
      "guaranteed returns",
      "winning stocks",
      "you should buy",
      "we recommend buying",
    ]) {
      expect(text).not.toContain(banned);
    }
  });

  it("names the six factors and the weight ordering, never the exact weights", () => {
    const { container } = render(<VsTrendSpiderPage />);
    const text = container.textContent || "";
    expect(text).toMatch(/Trend, Relative Strength, Fundamentals, Smart Money, Macro, Momentum/);
    // PR #342 disclosure boundary: the numeric weights are not public.
    expect(text).not.toMatch(/0\.25|0\.20|0\.15|0\.10|25%\s*trend|20%\s*relative/i);
  });
});
