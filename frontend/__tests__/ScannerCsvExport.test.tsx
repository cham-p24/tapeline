/**
 * Scanner page — "Export CSV" button (Pro CSV export).
 *
 * Contract pinned here:
 *   1. The button is ALWAYS visible — a shown-locked feature. Free users see
 *      it labelled with the required tier ("Export CSV · Pro").
 *   2. A Free click opens the csv_export PaywallModal and NEVER hits the
 *      export endpoint.
 *   3. A Pro click calls api.exportScannerCsv with the CURRENT filter params
 *      (what downloads is what's on screen) and opens no paywall.
 *   4. Server-authoritative fallback: if the export call 403s anyway (stale
 *      client tier), the TierGateError routes to the same paywall.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({ useUser: vi.fn() }));
vi.mock("@vercel/analytics", () => ({ track: vi.fn() }));
vi.mock("@/lib/gtag", () => ({ trackEvent: vi.fn() }));
vi.mock("@/lib/useLiveStream", () => ({
  useLiveStream: () => ({ status: "live", lastUpdate: null }),
}));
vi.mock("@/lib/useEarningsCalendar", () => ({
  useEarningsCalendar: () => new Map(),
}));
vi.mock("@/components/TodaysTape", () => ({
  TodaysTape: () => null,
  SECTOR_SLUG_TO_CANONICAL: {},
}));
vi.mock("@/components/RecentTickers", () => ({ RecentTickers: () => null }));
vi.mock("@/components/PresetMenu", () => ({ PresetMenu: () => null }));
vi.mock("@/components/RegimeLabel", () => ({ RegimeLabel: () => null }));
vi.mock("@/components/ScannerLegend", () => ({ ScannerLegend: () => null }));
vi.mock("@/components/LiveBadge", () => ({ LiveBadge: () => null }));
vi.mock("@/components/EarningsPill", () => ({ EarningsPill: () => null }));
vi.mock("@/components/HoverCard", () => ({
  HoverCard: ({ trigger }: { trigger: React.ReactNode }) => <>{trigger}</>,
}));
vi.mock("@/components/ScoreBreakdown", () => ({ ScoreBreakdown: () => null }));
// PaywallModal reduced to a marker div so assertions don't depend on the
// modal's own copy — we only care WHICH feature gate opened.
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
      scanner: vi.fn(),
      watchlistAdd: vi.fn(),
      exportScannerCsv: vi.fn(),
    },
    TierGateError,
    errorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  };
});

import ScannerPage from "@/app/app/scanner/page";
import { useUser } from "@/components/UserContext";
import { api, TierGateError } from "@/lib/api";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;
const mockedScanner = api.scanner as ReturnType<typeof vi.fn>;
const mockedExport = api.exportScannerCsv as ReturnType<typeof vi.fn>;

function setUser(tier: "free" | "pro" | "premium") {
  mockedUseUser.mockReturnValue({
    user: { id: "u1", email: "u@example.com", name: null, tier, created_at: null },
    loading: false, refresh: vi.fn(), signout: vi.fn(),
  });
}

function scannerResponse(tier: string) {
  return {
    count: 0,
    tier,
    row_cap: tier === "free" ? 10 : 1000,
    data_delayed_minutes: 0,
    items: [],
  };
}

describe("Scanner CSV export button", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedScanner.mockReset();
    mockedExport.mockReset();
    window.localStorage.clear();
  });

  it("shows the locked label for Free and opens the paywall instead of downloading", async () => {
    setUser("free");
    mockedScanner.mockResolvedValue(scannerResponse("free"));
    render(<ScannerPage />);

    const btn = await screen.findByRole("button", { name: /Export CSV/ });
    // Shown-locked: visible, labelled with the required tier.
    expect(btn).toHaveTextContent("Export CSV · Pro");

    fireEvent.click(btn);
    await waitFor(() => {
      expect(screen.getByTestId("paywall-csv_export")).toBeInTheDocument();
    });
    // The endpoint is never hit from a locked click.
    expect(mockedExport).not.toHaveBeenCalled();
  });

  it("downloads for Pro with the current filter params and opens no paywall", async () => {
    setUser("pro");
    mockedScanner.mockResolvedValue(scannerResponse("pro"));
    mockedExport.mockResolvedValue(undefined);
    render(<ScannerPage />);

    const btn = await screen.findByRole("button", { name: "Export CSV" });
    expect(btn).toHaveTextContent("Export CSV");
    fireEvent.click(btn);

    await waitFor(() => {
      expect(mockedExport).toHaveBeenCalledTimes(1);
    });
    // Export mirrors what's on screen — default filter state here.
    expect(mockedExport).toHaveBeenCalledWith(
      expect.objectContaining({
        min_score: 0,
        max_score: 100,
        sort: "score",
        order: "desc",
      }),
    );
    expect(screen.queryByTestId("paywall-csv_export")).not.toBeInTheDocument();
  });

  it("opens the paywall when the server 403s anyway (stale client tier)", async () => {
    setUser("pro");
    mockedScanner.mockResolvedValue(scannerResponse("pro"));
    mockedExport.mockRejectedValue(new TierGateError("CSV export is a Pro feature"));
    render(<ScannerPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Export CSV" }));
    await waitFor(() => {
      expect(screen.getByTestId("paywall-csv_export")).toBeInTheDocument();
    });
  });
});
