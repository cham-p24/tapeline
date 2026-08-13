"use client";

import Link from "next/link";
import { useUser } from "@/components/UserContext";
import { useFirstRunTip } from "@/components/FirstRunTip";
import { freeHasWatchlist } from "@/lib/pricing";

/**
 * Premium-trial status banner. Shows on every /app page while the user's
 * 14-day Premium trial is running.
 *
 * COMPLIANCE — Rule 6 (docs/COMPLIANCE_COPY_RULES.md). A factual statement
 * about the user's OWN real trial expiry is the one permitted time statement,
 * and only while it is styled calmly. So this banner uses a SINGLE neutral
 * treatment for the entire trial: no amber/red escalation as the end nears, no
 * pulsing, no seconds ticking down, no "last chance" / "hurry" / "don't lose"
 * language. The previous version escalated to the red loss token
 * (`bg-down/10 border-down/30 text-down`) at <= 3 days remaining and to
 * `warn` at <= 7 — that is manufactured pressure, and removing it is the point
 * of this component's styling being a constant rather than a ternary.
 *
 * The trial takes NO CARD. Its end is therefore NOT a billing event: nothing
 * is charged, there is nothing to cancel, and the account simply moves to
 * Free. The copy must never imply a charge or a cancellation deadline. (The
 * old copy — "Add a card to keep all features ... otherwise your account drops
 * to Free" — read as a looming billing decision; it now leads with what the
 * user has.)
 */

/**
 * Length of the Premium trial in days. Mirrors the backend trial grant and the
 * "14-day" figure used across the pricing surfaces. Local because
 * `lib/pricing.ts` has no trial constant yet — see the PR body follow-up.
 */
const TRIAL_DAYS = 14;

/** Days remaining at which the banner is still explaining the trial's START. */
const START_PHASE_DAYS_LEFT = TRIAL_DAYS - 1;

export function TrialBanner() {
  const { user } = useUser();
  const { tipVisible } = useFirstRunTip();
  // The first-run OnboardingTip already states "your 14-day Premium trial is
  // live" — don't stack the countdown on top of the welcome. Returns the moment
  // the tip is dismissed.
  if (tipVisible) return null;
  if (!user?.trial_ends_at) return null;

  const endsAt = new Date(user.trial_ends_at);
  const msLeft = endsAt.getTime() - Date.now();
  if (!Number.isFinite(msLeft) || msLeft <= 0) return null; // Expired — TrialEndedModal owns that moment.

  const daysLeft = Math.ceil(msLeft / (24 * 3600 * 1000));
  // First ~24-48h: the highest-value message is not the countdown, it is
  // "your trial actually started, and no card was taken". The most common
  // trial failure is a user who never realised Premium was switched on, or
  // who assumes a charge is coming.
  const isStart = daysLeft >= START_PHASE_DAYS_LEFT;
  const endLabel = endsAt.toLocaleDateString(undefined, { month: "short", day: "numeric" });

  return (
    <div
      data-testid="trial-banner"
      // Deliberately constant. Do not reintroduce a tone ternary here.
      className="mb-4 flex flex-col gap-2 rounded-lg bg-panel/60 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between"
    >
      <span className="text-muted">
        {isStart ? (
          <>
            <strong className="font-medium text-fg">Premium is active.</strong> You have every
            Premium feature for {TRIAL_DAYS} days, through {endLabel}. No card was taken, so
            nothing is charged and there is nothing to cancel — on {endLabel} the account moves
            to Free on its own.
          </>
        ) : (
          <>
            <strong className="font-medium text-fg">
              {daysLeft} day{daysLeft === 1 ? "" : "s"} left
            </strong>{" "}
            in your Premium trial, through {endLabel}. There is no card on file: nothing is
            charged and there is nothing to cancel. On {endLabel} the account moves to Free, and{" "}
            {freeHasWatchlist()
              ? "your watchlist, saved scans and alert rules stay intact."
              : "your saved scans and alert rules stay intact — your saved watchlist tickers are kept, and unlock on Pro."}{" "}
            {/* Voluntary mid-trial card-add. Checkout forwards trial_ends_at
                as Stripe's subscription trial_end, so this is factually
                accurate: adding a card now changes nothing until the date the
                trial was always going to end. Calm, no pressure — the
                commitment-device upside comes from the option existing, not
                from pushing it (compliance rule 6). */}
            Prefer to settle it now? Adding a card any time keeps Premium at the
            founding price &mdash; you&rsquo;re still not charged until {endLabel}.
          </>
        )}
      </span>
      <Link
        href="/app/billing"
        className="shrink-0 self-start rounded-md border border-border px-3 py-1 text-xs font-medium text-fg hover:bg-panel2 sm:self-auto"
      >
        View plans
      </Link>
    </div>
  );
}
