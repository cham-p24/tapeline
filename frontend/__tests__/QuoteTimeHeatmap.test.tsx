/**
 * The heatmap freshness chip shows the vendor's newest quote time when the API
 * sends one (`freshness.newest_quote_at`, backend Ticker.quote_at), beside the
 * write times it already labels as writes. With none it shows no quote time at
 * all — only the delay note — rather than a write time posing as one.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import HeatmapPage from "@/app/app/heatmap/page";
import { formatBadgeTime } from "@/components/LiveBadge";
import { PRICE_DELAY_NOTE } from "@/lib/freshness";

vi.mock("@/components/UserContext", () => ({ useUser: vi.fn() }));
vi.mock("@/lib/useLiveStream", () => {
  const markLoaded = () => {};
  return {
    AUTO_REFRESH_WINDOW_MS: 180_000,
    useLiveStream: () => ({ status: "connected", lastUpdate: null, markLoaded }),
  };
});
vi.mock("@/lib/api", () => ({
  api: { heatmap: vi.fn() },
  errorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));
vi.mock("@/lib/previews", () => ({ heatmapPreview: vi.fn() }));

import { useUser } from "@/components/UserContext";
import { api } from "@/lib/api";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;
const mockedHeatmap = api.heatmap as ReturnType<typeof vi.fn>;

const QUOTE = "2026-09-18T14:32:00+00:00";

function respond(newestQuote: string | null) {
  mockedHeatmap.mockResolvedValue({
    sectors: [{ sector: "Technology", tickers: [
      { symbol: "NVDA", name: "NVIDIA", score: 88, price: 120.5, change_pct_1d: 2.4, volume: 4e7, signal: "STRONG SETUP" },
    ] }],
    available_sectors: ["Technology"],
    query: null,
    freshness: {
      newest_updated_at: new Date().toISOString(),
      oldest_updated_at: new Date().toISOString(),
      newest_quote_at: newestQuote,
      oldest_quote_at: newestQuote,
      max_stale_minutes: 30,
      ticker_count: 1,
    },
  });
}

describe("heatmap freshness chip", () => {
  beforeEach(() => {
    mockedHeatmap.mockReset();
    mockedUseUser.mockReturnValue({
      user: { id: "u1", email: "u@example.com", name: null, tier: "pro", created_at: null },
      loading: false, refresh: vi.fn(), signout: vi.fn(),
    });
  });

  it("shows the vendor's newest quote time", async () => {
    respond(QUOTE);
    render(<HeatmapPage />);
    await waitFor(() => expect(screen.getByTestId("newest-quote")).toBeInTheDocument());
    expect(screen.getByTestId("newest-quote")).toHaveTextContent(
      `Newest quote: ${formatBadgeTime(new Date(QUOTE))}`,
    );
    expect(screen.getByTestId("price-delay-note")).toHaveTextContent(PRICE_DELAY_NOTE);
  });

  it("shows only the delay note when no tile carries a vendor time", async () => {
    respond(null);
    render(<HeatmapPage />);
    await waitFor(() => expect(screen.getByTestId("price-delay-note")).toBeInTheDocument());
    expect(screen.queryByTestId("newest-quote")).not.toBeInTheDocument();
  });
});
