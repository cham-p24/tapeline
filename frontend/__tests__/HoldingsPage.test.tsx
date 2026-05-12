/**
 * Holdings page (Recent Insider Buys feed) should render the table for
 * Premium users and the paywall overlay for non-Premium.
 *
 * Page was repurposed in 2026-05 from "Elite 13F holdings" (Quiver) to
 * "Recent insider buys" (SEC Form 4 via Finnhub). Test updated to match.
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
      feed_size: 1,
      items: [
        {
          symbol: "AAPL",
          insider_name: "LEVINSON ARTHUR D",
          transaction_date: "2026-05-06",
          share_change: -100473,
          transaction_price: 285.04,
          transaction_value: 28639286.92,
          code: "S",
        },
      ],
    }),
  },
}));

import { useUser } from "@/components/UserContext";
const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

describe("HoldingsPage", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
  });

  it("shows the insider buys table for a Premium user", async () => {
    mockedUseUser.mockReturnValue({
      user: { id: "u1", email: "p@example.com", name: null, tier: "premium", created_at: null },
      loading: false, refresh: vi.fn(), signout: vi.fn(),
    });
    render(<HoldingsPage />);
    expect(screen.getByText("Recent insider buys")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    // Insider name is title-cased on render
    expect(screen.getByText(/Levinson Arthur D/i)).toBeInTheDocument();
    // SELL action chip with the SEC code
    expect(screen.getByText(/SELL · S/)).toBeInTheDocument();
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
