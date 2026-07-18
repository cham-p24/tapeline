/**
 * Holdings page (Recent Insider Buys feed) — tier-branched data loading.
 *
 * Historical bug this pins down (2026-07-18): the page wrapped its body in
 * <Paywall>, which BLURS its children — but the Premium-gated GET /api/holdings
 * 403'd before anything rendered, so the blur sat over an EMPTY table. A
 * non-Premium user saw an upgrade card floating over nothing and therefore zero
 * evidence the feature had any content. Contract now:
 *
 *   1. Premium loads the full filterable feed (api.holdings) — no locked
 *      section, filters visible.
 *   2. Free/Pro load ONLY the preview (holdingsPreview), render the REAL rows
 *      unblurred, and show a locked section stating the REAL feed size with an
 *      upgrade link deep-linked to /app/billing?intent=premium.
 *   3. The Premium-gated endpoint is never touched by a non-Premium user.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import HoldingsPage from "@/app/app/holdings/page";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));

const fullRow = {
  symbol: "AAPL",
  insider_name: "LEVINSON ARTHUR D",
  transaction_date: "2026-05-06",
  share_change: -100473,
  transaction_price: 285.04,
  transaction_value: 28639286.92,
  code: "S",
};

const previewRows = [
  { symbol: "NVDA", insider_name: "HUANG JEN HSUN", transaction_date: "2026-07-15", share_change: 12000, transaction_price: 120.5, transaction_value: 1446000, code: "P" },
  { symbol: "MSFT", insider_name: "NADELLA SATYA", transaction_date: "2026-07-14", share_change: -5000, transaction_price: 410.2, transaction_value: 2051000, code: "S" },
  { symbol: "AMD", insider_name: "SU LISA T", transaction_date: "2026-07-13", share_change: 3000, transaction_price: 155.75, transaction_value: 467250, code: "P" },
];

vi.mock("@/lib/api", () => ({
  api: { holdings: vi.fn() },
  errorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));

vi.mock("@/lib/previews", () => ({
  holdingsPreview: vi.fn(),
  FREE_INSIDER_PREVIEW_LIMIT: 3,
}));

import { useUser } from "@/components/UserContext";
import { api } from "@/lib/api";
import { holdingsPreview } from "@/lib/previews";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;
const mockedHoldings = api.holdings as ReturnType<typeof vi.fn>;
const mockedPreview = holdingsPreview as ReturnType<typeof vi.fn>;

function setUser(tier: "free" | "pro" | "premium") {
  mockedUseUser.mockReturnValue({
    user: { id: "u1", email: "u@example.com", name: null, tier, created_at: null },
    loading: false, refresh: vi.fn(), signout: vi.fn(),
  });
}

describe("HoldingsPage", () => {
  beforeEach(() => {
    mockedUseUser.mockReset();
    mockedHoldings.mockReset();
    mockedPreview.mockReset();
  });

  it("shows the full insider buys table for a Premium user", async () => {
    setUser("premium");
    mockedHoldings.mockResolvedValue({ count: 1, feed_size: 1, items: [fullRow] });
    render(<HoldingsPage />);
    expect(screen.getByText("Recent insider buys")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    // Insider name is title-cased on render
    expect(screen.getByText(/Levinson Arthur D/i)).toBeInTheDocument();
    // SELL action chip with the SEC code
    expect(screen.getByText(/SELL · S/)).toBeInTheDocument();
    // Premium-only filters are present; no locked section.
    expect(screen.getByPlaceholderText("e.g. NVDA")).toBeInTheDocument();
    expect(screen.queryByText(/full feed on Premium/)).not.toBeInTheDocument();
    expect(mockedPreview).not.toHaveBeenCalled();
  });

  it("renders REAL preview rows and the real feed size for a Pro user", async () => {
    setUser("pro");
    mockedPreview.mockResolvedValue({
      count: 3, preview: true, limit: 3, days: 30, feed_size: 1842, items: previewRows,
    });
    render(<HoldingsPage />);
    await waitFor(() => {
      expect(screen.getByText("NVDA")).toBeInTheDocument();
    });
    // The page is NOT empty — all three real rows render in the normal table.
    expect(screen.getByText("MSFT")).toBeInTheDocument();
    expect(screen.getByText("AMD")).toBeInTheDocument();
    // Locked section states the real backend count…
    expect(
      screen.getByText("Showing 3 of 1,842 tracked filings — full feed on Premium"),
    ).toBeInTheDocument();
    // …and deep-links to billing with the premium intent pre-selected.
    expect(screen.getByRole("link", { name: /Upgrade to Premium/ }))
      .toHaveAttribute("href", "/app/billing?intent=premium");
    // The Premium-gated endpoint is never touched — no 403 spam.
    expect(mockedHoldings).not.toHaveBeenCalled();
  });

  it("omits the count rather than inventing one when the feed is cold", async () => {
    setUser("free");
    mockedPreview.mockResolvedValue({
      count: 0, preview: true, limit: 3, days: 30, feed_size: 0, items: [],
    });
    render(<HoldingsPage />);
    await waitFor(() => {
      expect(screen.getByText("Free shows the 3 most recent filings")).toBeInTheDocument();
    });
    expect(screen.queryByText(/of 0 tracked filings/)).not.toBeInTheDocument();
  });

  it("shows an error state with retry — not a false empty feed — on failure", async () => {
    setUser("free");
    mockedPreview.mockRejectedValue(new Error("backend unreachable"));
    render(<HoldingsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Couldn't load insider filings/)).toBeInTheDocument();
    });
    expect(screen.getByText("backend unreachable")).toBeInTheDocument();
    expect(screen.queryByText(/Backfilling insider feed/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Try again/ })).toBeInTheDocument();
  });
});
