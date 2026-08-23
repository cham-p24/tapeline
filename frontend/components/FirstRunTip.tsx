/**
 * First-run banner coordination.
 *
 * The /app banner stack can pile several rows on top of the page for a
 * brand-new user: the OnboardingTip welcome, the trial countdown, the news
 * ticker, an upgrade nudge. That wall buries the one thing a first-time user
 * should read — the welcome and its three "try this next" links.
 *
 * This context lets the promotional / status banners YIELD while the first-run
 * OnboardingTip is on screen, so a new user gets a clean welcome. The moment
 * they dismiss the tip (one click), the normal stack returns.
 *
 * Deliberately scoped: only the OnboardingTip sets `tipVisible`, and only the
 * *promotional* banners read it (TrialBanner, UpgradeNudge, BreakingNewsBar).
 * Account-health banners (Dunning, StaleData, EmailVerification) never consult
 * it — an action-required warning must never be hidden behind a welcome card.
 *
 * The default value is a no-op so every consumer still renders correctly when
 * no provider is mounted (e.g. in isolated component tests): tipVisible is
 * false and the setter does nothing.
 */
"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

type FirstRunTipValue = {
  /** True while the first-run OnboardingTip welcome is on screen. */
  tipVisible: boolean;
  /** Owned by OnboardingTip; promotional banners only read tipVisible. */
  setTipVisible: (visible: boolean) => void;
};

const FirstRunTipContext = createContext<FirstRunTipValue>({
  tipVisible: false,
  setTipVisible: () => {},
});

export function FirstRunTipProvider({ children }: { children: ReactNode }) {
  const [tipVisible, setTipVisible] = useState(false);
  return (
    <FirstRunTipContext.Provider value={{ tipVisible, setTipVisible }}>
      {children}
    </FirstRunTipContext.Provider>
  );
}

export function useFirstRunTip(): FirstRunTipValue {
  return useContext(FirstRunTipContext);
}
