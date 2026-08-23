/**
 * Scanner rows — score and price cells when we hold no value.
 *
 * Two bugs pinned here, both from optional chaining that swallowed the null
 * instead of naming it:
 *
 *   `{r.score?.toFixed(1)}`  → an EMPTY score cell. A blank cell reads as a
 *                              rendering fault, not as "we don't know".
 *   `${r.price?.toFixed(2)}` → a bare "$" with no number after it, which is
 *                              worse: the dollar sign asserts a price exists.
 *
 * Both must print the same em-dash the rest of the row already uses for
 * change/volume/market cap. ~72% of the universe has no daily price read, so
 * this is the common row, not the edge case.
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
    market_cap: 1_000_000_000,
    sub_trend: 70,
    sub_rs: 60,
    sub_fundamentals: 55,
    sub_momentum: 65,
    sub_macro: 50,
    sub_smart_money: 60,
    confidence_pct: 80,
    reason: null,
    updated_at: null,
    ...overrides,
  };
}

/**
 * Column order: watchlist star, ticker, sector, score, confidence, signal,
 * price, 1d, 5d, 1m, volume, market cap. The sector cell is asserted as a
 * positional anchor so a column insertion fails here loudly rather than
 * silently pointing these assertions at the wrong cell.
 */
function cells(row: HTMLElement) {
  const tds = [...row.querySelectorAll("td")];
  expect(tds[2].textContent, "column order changed — reindex this helper").toBe("Tech");
  return { score: tds[3], price: tds[6] };
}

describe("Scanner null score / price cells", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedScanner.mockReset();
    window.localStorage.clear();
    mockedUseUser.mockReturnValue({
      user: { id: "u1", email: "u@example.com", name: null, tier: "premium", created_at: null },
      loading: false, refresh: vi.fn(), signout: vi.fn(),
    });
  });

  it("prints an em-dash — never a bare '$', never a blank — when price and score are null", async () => {
    mockedScanner.mockResolvedValue({
      count: 2,
      tier: "premium",
      row_cap: 1000,
      total_matched: null,
      data_delayed_minutes: 0,
      items: [
        baseRow({ symbol: "HELD", name: "Held Co", score: 72.4, price: 12.5 }),
        baseRow({ symbol: "NOREAD", name: "No Read Co", score: null, price: null }),
      ],
    });

    render(<ScannerPage />);

    const held = (await screen.findByRole("link", { name: "HELD" })).closest("tr")!;
    expect(cells(held).score.textContent).toBe("72.4");
    expect(cells(held).price.textContent).toBe("$12.50");

    const none = (await screen.findByRole("link", { name: "NOREAD" })).closest("tr")!;
    expect(cells(none).score.textContent).toBe("—");
    expect(cells(none).price.textContent).toBe("—");

    // The specific broken renders this replaced.
    expect(none.textContent).not.toContain("$undefined");
    expect(none.textContent).not.toContain("NaN");
    // A lone dollar sign with no number is the worst of the three: it asserts
    // a price we do not hold.
    expect(cells(none).price.textContent).not.toBe("$");
    expect(cells(none).price.textContent!.trim()).not.toBe("");
  });

  it("still renders a real measured 0 price as $0.00, not as an em-dash", async () => {
    mockedScanner.mockResolvedValue({
      count: 1,
      tier: "premium",
      row_cap: 1000,
      total_matched: null,
      data_delayed_minutes: 0,
      items: [baseRow({ symbol: "ZEROP", name: "Zero Price Co", score: 0, price: 0 })],
    });

    render(<ScannerPage />);
    const row = (await screen.findByRole("link", { name: "ZEROP" })).closest("tr")!;
    // Zero is a measurement; only the unknown becomes an em-dash.
    expect(cells(row).price.textContent).toBe("$0.00");
    expect(cells(row).score.textContent).toBe("0.0");
  });
});
