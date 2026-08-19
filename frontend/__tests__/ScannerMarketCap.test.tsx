/**
 * Scanner page — "Mkt Cap" column (GAP #10).
 *
 * Contract pinned here:
 *   1. Each row renders a market-cap cell showing compact dollars for a real
 *      value (e.g. $2.50B).
 *   2. A null market_cap renders as an em-dash, never "$null"/"$NaN"/blank.
 *
 * jsdom does not apply Tailwind, so the `hidden sm:table-cell` cell is still in
 * the DOM and its text is assertable via row textContent.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({ useUser: vi.fn() }));
vi.mock("@/lib/gtag", () => ({
  trackEvent: vi.fn(),
  trackEventOnce: vi.fn(),
  trackFirstTickerAdded: vi.fn(),
  trackCapHit: vi.fn(),
  trackUpgradePromptShown: vi.fn(),
  trackUpgradePromptClicked: vi.fn(),
}));
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
vi.mock("@/components/Paywall", () => ({
  PaywallModal: ({ open, feature }: { open: boolean; feature: string }) =>
    open ? <div data-testid={`paywall-${feature}`} /> : null,
}));
vi.mock("@/lib/api", () => ({
  api: {
    scanner: vi.fn(),
    watchlistAdd: vi.fn(),
    exportScannerCsv: vi.fn(),
  },
  TierGateError: class TierGateError extends Error {},
  errorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));

import ScannerPage from "@/app/app/scanner/page";
import { useUser } from "@/components/UserContext";
import { api } from "@/lib/api";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;
const mockedScanner = api.scanner as ReturnType<typeof vi.fn>;

function baseRow(overrides: Record<string, unknown>) {
  return {
    symbol: "SYM",
    name: "A Company",
    sector: "Tech",
    asset_class: "stock",
    score: 90,
    signal: "HIGH CONVICTION",
    price: 50,
    change_pct_1d: 1.0,
    change_pct_5d: 2.0,
    change_pct_1m: 3.0,
    volume: 1_000_000,
    market_cap: null,
    sub_trend: 70,
    sub_rs: 60,
    sub_fundamentals: 55,
    sub_momentum: 65,
    sub_macro: 50,
    sub_smart_money: 60,
    confidence_pct: 80,
    reason: "Trend leads the composite.",
    updated_at: null,
    ...overrides,
  };
}

describe("Scanner Mkt Cap column", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedScanner.mockReset();
    window.localStorage.clear();
    mockedUseUser.mockReturnValue({
      user: { id: "u1", email: "u@example.com", name: null, tier: "premium", created_at: null },
      loading: false, refresh: vi.fn(), signout: vi.fn(),
    });
  });

  it("renders compact dollars for a real market cap and an em-dash for null", async () => {
    mockedScanner.mockResolvedValue({
      count: 2,
      tier: "premium",
      row_cap: 1000,
      total_matched: null,
      data_delayed_minutes: 0,
      items: [
        baseRow({ symbol: "CAPSET", name: "Cap Set Co", market_cap: 2_500_000_000 }),
        baseRow({ symbol: "CAPNUL", name: "Cap Null Co", market_cap: null }),
      ],
    });

    render(<ScannerPage />);

    // Header cell present.
    expect(await screen.findByText("Mkt Cap")).toBeInTheDocument();

    const setRow = (await screen.findByRole("link", { name: "CAPSET" })).closest("tr")!;
    expect(setRow.textContent).toContain("$2.50B");

    const nullRow = (await screen.findByRole("link", { name: "CAPNUL" })).closest("tr")!;
    expect(nullRow.textContent).toContain("—");
    // Never a broken render for the null cap.
    expect(nullRow.textContent).not.toContain("$null");
    expect(nullRow.textContent).not.toContain("NaN");
  });
});
