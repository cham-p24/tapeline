/**
 * Scanner page — the "Leveraged & inverse funds" toggle.
 *
 * Contract pinned here:
 *   1. The control exists, is OFF on first render, and the first scan sends
 *      NO include_leveraged param — the server's own default does the
 *      excluding, so the default lives in one place rather than two.
 *   2. Ticking it on refetches WITH include_leveraged, so what is on screen
 *      is what the server ranked (never a client-side post-filter — that was
 *      the asset_class bug, where the row cap was spent on rows the user had
 *      already excluded).
 *   3. The CSV export sends the same param as the on-screen scan. The export
 *      diverging from the visible filters is the exact defect this mirrors.
 *   4. A row that comes back flagged is LABELLED. It only ever appears
 *      because the user asked for it, so the label states a structural fact.
 *   5. COMPLIANCE: nothing this toggle renders may read as a judgement about
 *      the instrument. Asserted directly, because the pressure to add "risky"
 *      or a red warning here is exactly the pressure the descriptive-label
 *      posture exists to resist (see CLAUDE.md).
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

// One geared and one ordinary row, both real names from the live universe on
// 2026-09-07 — CONX was rank 7 of the anonymous top 10 that day.
const GEARED_ROW = {
  symbol: "CONX",
  name: "Direxion Daily COIN Bull 2X ETF",
  sector: "Funds & ETFs",
  asset_class: "etf",
  is_leveraged: true,
  score: 81.7,
  signal: "STRONG SETUP",
  price: 30.1,
  change_pct_1d: 1.2,
  change_pct_5d: 3.4,
  change_pct_1m: 8.1,
  volume: 900000,
  updated_at: "2026-09-07T21:00:00Z",
};

const PLAIN_ROW = {
  ...GEARED_ROW,
  symbol: "SPY",
  name: "SPDR S&P 500 ETF Trust",
  is_leveraged: false,
  score: 70.2,
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
  return screen.getByRole("checkbox", { name: /leveraged & inverse funds/i });
}

/** Query params of the Nth (0-indexed) scanner call. */
function scanParams(n: number): Record<string, unknown> {
  return mockedScanner.mock.calls[n][0] as Record<string, unknown>;
}

describe("Scanner leveraged & inverse toggle", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedScanner.mockReset();
    mockedExport.mockReset();
    window.localStorage.clear();
    setUser("pro");
  });

  it("is off by default and sends no include_leveraged on the first scan", async () => {
    mockedScanner.mockResolvedValue(scannerResponse([PLAIN_ROW]));
    render(<ScannerPage />);

    await waitFor(() => expect(mockedScanner).toHaveBeenCalled());
    expect(toggle()).not.toBeChecked();
    // Absent, not false: the server excludes by default, and restating that
    // default here is how the two drift apart.
    expect(scanParams(0)).not.toHaveProperty("include_leveraged");
  });

  it("refetches with include_leveraged when switched on", async () => {
    mockedScanner.mockResolvedValue(scannerResponse([PLAIN_ROW]));
    render(<ScannerPage />);
    await waitFor(() => expect(mockedScanner).toHaveBeenCalledTimes(1));

    fireEvent.click(toggle());

    await waitFor(() => expect(mockedScanner).toHaveBeenCalledTimes(2));
    expect(toggle()).toBeChecked();
    expect(scanParams(1)).toMatchObject({ include_leveraged: "true" });
  });

  it("sends the same param to the CSV export as to the on-screen scan", async () => {
    mockedScanner.mockResolvedValue(scannerResponse([PLAIN_ROW]));
    mockedExport.mockResolvedValue(undefined);
    render(<ScannerPage />);
    await waitFor(() => expect(mockedScanner).toHaveBeenCalledTimes(1));

    fireEvent.click(toggle());
    await waitFor(() => expect(mockedScanner).toHaveBeenCalledTimes(2));

    fireEvent.click(await screen.findByRole("button", { name: "Export CSV" }));
    await waitFor(() => expect(mockedExport).toHaveBeenCalledTimes(1));
    expect(mockedExport).toHaveBeenCalledWith(
      expect.objectContaining({ include_leveraged: "true" }),
    );
  });

  it("labels a flagged row, and leaves an ordinary row unlabelled", async () => {
    mockedScanner.mockResolvedValue(scannerResponse([GEARED_ROW, PLAIN_ROW]));
    render(<ScannerPage />);

    // One badge, on the geared row only — not one per rendered row.
    const badges = await screen.findAllByText(/leveraged \/ inverse/i);
    expect(badges).toHaveLength(1);
    expect(badges[0].closest("td")).toHaveTextContent("CONX");
  });

  it("states a fact and never a judgement", async () => {
    mockedScanner.mockResolvedValue(scannerResponse([GEARED_ROW]));
    render(<ScannerPage />);
    const badge = (await screen.findAllByText(/leveraged \/ inverse/i))[0];

    // Scoped to the copy this change introduced — the control's card and the
    // row badge — rather than the whole page, whose legend and disclaimers
    // legitimately use words like "risk" and whose signal dropdown contains
    // the band literally named "Caution". A page-wide grep would pass or
    // fail for reasons that have nothing to do with this toggle.
    const controlCard = toggle().closest("div");
    const scoped = [controlCard, badge].filter(Boolean) as HTMLElement[];

    // title= attributes are collected deliberately: a warning smuggled into
    // a tooltip is still a warning.
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
      .join(" ");

    // Sanity: the assertion is only meaningful while it actually has the
    // copy under test in hand. Without this, an empty string passes every
    // check below and the guard silently stops guarding.
    expect(text.toLowerCase()).toContain("leveraged");

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
    ]) {
      expect(text.toLowerCase()).not.toContain(banned);
    }
  });
});
