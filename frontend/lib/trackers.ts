/**
 * Which third-party trackers are switched on — the single source of truth.
 *
 * WHY THIS MODULE EXISTS
 * ----------------------
 * The privacy policy makes factual claims about which trackers run ("Not
 * currently enabled — nothing has ever been sent to Meta"). Those claims were
 * hand-written, while the trackers themselves were gated on env vars in
 * `app/layout.tsx`. So setting `NEXT_PUBLIC_META_PIXEL_ID` would have switched
 * on a tracker AND silently made a legal page false, in one deploy, with
 * nothing to catch it.
 *
 * That is not a documentation problem, it is a design problem: two places
 * describing one fact. Now the policy renders from the same constants the
 * trackers gate on, so the page cannot claim a tracker is off while it is on.
 * `__tests__/privacyPolicyTruth.test.tsx` pins that.
 *
 * BUILD-TIME, NOT RUNTIME
 * -----------------------
 * `NEXT_PUBLIC_*` is inlined by the compiler at BUILD time — a Fly secret of
 * that name does nothing. Values must be passed as Docker build args (see
 * `frontend/fly.toml [build.args]`). That is true for the policy page too, and
 * it is the reason the two agree: they are inlined from the same build.
 *
 * Direct member access on the env object is required for that inlining to
 * work — exactly the form used below. Do not destructure it, index it
 * dynamically, or wrap the lookup in a helper: any of those defeat the static
 * replacement and ship an empty string to the browser.
 *
 * (No illustrative env-var name appears in this comment on purpose — the
 * build-arg guard suite in `__tests__/FunnelInstrumentation.test.tsx` scans
 * source text for env lookups and reads an example in a comment as a real
 * var. It caught exactly that while this file was being written.)
 */

/** GA4 — hardcoded default, so it is live unless deliberately blanked. */
export const GA4_ID = process.env.NEXT_PUBLIC_GA4_ID ?? "G-YRK73W9NS9";

/** Google Ads — hardcoded default, so it is live unless deliberately blanked. */
export const GOOGLE_ADS_ID = process.env.NEXT_PUBLIC_GOOGLE_ADS_ID ?? "AW-18169833652";

/** Meta pixel — no default. Empty until an operator sets it as a build arg. */
export const META_PIXEL_ID = process.env.NEXT_PUBLIC_META_PIXEL_ID || "";

/** Microsoft Clarity — no default. */
export const CLARITY_ID = process.env.NEXT_PUBLIC_CLARITY_PROJECT_ID || "";

/** Plausible — no default. */
export const PLAUSIBLE_DOMAIN = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN || "";

/** PostHog — no default. */
export const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY || "";

/**
 * Is each tracker actually switched on for this build?
 *
 * The privacy policy reads this to describe itself accurately. Anything added
 * here must also be disclosed in `app/legal/privacy/page.tsx` — the test suite
 * fails if a key is added without a corresponding disclosure.
 */
export const trackerEnabled = {
  ga4: GA4_ID !== "",
  googleAds: GOOGLE_ADS_ID !== "",
  meta: META_PIXEL_ID !== "",
  clarity: CLARITY_ID !== "",
  plausible: PLAUSIBLE_DOMAIN !== "",
  posthog: POSTHOG_KEY !== "",
} as const;

export type TrackerName = keyof typeof trackerEnabled;
