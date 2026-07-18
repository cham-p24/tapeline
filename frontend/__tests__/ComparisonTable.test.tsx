/**
 * ComparisonTable sits under a literal "No asterisks." banner on /pricing, so
 * every Free-column cell must state the tier the backend actually enforces.
 * All Free-tier numbers derive from FREE_LIMITS in lib/pricing.ts (which
 * mirrors backend/app/services/tier.py + routers/squeeze.py) — a failure here
 * means the spec sheet has drifted from the deployed gating again.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ComparisonTable } from "@/components/ComparisonTable";
import { FREE_LIMITS } from "@/lib/pricing";

describe("ComparisonTable", () => {
  it("renders the post-#343 Free-tier limits from FREE_LIMITS", () => {
    render(<ComparisonTable />);
    // Look-ups: 12/day with the 24h first-session grace stated inline.
    expect(
      screen.getByText(
        `${FREE_LIMITS.dailyLookups} · unmetered first ${FREE_LIMITS.firstSessionGraceHours}h`,
      ),
    ).toBeInTheDocument();
    // Score breakdown row repeats the same daily cap.
    expect(
      screen.getByText(`${FREE_LIMITS.dailyLookups} look-ups/day`),
    ).toBeInTheDocument();
    // Scanner rows: top-10.
    expect(screen.getByText(`Top ${FREE_LIMITS.scannerRows}`)).toBeInTheDocument();
    // Watchlist: 5 saved tickers (raised from 3).
    expect(
      screen.getByText(`${FREE_LIMITS.watchlistTickers} tickers`),
    ).toBeInTheDocument();
    // Squeeze Watch: free top-3 preview, not "—".
    expect(
      screen.getByText(`Top-${FREE_LIMITS.squeezePreviewRows} preview`),
    ).toBeInTheDocument();
    // Browser push: 2 free alert rules, not "—".
    expect(
      screen.getByText(`${FREE_LIMITS.webPushAlerts} alert rules`),
    ).toBeInTheDocument();
  });

  it("does not sell the stale pre-#343 free tier", () => {
    render(<ComparisonTable />);
    expect(screen.queryByText("5 look-ups/day")).not.toBeInTheDocument();
    expect(screen.queryByText(/3-ticker watchlist/i)).not.toBeInTheDocument();
    expect(screen.queryByText("5 tickers · no alerts")).not.toBeInTheDocument();
  });
});
