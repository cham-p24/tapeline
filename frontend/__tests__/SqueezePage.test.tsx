/**
 * Squeeze Watch page — tier-branched data loading.
 *
 * Historical bug this pins down: the page unconditionally called the
 * Pro-gated GET /api/squeeze with no catch, so every Free user saw a false
 * "No squeeze setups right now" empty state (the 403 left rows = []) and the
 * SSE re-fire spammed the failing endpoint forever. Contract now:
 *
 *   1. Pro+ loads the full feed (api.squeeze) — no locked section.
 *   2. Free loads ONLY the top-3 preview (api.squeezePreview), renders the
 *      real rows, and shows a locked section stating the REAL total count
 *      with an upgrade link to /app/billing?intent=pro.
 *   3. A failed load renders an error state with a retry — never the
 *      "No squeeze setups" empty state.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import SqueezePage from "@/app/app/squeeze/page";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));

// The page subscribes to the backend SSE stream — jsdom has no EventSource,
// and the re-poll behaviour is covered by asserting which api.* fn is called.
vi.mock("@/lib/useLiveStream", () => ({
  useLiveStream: () => ({ status: "live", lastUpdate: null }),
}));

const fullRow = {
  symbol: "NVDA",
  spike_score: 91.2,
  squeeze_days: 7,
  volume_multiple: 1.42,
  obv_trend: "RISING",
  breakout_type: "bullish",
  suggested_window: "1-2 weeks",
  reason: "Bollinger squeeze with rising OBV.",
  updated_at: null,
};

const previewItems = [
  { symbol: "AAPL", spike_score: 88.4, squeeze_days: 5, breakout_type: "bullish", reason: "Tight bands.", updated_at: null },
  { symbol: "TSLA", spike_score: 84.1, squeeze_days: 4, breakout_type: "neutral", reason: "Compressed range.", updated_at: null },
  { symbol: "AMD", spike_score: 79.9, squeeze_days: 6, breakout_type: "bearish", reason: "Low volatility.", updated_at: null },
];

vi.mock("@/lib/api", () => ({
  api: {
    squeeze: vi.fn(),
    squeezePreview: vi.fn(),
  },
  errorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));

import { useUser } from "@/components/UserContext";
import { api } from "@/lib/api";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;
const mockedSqueeze = api.squeeze as ReturnType<typeof vi.fn>;
const mockedPreview = api.squeezePreview as ReturnType<typeof vi.fn>;

function setUser(tier: "free" | "pro" | "premium") {
  mockedUseUser.mockReturnValue({
    user: { id: "u1", email: "u@example.com", name: null, tier, created_at: null },
    loading: false, refresh: vi.fn(), signout: vi.fn(),
  });
}

describe("SqueezePage", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedSqueeze.mockReset();
    mockedPreview.mockReset();
  });

  it("loads the full feed for a Pro user with no locked section", async () => {
    setUser("pro");
    mockedSqueeze.mockResolvedValue({ count: 1, items: [fullRow] });
    render(<SqueezePage />);
    await waitFor(() => {
      expect(screen.getByText("NVDA")).toBeInTheDocument();
    });
    // Pro-only analytics column is populated (preview rows render "—" here).
    expect(screen.getByText("1.42x")).toBeInTheDocument();
    expect(mockedPreview).not.toHaveBeenCalled();
    expect(screen.queryByText(/shown on Free/)).not.toBeInTheDocument();
  });

  it("loads ONLY the preview for a Free user and shows the real locked count", async () => {
    setUser("free");
    mockedPreview.mockResolvedValue({
      count: 3, preview: true, limit: 3, total_setups: 12, items: previewItems,
    });
    render(<SqueezePage />);
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    // The 3 preview rows are REAL data, rendered in the normal table.
    expect(screen.getByText("TSLA")).toBeInTheDocument();
    expect(screen.getByText("AMD")).toBeInTheDocument();
    // Locked section states the real total from the backend…
    expect(
      screen.getByText("Top 3 of 12 current squeeze setups shown on Free"),
    ).toBeInTheDocument();
    // …and links to billing with the pro intent pre-selected.
    const cta = screen.getByRole("link", { name: /Upgrade to Pro/ });
    expect(cta).toHaveAttribute("href", "/app/billing?intent=pro");
    // The Pro-gated endpoint is never touched — no 403 spam on SSE re-fires.
    expect(mockedSqueeze).not.toHaveBeenCalled();
  });

  it("shows an error state — not the false empty state — when the load fails", async () => {
    setUser("free");
    mockedPreview.mockRejectedValue(new Error("backend unreachable"));
    render(<SqueezePage />);
    await waitFor(() => {
      expect(screen.getByText(/Couldn't load squeeze setups/)).toBeInTheDocument();
    });
    expect(screen.getByText("backend unreachable")).toBeInTheDocument();
    expect(screen.queryByText(/No squeeze setups right now/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Try again/ })).toBeInTheDocument();
  });
});
