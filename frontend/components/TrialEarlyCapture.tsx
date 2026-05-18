"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useUser } from "@/components/UserContext";
import { track } from "@vercel/analytics";

/**
 * Non-blocking dismissable sheet that fires for trial users with 5-9 days
 * left. Soft-conversion moment: catches the committed early cohort before
 * the trial hits the urgent phase. Sits bottom-right on desktop, hidden on
 * mobile (TrialBanner already does the heavy lifting there — adding a
 * second floating card on a small viewport is hostile).
 *
 * Conditions to render, all required:
 *   - user.tier === "premium"
 *   - user.trial_ends_at is set and in the future
 *   - days remaining is between 5 and 9 inclusive
 *   - localStorage flag not set (one impression per trial per user)
 *
 * Dismissal sets the flag for the rest of the trial. The persistent
 * TrialBanner in the page header keeps the upgrade prompt visible.
 */
export function TrialEarlyCapture() {
  const { user } = useUser();
  const [open, setOpen] = useState(false);
  const [daysLeft, setDaysLeft] = useState(0);

  useEffect(() => {
    if (!user || user.tier !== "premium" || !user.trial_ends_at) return;
    if (typeof window === "undefined") return;
    const endsAt = new Date(user.trial_ends_at).getTime();
    if (!Number.isFinite(endsAt) || endsAt <= Date.now()) return;
    const dl = Math.ceil((endsAt - Date.now()) / 86_400_000);
    if (dl < 5 || dl > 9) return;
    try {
      const key = `tapeline_trial_early_capture_${user.id || user.email}`;
      if (window.localStorage.getItem(key) === "1") return;
      setDaysLeft(dl);
      setOpen(true);
      track("trial_early_capture_shown", { days_left: dl });
    } catch {
      // localStorage failures are non-fatal
    }
  }, [user]);

  function dismiss(reason: "x" | "later" | "clicked") {
    try {
      if (user) {
        const key = `tapeline_trial_early_capture_${user.id || user.email}`;
        window.localStorage.setItem(key, "1");
      }
    } catch {
      // ignore
    }
    if (reason !== "clicked") {
      track("trial_early_capture_dismissed", { reason });
    }
    setOpen(false);
  }

  if (!open) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40 hidden justify-end p-6 sm:flex">
      <div className="pointer-events-auto max-w-sm rounded-xl border border-accent/40 bg-panel/95 p-4 shadow-2xl shadow-accent/10 backdrop-blur">
        <div className="flex items-start gap-3">
          <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-accent" aria-hidden="true" />
          <div className="flex-1">
            <div className="text-sm font-semibold text-fg">
              Lock in your trial price &mdash; {daysLeft} days left
            </div>
            <p className="mt-1 text-xs text-muted">
              Add a card now and we won&rsquo;t charge a thing unless you
              decide to stay past day 14. One less thing to remember when
              the trial ends.
            </p>
            <div className="mt-3 flex items-center gap-3">
              <Link
                href="/app/billing?utm_source=trial_early_capture"
                onClick={() => {
                  track("trial_early_capture_clicked", { days_left: daysLeft });
                  dismiss("clicked");
                }}
                className="flex h-8 items-center justify-center rounded-md bg-accent px-3 text-xs font-medium text-white hover:opacity-90"
              >
                Add a card
              </Link>
              <button
                onClick={() => dismiss("later")}
                className="text-xs text-muted hover:text-fg"
              >
                Maybe later
              </button>
            </div>
          </div>
          <button
            onClick={() => dismiss("x")}
            aria-label="Dismiss"
            className="-mr-1 -mt-1 rounded p-1 text-lg leading-none text-muted hover:bg-black/30 hover:text-fg"
          >
            &times;
          </button>
        </div>
      </div>
    </div>
  );
}
