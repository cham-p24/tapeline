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
  } catch {
    // Analytics must never break the page.
  }
}
