"use client";

/**
 * PostHog product-analytics wiring. Env-gated — if NEXT_PUBLIC_POSTHOG_KEY
 * is empty the SDK is never loaded, no events are sent, and the wrapper is
 * effectively a no-op. Same shape as the Resend / Stripe / FRED env gates
 * elsewhere in the codebase.
 *
 * Why PostHog on top of Vercel Analytics? Vercel's free tier only shows
 * page-level traffic counts. PostHog's free tier (1M events/mo) gives
 * funnel analysis, retention cohorts, and event-level inspection — needed
 * to actually measure the conversion stack we've been building.
 *
 * Setup steps for the operator:
 *   1. Create a PostHog account at https://app.posthog.com (free tier).
 *   2. Grab the Project API Key from Settings → Project → API Keys.
 *   3. Set `NEXT_PUBLIC_POSTHOG_KEY` (and optionally `NEXT_PUBLIC_POSTHOG_HOST`
 *      if you're on EU cloud or self-hosted) in Vercel env vars.
 *   4. Redeploy. The next session will start firing events.
 *
 * Identification: when the UserContext resolves a logged-in user, this
 * component calls `posthog.identify(user.id, traits)`. Anonymous sessions
 * stay under PostHog's auto-generated distinct_id and are merged with the
 * authenticated identity on first identify.
 */

import { useEffect } from "react";
import { useUser } from "@/components/UserContext";

const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY || "";
const POSTHOG_HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com";

/**
 * Initialises PostHog once on mount. Subsequent renders are no-ops thanks
 * to the singleton-style init inside posthog-js (calling .init() twice is
 * safe but emits a console warning we don't want).
 */
export function PostHogProvider({ children }: { children: React.ReactNode }) {
  const { user } = useUser();

  useEffect(() => {
    if (!POSTHOG_KEY) return;
    let cancelled = false;
    (async () => {
      // Lazy import so the bundle stays slim when PostHog isn't configured.
      const { default: posthog } = await import("posthog-js");
      if (cancelled) return;
      if ((posthog as { __loaded?: boolean }).__loaded) return;
      posthog.init(POSTHOG_KEY, {
        api_host: POSTHOG_HOST,
        person_profiles: "identified_only",
        capture_pageview: true,
        capture_pageleave: true,
        // We rely on Vercel Analytics for raw pageviews — PostHog is here
        // for funnel + identified-user behaviour. Disabling autocapture
        // keeps the event volume low enough to stay inside the free tier.
        autocapture: false,
        loaded: (ph) => {
          (ph as { __loaded?: boolean }).__loaded = true;
        },
      });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!POSTHOG_KEY) return;
    if (!user?.id) return;
    let cancelled = false;
    (async () => {
      const { default: posthog } = await import("posthog-js");
      if (cancelled) return;
      // Identify uses the Tapeline user id as the distinct identifier so
      // it joins with the backend events (Stripe webhook, drip sends, etc.)
      // that we may eventually pipe into PostHog too.
      posthog.identify(user.id, {
        email: user.email,
        tier: user.tier,
        is_admin: user.is_admin,
        is_lifetime: user.is_lifetime,
        trial_ends_at: user.trial_ends_at,
        created_at: user.created_at,
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.id, user?.tier, user?.email, user?.is_admin, user?.is_lifetime, user?.trial_ends_at, user?.created_at]);

  return <>{children}</>;
}
