/**
 * PricingTable should render the plan columns at the canonical price points.
 * If this test fails, pricing copy has drifted from
 * `backend/app/services/tier.py` — sync them before shipping.
 *
 * Annual-default suite (founder decision 2026-07-18): the default render is
 * ANNUAL with the explicit "billed annually ($99/yr)" qualifier on every
 * annual per-month figure; monthly is one toggle click away; and the plan
 * cards + ComparisonTable header share one toggle state so they can never
 * show different billing periods on the same screen.
 *
 * CARD GATE (2026-08-22). The $0 column used to be a "Free" plan card with a
 * "Start free" button into /signup and a footnote promising a card-free
 * signup. A new account now adds a card at first sign-in
 * (`services/tier.must_add_card`), so a self-serve free tier is no longer on
 * offer and selling one here would be the most expensive false claim on the
 * site. The $0 column is now the PUBLIC RECORD — genuinely free, genuinely
 * account-free — and the suite below pins that contract in both directions:
 * the public-record column must be there, and no card-free ACCOUNT may be
 * advertised anywhere on this component.
 */
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PricingTable } from "@/components/PricingTable";
import { ComparisonTable } from "@/components/ComparisonTable";
import { BillingPeriodProvider } from "@/components/BillingToggle";
import { PRICING, REFUND, usd, billedAnnuallyNote } from "@/lib/pricing";

/** Escape a literal string for use inside a RegExp ("$8.25 (…)" etc.). */
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

describe("PricingTable", () => {
  it("renders the public-record, Pro, and Premium columns", () => {
    render(<PricingTable />);
    expect(screen.getByRole("heading", { name: /public record/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pro" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Premium" })).toBeInTheDocument();
    // The $0 column is no longer a signup destination: its CTA goes to the
    // public record, not to /signup.
    const free = screen.getByRole("link", { name: /read the record/i });
    expect(free).toHaveAttribute("href", "/scorecard");
  });

  it("defaults to ANNUAL with the billed-annually qualifier and real totals", () => {
    render(<PricingTable />);
    // Annual effective-monthly headline rates by default…
    expect(screen.getByText(usd(PRICING.pro.annualPerMonth))).toBeInTheDocument();
    expect(screen.getByText(usd(PRICING.premium.annualPerMonth))).toBeInTheDocument();
    // …never bare: each carries "billed annually ($99/yr)" from the shared helper.
    expect(screen.getByText(new RegExp(esc(billedAnnuallyNote(PRICING.pro))))).toBeInTheDocument();
    expect(screen.getByText(new RegExp(esc(billedAnnuallyNote(PRICING.premium))))).toBeInTheDocument();
    // No monthly sticker anywhere in the default view.
    expect(screen.queryByText(usd(PRICING.pro.monthly))).not.toBeInTheDocument();
    expect(screen.queryByText(usd(PRICING.premium.monthly))).not.toBeInTheDocument();
  });

  it("keeps monthly one click away and shows it consistently", () => {
    render(<PricingTable />);
    fireEvent.click(screen.getByRole("button", { name: /monthly/i }));
    expect(screen.getByText(usd(PRICING.pro.monthly))).toBeInTheDocument();
    expect(screen.getByText(usd(PRICING.premium.monthly))).toBeInTheDocument();
    // The annual effective rate never lingers on the monthly view.
    expect(screen.queryByText(usd(PRICING.pro.annualPerMonth))).not.toBeInTheDocument();
  });

  it("keeps the plan cards and the comparison header on ONE toggle state", () => {
    // The /pricing page wraps both in BillingPeriodProvider — this is the
    // regression test for the pre-decision screen where cards said $9.99
    // while the always-annual comparison header said $8.25.
    render(
      <BillingPeriodProvider>
        <PricingTable />
        <ComparisonTable />
      </BillingPeriodProvider>,
    );
    // Default: annual everywhere — card + header both show $8.25, no $9.99.
    expect(screen.getAllByText(usd(PRICING.pro.annualPerMonth)).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(usd(PRICING.pro.monthly))).not.toBeInTheDocument();
    // Flip to monthly: both surfaces flip together.
    fireEvent.click(screen.getByRole("button", { name: /monthly/i }));
    expect(screen.getAllByText(usd(PRICING.pro.monthly)).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(usd(PRICING.premium.monthly)).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(usd(PRICING.pro.annualPerMonth))).not.toBeInTheDocument();
    expect(screen.queryByText(usd(PRICING.premium.annualPerMonth))).not.toBeInTheDocument();
  });

  it("shows a sales contact line for B2B / lifetime instead of a third row of cards", () => {
    // Anchor cards (Team / Enterprise / Lifetime) were retired 2026-05-04
    // for visual cleanup — sales-curious buyers email instead.
    render(<PricingTable />);
    expect(screen.getByText(/sales@tapeline\.io/i)).toBeInTheDocument();
  });

  it("states the card-required trial as a mechanism, not just a label", () => {
    // The trial takes a card, so the disclosure has to say WHAT is charged
    // and WHEN — $0 today, first charge on day 14 — plus a real, unpunished
    // way out. A vague "free trial" label here would be the exact failure
    // this test exists to catch.
    render(<PricingTable />);
    expect(screen.getByText(/14-day Premium trial — \$0 today/i)).toBeInTheDocument();
    expect(screen.getByText(/card at first sign-in/i)).toBeInTheDocument();
    expect(screen.getByText(/day 14, at the plan and billing period you picked/i)).toBeInTheDocument();
    // The way out is a link to the free public record, not a dead sentence.
    expect(screen.getByRole("link", { name: /public record/i })).toHaveAttribute(
      "href",
      "/scorecard",
    );
  });

  it("advertises one-click cancel with no survey gate", () => {
    render(<PricingTable />);
    expect(screen.getByText(/Cancel in one click/i)).toBeInTheDocument();
    expect(screen.getByText(/No survey to complete/i)).toBeInTheDocument();
  });

  it("sells the public record — the surface that is genuinely free and account-free", () => {
    // Everything listed in the $0 column has to be reachable with no account:
    // the daily Top 10, the scorecard, the per-ticker pages, the raw exports
    // and the published formula. If a line here ever needs a login, it does
    // not belong in this column.
    render(<PricingTable />);
    expect(screen.getByText(/open to everyone — no account/i)).toBeInTheDocument();
    expect(screen.getByText(/the daily top 10, live/i)).toBeInTheDocument();
    expect(screen.getByText(/full scorecard/i)).toBeInTheDocument();
    expect(screen.getByText(/raw record as CSV and JSON/i)).toBeInTheDocument();
    expect(screen.getByText(/no account, no card, no email/i)).toBeInTheDocument();
  });

  it("never advertises a card-free ACCOUNT, and keeps the grandfather clause visible", () => {
    // The regression this file exists to prevent from here on. Every one of
    // these phrases was live on this component before the card gate and each
    // is now false for a new user. The public record staying free is the
    // claim that survives — it is asserted in the test above, not banned here.
    const { container } = render(<PricingTable />);
    const text = (container.textContent || "").toLowerCase();
    for (const banned of [
      "free forever",
      "never asks for a card",
      "start free",
      "signing up asks for an email and a password",
    ]) {
      expect(text).not.toContain(banned);
    }
    // Grandfathered accounts must be told, on the pricing page, that the wall
    // is not for them.
    expect(text).toContain("before 22 august 2026");
  });

  it("states the refund guarantee from the REFUND single source of truth", () => {
    render(<PricingTable />);
    expect(screen.getByText(REFUND.short)).toBeInTheDocument();
  });

  it("states payment security as a plain fact, not a badge", () => {
    // Deliberately NOT a shield/seal: the claim has to be something the
    // reader can verify (the card form is on Stripe's domain) rather than a
    // security assertion Tapeline makes about itself.
    render(<PricingTable />);
    expect(
      screen.getByText(/Card details are entered on Stripe’s own checkout page/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/never reaches a Tapeline server/i),
    ).toBeInTheDocument();
  });

  it("discloses the charge currency before the redirect", () => {
    // Currency is stated on OUR page so checkout.stripe.com can't surprise.
    // With no API reachable in jsdom the hook keeps its currency-only default
    // sourced from PRICING.currency — and says nothing at all about tax,
    // which is the safe direction when the tax posture is unconfirmed.
    render(<PricingTable />);
    expect(
      screen.getByText(new RegExp(`Charged in ${PRICING.currency}`, "i")),
    ).toBeInTheDocument();
    expect(screen.queryByText(/No tax is added/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Tax may be added/i)).not.toBeInTheDocument();
  });

  it("explains the money-back mechanism at the annual decision point", () => {
    // Annual buyers commit 12 months up front — the useful reassurance is the
    // procedure and the timing, not a seal. Window derives from REFUND.
    render(<PricingTable />);
    expect(
      screen.getByText(new RegExp(`within ${REFUND.windowDays} days of your first charge`, "i")),
    ).toBeInTheDocument();
    expect(screen.getByText(/no form and\s+no reason required/i)).toBeInTheDocument();
    // Monthly view drops it — the annual commitment is what warrants it.
    fireEvent.click(screen.getByRole("button", { name: /monthly/i }));
    expect(
      screen.queryByText(new RegExp(`within ${REFUND.windowDays} days of your first charge`, "i")),
    ).not.toBeInTheDocument();
  });
});
