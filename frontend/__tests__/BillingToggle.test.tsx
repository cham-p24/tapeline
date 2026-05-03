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

  it("defaults to annual billing and shows charm-priced effective monthly", () => {
    render(<BillingPage />);
    // Annual is the default; charm pricing displays Pro at $24.99/mo
    // ($299/yr) and Premium at $40.99/mo ($491/yr).
    expect(screen.getByText("$24.99")).toBeInTheDocument();
    expect(screen.getByText("$40.99")).toBeInTheDocument();
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
