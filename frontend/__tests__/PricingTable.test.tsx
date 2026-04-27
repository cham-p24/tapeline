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

  it("shows the three anchor offerings (Team / Enterprise / Lifetime)", () => {
    render(<PricingTable />);
    expect(screen.getByRole("heading", { name: "Team" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Enterprise" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Founder.s Lifetime/ })).toBeInTheDocument();
  });

  it("shows the 14-day trial commitment", () => {
    render(<PricingTable />);
    expect(screen.getByText(/14-day Pro trial/i)).toBeInTheDocument();
  });
});
