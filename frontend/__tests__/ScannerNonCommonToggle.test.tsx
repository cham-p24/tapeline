/**
 * Scanner page: the "Notes, preferreds & warrants" toggle.
 *
 * Same contract as ScannerLeveragedToggle.test.tsx, for the second default
 * exclusion (backend SCANNER_INCLUDE_NON_COMMON_DEFAULT):
 *   1. Off on first render, and the first scan sends NO include_non_common:
 *      the server's default does the excluding, so it lives in one place.
 *   2. Ticking it refetches WITH include_non_common.
 *   3. The CSV export sends the same param as the on-screen scan.
 *   4. A flagged row is LABELLED, once, and an ordinary row is not.
 *   5. COMPLIANCE: nothing it renders reads as a judgement about the listing.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({ useUser: vi.fn() }));
vi.mock("@/lib/gtag", () => ({
  trackEvent: vi.fn(),
  trackEventOnce: vi.fn(),
  trackFirstTickerAdded: vi.fn(),
  trackCapHit: vi.fn(),
  trackUpgradePromptShown: vi.fn(),
  trackUpgradePromptClicked: vi.fn(),
}));
vi.mock("@/lib/useLiveStream", () => {
  // Stable like the real hook's useCallback: pages list it in effect deps.
  const markLoaded = () => {};
  return {
    useLiveStream: () => ({ status: "connected", lastUpdate: null, markLoaded }),
  };
});
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
vi.mock("@/components/Paywall", () => ({
  PaywallModal: ({ open, feature }: { open: boolean; feature: string }) =>
    open ? <div data-testid={`paywall-${feature}`} /> : null,
}));
vi.mock("@/lib/api", () => {
  class TierGateError extends Error {
    readonly status = 403;
    readonly requiredTier: "pro" | "premium" = "pro";
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
import { api } from "@/lib/api";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;
const mockedScanner = api.scanner as ReturnType<typeof vi.fn>;
const mockedExport = api.exportScannerCsv as ReturnType<typeof vi.fn>;

function setUser(tier: "free" | "pro" | "premium") {
  mockedUseUser.mockReturnValue({
    user: { id: "u1", email: "u@example.com", name: null, tier, created_at: null },
    loading: false,
    refresh: vi.fn(),
    signout: vi.fn(),
  });
}

// Real names from the live universe on 2026-09-18. GREEL read STRONG SETUP
// at 70.4 that day; it is a senior note, not Greenidge's common stock.
const NOTE_ROW = {
  symbol: "GREEL",
  name: "Greenidge Generation Holdings Inc. 8.50% Senior Notes due 2026",
  sector: "Information Technology",
  asset_class: "equity",
  is_leveraged: false,
  is_non_common: true,
  score: 70.4,
  signal: "STRONG SETUP",
  price: 24.1,
  change_pct_1d: 0.2,
  change_pct_5d: 0.4,
  change_pct_1m: 1.1,
  volume: 7000,
  updated_at: "2026-09-18T21:00:00Z",
};

const STOCK_ROW = {
  ...NOTE_ROW,
  symbol: "PFBC",
  name: "Preferred Bank",
  sector: "Financials",
  is_non_common: false,
  score: 62.5,
  signal: "CONSTRUCTIVE",
};

function scannerResponse(items: object[]) {
  return {
    count: items.length,
    tier: "pro",
    row_cap: 1000,
    total_matched: null,
    data_delayed_minutes: 0,
    items,
  };
}

/** The control, found the way a user finds it: by its visible label. */
function toggle() {
  return screen.getByRole("checkbox", { name: /notes, preferreds & warrants/i });
}

function scanParams(n: number): Record<string, unknown> {
  return mockedScanner.mock.calls[n][0] as Record<string, unknown>;
}

describe("Scanner notes, preferreds & warrants toggle", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedScanner.mockReset();
    mockedExport.mockReset();
    window.localStorage.clear();
    setUser("pro");
  });

  it("is off by default and sends no include_non_common on the first scan", async () => {
    mockedScanner.mockResolvedValue(scannerResponse([STOCK_ROW]));
    render(<ScannerPage />);

    await waitFor(() => expect(mockedScanner).toHaveBeenCalled());
    expect(toggle()).not.toBeChecked();
    expect(scanParams(0)).not.toHaveProperty("include_non_common");
  });

  it("refetches with include_non_common when switched on", async () => {
    mockedScanner.mockResolvedValue(scannerResponse([STOCK_ROW]));
    render(<ScannerPage />);
    await waitFor(() => expect(mockedScanner).toHaveBeenCalledTimes(1));

    fireEvent.click(toggle());

    await waitFor(() => expect(mockedScanner).toHaveBeenCalledTimes(2));
    expect(toggle()).toBeChecked();
    expect(scanParams(1)).toMatchObject({ include_non_common: "true" });
    // The two exclusions are independent: this one does not switch the
    // leveraged one on.
    expect(scanParams(1)).not.toHaveProperty("include_leveraged");
  });

  it("sends the same param to the CSV export as to the on-screen scan", async () => {
    mockedScanner.mockResolvedValue(scannerResponse([STOCK_ROW]));
    mockedExport.mockResolvedValue(undefined);
    render(<ScannerPage />);
    await waitFor(() => expect(mockedScanner).toHaveBeenCalledTimes(1));

    fireEvent.click(toggle());
    await waitFor(() => expect(mockedScanner).toHaveBeenCalledTimes(2));

    fireEvent.click(await screen.findByRole("button", { name: "Export CSV" }));
    await waitFor(() => expect(mockedExport).toHaveBeenCalledTimes(1));
    expect(mockedExport).toHaveBeenCalledWith(
      expect.objectContaining({ include_non_common: "true" }),
    );
  });

  it("labels a flagged row, and leaves an ordinary row unlabelled", async () => {
    mockedScanner.mockResolvedValue(scannerResponse([NOTE_ROW, STOCK_ROW]));
    render(<ScannerPage />);

    const badges = await screen.findAllByText(/not common stock/i);
    expect(badges).toHaveLength(1);
    expect(badges[0].closest("td")).toHaveTextContent("GREEL");
  });

  it("states a fact and never a judgement", async () => {
    mockedScanner.mockResolvedValue(scannerResponse([NOTE_ROW]));
    render(<ScannerPage />);
    const badge = (await screen.findAllByText(/not common stock/i))[0];

    // Scoped to this control's card and the row badge; see the leveraged
    // test for why a page-wide grep would test the wrong thing.
    const controlCard = toggle().closest("div");
    const scoped = [controlCard, badge].filter(Boolean) as HTMLElement[];
    const text = scoped
      .map((el) => {
        const titles = [
          el.getAttribute("title") ?? "",
          ...Array.from(el.querySelectorAll("[title]")).map(
            (n) => n.getAttribute("title") ?? "",
          ),
        ];
        return `${el.textContent ?? ""} ${titles.join(" ")}`;
      })
      .join(" ")
      .toLowerCase();

    // Sanity: only meaningful while the copy under test is in hand.
    expect(text).toContain("common shares");

    for (const banned of [
      "risky",
      "risk",
      "dangerous",
      "avoid",
      "warning",
      "caution",
      "not suitable",
      "beware",
      "careful",
      "junk",
      "worthless",
    ]) {
      expect(text).not.toContain(banned);
    }
  });
});
