/**
 * First-run banner coordination (components/FirstRunTip.tsx).
 *
 * Contract: while the first-run OnboardingTip welcome is on screen, the
 * promotional / status banners yield so a brand-new user gets a clean welcome;
 * the moment the tip is dismissed, the normal stack returns. TrialBanner stands
 * in for the promotional layer here — it only needs useUser, so it's the
 * cleanest of the three (UpgradeNudge/BreakingNewsBar fetch their own data) to
 * prove the yield wiring end-to-end.
 *
 * The account-health banners (Dunning/StaleData/EmailVerification) are mounted
 * OUTSIDE this provider in the layout and are intentionally not covered here —
 * they must never yield, so they never consult the context.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({ useUser: vi.fn() }));

import { useUser } from "@/components/UserContext";
import { TrialBanner } from "@/components/TrialBanner";
import { OnboardingTip } from "@/components/OnboardingTip";
import { FirstRunTipProvider } from "@/components/FirstRunTip";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

/** A brand-new trialing user: recent enough for the OnboardingTip (<=48h old)
 *  AND on a live trial, so BOTH the welcome and the trial banner want in. */
function newTrialingUser() {
  return {
    user: {
      id: "u_new",
      email: "new@example.com",
      name: "Sam",
      tier: "premium",
      trial_ends_at: new Date(Date.now() + 10 * 86_400_000).toISOString(),
      created_at: new Date(Date.now() - 3_600_000).toISOString(), // 1h ago
    },
    loading: false,
    refresh: vi.fn(),
    signout: vi.fn(),
  };
}

beforeEach(() => {
  mockedUseUser.mockReset();
  try {
    localStorage.clear();
  } catch {
    /* jsdom always has localStorage; guard is belt-and-braces */
  }
});

describe("FirstRunTip — promotional banners yield to the welcome", () => {
  it("hides the TrialBanner while the welcome shows, and restores it on dismiss", async () => {
    mockedUseUser.mockReturnValue(newTrialingUser());
    render(
      <FirstRunTipProvider>
        <TrialBanner />
        <OnboardingTip />
      </FirstRunTipProvider>,
    );

    // Welcome appears; the trial countdown yields beneath it.
    expect(
      await screen.findByText(/three things to try first/i),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByTestId("trial-banner")).not.toBeInTheDocument(),
    );

    // Dismiss the welcome → the trial banner comes back, welcome gone.
    fireEvent.click(
      screen.getByRole("button", { name: /dismiss welcome tip/i }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("trial-banner")).toBeInTheDocument(),
    );
    expect(
      screen.queryByText(/three things to try first/i),
    ).not.toBeInTheDocument();
  });

  it("shows the TrialBanner normally when the welcome was already dismissed", async () => {
    localStorage.setItem("tapeline_onboarding_dismissed_v1", "1");
    mockedUseUser.mockReturnValue(newTrialingUser());
    render(
      <FirstRunTipProvider>
        <TrialBanner />
        <OnboardingTip />
      </FirstRunTipProvider>,
    );

    // No welcome (already dismissed) → the trial banner is present from the start.
    expect(await screen.findByTestId("trial-banner")).toBeInTheDocument();
    expect(
      screen.queryByText(/three things to try first/i),
    ).not.toBeInTheDocument();
  });
});
