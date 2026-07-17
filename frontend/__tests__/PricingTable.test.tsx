/**
 * PricingTable should render the three plans (Free / Pro / Premium) at the
 * canonical price points. If this test fails, pricing copy has drifted from
 * `backend/app/services/tier.py` — sync them before shipping.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PricingTable } from "@/components/PricingTable";
import { FREE_LIMITS, REFUND } from "@/lib/pricing";

describe("PricingTable", () => {
  it("renders Free, Pro, and Premium plans", () => {
    render(<PricingTable />);
    expect(screen.getByRole("heading", { name: "Free" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pro" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Premium" })).toBeInTheDocument();
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
