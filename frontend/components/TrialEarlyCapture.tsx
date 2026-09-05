"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useUser } from "@/components/UserContext";
import { useCardOnFile, type CardOnFile } from "@/components/TrialBanner";
import { FREE_LIMITS } from "@/lib/pricing";
import { trackEvent } from "@/lib/gtag";

/**
 * Non-blocking dismissable sheet that fires for trial users with 5-9 days
 * left. Sits bottom-right on desktop, hidden on mobile (TrialBanner already
 * does the heavy lifting there — adding a second floating card on a small
 * viewport is hostile).
 *
 * WHAT THIS COMPONENT IS FOR: capturing a card from a trial that does not have
 * one. That makes the card state a hard gate, not a copy detail.
 *
 *   cardOnFile === true  → renders NOTHING. Since 2026-08 the 30-day Premium
 *       trial is started through Stripe Checkout, so the ordinary trialist
 *       already has a card on file and their first charge is already
 *       scheduled. Showing them "Add a card" would be asking for something
 *       they have already given, and the sheet has no other job.
 *   cardOnFile === false → the full legacy nudge (an account from the old
 *       auto-granted card-free trial). Copy unchanged.
 *   cardOnFile === null  → card state unknown (API unreachable). The sheet
 *       still states the Premium → Free delta, but drops BOTH the add-a-card
 *       ask and the "nothing to cancel" claim, because neither can be
 *       supported without knowing whether a charge is scheduled.
 *
 * The body NAMES the Premium → Free feature delta (what Free keeps vs what
 * Pro/Premium add), derived from FREE_LIMITS so it can't drift from the
 * enforced caps. During the trial every Free wall is suppressed, so a trial
 * user never feels what they'd lose until the walls appear at trial end — by
 * which point most have gone. Stating the delta here, while they still hold
 * Premium, is the primary trial→paid lever. It is a factual account statement,
 * never urgency: do NOT add "act now" / "last chance" / a price deadline.
 *
 * COMPLIANCE (Rule 6 — see docs/COMPLIANCE_COPY_RULES.md): stating the days
 * remaining on the user's OWN trial is permitted, because it is a factual
 * statement about their account. What is NOT permitted is attaching that
 * countdown to a price or offer deadline. This component previously read
 * "Lock in your trial price — N days left", which invented a deadline that
 * does not exist (founding pricing is permanent, not time-limited) and is
 * exactly the manufactured-scarcity pattern the rule prohibits. Keep the
 * copy descriptive: say what happens, and what does not.
 *
 * There is deliberately no "urgent phase" — TrialBanner holds one calm,
 * constant treatment from day 14 to day 1 (see #362). Do not reintroduce
 * escalating styling or language here.
 *
 * Conditions to render, all required:
 *   - user.tier === "premium"
 *   - user.trial_ends_at is set and in the future
 *   - days remaining is between 5 and 9 inclusive
 *   - the account does NOT have a card on file (see the gate above)
 *   - localStorage flag not set (one impression per trial per user)
 *
 * Dismissal sets the flag for the rest of the trial. The persistent
 * TrialBanner in the page header keeps the plan link visible.
 */
export function TrialEarlyCapture({
  cardOnFile: cardOnFileProp,
}: {
  /** Test/preview override for the /api/me-derived card state. */
  cardOnFile?: CardOnFile;
} = {}) {
  const { user } = useUser();
  const [open, setOpen] = useState(false);
  const [daysLeft, setDaysLeft] = useState(0);

  // Cheap "might be on a trial" gate for the card lookup — deliberately does
  // NOT read the clock (that would make the render impure); the effect below
  // still does the real expiry check before anything is shown.
  const maybeOnTrial = !!user && user.tier === "premium" && !!user.trial_ends_at;
  const fetched = useCardOnFile(maybeOnTrial && cardOnFileProp === undefined);
  const cardOnFile = cardOnFileProp === undefined ? fetched : cardOnFileProp;

  useEffect(() => {
    if (!user || user.tier !== "premium" || !user.trial_ends_at) return;
    if (typeof window === "undefined") return;
    // Hard gate: nothing to capture from an account that already has a card.
    if (cardOnFile === true) return;
    const endsAt = new Date(user.trial_ends_at).getTime();
    if (!Number.isFinite(endsAt) || endsAt <= Date.now()) return;
    const dl = Math.ceil((endsAt - Date.now()) / 86_400_000);
    if (dl < 5 || dl > 9) return;
    try {
      const key = `tapeline_trial_early_capture_${user.id || user.email}`;
      if (window.localStorage.getItem(key) === "1") return;
      setDaysLeft(dl);
      setOpen(true);
      trackEvent("trial_early_capture_shown", { days_left: dl });
    } catch {
      // localStorage failures are non-fatal
    }
  }, [user, cardOnFile]);

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
      trackEvent("trial_early_capture_dismissed", { reason });
    }
    setOpen(false);
  }

  if (!open || cardOnFile === true) return null;

  const knownCardless = cardOnFile === false;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40 hidden justify-end p-6 sm:flex">
      <div
        data-testid="trial-early-capture"
        className="pointer-events-auto max-w-sm rounded-xl border border-accent/40 bg-surface p-4 shadow-2xl shadow-accent/10"
      >
        <div className="flex items-start gap-3">
          <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-accent" aria-hidden="true" />
          <div className="flex-1">
            <div className="text-sm font-semibold text-fg">
              Your Premium trial has {daysLeft} {daysLeft === 1 ? "day" : "days"} left
            </div>
            <p className="mt-1 text-xs text-muted">
              You have every Premium feature right now. When the trial ends,
              Free keeps the top {FREE_LIMITS.scannerRows} scored rows and{" "}
              {FREE_LIMITS.dailyLookups}{" "}look-ups a day &mdash; the full
              real-time universe and unlimited look-ups are Pro and Premium.
              {knownCardless ? (
                <>
                  {" "}Adding a card keeps them on; it doesn&rsquo;t charge you or
                  shorten the trial, and if you&rsquo;d rather not, the account
                  moves to Free on its own &mdash; nothing to cancel.
                </>
              ) : (
                <>
                  {" "}Billing shows your current plan and exactly what happens
                  when the trial ends.
                </>
              )}
            </p>
            <div className="mt-3 flex items-center gap-3">
              <Link
                href="/app/billing?utm_source=trial_early_capture"
                onClick={() => {
                  trackEvent("trial_early_capture_clicked", { days_left: daysLeft });
                  dismiss("clicked");
                }}
                className="flex h-8 items-center justify-center rounded-md bg-accent px-3 text-xs font-medium text-white hover:opacity-90"
              >
                {knownCardless ? "Add a card" : "Open billing"}
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
            className="-mr-1 -mt-1 rounded p-1 text-lg leading-none text-muted hover:bg-panel2 hover:text-fg"
          >
            &times;
          </button>
        </div>
      </div>
    </div>
  );
}
