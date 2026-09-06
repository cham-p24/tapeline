/**
 * The Premium trial offer, on the scanner, above the table.
 *
 * WHY IT IS HERE AND NOT ON A FORK BEFORE THE PRODUCT
 * --------------------------------------------------
 * Until now signup's default post-auth destination was
 * `/app/billing?trial=start`, so the journey was signup → /app/onboarding → a
 * payment decision → and only then a scored row. Every comparable product
 * (Stock Rover, Simply Wall St, Stock Unlock, Koyfin, Danelfin, TradingView)
 * lands a new account in the product first; none interposes a payment decision
 * before the first result. The founder's own data says the same thing: while a
 * card wall briefly stood at /app/start (#548 → #683), three accounts hit it,
 * none added a card, none ran a single scan, and two never opened the payment
 * page.
 *
 * So the default destination is the scanner, and the offer follows the user
 * there. It renders the SAME <TrialOfferPanel> /app/billing renders — same
 * component, same disclosure, same wording — because the offer moved, it did
 * not soften.
 *
 * WHAT MAKES IT A BANNER RATHER THAN A WALL
 * -----------------------------------------
 *   - It is dismissible, and the dismissal is permanent (localStorage). The
 *     offer is still one click away on /app/billing afterwards, and the panel's
 *     own closing line says so.
 *   - It YIELDS to the first-run welcome via the existing FirstRunTip context —
 *     the same mechanism TrialBanner, UpgradeNudge and BreakingNewsBar use. A
 *     brand-new account reads OnboardingTip's "three things to try first"; the
 *     trial offer appears only once that is dismissed. Deliberately no second
 *     banner-coordination system.
 *   - Nothing auto-navigates. The only thing that reaches Stripe is the user
 *     pressing the trial button, exactly as on /app/billing.
 *
 * ELIGIBILITY is deliberately conservative on the client — the authoritative
 * "has this account already had its trial?" gate lives in the backend checkout
 * path (routers/billing.py). This only decides whether to render the offer.
 */
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useUser } from "@/components/UserContext";
import { useFirstRunTip } from "@/components/FirstRunTip";
import { TrialOfferPanel } from "@/components/TrialOfferPanel";
import { DEFAULT_BILLING_PERIOD, PRICING } from "@/lib/pricing";
import { TRIAL_DAYS } from "@/lib/trial";
import { rememberTrialCheckout } from "@/lib/trialCheckout";
import { trackEvent } from "@/lib/gtag";
import { handle401, errorMessage } from "@/lib/api";
import { errorText } from "@/lib/errorText";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const STORAGE_KEY = "tapeline_scanner_trial_offer_dismissed_v1";

export function ScannerTrialOffer() {
  const { user, loading } = useUser();
  const { tipVisible } = useFirstRunTip();
  // Start dismissed so a user who closed it yesterday never sees a flash before
  // the localStorage check resolves. hidden→shown is fine; shown→hidden is the
  // jarring direction. (Same reasoning as UpgradeNudge.)
  const [dismissed, setDismissed] = useState(true);
  const [billingPeriod, setBillingPeriod] = useState<"monthly" | "annual">(DEFAULT_BILLING_PERIOD);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // Computed once per mount so the quoted first-charge date cannot drift
  // mid-session. Mirrors the trial_end the backend sets on the Checkout
  // session (now + TRIAL_DAYS).
  const [firstCharge] = useState(() => new Date(Date.now() + TRIAL_DAYS * 86_400_000));

  useEffect(() => {
    try {
      setDismissed(localStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      // localStorage blocked — fail open and show the offer once.
      setDismissed(false);
    }
  }, []);

  function dismiss() {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore — the panel still closes for this session */
    }
    setDismissed(true);
    trackEvent("trial_offer_dismissed", { surface: "scanner" });
  }

  async function startTrial() {
    setBusy(true);
    setErr(null);
    // Same funnel event /app/billing fires, with the surface named so the two
    // starting points are distinguishable. A click is not a trial — `start_trial`
    // itself fires on the confirmed return to /app/billing.
    trackEvent("begin_checkout", {
      tier: "premium",
      billing_period: billingPeriod,
      current_tier: "free",
      on_trial: false,
      start_trial: true,
      surface: "scanner",
      value: billingPeriod === "annual" ? PRICING.premium.annual : PRICING.premium.monthly,
      currency: "USD",
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
      const body = await res.json();
      if (res.ok && body.url) {
        // The return from Stripe always lands on /app/billing, which reads this
        // record to tell a $0 trial start from a purchase. Written BEFORE we
        // navigate — see lib/trialCheckout.ts for why it is not optional.
        rememberTrialCheckout("premium");
        window.location.href = body.url;
        return;
      }
      if (res.status === 401) {
        handle401(res.status);
        return;
      }
      setErr(errorText(body, `Checkout failed (${res.status})`));
    } catch (e: unknown) {
      setErr(errorMessage(e) || "Checkout failed");
    } finally {
      setBusy(false);
    }
  }

  if (loading || !user) return null;
  // Yield to the first-run welcome. Same contract as the other promo banners.
  if (tipVisible) return null;
  if (dismissed) return null;
  // Free, and has never had a trial. A paid or already-trialled account is not
  // offered something it cannot accept.
  if ((user.tier || "free") !== "free") return null;
  if (user.trial_ends_at) return null;

  return (
    <div className="mt-4">
      <TrialOfferPanel
        billingPeriod={billingPeriod}
        onBillingPeriod={setBillingPeriod}
        firstCharge={firstCharge}
        busy={busy}
        onStartTrial={startTrial}
        // On the scanner the decline is not a journey — the reader is already
        // on the free plan, looking at it. Closing the panel IS continuing on
        // the Free plan, so the control does that rather than linking to the
        // page it is rendered on.
        onDecline={dismiss}
        laterHint={
          <>
            You can start the trial later from your{" "}
            <Link href="/app/billing" className="text-accent hover:underline">
              billing page
            </Link>{" "}
            &mdash; it is there whenever you want it.
          </>
        }
      />
      {err && (
        <p role="status" className="mt-2 text-xs text-down">
          {err}
        </p>
      )}
    </div>
  );
}
