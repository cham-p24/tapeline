/**
 * Holdings page should render the elite-fund table for Premium users
 * and the paywall overlay for non-Premium.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import HoldingsPage from "@/app/app/holdings/page";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    holdings: vi.fn().mockResolvedValue({
      count: 1,
      items: [{
        id: 1, fund_name: "Berkshire Hathaway", manager: "Buffett", cik: "0001067983",
        symbol: "AAPL", value_usd: 1_500_000_000, shares: 905_000_000, percent_portfolio: 12.3,
        fetched_at: "2026-04-27T00:00:00Z",
      }],
    }),
    holdingsFunds: vi.fn().mockResolvedValue({
      items: [{ name: "Berkshire Hathaway", manager: "Buffett", cik: "0001067983", slug: "berkshire-hathaway" }],
    }),
  },
}));

import { useUser } from "@/components/UserContext";
const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

describe("HoldingsPage", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
  });

  it("shows the holdings table for a Premium user", async () => {
    mockedUseUser.mockReturnValue({
      user: { id: "u1", email: "p@example.com", name: null, tier: "premium", created_at: null },
      loading: false, refresh: vi.fn(), signout: vi.fn(),
    });
    render(<HoldingsPage />);
    expect(screen.getByText("Elite holdings")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Berkshire Hathaway")).toBeInTheDocument();
    });
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("$1.50B")).toBeInTheDocument();
  });

  it("blocks the data behind a paywall for a Pro user", () => {
    mockedUseUser.mockReturnValue({
      user: { id: "u1", email: "p@example.com", name: null, tier: "pro", created_at: null },
      loading: false, refresh: vi.fn(), signout: vi.fn(),
    });
    render(<HoldingsPage />);
    expect(screen.getByText(/Premium feature/i)).toBeInTheDocument();
  });
});
