/**
 * Typed wrapper around the global `gtag()` function injected by GA4.
 *
 * Why a helper at all? Three reasons:
 *  1. Type-safe event names — only the events Tapeline actually fires
 *     (sign_up, start_trial, subscribe, etc.) so typos don't silently
 *     drop into the void.
 *  2. SSR-safe — guards against gtag being undefined on the server.
 *  3. One place to add hashed user IDs / consent flags / DebugView toggles
 *     when the time comes.
 *
 * Use from any client component:
 *
 *   import { trackEvent } from "@/lib/gtag";
 *   ...
 *   onSubmit={() => { trackEvent("sign_up", { method: "email" }); ... }}
 *
 * Events fired here flow into GA4 → Reports → Events. To make any of
 * them count toward conversions for ROAS / acquisition reports, flag
 * them in GA4 Admin → Events → toggle "Mark as conversion".
 */

type GtagFn = (
  command: "event" | "config" | "js" | "set" | "consent",
  ...args: unknown[]
) => void;

declare global {
  interface Window {
    gtag?: GtagFn;
    dataLayer?: unknown[];
  }
}

/**
 * Events Tapeline fires. Add to this union as new conversion points
 * are wired up — never call trackEvent with a string literal that
 * isn't in this list (TS will reject it).
 */
export type TapelineEvent =
  // Top of funnel
  | "page_view"
  // Signup funnel
  | "sign_up_started"      // Signup form opened
  | "sign_up"              // Account created — primary lead conversion
  // Trial → paid funnel
  | "start_trial"          // Card captured, trial begins
  | "subscribe"            // First paid charge — primary revenue conversion
  // Engagement signals
  | "view_scorecard"       // Visit /scorecard
  | "view_ticker"          // Visit /t/[symbol]
  | "open_scanner";        // Open /app/scanner

// Production Google Ads conversion tag (Jun-2026 search campaign). Env still
// overrides; mirrors the hardcoded GA4 default in app/layout.tsx. Conversion
// forwarding stays a no-op until the matching *_LABEL below is also set.
const GOOGLE_ADS_ID = process.env.NEXT_PUBLIC_GOOGLE_ADS_ID ?? "AW-18169833652";

/**
 * Per-event Google Ads conversion labels. Each label comes from a Google Ads
 * conversion action (Goals -> Conversions -> New conversion action ->
 * Website). When the Ads ID AND the matching label are set, trackEvent
 * forwards that event to Google Ads as a `conversion` (send_to:
 * AW-XXXX/LABEL) so paid-search ROAS + Smart Bidding optimise on real
 * signups / subscriptions. Any unset label is simply skipped — GA4 still
 * gets the event regardless.
 */
const ADS_CONVERSION_LABEL: Partial<Record<TapelineEvent, string>> = {
  sign_up: process.env.NEXT_PUBLIC_GOOGLE_ADS_SIGNUP_LABEL || "",
  start_trial: process.env.NEXT_PUBLIC_GOOGLE_ADS_TRIAL_LABEL || "",
  subscribe: process.env.NEXT_PUBLIC_GOOGLE_ADS_SUBSCRIBE_LABEL || "",
};

/**
 * Track a typed event. No-op on the server, no-op if GA4 hasn't
 * loaded yet (e.g. ad-blocker, network failure). Never throws — fire
 * and forget.
 */
export function trackEvent(
  event: TapelineEvent,
  params?: Record<string, string | number | boolean>,
): void {
  if (typeof window === "undefined") return;
  if (typeof window.gtag !== "function") return;
  try {
    window.gtag("event", event, params ?? {});
    // Mirror conversion-worthy events to Google Ads (no-op unless an Ads ID +
    // matching label are configured). This is what makes paid-search clicks
    // attributable to real signups/subscriptions in the Ads dashboard.
    const adsLabel = ADS_CONVERSION_LABEL[event];
    if (GOOGLE_ADS_ID && adsLabel) {
      window.gtag("event", "conversion", { send_to: `${GOOGLE_ADS_ID}/${adsLabel}` });
    }
  } catch {
    // Analytics must never break the page.
  }
}
