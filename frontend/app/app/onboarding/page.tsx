"use client";

/**
 * Post-signup provisioning hand-off.
 *
 * Every new account passes through this route exactly once on its way into
 * the product: the email path is pushed here by /signup, and the backend
 * redirects brand-new OAuth users here too (routers/oauth.py — `?oauth=1`).
 *
 * It ASKS NOTHING. This route used to be a four-question "Tell us a bit about
 * you" survey standing between signup and the first working screen; the
 * questions were removed 2026-08-19 because the product has to be the first
 * thing a new account sees. Do not add questions back here.
 *
 * What survives is the mechanical work that has to happen once per account:
 *
 *   1. POST /api/me/onboarding. This stamps `onboarding_completed_at` and —
 *      the part that matters — runs the SERVER-side day-1 watchlist seeder
 *      (routers/me.py:_seed_watchlist_for_new_user). That seeder already
 *      handles "no sector was chosen": it falls back to the top-scored live
 *      tickers in the universe, with the same freshness + data-quality floor
 *      the scanner uses, and deliberately leaves a free slot under the tier
 *      cap so the user's own first add — the activation action — never 403s.
 *      So killing the survey does NOT produce a blanker first screen: the
 *      pre-population survives, it just stops being conditional on an answer.
 *   2. The OAuth `sign_up` conversion, which fires nowhere else (OAuth
 *      signups never touch the /signup form). It used to fire PAIRED with
 *      `start_trial`, because account creation auto-granted a 14-day Premium
 *      trial. It no longer does: since 2026-08 the trial is a separate,
 *      card-required opt-in through Stripe Checkout, so `start_trial` moved to
 *      the moment the user actually starts one (app/app/billing/page.tsx).
 *      Firing it here would count a trial that does not exist.
 *   3. Forwarding to `next` — /app/billing with the intent restated when the
 *      visitor arrived from a /pricing plan CTA or from signup (where `next`
 *      carries the trial offer), otherwise the scanner.
 *
 * Consent is never touched here: `marketing_opt_in: null` means "no answer"
 * and the backend leaves the stored value alone, so consent granted on the
 * /signup form (its two unchecked-by-default boxes) survives untouched.
 */

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";
import { handle401 } from "@/lib/api";
import { trackEvent, trackEventOnce } from "@/lib/gtag";
import { useUser } from "@/components/UserContext";
import { safeNext } from "@/lib/safeNext";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// Dedupe key: the OAuth signup conversion must fire at most once per browser.
// New Google users land here at /app/onboarding?oauth=1. The key name is kept
// as-is on purpose — renaming it would re-fire `sign_up` for every browser
// that already converted under the old (signup + start_trial) pair.
const OAUTH_CONVERSION_FIRED_KEY = "tapeline_oauth_conversion_fired";

export default function OnboardingPage() {
  return (
    <Suspense fallback={null}>
      <OnboardingHandoff />
    </Suspense>
  );
}

function OnboardingHandoff() {
  const router = useRouter();
  const qp = useSearchParams();
  // Guard the forward against open-redirect payloads (//evil.com,
  // https://evil.com) carried in from /signup?next=… or the OAuth callback.
  const next = safeNext(qp.get("next"));
  // Already fetched by UserProvider at the root layout, so reading it here
  // costs nothing extra on the signup path — see the provisioning effect.
  const { user, loading } = useUser();

  // OAuth signup conversion. The backend redirects NEW Google/OAuth users to
  // /app/onboarding?oauth=1, but OAuth signups never touch the /signup form
  // where `sign_up` fires — so without this they're invisible to GA4/Ads.
  // Fire it once, deduped per browser (localStorage) with a ref guard for
  // React strict-mode double-mount.
  //
  // The localStorage flag is now written by trackEventOnce AFTER a confirmed
  // dispatch, never before. The old order set the flag first and then called
  // trackEvent, which silently no-opped whenever gtag.js hadn't finished
  // loading — and since gtag loads afterInteractive while this effect runs at
  // mount, that race permanently lost the OAuth signup conversion on this
  // browser. trackEvent also queues-and-retries now, so a slow load delays
  // the event instead of dropping it. That queue is module-scope, so it also
  // survives the route change this page performs a beat later.
  const oauthFiredRef = useRef(false);
  useEffect(() => {
    if (qp.get("oauth") == null) return;
    if (oauthFiredRef.current) return;
    oauthFiredRef.current = true;
    // OAuth account creation === same conversion bucket as an email signup.
    // Creating the account no longer starts a trial (the trial is a separate,
    // card-required opt-in), so this is a single event now — `start_trial`
    // fires from the billing page when a trial is actually started.
    trackEventOnce(OAUTH_CONVERSION_FIRED_KEY, "sign_up", { method: "oauth" });
  }, [qp]);

  // Provision the account, then forward. Runs once per mount (ref guard for
  // React strict-mode double-mount) and never blocks on anything optional.
  const provisionedRef = useRef(false);
  useEffect(() => {
    // Wait for the session fetch so the already-onboarded check below is real.
    // It always resolves — UserProvider clears `loading` in a finally — so
    // this can never strand anyone here. On the email path the fetch has
    // already settled (root layout, resolved while they were on /signup) so
    // the wait costs nothing; on the OAuth path it is a full page load and
    // that fetch would have happened on the next screen anyway.
    if (loading) return;
    if (provisionedRef.current) return;
    provisionedRef.current = true;

    (async () => {
      // Only provision an account that has never been through here. The POST
      // writes trading_style / referral_source / sectors_of_interest from the
      // body, so re-running it for a user who answered the old survey would
      // null their stored profile (and drop the scanner's sector pre-tune).
      if (!user?.onboarding_completed_at) {
        try {
          const res = await fetch(`${API_BASE}/api/me/onboarding`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              // Nothing was asked, so nothing is asserted. null consent =
              // "no answer" — the backend leaves stored consent untouched,
              // which is what protects an opt-in granted on the signup form.
              // The empty sector list is exactly what makes the server-side
              // seeder fall back to the top-scored names across the whole
              // live universe (see the file header).
              trading_style: null,
              referral_source: null,
              marketing_opt_in: null,
              sectors_of_interest: [],
              skipped: true,
            }),
          });
          if (res.status === 401) {
            // Session is gone. handle401 hard-navigates to /signin?next=<here>
            // so they come back and provision after signing in — don't race
            // that with the client-side forward below.
            handle401(res.status);
            return;
          }
          trackEvent("onboarding_submitted", {
            skipped: true,
            sectors: 0,
            // Distinguishes an auto-provision from the old survey's real
            // submit/skip in GA4, so the two aren't read as the same thing.
            auto: true,
          });
        } catch {
          // Fall through and forward anyway. A failed provision costs the
          // starter watchlist, not the product — and nothing in the app gates
          // on onboarding_completed_at — so stranding a brand-new account on
          // a status screen would be strictly worse than losing the seed.
        }
      }
      // replace, not push: this route forwards itself, so leaving it in the
      // history stack would make Back from the scanner bounce straight off it
      // again.
      router.replace(next);
      router.refresh();
    })();
  }, [loading, user, next, router]);

  // Nothing here is interactive — it renders for the length of one POST.
  // Deliberately quiet: a status line, and the one fact worth knowing about
  // what we just did on the user's behalf.
  return (
    <main id="main" className="mx-auto max-w-2xl px-4 py-10 sm:py-14">
      <div role="status" aria-live="polite">
        <h1 className="text-3xl font-bold tracking-tight">
          Setting up your account
        </h1>
        <p className="mt-2 text-sm text-muted">
          We&apos;re starting your watchlist with the top-scored names on the
          live tape. You can remove them anytime.
        </p>
      </div>
    </main>
  );
}
