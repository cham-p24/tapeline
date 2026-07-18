/**
 * PricingTable should render the three plans (Free / Pro / Premium) at the
 * canonical price points. If this test fails, pricing copy has drifted from
 * `backend/app/services/tier.py` — sync them before shipping.
 *
 * Annual-default suite (founder decision 2026-07-18): the default render is
 * ANNUAL with the explicit "billed annually ($99/yr)" qualifier on every
 * annual per-month figure; monthly is one toggle click away; and the plan
 * cards + ComparisonTable header share one toggle state so they can never
 * show different billing periods on the same screen.
 */
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PricingTable } from "@/components/PricingTable";
import { ComparisonTable } from "@/components/ComparisonTable";
import { BillingPeriodProvider } from "@/components/BillingToggle";
import { PRICING, FREE_LIMITS, REFUND, usd, billedAnnuallyNote } from "@/lib/pricing";

/** Escape a literal string for use inside a RegExp ("$8.25 (…)" etc.). */
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

describe("PricingTable", () => {
  it("renders Free, Pro, and Premium plans", () => {
    render(<PricingTable />);
    expect(screen.getByRole("heading", { name: "Free" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pro" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Premium" })).toBeInTheDocument();
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

  it("shows the 14-day trial commitment", () => {
    render(<PricingTable />);
    expect(screen.getByText(/14-day Premium trial/i)).toBeInTheDocument();
  });

  it("sells the Free tier the backend actually enforces (FREE_LIMITS)", () => {
    // Post-#343 retune: 12 look-ups/day (24h grace), 5-ticker watchlist,
    // top-10 rows, squeeze top-3 preview, 2 web-push alerts. The card must
    // derive from FREE_LIMITS — a failure here means the marketing copy has
    // drifted from backend/app/services/tier.py again.
    render(<PricingTable />);
    expect(
      screen.getByText(
        new RegExp(`${FREE_LIMITS.dailyLookups} ticker look-ups per day`, "i"),
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`unmetered your first ${FREE_LIMITS.firstSessionGraceHours}h`, "i")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`Top-${FREE_LIMITS.scannerRows} scanner rows`, "i")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`Watchlist \\(${FREE_LIMITS.watchlistTickers} tickers\\)`, "i")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`Squeeze Watch top-${FREE_LIMITS.squeezePreviewRows} preview`, "i")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`${FREE_LIMITS.webPushAlerts} browser push alerts`, "i")),
    ).toBeInTheDocument();
  });

  it("states the refund guarantee from the REFUND single source of truth", () => {
    render(<PricingTable />);
    expect(screen.getByText(REFUND.short)).toBeInTheDocument();
  });

  it("shows the Stripe payment-security trust badge near the CTAs", () => {
    // Trust badge at the decision point (Part 2 / trust badges). Text is
    // split across spans ("Payments secured by" + "Stripe").
    render(<PricingTable />);
    expect(screen.getByText(/Payments secured by/i)).toBeInTheDocument();
    expect(screen.getByText("Stripe")).toBeInTheDocument();
  });
});
