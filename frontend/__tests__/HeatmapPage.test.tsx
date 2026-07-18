/**
 * Market Heatmap page — tier-branched data loading.
 *
 * Historical bug this pins down (2026-07-18): the page wrapped its body in
 * <Paywall>, which BLURS its children — but the Pro-gated GET /api/heatmap
 * 403'd before anything rendered, so the blur sat over an EMPTY grid reading
 * "Showing 0 tickers across 0 sectors". A Free user's product shot sold
 * nothing. Contract now:
 *
 *   1. Pro+ loads the full per-ticker heatmap (api.heatmap) — filters visible,
 *      no locked section.
 *   2. Free loads ONLY the public sector aggregate (heatmapPreview) and
 *      renders REAL, populated sector tiles unblurred, with a locked section
 *      stating the REAL live-ticker count and deep-linking to
 *      /app/billing?intent=pro.
 *   3. The Pro-gated endpoint is never touched by a Free user.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import HeatmapPage from "@/app/app/heatmap/page";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));

vi.mock("@/lib/useLiveStream", () => ({
  useLiveStream: () => ({ status: "live", lastUpdate: null }),
}));

const proSectors = [
  {
    sector: "Technology",
    tickers: [
      { symbol: "NVDA", name: "NVIDIA Corp", score: 88, price: 120.5, change_pct_1d: 2.4, volume: 40_000_000, signal: "BUY" },
    ],
  },
];

const previewSectors = [
  { sector: "Technology", change_pct_1d: 1.24, ticker_count: 312 },
  { sector: "Energy", change_pct_1d: -0.87, ticker_count: 96 },
  { sector: "Health Care", change_pct_1d: 0.11, ticker_count: 140 },
];

vi.mock("@/lib/api", () => ({
  api: { heatmap: vi.fn() },
  errorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));

vi.mock("@/lib/previews", () => ({
  heatmapPreview: vi.fn(),
}));

import { useUser } from "@/components/UserContext";
import { api } from "@/lib/api";
import { heatmapPreview } from "@/lib/previews";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;
const mockedHeatmap = api.heatmap as ReturnType<typeof vi.fn>;
const mockedPreview = heatmapPreview as ReturnType<typeof vi.fn>;

function setUser(tier: "free" | "pro" | "premium") {
  mockedUseUser.mockReturnValue({
    user: { id: "u1", email: "u@example.com", name: null, tier, created_at: null },
    loading: false, refresh: vi.fn(), signout: vi.fn(),
  });
}

describe("HeatmapPage", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedHeatmap.mockReset();
    mockedPreview.mockReset();
  });

  it("loads the full per-ticker heatmap for a Pro user", async () => {
    setUser("pro");
    mockedHeatmap.mockResolvedValue({
      sectors: proSectors,
      available_sectors: ["Technology"],
      query: null,
      freshness: null,
    });
    render(<HeatmapPage />);
    await waitFor(() => {
      expect(screen.getByText("NVDA")).toBeInTheDocument();
    });
    expect(mockedPreview).not.toHaveBeenCalled();
    expect(screen.queryByText(/are on Pro/)).not.toBeInTheDocument();
    // Pro-only ticker search is present.
    expect(screen.getByPlaceholderText(/Search ticker/)).toBeInTheDocument();
  });

  it("renders a REAL populated sector heatmap for a Free user", async () => {
    setUser("free");
    mockedPreview.mockResolvedValue({ count: 3, sectors: previewSectors });
    render(<HeatmapPage />);
    await waitFor(() => {
      expect(screen.getByText("Technology")).toBeInTheDocument();
    });
    // The blur used to cover nothing — now there are real, populated tiles.
    expect(screen.getByText("Energy")).toBeInTheDocument();
    expect(screen.getByText("Health Care")).toBeInTheDocument();
    expect(screen.getByText("+1.24%")).toBeInTheDocument();
    expect(screen.getByText("-0.87%")).toBeInTheDocument();
    expect(screen.getByText("312 tickers")).toBeInTheDocument();
    // Locked copy states the REAL summed live-ticker count (312+96+140 = 548).
    expect(
      screen.getByText("Per-ticker tiles for 548 live tickers are on Pro"),
    ).toBeInTheDocument();
    // Deep-links to billing with the pro intent pre-selected.
    expect(screen.getByRole("link", { name: /Upgrade to Pro/ }))
      .toHaveAttribute("href", "/app/billing?intent=pro");
    // Pro-gated endpoint untouched, and the Pro-only filters are hidden.
    expect(mockedHeatmap).not.toHaveBeenCalled();
    expect(screen.queryByPlaceholderText(/Search ticker/)).not.toBeInTheDocument();
  });

  it("omits the ticker count rather than inventing one when there is no data", async () => {
    setUser("free");
    mockedPreview.mockResolvedValue({ count: 0, sectors: [] });
    render(<HeatmapPage />);
    await waitFor(() => {
      expect(screen.getByText("Per-ticker tiles are on Pro")).toBeInTheDocument();
    });
    expect(screen.getByText(/No sector data available right now/)).toBeInTheDocument();
    expect(screen.queryByText(/0 live tickers/)).not.toBeInTheDocument();
  });

  it("shows an error state with retry when the preview load fails", async () => {
    setUser("free");
    mockedPreview.mockRejectedValue(new Error("backend unreachable"));
    render(<HeatmapPage />);
    await waitFor(() => {
      expect(screen.getByText(/Couldn't load the heatmap/)).toBeInTheDocument();
    });
    expect(screen.getByText("backend unreachable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Try again/ })).toBeInTheDocument();
  });
});
