/**
 * TrialEndedModal — the one-time "your trial ended" prompt. Two copy contracts:
 *   1. The downgrade description must state the REAL Free tier from
 *      FREE_LIMITS (12 look-ups/day, 5-ticker watchlist, 2 push alerts) —
 *      never the stale pre-#343 tier, and never overstate the drop.
 *   2. The refund line derives from REFUND (30-day guarantee).
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
import { FREE_LIMITS, REFUND } from "@/lib/pricing";

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
  it("describes the real post-#343 Free tier from FREE_LIMITS", () => {
    render(<TrialEndedModal />);
    const body = screen.getByText(/now on Free forever/i);
    const text = body.textContent ?? "";
    expect(text).toContain(`top ${FREE_LIMITS.scannerRows} scanner rows`);
    expect(text).toContain(`${FREE_LIMITS.dailyLookups} look-ups a day`);
    expect(text).toContain(`${FREE_LIMITS.watchlistTickers}-ticker watchlist`);
    expect(text).toContain(`${FREE_LIMITS.webPushAlerts} browser push alerts`);
    // Never the stale pre-#343 numbers.
    expect(text).not.toContain("5 look-ups");
    expect(text).not.toContain("3-ticker watchlist");
  });

  it("states the refund guarantee from REFUND", () => {
    render(<TrialEndedModal />);
    expect(screen.getByText(new RegExp(REFUND.short, "i"))).toBeInTheDocument();
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
