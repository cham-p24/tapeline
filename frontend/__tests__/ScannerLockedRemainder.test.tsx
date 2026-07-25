/**
 * Scanner page — "show don't hide" locked-remainder band.
 *
 * Contract pinned here:
 *   1. Free user, capped page: when the server reports total_matched greater
 *      than the rows it returned, a locked-remainder band renders stating the
 *      REAL held-back count (total_matched − rows shown) and links to
 *      /app/billing?intent=pro. No fabricated symbols/scores appear in it.
 *   2. Pro user: total_matched is null (they page the whole universe), so the
 *      band NEVER renders.
 *   3. Free user whose whole match set fits under the cap (total_matched ==
 *      rows shown): no band — there's nothing hidden to advertise.
 *   4. Instrumentation: the band firing counts as upgrade_prompt_shown, and its
 *      CTA click fires upgrade_prompt_clicked — the middle of the free→paid
 *      funnel.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({ useUser: vi.fn() }));
vi.mock("@vercel/analytics", () => ({ track: vi.fn() }));
vi.mock("@/lib/gtag", () => ({
  trackEvent: vi.fn(),
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
import { api } from "@/lib/api";
import { trackUpgradePromptShown, trackUpgradePromptClicked } from "@/lib/gtag";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;
const mockedScanner = api.scanner as ReturnType<typeof vi.fn>;
const mockedShown = trackUpgradePromptShown as ReturnType<typeof vi.fn>;
const mockedClicked = trackUpgradePromptClicked as ReturnType<typeof vi.fn>;

function setUser(tier: "free" | "pro" | "premium") {
  mockedUseUser.mockReturnValue({
    user: { id: "u1", email: "u@example.com", name: null, tier, created_at: null },
    loading: false, refresh: vi.fn(), signout: vi.fn(),
  });
}

// A complete-enough scanner row so the table cells (score/price/pct/volume) can
// all render without a toFixed on undefined.
function row(i: number) {
  return {
    symbol: `TST${i}`,
    name: `Test Co ${i}`,
    sector: "Information Technology",
    asset_class: "stock",
    score: 90 - i,
    signal: "HIGH CONVICTION",
    price: 100 + i,
    change_pct_1d: 1.2,
    change_pct_5d: 2.3,
    change_pct_1m: 3.4,
    volume: 1_000_000,
    confidence_pct: 80,
    reason: "Trend and momentum lead the composite.",
    updated_at: null,
  };
}

function scannerResponse(opts: {
  tier: string;
  rowCap: number;
  totalMatched: number | null;
  rows: number;
}) {
  return {
    count: opts.rows,
    tier: opts.tier,
    row_cap: opts.rowCap,
    total_matched: opts.totalMatched,
    data_delayed_minutes: 0,
    items: Array.from({ length: opts.rows }, (_, i) => row(i)),
  };
}

describe("Scanner locked-remainder band", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedScanner.mockReset();
    mockedShown.mockReset();
    mockedClicked.mockReset();
    window.localStorage.clear();
  });

  it("renders the real held-back count for a capped Free user and links to Pro", async () => {
    setUser("free");
    // 137 rows match; the cap lets 10 through → 127 held back.
    mockedScanner.mockResolvedValue(
      scannerResponse({ tier: "free", rowCap: 10, totalMatched: 137, rows: 10 }),
    );
    render(<ScannerPage />);

    const band = await screen.findByTestId("scanner-locked-remainder");
    // The REAL count (137 − 10), not a fabricated one.
    expect(within(band).getByText(/127/)).toBeInTheDocument();
    expect(within(band).getByText(/more tickers match your/i)).toBeInTheDocument();
    const cta = within(band).getByRole("link", { name: /Upgrade to Pro/i });
    expect(cta).toHaveAttribute("href", "/app/billing?intent=pro");

    // Visible upgrade prompt is measured for the funnel.
    await waitFor(() =>
      expect(mockedShown).toHaveBeenCalledWith("scanner", "scanner_rows"),
    );

    // Clicking the CTA fires the click half of the funnel.
    fireEvent.click(cta);
    expect(mockedClicked).toHaveBeenCalledWith("scanner", "scanner_rows");
  });

  it("does NOT render the band for a Pro user (total_matched null)", async () => {
    setUser("pro");
    mockedScanner.mockResolvedValue(
      scannerResponse({ tier: "pro", rowCap: 1000, totalMatched: null, rows: 10 }),
    );
    render(<ScannerPage />);

    // Wait for the fetch to resolve and rows to paint.
    await waitFor(() => expect(mockedScanner).toHaveBeenCalled());
    await screen.findByText("TST0");
    expect(screen.queryByTestId("scanner-locked-remainder")).not.toBeInTheDocument();
    expect(mockedShown).not.toHaveBeenCalled();
  });

  it("does NOT render the band when the whole match set fits under the cap", async () => {
    setUser("free");
    // Only 6 rows match — fewer than the cap of 10 — so nothing is hidden.
    mockedScanner.mockResolvedValue(
      scannerResponse({ tier: "free", rowCap: 10, totalMatched: 6, rows: 6 }),
    );
    render(<ScannerPage />);

    await screen.findByText("TST0");
    expect(screen.queryByTestId("scanner-locked-remainder")).not.toBeInTheDocument();
  });
});
