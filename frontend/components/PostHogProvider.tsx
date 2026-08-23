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

import { useEffect, useRef } from "react";
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
        // App Router does client-side navigation, so the legacy `true` would
        // capture one pageview per hard load and nothing for the rest of the
        // session. 'history_change' is the SPA-correct value.
        capture_pageview: "history_change",
        capture_pageleave: true,
        // Autocapture is the entire point of PostHog at this scale: it records
        // clicks we never thought to instrument, which is what you need when
        // you cannot yet predict where people get stuck. The previous `false`
        // cited free-tier volume and referred to Vercel Analytics for raw
        // pageviews — both stale: Vercel analytics was removed in #463, and
        // the free tier is 1M events/month against a handful of sessions.
        autocapture: true,
        session_recording: {
          // Replay masks INPUT values by default but not general text, and
          // /app/api-keys renders a freshly-minted `tl_live_…` key as a text
          // node — a recording would be the only surviving plaintext copy.
          // Anything carrying `ph-mask` is redacted in the replay.
          maskTextSelector: ".ph-mask",
        },
        loaded: (ph) => {
          (ph as { __loaded?: boolean }).__loaded = true;
        },
      });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Tracks the previously-identified user so a sign-out can be detected.
  const lastIdentified = useRef<string | null>(null);

  useEffect(() => {
    if (!POSTHOG_KEY) return;
    let cancelled = false;

    // Sign-out: without an explicit reset, posthog-js keeps the same distinct_id
    // and the NEXT person to use this browser is merged into the previous
    // person's profile. On the founder's own machine that silently welds owner
    // sessions onto real user profiles.
    if (!user?.id) {
      if (!lastIdentified.current) return;
      lastIdentified.current = null;
      (async () => {
        const { default: posthog } = await import("posthog-js");
        if (!cancelled) posthog.reset();
      })();
      return () => {
        cancelled = true;
      };
    }

    const id = user.id;
    (async () => {
      const { default: posthog } = await import("posthog-js");
      if (cancelled) return;
      // The Tapeline user id is the distinct identifier so this joins with
      // backend events (Stripe webhook, drip sends) if those are ever piped in.
      // Deliberately NO email: it is PII crossing to a US processor, and
      // `user.id` is already an opaque `u_<uuid4hex>` that the founder can map
      // back to a person from his own database whenever he actually needs to.
      posthog.identify(id, {
        tier: user.tier,
        is_admin: user.is_admin,
        is_lifetime: user.is_lifetime,
        trial_ends_at: user.trial_ends_at,
        created_at: user.created_at,
      });
      lastIdentified.current = id;
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.id, user?.tier, user?.is_admin, user?.is_lifetime, user?.trial_ends_at, user?.created_at]);

  return <>{children}</>;
}
