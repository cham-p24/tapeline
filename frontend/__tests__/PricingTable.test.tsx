/**
 * PricingTable should render the three plans (Free / Pro / Premium) at the
 * canonical price points. If this test fails, pricing copy has drifted from
 * `backend/app/services/tier.py` — sync them before shipping.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PricingTable } from "@/components/PricingTable";

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
});
