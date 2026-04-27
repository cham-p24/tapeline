/**
 * Billing page should expose monthly/annual toggle and reflect the right
 * effective monthly price for each tier when annual is selected.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import BillingPage from "@/app/app/billing/page";

vi.mock("@/components/UserContext", () => ({
  useUser: () => ({
    user: { id: "u1", email: "p@example.com", name: null, tier: "free", created_at: null },
    loading: false, refresh: vi.fn(), signout: vi.fn(),
  }),
}));

vi.mock("@/components/Paywall", () => ({
  Paywall: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe("BillingPage", () => {
  it("renders the three plan cards", () => {
    render(<BillingPage />);
    expect(screen.getByRole("heading", { name: "Free" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pro" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Premium" })).toBeInTheDocument();
  });

  it("defaults to annual billing and shows discounted prices", () => {
    render(<BillingPage />);
    // Annual is the default; Pro should show $24 (effective monthly), Premium $41
    expect(screen.getByText("$24")).toBeInTheDocument();
    expect(screen.getByText("$41")).toBeInTheDocument();
  });

  it("switches to monthly pricing when toggle is clicked", () => {
    render(<BillingPage />);
    const monthlyBtn = screen.getByRole("button", { name: /monthly/i });
    fireEvent.click(monthlyBtn);
    // After toggling, prices should be the headline monthly prices
    expect(screen.getByText("$29")).toBeInTheDocument();
    expect(screen.getByText("$49")).toBeInTheDocument();
  });
});
