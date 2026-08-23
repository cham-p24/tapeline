/**
 * Watchlist page — Pro+ lock after the 2026-08-02 cutover.
 *
 * Contract pinned here:
 *   1. Free user PAST the cutover (freeHasWatchlist() === false): the interactive
 *      list is replaced by a locked upgrade state that teases their saved tickers
 *      ("Your watchlist is a Pro feature", the symbols, an Unlock-with-Pro CTA)
 *      and hides the add control.
 *   2. Free user BEFORE the cutover: the normal interactive watchlist (add input
 *      present, no lock).
 *   3. Paid users (Pro/Premium) are NEVER locked, even past the cutover.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({ useUser: vi.fn() }));
vi.mock("@/lib/useLiveStream", () => ({
  useLiveStream: () => ({ status: "live", lastUpdate: null }),
}));
vi.mock("@/components/LiveBadge", () => ({ LiveBadge: () => null }));
vi.mock("@/components/Skeleton", () => ({ TableSkeleton: () => null }));
vi.mock("@/components/RecentTickers", () => ({ RecentTickers: () => null }));
vi.mock("@/components/WatchlistTabs", () => ({ WatchlistTabs: () => null }));
vi.mock("@/components/FilterBar", () => ({
  SearchBox: () => null,
  useDebounced: (v: string) => v,
}));
vi.mock("@/lib/filters", () => ({ matchesQuery: () => true }));
vi.mock("@/lib/auth", () => ({ canUse: () => false }));
// Mock the FULL @/lib/gtag surface, not just the two fns this file asserts on.
// A partial factory (missing trackEvent) can leak across vitest workers and
// leave an unrelated file — e.g. SignupForm, which uses the real trackEvent —
// seeing `trackEvent is not a function`. Mirror the complete shape the sibling
// Scanner tests mock so this file can never poison another.
vi.mock("@/lib/gtag", () => ({
  trackEvent: vi.fn(),
  trackFirstTickerAdded: vi.fn(),
  trackCapHit: vi.fn(),
  trackUpgradePromptShown: vi.fn(),
  trackUpgradePromptClicked: vi.fn(),
}));
vi.mock("@/components/Paywall", () => ({
  PaywallModal: ({ open, feature }: { open: boolean; feature: string }) =>
    open ? <div data-testid={`paywall-${feature}`} /> : null,
}));
vi.mock("@/lib/pricing", () => ({ freeHasWatchlist: vi.fn() }));
vi.mock("@/lib/api", () => {
  class TierGateError extends Error {
    readonly status = 403;
  }
  return {
    api: {
      watchlist: vi.fn(),
      watchlists: vi.fn(),
      popularTickers: vi.fn(),
      watchlistAdd: vi.fn(),
      watchlistRemove: vi.fn(),
      watchlistMove: vi.fn(),
      exportWatchlistCsv: vi.fn(),
    },
    TierGateError,
    errorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  };
});

import WatchlistPage from "@/app/app/watchlist/page";
import { useUser } from "@/components/UserContext";
import { api } from "@/lib/api";
import { freeHasWatchlist } from "@/lib/pricing";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;
const mockedWatchlist = api.watchlist as ReturnType<typeof vi.fn>;
const mockedWatchlists = api.watchlists as ReturnType<typeof vi.fn>;
const mockedPopular = api.popularTickers as ReturnType<typeof vi.fn>;
const mockedFree = freeHasWatchlist as ReturnType<typeof vi.fn>;

function setUser(tier: "free" | "pro" | "premium") {
  mockedUseUser.mockReturnValue({
    user: { id: "u1", email: "u@example.com", name: null, tier, created_at: null },
    loading: false,
    refresh: vi.fn(),
    signout: vi.fn(),
  });
}

function item(id: number, symbol: string) {
  return {
    id, symbol, price: 100, change_pct_1d: 1, current_score: 80,
    baseline_score: 75, score_delta: 5, signal: "BUY", reason: "x",
    alert_triggered: false, watchlist_id: 1,
  };
}

describe("Watchlist — Pro+ lock after the 2026-08-02 cutover", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedWatchlist.mockReset();
    mockedWatchlists.mockReset();
    mockedPopular.mockReset();
    mockedFree.mockReset();
    mockedWatchlists.mockResolvedValue({ items: [] });
    mockedPopular.mockResolvedValue({ items: [] });
  });

  it("locks the watchlist for a Free user past the cutover and teases their saved tickers", async () => {
    setUser("free");
    mockedFree.mockReturnValue(false); // past cutover
    mockedWatchlist.mockResolvedValue({
      items: [item(1, "AAPL"), item(2, "MSFT"), item(3, "NVDA")],
    });
    render(<WatchlistPage />);

    expect(await screen.findByText("Your watchlist is a Pro feature")).toBeInTheDocument();
    expect(screen.getByText("AAPL")).toBeInTheDocument(); // teased pill
    expect(screen.getByRole("button", { name: /Unlock with Pro/i })).toBeInTheDocument();
    // The add control is gone in the locked state.
    expect(screen.queryByPlaceholderText("AAPL")).not.toBeInTheDocument();
  });

  it("keeps the normal interactive watchlist for a Free user BEFORE the cutover", async () => {
    setUser("free");
    mockedFree.mockReturnValue(true); // before cutover
    mockedWatchlist.mockResolvedValue({ items: [item(1, "TSLA")] });
    render(<WatchlistPage />);

    expect(await screen.findByPlaceholderText("AAPL")).toBeInTheDocument(); // add input
    expect(screen.queryByText("Your watchlist is a Pro feature")).not.toBeInTheDocument();
  });

  it("never locks a Pro user, even past the cutover", async () => {
    setUser("pro");
    mockedFree.mockReturnValue(false); // past cutover, but paid
    mockedWatchlist.mockResolvedValue({ items: [item(1, "TSLA")] });
    render(<WatchlistPage />);

    expect(await screen.findByPlaceholderText("AAPL")).toBeInTheDocument();
    expect(screen.queryByText("Your watchlist is a Pro feature")).not.toBeInTheDocument();
  });
});
