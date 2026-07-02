/**
 * TodaysTape — the first-session "aha" strip above the scanner table.
 * Contract:
 *   - renders regime + top-3 HIGH CONVICTION picks (with their one-sentence
 *     why) + the latest back-checked scorecard day for accounts < 7 days old
 *   - reports LOSING scorecard days just as plainly as winning ones
 *   - renders nothing (and fetches nothing) for older accounts or signed-out
 *   - never uses prescriptive language
 *   - helper exports: isNewUser window math, latestScoredDay honesty rules,
 *     and the sector slug→canonical map the scanner pre-tune relies on
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const regimeMock = vi.hoisted(() => vi.fn());
const scannerMock = vi.hoisted(() => vi.fn());
const scorecardMock = vi.hoisted(() => vi.fn());
const useUserMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", () => ({
  api: {
    regime: (...a: unknown[]) => regimeMock(...a),
    scanner: (...a: unknown[]) => scannerMock(...a),
    scorecard: (...a: unknown[]) => scorecardMock(...a),
  },
}));
vi.mock("@/components/UserContext", () => ({
  useUser: () => useUserMock(),
}));

import {
  TodaysTape,
  isNewUser,
  latestScoredDay,
  SECTOR_SLUG_TO_CANONICAL,
  NEW_USER_WINDOW_DAYS,
} from "@/components/TodaysTape";
import type { ScorecardEntry } from "@/lib/api";

const DAY_MS = 86_400_000;

function freshUser(daysOld = 1) {
  return {
    user: {
      id: "u1",
      email: "new@example.com",
      name: "New",
      tier: "premium",
      created_at: new Date(Date.now() - daysOld * DAY_MS).toISOString(),
    },
    loading: false,
    refresh: async () => {},
    signout: async () => {},
  };
}

function entry(alpha: number | null): ScorecardEntry {
  return {
    rank: 1,
    symbol: "AAPL",
    score_at_flag: 90,
    price_at_flag: 100,
    price_next_day: alpha === null ? null : 101,
    change_pct_1d_after: alpha === null ? null : 1.0,
    spy_change_pct_1d: alpha === null ? null : 0.5,
    alpha_vs_spy: alpha,
  };
}

const PICKS = [
  {
    symbol: "NVDA",
    name: "NVIDIA",
    sector: "Information Technology",
    asset_class: "stock",
    score: 91.2,
    signal: "HIGH CONVICTION",
    price: 500,
    change_pct_1d: 2.1,
    change_pct_5d: 4.0,
    change_pct_1m: 9.0,
    volume: 1000,
    reason: "Uptrend intact with strong relative strength. Second sentence to be trimmed.",
    updated_at: null,
  },
  {
    symbol: "MSFT",
    name: "Microsoft",
    sector: "Information Technology",
    asset_class: "stock",
    score: 88.4,
    signal: "HIGH CONVICTION",
    price: 400,
    change_pct_1d: 1.0,
    change_pct_5d: 2.0,
    change_pct_1m: 5.0,
    volume: 900,
    reason: "Momentum confirmed by volume expansion.",
    updated_at: null,
  },
  {
    symbol: "AVGO",
    name: "Broadcom",
    sector: "Information Technology",
    asset_class: "stock",
    score: 86.9,
    signal: "HIGH CONVICTION",
    price: 1300,
    change_pct_1d: 0.4,
    change_pct_5d: 1.1,
    change_pct_1m: 3.2,
    volume: 800,
    reason: "Breadth-supported trend with fundamentals holding up.",
    updated_at: null,
  },
];

beforeEach(() => {
  regimeMock.mockReset();
  scannerMock.mockReset();
  scorecardMock.mockReset();
  useUserMock.mockReset();
});

describe("TodaysTape", () => {
  it("renders regime, top-3 picks with their why, and the latest scorecard day for a first-week user", async () => {
    useUserMock.mockReturnValue(freshUser(1));
    regimeMock.mockResolvedValue({ regime: "BULL" });
    scannerMock.mockResolvedValue({ count: 3, tier: "premium", row_cap: 1000, data_delayed_minutes: 0, items: PICKS });
    scorecardMock.mockResolvedValue({
      summary: {},
      days: {
        // Newest day not yet back-checked → must fall back to the prior day.
        "2026-07-02": [entry(null)],
        "2026-07-01": [entry(0.8), entry(-0.4), entry(1.2)],
      },
    });

    render(<TodaysTape />);

    await waitFor(() => expect(screen.getByText("Bull")).toBeInTheDocument());
    expect(screen.getByText(/Today.s tape/i)).toBeInTheDocument();
    expect(screen.getByText("NVDA")).toBeInTheDocument();
    expect(screen.getByText("MSFT")).toBeInTheDocument();
    expect(screen.getByText("AVGO")).toBeInTheDocument();
    // One-sentence why, trimmed at the first period.
    expect(
      screen.getByText("Uptrend intact with strong relative strength."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Second sentence/)).not.toBeInTheDocument();
    // Scorecard: 2 of 3 beat SPY on the latest BACK-CHECKED day.
    expect(screen.getByText(/2026-07-01/)).toBeInTheDocument();
    expect(screen.getByText(/2 of 3/)).toBeInTheDocument();
    // Picks link to their ticker pages; the strip requested HIGH CONVICTION only.
    expect(screen.getByText("NVDA").closest("a")).toHaveAttribute("href", "/app/ticker/NVDA");
    expect(scannerMock).toHaveBeenCalledWith(
      expect.objectContaining({ signal: "HIGH CONVICTION", limit: 3 }),
    );
  });

  it("reports a losing scorecard day honestly", async () => {
    useUserMock.mockReturnValue(freshUser(2));
    regimeMock.mockResolvedValue({ regime: "BEAR" });
    scannerMock.mockResolvedValue({ count: 0, tier: "premium", row_cap: 1000, data_delayed_minutes: 0, items: [] });
    scorecardMock.mockResolvedValue({
      summary: {},
      days: { "2026-07-01": [entry(-0.5), entry(-1.2), entry(-0.1)] },
    });

    render(<TodaysTape />);

    await waitFor(() => expect(screen.getByText(/0 of 3/)).toBeInTheDocument());
    expect(screen.getByText(/wins and losses both counted/i)).toBeInTheDocument();
    // Empty HIGH CONVICTION tape is stated, not papered over.
    expect(screen.getByText(/No HIGH CONVICTION signals/i)).toBeInTheDocument();
  });

  it("stays descriptive — no prescriptive language anywhere", async () => {
    useUserMock.mockReturnValue(freshUser(1));
    regimeMock.mockResolvedValue({ regime: "BULL" });
    scannerMock.mockResolvedValue({ count: 3, tier: "premium", row_cap: 1000, data_delayed_minutes: 0, items: PICKS });
    scorecardMock.mockResolvedValue({ summary: {}, days: { "2026-07-01": [entry(1.0)] } });

    const { container } = render(<TodaysTape />);
    await waitFor(() => expect(screen.getByText("NVDA")).toBeInTheDocument());
    expect(container.textContent ?? "").not.toMatch(
      /\b(buy|sell|should|recommend|guarantee)\b/i,
    );
    expect(screen.getByText(/not investment advice/i)).toBeInTheDocument();
  });

  it("renders nothing and fetches nothing for an account older than the window", () => {
    useUserMock.mockReturnValue(freshUser(NEW_USER_WINDOW_DAYS + 5));
    const { container } = render(<TodaysTape />);
    expect(container).toBeEmptyDOMElement();
    expect(regimeMock).not.toHaveBeenCalled();
    expect(scannerMock).not.toHaveBeenCalled();
    expect(scorecardMock).not.toHaveBeenCalled();
  });

  it("renders nothing when signed out", () => {
    useUserMock.mockReturnValue({ user: null, loading: false, refresh: async () => {}, signout: async () => {} });
    const { container } = render(<TodaysTape />);
    expect(container).toBeEmptyDOMElement();
    expect(scannerMock).not.toHaveBeenCalled();
  });

  it("renders nothing when every fetch fails", async () => {
    useUserMock.mockReturnValue(freshUser(1));
    regimeMock.mockRejectedValue(new Error("down"));
    scannerMock.mockRejectedValue(new Error("down"));
    scorecardMock.mockRejectedValue(new Error("down"));

    const { container } = render(<TodaysTape />);
    // Let the rejected promises settle.
    await Promise.resolve();
    await Promise.resolve();
    expect(container).toBeEmptyDOMElement();
  });
});

describe("isNewUser", () => {
  const now = Date.parse("2026-07-03T00:00:00Z");

  it("true inside the 7-day window, false outside", () => {
    expect(isNewUser("2026-07-01T00:00:00Z", now)).toBe(true);
    expect(isNewUser("2026-06-27T00:00:01Z", now)).toBe(true);
    expect(isNewUser("2026-06-25T00:00:00Z", now)).toBe(false);
  });

  it("false for missing or malformed timestamps", () => {
    expect(isNewUser(null, now)).toBe(false);
    expect(isNewUser(undefined, now)).toBe(false);
    expect(isNewUser("not-a-date", now)).toBe(false);
  });
});

describe("latestScoredDay", () => {
  it("skips newer days that have no back-checked entries", () => {
    const days = {
      "2026-07-02": [entry(null), entry(null)],
      "2026-07-01": [entry(0.5), entry(-0.3)],
      "2026-06-30": [entry(2.0)],
    };
    expect(latestScoredDay(days)).toEqual({ date: "2026-07-01", beat: 1, total: 2 });
  });

  it("returns null when nothing is back-checked yet", () => {
    expect(latestScoredDay({ "2026-07-02": [entry(null)] })).toBeNull();
    expect(latestScoredDay({})).toBeNull();
  });

  it("counts only strictly-positive alpha as a beat (alpha=0 is not a win)", () => {
    const days = { "2026-07-01": [entry(0), entry(0.1)] };
    expect(latestScoredDay(days)).toEqual({ date: "2026-07-01", beat: 1, total: 2 });
  });
});

describe("SECTOR_SLUG_TO_CANONICAL", () => {
  it("maps every onboarding slug to a canonical scanner sector label", () => {
    // Slugs mirror backend _ALLOWED_SECTORS (routers/me.py); labels mirror
    // services/sector.py CANONICAL_ORDER (same strings the scanner's sector
    // dropdown offers).
    expect(SECTOR_SLUG_TO_CANONICAL["technology"]).toBe("Information Technology");
    expect(SECTOR_SLUG_TO_CANONICAL["healthcare"]).toBe("Health Care");
    expect(SECTOR_SLUG_TO_CANONICAL["etfs"]).toBe("Funds & ETFs");
    expect(Object.keys(SECTOR_SLUG_TO_CANONICAL)).toHaveLength(13);
    for (const label of Object.values(SECTOR_SLUG_TO_CANONICAL)) {
      expect(label).toBeTruthy();
    }
  });
});
