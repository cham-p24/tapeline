/**
 * Watchlist page — "Export CSV" button (Pro CSV export).
 *
 * Same contract as the scanner's button (see ScannerCsvExport.test.tsx):
 * shown-locked for Free (click opens the csv_export paywall, endpoint never
 * hit), downloads for Pro via api.exportWatchlistCsv (scoped to the active
 * list tab — null = all lists).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({ useUser: vi.fn() }));
vi.mock("@/lib/useLiveStream", () => ({
  useLiveStream: () => ({ status: "live", lastUpdate: null }),
}));
vi.mock("@/components/LiveBadge", () => ({ LiveBadge: () => null }));
vi.mock("@/components/RecentTickers", () => ({ RecentTickers: () => null }));
vi.mock("@/components/WatchlistTabs", () => ({ WatchlistTabs: () => null }));
vi.mock("@/components/Paywall", () => ({
  PaywallModal: ({ open, feature }: { open: boolean; feature: string }) =>
    open ? <div data-testid={`paywall-${feature}`} /> : null,
}));
vi.mock("@/lib/api", () => {
  class TierGateError extends Error {
    readonly status = 403;
    readonly requiredTier: "pro" | "premium";
    constructor(message: string) {
      super(message);
      this.name = "TierGateError";
      this.requiredTier = /premium/i.test(message) ? "premium" : "pro";
    }
  }
  return {
    api: {
      watchlist: vi.fn(),
      watchlists: vi.fn(),
      popularTickers: vi.fn(),
      watchlistAdd: vi.fn(),
      watchlistMove: vi.fn(),
      watchlistRemove: vi.fn(),
      exportWatchlistCsv: vi.fn(),
    },
    TierGateError,
    errorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  };
});

import WatchlistPage from "@/app/app/watchlist/page";
import { useUser } from "@/components/UserContext";
import { api } from "@/lib/api";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;
const mockedWatchlist = api.watchlist as ReturnType<typeof vi.fn>;
const mockedWatchlists = api.watchlists as ReturnType<typeof vi.fn>;
const mockedPopular = api.popularTickers as ReturnType<typeof vi.fn>;
const mockedExport = api.exportWatchlistCsv as ReturnType<typeof vi.fn>;

function setUser(tier: "free" | "pro" | "premium") {
  mockedUseUser.mockReturnValue({
    user: { id: "u1", email: "u@example.com", name: null, tier, created_at: null },
    loading: false, refresh: vi.fn(), signout: vi.fn(),
  });
}

describe("Watchlist CSV export button", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedWatchlist.mockReset().mockResolvedValue({ count: 0, items: [] });
    mockedWatchlists.mockReset().mockResolvedValue({ count: 0, items: [] });
    mockedPopular.mockReset().mockResolvedValue({ items: [], cached: false });
    mockedExport.mockReset();
  });

  it("shows the locked label for Free and opens the paywall instead of downloading", async () => {
    setUser("free");
    render(<WatchlistPage />);

    const btn = await screen.findByRole("button", { name: /Export CSV/ });
    expect(btn).toHaveTextContent("Export CSV · Pro");

    fireEvent.click(btn);
    await waitFor(() => {
      expect(screen.getByTestId("paywall-csv_export")).toBeInTheDocument();
    });
    expect(mockedExport).not.toHaveBeenCalled();
  });

  it("downloads for Pro (all lists when no tab is active) with no paywall", async () => {
    setUser("pro");
    mockedExport.mockResolvedValue(undefined);
    render(<WatchlistPage />);

    const btn = await screen.findByRole("button", { name: "Export CSV" });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(mockedExport).toHaveBeenCalledTimes(1);
    });
    // activeId is null on load — export covers every list.
    expect(mockedExport).toHaveBeenCalledWith(null);
    expect(screen.queryByTestId("paywall-csv_export")).not.toBeInTheDocument();
  });
});
