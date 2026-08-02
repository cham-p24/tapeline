"use client";

import { useMemo } from "react";
import type { SessionUser } from "@/lib/auth";
import { UserCtx } from "@/components/UserContext";
import { FirstRunTipProvider } from "@/components/FirstRunTip";
import { OnboardingTip } from "@/components/OnboardingTip";
import { TrialEarlyCapture } from "@/components/TrialEarlyCapture";

/**
 * Verification harness (non-production only — see the page-level guard).
 *
 * Injects a mocked session — a fresh-signup Premium-trial user with 7 days
 * left — so the two auth+state-gated surfaces actually render:
 *   - OnboardingTip     (welcome card; shows when created_at <= 48h)
 *   - TrialEarlyCapture (trial nudge; shows for a premium trial, 5-9 days left,
 *                        fixed bottom-right on desktop viewports)
 * The nearest UserCtx.Provider wins, so this mock overrides the real session
 * for this subtree without touching /api/me.
 */
export function TrialWelcomePreview() {
  const value = useMemo(() => {
    const now = Date.now();
    const user: SessionUser = {
      id: "preview-user",
      email: "preview@tapeline.io",
      name: "Alex Trader",
      tier: "premium",
      // Fresh signup → OnboardingTip's <=48h gate passes.
      created_at: new Date(now).toISOString(),
      // 7 days left → TrialEarlyCapture's 5-9 day window passes.
      trial_ends_at: new Date(now + 7 * 86_400_000).toISOString(),
    };
    return {
      user,
      loading: false,
      refresh: async () => {},
      signout: async () => {},
    };
  }, []);

  return (
    <UserCtx.Provider value={value}>
      <FirstRunTipProvider>
        <main style={{ maxWidth: 760, margin: "0 auto", padding: "40px 24px" }}>
          <p style={{ fontSize: 12, opacity: 0.6, marginBottom: 20 }}>
            Non-production preview — mocked Premium trial user (fresh signup, 7
            days left). Below: the welcome card (OnboardingTip). The trial nudge
            (TrialEarlyCapture) is fixed to the bottom-right on desktop widths.
          </p>
          <OnboardingTip />
          <TrialEarlyCapture />
        </main>
      </FirstRunTipProvider>
    </UserCtx.Provider>
  );
}
