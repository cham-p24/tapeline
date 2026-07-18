/**
 * Congress Trades page — tier-branched data loading.
 *
 * Historical bug this pins down (2026-07-18): the page wrapped its body in
 * <Paywall>, which BLURS its children — but the Premium-gated GET /api/congress
 * 403'd before anything rendered, so the blur sat over an EMPTY table. A
 * non-Premium user saw an upgrade card floating over nothing and therefore zero
 * evidence the feed had any content. Contract now:
 *
 *   1. Premium loads the full feed (api.congress) — filters visible, no locked
 *      section.
 *   2. Free/Pro load ONLY the preview (congressPreview), render the 3 REAL
 *      disclosures unblurred, and show a locked section stating the REAL total
 *      with an upgrade link deep-linked to /app/billing?intent=premium.
 *   3. A failed load renders an error state with retry — never the false
 *      "No disclosed trades" empty state.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import CongressPage from "@/app/app/congress/page";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));

// The page subscribes to the backend SSE stream — jsdom has no EventSource.
vi.mock("@/lib/useLiveStream", () => ({
  useLiveStream: () => ({ status: "live", lastUpdate: null }),
}));

const trades = [
  { id: 1, politician: "Rep A", chamber: "House", party: "D", symbol: "NVDA", direction: "BUY", amount_min: 1001, amount_max: 15000, trade_date: "2026-06-01", disclosed_at: "2026-07-15T00:00:00Z" },
  { id: 2, politician: "Sen B", chamber: "Senate", party: "R", symbol: "MSFT", direction: "SELL", amount_min: 15001, amount_max: 50000, trade_date: "2026-06-02", disclosed_at: "2026-07-14T00:00:00Z" },
  { id: 3, politician: "Rep C", chamber: "House", party: "I", symbol: "AMD", direction: "BUY", amount_min: 1001, amount_max: 15000, trade_date: "2026-06-03", disclosed_at: "2026-07-13T00:00:00Z" },
];

vi.mock("@/lib/api", () => ({
  api: { congress: vi.fn() },
  errorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));

vi.mock("@/lib/previews", () => ({
  congressPreview: vi.fn(),
  FREE_CONGRESS_PREVIEW_LIMIT: 3,
}));

import { useUser } from "@/components/UserContext";
import { api } from "@/lib/api";
import { congressPreview } from "@/lib/previews";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;
const mockedCongress = api.congress as ReturnType<typeof vi.fn>;
const mockedPreview = congressPreview as ReturnType<typeof vi.fn>;

function setUser(tier: "free" | "pro" | "premium") {
  mockedUseUser.mockReturnValue({
    user: { id: "u1", email: "u@example.com", name: null, tier, created_at: null },
    loading: false, refresh: vi.fn(), signout: vi.fn(),
  });
}

describe("CongressPage", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedCongress.mockReset();
    mockedPreview.mockReset();
  });

  it("loads the full feed for a Premium user with no locked section", async () => {
    setUser("premium");
    mockedCongress.mockResolvedValue({ count: 3, items: trades });
    render(<CongressPage />);
    await waitFor(() => {
      expect(screen.getByText("NVDA")).toBeInTheDocument();
    });
    expect(mockedPreview).not.toHaveBeenCalled();
    expect(screen.queryByText(/full feed on Premium/)).not.toBeInTheDocument();
    // Filters are Premium-only and present here.
    expect(screen.getByLabelText("Search ticker or politician")).toBeInTheDocument();
  });

  it("renders REAL preview rows and the real total for a Free user", async () => {
    setUser("free");
    mockedPreview.mockResolvedValue({
      count: 3, preview: true, limit: 3, total_disclosures: 1204, items: trades,
    });
    render(<CongressPage />);
    await waitFor(() => {
      expect(screen.getByText("NVDA")).toBeInTheDocument();
    });
    // The page is NOT empty — all three real disclosures render normally.
    expect(screen.getByText("MSFT")).toBeInTheDocument();
    expect(screen.getByText("AMD")).toBeInTheDocument();
    expect(screen.getByText("Rep A")).toBeInTheDocument();
    // Locked section states the real backend count…
    expect(
      screen.getByText("Showing 3 of 1,204 disclosures — full feed on Premium"),
    ).toBeInTheDocument();
    // …and deep-links to billing with the premium intent pre-selected.
    expect(screen.getByRole("link", { name: /Upgrade to Premium/ }))
      .toHaveAttribute("href", "/app/billing?intent=premium");
    // The Premium-gated endpoint is never touched — no 403 spam on SSE re-fires.
    expect(mockedCongress).not.toHaveBeenCalled();
  });

  it("omits the count rather than inventing one when the feed is empty", async () => {
    setUser("free");
    mockedPreview.mockResolvedValue({
      count: 0, preview: true, limit: 3, total_disclosures: 0, items: [],
    });
    render(<CongressPage />);
    await waitFor(() => {
      expect(screen.getByText("Free shows the 3 most recent disclosures")).toBeInTheDocument();
    });
    expect(screen.queryByText(/of 0 disclosures/)).not.toBeInTheDocument();
  });

  it("shows an error state with retry — not the false empty state — on failure", async () => {
    setUser("free");
    mockedPreview.mockRejectedValue(new Error("backend unreachable"));
    render(<CongressPage />);
    await waitFor(() => {
      expect(screen.getByText(/Couldn't load disclosed trades/)).toBeInTheDocument();
    });
    expect(screen.getByText("backend unreachable")).toBeInTheDocument();
    expect(screen.queryByText(/No disclosed trades loaded yet/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Try again/ })).toBeInTheDocument();
  });
});
