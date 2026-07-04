/**
 * CompareLayout powers 14 of the 17 /compare/* pages. Before the front-door
 * conversion pass, these pages' only signup CTA sat below the FAQ — a
 * comparison-shopper who skimmed the table and left never saw an offer. This
 * suite pins the two things that fix must keep true on every compare page:
 *   1. An above-the-fold primary CTA to /signup?from=compare, before the
 *      comparison table.
 *   2. The mid-funnel email capture still renders for visitors not ready to
 *      start an account.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CompareLayout } from "@/components/CompareLayout";

const baseProps = {
  competitor: "TestRival",
  competitorUrl: "https://example.com",
  competitorPriceMonthly: 20,
  slug: "testrival",
  heading: "Tapeline vs TestRival",
  lede: "A one-line lede for the comparison.",
  wins: [{ label: "Composite score", tapeline: "✓ Yes", competitor: "Not available" }],
  tradeoffs: [
    { label: "Universe size", tapeline: "~2,500", competitor: "9,000+", note: "note text" },
  ],
  faq: [{ q: "Is this a test?", a: "Yes." }],
  verifiedOn: "2026-07-04",
};

describe("CompareLayout", () => {
  it("renders an above-the-fold signup CTA to /signup?from=compare", () => {
    render(<CompareLayout {...baseProps} />);
    const ctas = screen.getAllByRole("link", { name: /try the live scanner free — no card/i });
    expect(ctas.length).toBeGreaterThan(0);
    ctas.forEach((cta) => expect(cta).toHaveAttribute("href", "/signup?from=compare"));
  });

  it("surfaces the founding offer (free tier + money-back) on the page", () => {
    render(<CompareLayout {...baseProps} />);
    expect(screen.getAllByText(/free forever tier/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/30-day money-back guarantee/i).length).toBeGreaterThan(0);
  });

  it("renders the mid-funnel email capture form", () => {
    render(<CompareLayout {...baseProps} />);
    // NewsletterCapture renders a labelled form + its submit button.
    expect(screen.getByRole("form", { name: /newsletter signup/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /get free daily picks/i }),
    ).toBeInTheDocument();
  });
});
