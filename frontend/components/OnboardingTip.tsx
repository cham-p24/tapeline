/**
 * One-shot "you're new — here's where to start" callout.
 *
 * Shows on the first /app/* visit after signup. Dismissed permanently
 * via localStorage so returning users don't see it. Single component,
 * single click to dismiss, three concrete actions to take next — the
 * lightest possible onboarding that still beats "blank scanner page".
 *
 * Why no multi-step tour: the more steps in an onboarding flow, the
 * lower completion rate. A single dense callout with three actionable
 * links converts better than five sequential popovers nobody finishes.
 */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useUser } from "@/components/UserContext";

const STORAGE_KEY = "tapeline_onboarding_dismissed_v1";

export function OnboardingTip() {
  const { user, loading } = useUser();
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (loading || !user) return;
    // Only show if (a) the user has never dismissed it, AND (b) they
    // signed up recently — old accounts opening the app after a feature
    // launch shouldn't get a "welcome!" message.
    try {
      const dismissed = localStorage.getItem(STORAGE_KEY);
      if (dismissed) return;
      const created = user.created_at ? new Date(user.created_at).getTime() : 0;
      const ageHours = (Date.now() - created) / (1000 * 60 * 60);
      if (ageHours <= 48) setShow(true);
    } catch {
      /* localStorage blocked — silently skip the tip rather than nag. */
    }
  }, [user, loading]);

  function dismiss() {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
    setShow(false);
  }

  if (!show) return null;

  return (
    <div className="mb-4 overflow-hidden rounded-xl border border-accent/40 bg-gradient-to-br from-accent/10 via-panel to-panel">
      <div className="flex items-start gap-4 p-5">
        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-accent/20 text-accent text-lg">
          👋
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-semibold tracking-tight">
            Welcome{user?.name ? `, ${user.name.split(" ")[0]}` : ""}. Three things to try first.
          </h3>
          <p className="mt-1 text-sm text-muted">
            Your 14-day Premium trial is live. No credit card on file.
          </p>
          <ul className="mt-3 space-y-1.5 text-sm">
            <li className="flex items-start gap-2">
              <span className="text-accent flex-shrink-0">→</span>
              <span>
                <Link href="/app/scanner" className="text-fg hover:text-accent transition-colors">
                  Scan the universe
                </Link>{" "}
                — every ticker scored 0–100, hover any score for the 6-factor breakdown.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-accent flex-shrink-0">→</span>
              <span>
                <Link href="/app/watchlist" className="text-fg hover:text-accent transition-colors">
                  Set up a watchlist
                </Link>{" "}
                — one click adds 8 mega-caps + SPY so smart alerts can fire from day one.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-accent flex-shrink-0">→</span>
              <span>
                <Link href="/scorecard" className="text-fg hover:text-accent transition-colors">
                  See the public scorecard
                </Link>{" "}
                — every score we publish, back-checked against next-day prices.
              </span>
            </li>
          </ul>
        </div>
        <button
          onClick={dismiss}
          aria-label="Dismiss welcome tip"
          className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-muted hover:bg-panel2 hover:text-fg transition-colors"
        >
          <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
