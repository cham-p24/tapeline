"use client";

/**
 * /app/start — the card gate.
 *
 * This is the one screen standing between a brand-new account and the
 * logged-in product. An account created on or after the cutover has to put a
 * card on file before /app/* opens; the layout sends every other /app route
 * here while that is true (see app/app/layout.tsx), and sends the user back
 * out the moment it stops being true.
 *
 * WHO NEVER SEES THIS PAGE, and it is not a short list: every account created
 * before the cutover, every admin, every lifetime account, and anyone with a
 * card already on file. The verdict is `must_add_card` on the session payload
 * and it is computed server-side from one dated constant. This page re-derives
 * nothing — it renders the wall only when told to, and redirects out
 * otherwise.
 *
 * THE RULES THIS SCREEN HAS TO OBEY. It is asking for a card before the person
 * has seen a single screen of the product, which is the least earned ask in
 * the whole funnel, so the disclosure has to be better than the one on the
 * billing page, not worse:
 *
 *  1. THE FULL TERMS, AS REAL BODY TEXT, ABOVE THE BUTTON. $0 today, the exact
 *     calendar date of the first charge, the exact amount, that one click
 *     cancels before then, and that we email three days ahead of the charge.
 *     Not a tooltip, not an image, not behind a <details>, not on the next
 *     screen. (The three-days-ahead email is a real thing we send — it is the
 *     `customer.subscription.trial_will_end` branch in
 *     backend/app/routers/webhooks.py — so stating it here is a promise the
 *     system keeps, not a reassurance.)
 *  2. A REAL WAY OUT, NOT PUNISHED. The public record and today's picks stay
 *     free and need no account at all; both are linked, plainly, right here,
 *     as is signing out. Someone who does not want to give us a card must be
 *     able to leave with something rather than be cornered.
 *  3. NOTHING AUTOMATIC. The page never redirects into Stripe on its own,
 *     nothing is pre-ticked beyond the site-wide billing-period default, and
 *     no urgency, scarcity or countdown appears anywhere on it.
 *  4. ONE CHECKOUT PATH. The button POSTs to the same /api/billing/checkout
 *     with the same `start_trial` flag the billing page uses — Stripe Checkout
 *     in mode=subscription with subscription_data.trial_end. There is no
 *     second, gate-only payment path to keep in sync or to get wrong.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@/components/UserContext";
import { TRIAL_DAYS } from "@/components/TrialBanner";
import { PRICING, DEFAULT_BILLING_PERIOD, usd, usdCompact, type BillingPeriod } from "@/lib/pricing";
import { userLocale } from "@/lib/datetime";
import { trackEvent } from "@/lib/gtag";
import { errorMessage, handle401 } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/** Where a user who declines still gets something real, for free, with no account. */
const PUBLIC_RECORD_PATH = "/scorecard";
const PUBLIC_PICKS_PATH = "/daily-picks";

/**
 * Trial-start marker read by the billing page's return-from-Stripe handler.
 *
 * The key is duplicated from app/app/billing/page.tsx on purpose — that page
 * owns it, and it is a page module, so importing the constant would drag the
 * whole billing page into this bundle. If the two ever drift, the failure is
 * benign: this is the belt, and the `trial=1` flag the backend puts on the
 * success_url is the braces. Both exist so a $0 trial start can never be
 * reported as a paid `subscribe` and book revenue nobody paid.
 */
const TRIAL_CHECKOUT_INTENT_KEY = "tapeline_trial_checkout_intent";

/**
 * When we last handed this browser off to Stripe from THIS page.
 *
 * Stripe's success_url lands on /app/billing, but the tier flip happens on a
 * webhook, so for a few seconds after a completed checkout the session can
 * still say `must_add_card` — and the layout will bounce the user straight
 * back here. Being shown the card wall seconds after handing over a card is
 * the single worst thing this screen could do, so while this marker is fresh
 * the page re-checks the session in the background and says, calmly, that a
 * confirmation may still be landing.
 *
 * It never claims the checkout was COMPLETED — we cannot know that, the user
 * may have backed out — so the wall stays fully usable underneath the note.
 */
const CHECKOUT_HANDOFF_KEY = "tapeline_card_gate_handoff";
/** How long after a hand-off we keep re-checking. Comfortably longer than a webhook. */
const CONFIRM_WINDOW_MS = 90_000;
/** How often we re-check while inside that window. */
const CONFIRM_POLL_MS = 3_000;

/** Shared focus treatment — the tinted panel loses the global ring too easily. */
const FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background";

/** Long-form date for the disclosure, e.g. "5 September 2026". */
function longDate(d: Date): string {
  return d.toLocaleDateString(userLocale(), {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function rememberHandoff(): void {
  try {
    window.sessionStorage.setItem(CHECKOUT_HANDOFF_KEY, String(Date.now()));
    window.sessionStorage.setItem(
      TRIAL_CHECKOUT_INTENT_KEY,
      JSON.stringify({ tier: "premium", at: Date.now() }),
    );
  } catch {
    // Storage blocked. The `trial=1` success_url flag still covers the
    // analytics half; the only thing lost is the "still confirming" note.
  }
}

/** Milliseconds since the hand-off, or null if there wasn't a fresh one. */
function handoffAge(): number | null {
  try {
    const raw = window.sessionStorage.getItem(CHECKOUT_HANDOFF_KEY);
    if (!raw) return null;
    const at = Number(raw);
    if (!Number.isFinite(at)) return null;
    const age = Date.now() - at;
    return age >= 0 && age < CONFIRM_WINDOW_MS ? age : null;
  } catch {
    return null;
  }
}

function clearHandoff(): void {
  try {
    window.sessionStorage.removeItem(CHECKOUT_HANDOFF_KEY);
  } catch {
    /* nothing to clean up */
  }
}

export default function CardGateStartPage() {
  const router = useRouter();
  const { user, loading, mustAddCard, refresh, signout } = useUser();
  const gated = mustAddCard === true;

  const [billingPeriod, setBillingPeriod] = useState<BillingPeriod>(DEFAULT_BILLING_PERIOD);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [awaitingStripe, setAwaitingStripe] = useState(false);
  // The date Stripe will take the first charge if the trial starts now. Fixed
  // at mount so the quoted date can't slide underneath the user mid-session,
  // and it mirrors the trial_end the backend sets on the Checkout session
  // (subscription_data.trial_end = now + TRIAL_DAYS).
  const [firstCharge] = useState(() => new Date(Date.now() + TRIAL_DAYS * 86_400_000));

  // Not gated? Then this page is not for you. Covers the grandfathered
  // account that typed the URL, the subscriber who bookmarked it, and the
  // moment the card lands and the flag flips.
  useEffect(() => {
    if (loading || gated) return;
    clearHandoff();
    router.replace("/app/scanner");
  }, [loading, gated, router]);

  // Re-check the session for a short window after we sent someone to Stripe.
  // Pure background work: it changes what the note says, never what the page
  // lets the user do.
  useEffect(() => {
    if (handoffAge() === null) return;
    setAwaitingStripe(true);
    const id = setInterval(() => {
      if (handoffAge() === null) {
        clearInterval(id);
        clearHandoff();
        setAwaitingStripe(false);
        return;
      }
      void refresh();
    }, CONFIRM_POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const startCheckout = useCallback(async () => {
    setBusy(true);
    setErr(null);
    // Same funnel event, same shape, as every other upgrade CTA — `surface`
    // is the only addition, so the gate's contribution is separable in GA4.
    // A click is not a trial: `start_trial` fires on the confirmed return,
    // not here.
    trackEvent("begin_checkout", {
      tier: "premium",
      billing_period: billingPeriod,
      current_tier: user?.tier ?? "free",
      start_trial: true,
      surface: "card_gate",
      value: billingPeriod === "annual" ? PRICING.premium.annual : PRICING.premium.monthly,
      currency: PRICING.currency,
    });
    try {
      const res = await fetch(`${API_BASE}/api/billing/checkout`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tier: "premium",
          billing_period: billingPeriod,
          start_trial: true,
        }),
      });
      const body = await res.json().catch(() => ({} as { url?: string; detail?: string }));
      if (res.ok && body.url) {
        rememberHandoff();
        window.location.href = body.url;
        return;
      }
      if (res.status === 401) {
        handle401(res.status);
        return;
      }
      setErr(
        typeof body.detail === "string" && body.detail
          ? body.detail
          : `We couldn't open Stripe (${res.status}). Nothing was charged. Email support@tapeline.io and we'll sort it out.`,
      );
    } catch (e: unknown) {
      setErr(
        errorMessage(e) ||
          "We couldn't reach Stripe. Nothing was charged — please try again.",
      );
    } finally {
      setBusy(false);
    }
  }, [billingPeriod, user?.tier]);

  // Session verdict unknown, or we're on our way out. Render nothing rather
  // than flash a paywall at someone who may not owe us a card at all — the
  // layout is already showing a neutral frame in both cases.
  if (loading || !gated) return null;

  const chargeDate = longDate(firstCharge);
  const amount =
    billingPeriod === "annual"
      ? `${usdCompact(PRICING.premium.annual)} for the year`
      : `${usd(PRICING.premium.monthly)} for the month`;

  return (
    <main id="main" tabIndex={-1} className="mx-auto w-full max-w-2xl px-4 py-10 sm:px-6 sm:py-14">
      {/* Returning from Stripe, possibly ahead of the webhook. States only
          what is true in BOTH cases — completed and backed-out — so the wall
          below stays usable and nobody is left waiting on a screen that has
          assumed something about them. */}
      {awaitingStripe && (
        <div
          data-testid="card-gate-confirming"
          role="status"
          aria-live="polite"
          className="mb-6 rounded-lg border border-border bg-panel p-4 text-sm text-muted"
        >
          Just come back from Stripe? A completed checkout can take a few
          seconds to reach us, and this page clears itself the moment it does.
          Nothing was charged today either way.{" "}
          <button
            type="button"
            onClick={() => void refresh()}
            className={`rounded text-fg underline underline-offset-2 hover:text-accent ${FOCUS}`}
          >
            Check again
          </button>
        </div>
      )}

      {/* Step 2 of the sign-up, named as such. /signup now says a card step is
          coming; this is that step, so the visitor arrives at something they
          were told about. */}
      <ol
        aria-label="Sign-up steps"
        className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-muted"
      >
        <li>1. Your details</li>
        <li aria-hidden="true">&rarr;</li>
        <li aria-current="step" className="font-semibold text-fg">
          2. Card
        </li>
      </ol>

      {/* LEADS WITH THE TRIAL, NOT THE COST — and the card is still in the very
          next sentence, not a screen later.

          The old h1 was "Add a card to open Tapeline", which named the price of
          entry and never the thing being bought. That is honest but it is not
          the whole truth: what the card starts is {TRIAL_DAYS} days of Premium
          for $0. Stating the ask first and the offer second understates our own
          product to the one person who has already said yes to everything else.

          This is NOT a licence to soften the card. Rule 1 at the top of this
          file still stands: the full terms are real body text above the button,
          the exact first-charge date and amount are below, and "no credit card"
          never appears anywhere near the trial. */}
      <h1 className="mt-4 text-3xl font-bold tracking-tight">
        Start your {TRIAL_DAYS}-day Premium trial
      </h1>
      <p className="mt-3 text-sm leading-relaxed text-muted">
        It takes a card and charges <strong className="text-fg">$0 today</strong>
        {" "}&mdash; the card is what opens the app, and the trial becomes a paid
        subscription if you keep it. Here is exactly what that means, before you
        enter anything.
      </p>

      {/* Billing period. Nothing is pre-ticked beyond the site-wide default,
          and switching it rewrites the amount in the disclosure below. */}
      <div className="mt-7">
        <div id="gate-period-label" className="text-[11px] uppercase tracking-wider text-muted">
          Plan after the trial
        </div>
        <div
          role="group"
          aria-labelledby="gate-period-label"
          className="mt-2 inline-flex rounded-full border border-border bg-surface p-1"
        >
          {(["annual", "monthly"] as const).map((p) => (
            <button
              key={p}
              type="button"
              aria-pressed={billingPeriod === p}
              onClick={() => setBillingPeriod(p)}
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
      <ul data-testid="card-gate-terms" className="mt-6 space-y-2.5 text-sm text-fg">
        <li className="flex gap-2">
          <span aria-hidden="true" className="text-muted">·</span>
          <span>
            <strong className="font-semibold">$0 today.</strong> Adding the card
            charges you nothing now.
          </span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden="true" className="text-muted">·</span>
          <span>
            <strong className="font-semibold">Your first charge is on {chargeDate}</strong>{" "}
            &mdash; {amount}, and then{" "}
            {billingPeriod === "annual" ? "every year" : "every month"} until you
            cancel.
          </span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden="true" className="text-muted">·</span>
          <span>
            <strong className="font-semibold">Cancel in one click</strong> from
            your billing page any time before {chargeDate} and you are never
            charged.
          </span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden="true" className="text-muted">·</span>
          <span>
            <strong className="font-semibold">We email you three days before</strong>{" "}
            that charge, so it cannot arrive unannounced.
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

      {err && (
        <div
          role="alert"
          className="mt-6 rounded-lg border border-down/40 bg-down/5 p-4 text-sm text-down"
        >
          {err}
        </div>
      )}

      <button
        type="button"
        onClick={() => void startCheckout()}
        disabled={busy}
        data-testid="card-gate-cta"
        className={`mt-7 flex h-11 w-full items-center justify-center rounded-md border border-accent bg-accent/15 px-4 text-sm font-medium text-fg transition-colors hover:bg-accent/25 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto sm:min-w-[18rem] ${FOCUS}`}
      >
        {busy ? "Opening Stripe…" : "Add a card on Stripe"}
      </button>

      {/* THE WAY OUT. Not a footnote and not a dark-pattern "no thanks, I hate
          value" line — two real, free destinations that need no account at
          all, plus the door. */}
      <section
        data-testid="card-gate-exits"
        aria-labelledby="gate-exits-heading"
        className="mt-10 border-t border-border pt-6"
      >
        <h2 id="gate-exits-heading" className="text-sm font-semibold">
          Not ready to hand over a card?
        </h2>
        <p className="mt-1.5 text-sm leading-relaxed text-muted">
          That is a fine answer, and it does not cost you the thing most people
          came for. Two pages stay open to everyone, free, with no account and
          no card:
        </p>
        <ul className="mt-3 space-y-2 text-sm">
          <li>
            <Link
              href={PUBLIC_RECORD_PATH}
              className={`rounded font-medium text-accent underline underline-offset-2 hover:text-fg ${FOCUS}`}
            >
              The public record
            </Link>
            <span className="text-muted">
              {" "}&mdash; every daily top-10 we have published, frozen when it
              printed and checked against SPY. Losing days included.
            </span>
          </li>
          <li>
            <Link
              href={PUBLIC_PICKS_PATH}
              className={`rounded font-medium text-accent underline underline-offset-2 hover:text-fg ${FOCUS}`}
            >
              Today&rsquo;s picks
            </Link>
            <span className="text-muted">
              {" "}&mdash; today&rsquo;s top 10, the same list the morning email carries.
            </span>
          </li>
        </ul>
        <p className="mt-4 text-sm text-muted">
          <button
            type="button"
            onClick={async () => {
              await signout();
              window.location.href = "/";
            }}
            className={`rounded font-medium text-fg underline underline-offset-2 hover:text-accent ${FOCUS}`}
          >
            Sign out
          </button>
          {" "}&mdash; your account stays as it is, and this page is here whenever
          you want it.
        </p>
      </section>

      <p className="mt-8 text-xs leading-relaxed text-subtle">
        Questions before you decide: support@tapeline.io. Our{" "}
        <Link href="/legal/refund" className={`rounded underline underline-offset-2 hover:text-fg ${FOCUS}`}>
          refund policy
        </Link>{" "}
        and{" "}
        <Link href="/legal/terms" className={`rounded underline underline-offset-2 hover:text-fg ${FOCUS}`}>
          terms
        </Link>{" "}
        apply.
      </p>
    </main>
  );
}
