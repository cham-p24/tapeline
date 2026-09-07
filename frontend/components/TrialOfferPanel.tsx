/**
 * The 30-day Premium trial offer — the ONE surface that asks for a card in
 * exchange for a trial, and therefore the one that has to be beyond reproach.
 *
 * WHY IT LIVES IN components/ NOW
 * -------------------------------
 * It was a private function inside app/app/billing/page.tsx, because
 * /app/billing was the only place it rendered: signup's default post-auth
 * destination was `/app/billing?trial=start`, so a brand-new account met a
 * payment decision BEFORE it had seen a single scored row. Stock Rover, Simply
 * Wall St, Stock Unlock, Koyfin, Danelfin and TradingView all drop a new
 * account straight into the product instead, and the founder's own data agrees:
 * when a card wall briefly stood at /app/start (#548 → #683), three accounts
 * hit it, none added a card, none ran a single scan, and two never opened the
 * payment page.
 *
 * So the default destination is now the scanner and the offer travels to it —
 * as a dismissible panel above the table (components/ScannerTrialOffer.tsx).
 * The offer MOVED; it did not soften. Every word of the disclosure below is the
 * same text that has always been on /app/billing, and both surfaces render this
 * one component so they cannot drift.
 *
 * NON-NEGOTIABLES, all enforced by __tests__/TrialStartOffer.test.tsx (billing)
 * and __tests__/ScannerTrialOffer.test.tsx (scanner):
 *
 *   1. FULL DISCLOSURE BEFORE THE CARD. Four facts as real body text (not an
 *      image, not a tooltip, not behind a <details>): $0 charged today, the
 *      exact calendar date of the first charge, the amount that will be
 *      charged, and that one click cancels before then. If the user only reads
 *      the buttons they have still been told the price and the date.
 *   2. THE DECLINE IS EQUAL, AND TRUE. The decline is the same size and the
 *      same typographic weight as the trial button, sits beside it, is not a
 *      greyed-out afterthought, and is not preceded by a guilt line.
 *
 *      It must also DESCRIBE WHAT ACTUALLY HAPPENS. This has been wrong in
 *      both directions, so the history is worth keeping:
 *
 *      The panel shipped with one unconditional decline reading "Continue on
 *      the Free plan → /app/scanner", promising "live scores, top-N scanner, N
 *      look-ups a day". From CARD_GATE_START (2026-08-22) every word of that
 *      was false for a new account: /app/scanner was not in
 *      CARD_GATE_PASSTHROUGH, so app/app/layout.tsx replaced it with the card
 *      wall the instant they clicked. So the decline was FORKED on
 *      `cardRequired` (the server's `must_add_card`): a gated account was told
 *      the signed-in app stays locked without a card and was pointed at the
 *      public record instead.
 *
 *      #683 (2026-08-30) removed the wall, which made the FORK the lie — it
 *      was telling every card-free account the app was locked when the free
 *      scanner was one click away, and routing them off the product to say so.
 *      The fork is gone and the decline is unconditional again: everyone
 *      continues on the Free plan, to /app/scanner, which is now true for
 *      every account that can see this panel.
 *
 *      THE RULE, which outlived both mistakes: the decline must describe the
 *      destination it actually leads to. Never promise a Free tier the reader
 *      cannot reach, and never withhold one they can. That rule is also why
 *      `onDecline` exists: ON the scanner, "Continue on the Free plan" is not
 *      a journey anywhere — the reader is already there, on the free plan,
 *      looking at it — so the control dismisses the panel and leaves them
 *      where they are, rather than linking them to the page they are on.
 *   3. NO DARK PATTERNS. No auto-redirect into Stripe (the button is the only
 *      thing that navigates), nothing pre-ticked, no countdown, no scarcity,
 *      no "N spots left", no fake discount. Compliance rule 6 — and the copy
 *      linter (scripts/lint-copy-compliance.mjs) will fail the build for most
 *      of them anyway.
 *   4. KEYBOARD OPERABLE. Everything interactive is a real <button> or <a>,
 *      in reading order, with the global :focus-visible ring plus an explicit
 *      focus ring here so it stays visible on the tinted panel.
 *
 * The billing-period choice lives inside the panel because the AMOUNT in the
 * disclosure has to be the amount for the period actually selected. On
 * /app/billing it shares state with the plan picker's toggle below, so the two
 * can never disagree.
 */
"use client";

import Link from "next/link";
import { PRICING, FREE_LIMITS, usd, usdCompact, freeHasWatchlist } from "@/lib/pricing";
import { TRIAL_DAYS } from "@/lib/trial";
import { longDate } from "@/lib/datetime";
import { ACTIVE_SCORED_TICKERS } from "@/lib/universe";

export function TrialOfferPanel({
  billingPeriod,
  onBillingPeriod,
  firstCharge,
  busy,
  onStartTrial,
  onDecline,
  laterHint,
}: {
  billingPeriod: "monthly" | "annual";
  onBillingPeriod: (p: "monthly" | "annual") => void;
  firstCharge: Date;
  busy: boolean;
  onStartTrial: () => void;
  /**
   * Scanner variant: the decline becomes a button that closes the panel in
   * place, instead of a link to /app/scanner. Same label, same size, same
   * weight — see non-negotiable 2. Omitted on /app/billing, where the link
   * genuinely takes the reader somewhere.
   */
  onDecline?: () => void;
  /**
   * The trailing "…and you can start the trial later" sentence. Defaults to
   * the billing-page wording ("from this page"), which is false anywhere else,
   * so the scanner passes its own. This is the ONLY sentence either surface
   * may vary — the four disclosure facts above it are fixed.
   */
  laterHint?: React.ReactNode;
}) {
  const chargeDate = longDate(firstCharge);
  const amount =
    billingPeriod === "annual"
      ? `${usdCompact(PRICING.premium.annual)} for the year`
      : `${usd(PRICING.premium.monthly)} for the month`;
  const FOCUS =
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background";
  // Identical classes on both halves of the fork — the test asserts the decline
  // is never dimmed, shrunk or de-weighted relative to the trial button.
  const FORK_BUTTON = `flex h-11 flex-1 items-center justify-center rounded-md border border-border bg-surface px-4 text-sm font-medium text-fg transition-colors hover:bg-panel2 ${FOCUS}`;

  return (
    <section
      data-testid="trial-offer"
      aria-labelledby="trial-offer-heading"
      className="rounded-2xl border border-border bg-panel p-6"
    >
      <h2 id="trial-offer-heading" className="text-xl font-semibold">
        Start your {TRIAL_DAYS}-day Premium trial &mdash; or don&rsquo;t
      </h2>
      <p className="mt-1.5 text-sm text-muted">
        Every Premium feature for {TRIAL_DAYS} days: the full ~{ACTIVE_SCORED_TICKERS.toLocaleString("en-US")}-ticker live
        universe, score breakdowns, Congressional trades and insider buys,
        watchlist of 200 and unlimited email alerts. Starting the trial takes a
        card, because it becomes a paid subscription if you keep it. Here is
        exactly what that means.
      </p>

      {/* Billing period — nothing is pre-ticked beyond the site-wide default,
          and switching it rewrites the amount in the disclosure below. */}
      <div className="mt-5">
        <div id="trial-period-label" className="text-[11px] uppercase tracking-wider text-muted">
          Plan after the trial
        </div>
        <div
          role="group"
          aria-labelledby="trial-period-label"
          className="mt-2 inline-flex rounded-full border border-border bg-surface p-1"
        >
          {(["annual", "monthly"] as const).map((p) => (
            <button
              key={p}
              type="button"
              aria-pressed={billingPeriod === p}
              onClick={() => onBillingPeriod(p)}
              className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all ${FOCUS} ${
                billingPeriod === p ? "bg-fg text-background" : "text-muted hover:text-fg"
              }`}
            >
              {p === "annual"
                ? `Annual · ${usdCompact(PRICING.premium.annual)}/yr`
                : `Monthly · ${usd(PRICING.premium.monthly)}/mo`}
            </button>
          ))}
        </div>
      </div>

      {/* THE DISCLOSURE. Plain text, always visible, never collapsed. */}
      <ul data-testid="trial-disclosure" className="mt-5 space-y-2 text-sm text-fg">
        <li className="flex gap-2">
          <span aria-hidden="true" className="text-muted">·</span>
          <span>
            <strong className="font-semibold">$0 today.</strong> Starting the
            trial charges you nothing now.
          </span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden="true" className="text-muted">·</span>
          <span>
            <strong className="font-semibold">Your first charge is on {chargeDate}</strong>{" "}
            &mdash; {amount}, and then {billingPeriod === "annual" ? "every year" : "every month"}{" "}
            until you cancel.
          </span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden="true" className="text-muted">·</span>
          <span>
            <strong className="font-semibold">Cancel in one click</strong> from the
            billing page any time before {chargeDate} and you are never charged.
          </span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden="true" className="text-muted">·</span>
          <span>
            Card details are entered on Stripe&rsquo;s own checkout page. Your
            card number never reaches a Tapeline server.
          </span>
        </li>
      </ul>

      {/* THE FORK. Same height, same width behaviour, same font weight. */}
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={onStartTrial}
          disabled={busy}
          className={`flex h-11 flex-1 items-center justify-center rounded-md border border-accent bg-accent/15 px-4 text-sm font-medium text-fg transition-colors hover:bg-accent/25 disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
        >
          {busy ? "Opening Stripe…" : `Start the ${TRIAL_DAYS}-day trial`}
        </button>
        {onDecline ? (
          <button type="button" onClick={onDecline} className={FORK_BUTTON}>
            Continue on the Free plan
          </button>
        ) : (
          <Link href="/app/scanner" className={FORK_BUTTON}>
            Continue on the Free plan
          </Link>
        )}
      </div>

      <p className="mt-4 text-xs text-muted leading-relaxed">
        Declining costs you nothing: you stay on the Free plan &mdash; live scores,
        top-{FREE_LIMITS.scannerRows}{" "}scanner, {FREE_LIMITS.dailyLookups}{" "}look-ups a day
        {freeHasWatchlist() ? `, a ${FREE_LIMITS.watchlistTickers}-ticker watchlist` : ""}, and
        {" "}{FREE_LIMITS.savedScans}{" "}saved screen &mdash; and no further charge is made. The
        public record stays open too, with no account at all.{" "}
        {laterHint ?? (
          <>You can start the trial later from this page &mdash; it is here whenever you want it.</>
        )}
      </p>
    </section>
  );
}
