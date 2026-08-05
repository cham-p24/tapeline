/**
 * TrialEndedModal — the one-time "your trial ended" prompt. Copy contracts:
 *   1. The downgrade preview must list the REAL Free tier from FREE_LIMITS
 *      (12 look-ups/day, 5-ticker watchlist, top-10 scanner, top-3 squeeze
 *      preview, 2 push alerts, public scorecard) — never the stale pre-#343
 *      tier, and never overstate the drop.
 *   2. The refund line derives from REFUND (30-day guarantee).
 *   3. Rules 6/7: no loss-aversion framing about market opportunities, and no
 *      claim that anything was charged (the trial takes no card).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));
vi.mock("@vercel/analytics", () => ({
  track: vi.fn(),
}));

import { TrialEndedModal } from "@/components/TrialEndedModal";
import { useUser } from "@/components/UserContext";
import { FREE_LIMITS, REFUND, freeHasWatchlist } from "@/lib/pricing";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

// A free user whose 14-day trial expired 3 days ago.
const EXPIRED_TRIAL_USER = {
  user: {
    id: "u_1",
    email: "f@example.com",
    name: null,
    tier: "free",
    trial_ends_at: new Date(Date.now() - 3 * 86_400_000).toISOString(),
    created_at: null,
  },
  loading: false,
  refresh: vi.fn(),
  signout: vi.fn(),
};

beforeEach(() => {
  localStorage.clear();
  mockedUseUser.mockReturnValue(EXPIRED_TRIAL_USER);
});

describe("TrialEndedModal", () => {
  it("lists the real post-#343 Free tier from FREE_LIMITS", () => {
    const { container } = render(<TrialEndedModal />);
    const text = container.textContent ?? "";
    expect(screen.getByText(/what your free account keeps/i)).toBeInTheDocument();
    expect(text).toContain(`${FREE_LIMITS.dailyLookups} ticker look-ups a day`);
    // Watchlist is Pro-only after the 2026-08-02 cutover → listed as a Free
    // "keep" only while Free still includes one.
    if (freeHasWatchlist()) {
      expect(text).toContain(`${FREE_LIMITS.watchlistTickers}-ticker watchlist`);
    } else {
      expect(text).not.toContain("-ticker watchlist");
    }
    expect(text).toContain(`top ${FREE_LIMITS.scannerRows} scanner rows`);
    expect(text).toContain(`top-${FREE_LIMITS.squeezePreviewRows} preview`);
    expect(text).toContain(`${FREE_LIMITS.webPushAlerts} browser push alerts`);
    expect(text).toMatch(/full public scorecard/i);
    // Never the stale pre-#343 numbers.
    expect(text).not.toContain("5 look-ups");
    expect(text).not.toContain("3-ticker watchlist");
  });

  it("states that nothing was charged — the trial takes no card", () => {
    const { container } = render(<TrialEndedModal />);
    const text = container.textContent ?? "";
    expect(text).toMatch(/nothing was charged/i);
    expect(text).toMatch(/never took a card/i);
  });

  it("uses no loss-aversion framing about market opportunities", () => {
    const { container } = render(<TrialEndedModal />);
    const text = container.textContent ?? "";
    for (const phrase of [
      /what you missed/i,
      /you'?d have (?:caught|seen|found)/i,
      /setups? you/i,
      /miss(?:ed|ing)? out/i,
      /last chance/i,
      /hurry/i,
      /moved \d+%/i,
      /(?:gained|lost|rallied|surged|jumped)/i,
    ]) {
      expect(text).not.toMatch(phrase);
    }
  });

  it("states the refund guarantee from REFUND", () => {
    render(<TrialEndedModal />);
    expect(screen.getByText(new RegExp(REFUND.short, "i"))).toBeInTheDocument();
  });

  it("states the one-time save offer only when the server says it's available", () => {
    // Flag present → the offer line renders, stated as a standing fact
    // (no countdown — rule 6; it genuinely has no deadline).
    mockedUseUser.mockReturnValue({
      ...EXPIRED_TRIAL_USER,
      user: { ...EXPIRED_TRIAL_USER.user, trial_save_offer_available: true },
    });
    const { container } = render(<TrialEndedModal />);
    const text = container.textContent ?? "";
    expect(text).toContain("50% off your first 3 months");
    expect(text).toContain("applied automatically at checkout");
    expect(text).not.toMatch(/expires (?:in|soon)|last chance|hurry/i);
  });

  it("omits the save offer when the server flag is absent", () => {
    const { container } = render(<TrialEndedModal />);
    expect(container.textContent ?? "").not.toContain(
      "50% off your first 3 months",
    );
  });

  it("renders nothing while the trial is still active", () => {
    mockedUseUser.mockReturnValue({
      ...EXPIRED_TRIAL_USER,
      user: {
        ...EXPIRED_TRIAL_USER.user,
        trial_ends_at: new Date(Date.now() + 3 * 86_400_000).toISOString(),
      },
    });
    const { container } = render(<TrialEndedModal />);
    expect(container).toBeEmptyDOMElement();
  });
});
