"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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
 * TWO KINDS OF TRIAL NOW EXIST, and this banner must never mix them up.
 *
 *   CARD ON FILE (the current trial, 2026-08 onward). Starting the trial goes
 *   through Stripe Checkout (mode=subscription, subscription_data.trial_end),
 *   so a card IS attached, $0 is taken today, and the FIRST CHARGE LANDS ON
 *   THE TRIAL-END DATE unless the user cancels first. That is a real upcoming
 *   billing event and the banner is obliged to say so in plain words: nothing
 *   charged yet, the exact date of the first charge, and that one click
 *   cancels before then. Telling this user "no card was taken" would be a lie,
 *   and telling them to "add a card" would be nagging them for something they
 *   have already given us — see #4 of the card-required-trial brief.
 *
 *   NO CARD ON FILE (legacy). Accounts that were auto-granted the old
 *   card-free trial at signup. For them the trial end is NOT a billing event:
 *   nothing is charged, there is nothing to cancel, and the account simply
 *   moves to Free. That copy is preserved verbatim below.
 *
 * When the card state is still UNKNOWN (fetch in flight, or the API is
 * unreachable) the banner states only what it can prove — Premium is active
 * through <date> — and makes NO claim in either direction. Unknown must never
 * degrade into the no-card copy: asserting "no card was taken" to someone who
 * has a charge coming is the worst failure this component can have.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * Length of the Premium trial in days. Mirrors the backend trial grant and the
 * "14-day" figure used across the pricing surfaces. Local because
 * `lib/pricing.ts` has no trial constant yet — see the PR body follow-up.
 */
export const TRIAL_DAYS = 14;

/** Days remaining at which the banner is still explaining the trial's START. */
const START_PHASE_DAYS_LEFT = TRIAL_DAYS - 1;

/**
 * `true` = a Stripe customer record (i.e. a card) is attached to this account.
 * `false` = definitively none. `null` = not known yet — callers must treat
 * this as "make no claim", never as "no card".
 */
export type CardOnFile = boolean | null;

// One in-flight request per page load, shared by every consumer of the hook
// (TrialBanner renders in the /app layout; TrialEarlyCapture is mounted
// alongside it). Without the memo a trial user pays for the same round-trip
// twice on every route change.
let _cardOnFilePromise: Promise<CardOnFile> | null = null;

/** Reset hook — tests only. Clears the module-scope request memo. */
export function __resetCardOnFileCache(): void {
  _cardOnFilePromise = null;
}

async function readJson(url: string): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(url, { credentials: "include", cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/**
 * Resolve "does this account have a card on file?".
 *
 * Source of truth order:
 *   1. GET /api/me — an EXPLICIT boolean, if the session payload carries one
 *      (`has_card_on_file`, or `billing.has_payment_method` /
 *      `billing.has_subscription`). This is the field the card-required-trial
 *      backend adds, and it is preferred because it costs no extra request.
 *   2. GET /api/billing/retention-options — `has_subscription`, which is
 *      literally `bool(user.stripe_customer_id)` server-side. This is the
 *      unambiguous fallback that works TODAY, and the same signal the billing
 *      page already gates its portal/cancel buttons on.
 *
 * Deliberately NOT derived from /api/me's `on_trial`. That flag currently
 * means "in a trial AND has no Stripe customer" (services/tier.is_on_trial),
 * so it happens to answer the question today — but the moment the trial gains
 * a card that definition has to change, and a banner that silently inverts its
 * claim when a backend predicate is widened is exactly the bug we cannot ship.
 */
async function resolveCardOnFile(): Promise<CardOnFile> {
  const me = await readJson(`${API_BASE}/api/me`);
  if (me) {
    const billing = (me.billing ?? {}) as Record<string, unknown>;
    for (const v of [
      me.has_card_on_file,
      billing.has_payment_method,
      billing.has_subscription,
    ]) {
      if (typeof v === "boolean") return v;
    }
  }
  const retention = await readJson(`${API_BASE}/api/billing/retention-options`);
  if (retention && typeof retention.has_subscription === "boolean") {
    return retention.has_subscription;
  }
  return null;
}

/**
 * Card-on-file state for the signed-in user. `enabled` gates the request so
 * the two trial components never hit the network for the ~99% of page loads
 * where nobody is on a trial at all.
 */
export function useCardOnFile(enabled: boolean): CardOnFile {
  const [cardOnFile, setCardOnFile] = useState<CardOnFile>(null);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    if (!_cardOnFilePromise) _cardOnFilePromise = resolveCardOnFile();
    _cardOnFilePromise.then((v) => {
      if (alive) setCardOnFile(v);
    });
    return () => {
      alive = false;
    };
  }, [enabled]);
  return cardOnFile;
}

export function TrialBanner() {
  const { user } = useUser();
  const { tipVisible } = useFirstRunTip();

  const endsAt = user?.trial_ends_at ? new Date(user.trial_ends_at) : null;
  const msLeft = endsAt ? endsAt.getTime() - Date.now() : NaN;
  const running = !!endsAt && Number.isFinite(msLeft) && msLeft > 0;
  // Hooks must run unconditionally, so the early returns below sit AFTER this.
  const cardOnFile = useCardOnFile(running);

  // The first-run OnboardingTip already states the trial is live — don't stack
  // the status strip on top of the welcome. Returns the moment it's dismissed.
  if (tipVisible) return null;
  if (!running || !endsAt) return null; // Expired → TrialEndedModal owns that moment.

  const daysLeft = Math.ceil(msLeft / (24 * 3600 * 1000));
  // First ~24-48h: the highest-value message is not the countdown, it is
  // "your trial actually started, and here is exactly what happens next".
  const isStart = daysLeft >= START_PHASE_DAYS_LEFT;
  const endLabel = endsAt.toLocaleDateString(undefined, { month: "short", day: "numeric" });

  return (
    <div
      data-testid="trial-banner"
      data-card-on-file={cardOnFile === null ? "unknown" : String(cardOnFile)}
      // Deliberately constant. Do not reintroduce a tone ternary here.
      className="mb-4 flex flex-col gap-2 rounded-lg bg-panel/60 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between"
    >
      <span className="text-muted">
        {cardOnFile === true ? (
          /* CARD ON FILE. A charge really is coming, so the date of it and the
             one-click exit are the two facts this user needs — stated as plain
             text, every time, at every point in the trial. No amount here:
             the banner cannot know the billing period the user chose, and a
             guessed figure would be worse than the exact one on /app/billing,
             which this row links to. */
          <>
            <strong className="font-medium text-fg">
              {isStart
                ? "Premium is active."
                : `${daysLeft} day${daysLeft === 1 ? "" : "s"} left`}
            </strong>{" "}
            {isStart
              ? `You have every Premium feature for ${TRIAL_DAYS} days, through ${endLabel}.`
              : `in your Premium trial, through ${endLabel}.`}{" "}
            Nothing has been charged. Your first charge is on {endLabel}; one
            click in Billing ends the trial before then and you are not charged
            at all.
          </>
        ) : cardOnFile === false ? (
          /* NO CARD ON FILE (legacy trial). Trial end is not a billing event
             for these accounts — nothing is charged and there is nothing to
             cancel. Copy preserved from the pre-card-required trial. */
          isStart ? (
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
          )
        ) : (
          /* UNKNOWN. State only what the session payload proves, and make no
             claim about a card in either direction. */
          <>
            <strong className="font-medium text-fg">
              {isStart
                ? "Premium is active."
                : `${daysLeft} day${daysLeft === 1 ? "" : "s"} left`}
            </strong>{" "}
            {isStart
              ? `You have every Premium feature for ${TRIAL_DAYS} days, through ${endLabel}.`
              : `in your Premium trial, through ${endLabel}.`}{" "}
            Billing shows exactly what happens on {endLabel}.
          </>
        )}
      </span>
      <Link
        href="/app/billing"
        className="shrink-0 self-start rounded-md border border-border px-3 py-1 text-xs font-medium text-fg hover:bg-panel2 sm:self-auto"
      >
        {cardOnFile === true ? "Manage plan" : "View plans"}
      </Link>
    </div>
  );
}
