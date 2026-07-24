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
  | "begin_checkout"       // Upgrade clicked — Stripe Checkout about to open
  | "subscribe"            // First paid charge — primary revenue conversion
  // Engagement signals
  | "view_scorecard"       // Visit /scorecard
  | "view_ticker"          // Visit /t/[symbol]
  | "open_scanner"         // Open /app/scanner
  // Activation signals — GA4-only (deliberately absent from
  // ADS_CONVERSION_LABEL below so they do NOT forward to the Google Ads
  // "Sign-up" conversion and pollute paid ROAS).
  | "newsletter_signup"    // Email opt-in to the daily digest (NOT an account signup)
  | "first_ticker_added"   // First watchlist add of the session
  // Free→paid micro-funnel — GA4-only (never forwarded to Google Ads; these are
  // on-site conversion diagnostics, not acquisition conversions). Closes the
  // chain cap_hit → upgrade_prompt_shown → upgrade_prompt_clicked →
  // begin_checkout (begin_checkout already exists above). The DURABLE signal is
  // the server-side cap_events table; these client events add the on-screen half
  // (prompt seen / clicked) that the backend can't observe. See lib docs +
  // backend/app/services/cap_events.py.
  | "cap_hit"              // A free user was refused MORE of a metered cap (client-observed)
  | "gate_encountered"     // A free user met a tier feature gate (the Paywall lock rendered)
  | "upgrade_prompt_shown" // An upgrade prompt/paywall actually became visible
  | "upgrade_prompt_clicked"; // The upgrade CTA on that prompt was clicked

// Production Google Ads conversion tag (Jun-2026 search campaign). Env still
// overrides; mirrors the hardcoded GA4 default in app/layout.tsx. The sign_up
// and subscribe conversion labels are now live (see ADS_CONVERSION_LABEL
// below), so signups + paid subscriptions forward as conversions; only
// start_trial forwarding stays a no-op (deliberately — see note below).
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
  // sign_up label is LIVE: the "Sign-up" conversion action (Manual event,
  // Primary, count=One) created in Google Ads account 271-638-2397 on
  // 2026-06-05. The label is not a secret — it ships in client-side JS by
  // design (it's only meaningful paired with the public AW-ID). Hardcoded as
  // the default, mirroring GOOGLE_ADS_ID above, so signups count as
  // conversions from signup #1 with no Vercel env var required. Env still
  // overrides if ever needed.
  sign_up: process.env.NEXT_PUBLIC_GOOGLE_ADS_SIGNUP_LABEL || "PLnpCJvM8LgcELTRhthD",
  // subscribe label is LIVE: the "Subscribe" conversion action (Manual event,
  // Primary, count=One, value="use different values" so it reads the per-tier
  // first-charge price the checkout-success page passes) created in Google Ads
  // account 271-638-2397 on 2026-06-06. Hardcoded default, like sign_up above.
  subscribe: process.env.NEXT_PUBLIC_GOOGLE_ADS_SUBSCRIBE_LABEL || "1GH_CIT50rkcELTRhthD",
  // start_trial is intentionally left unset: the 14-day trial auto-starts at
  // signup, so trackEvent("start_trial") fires at the SAME instant as
  // trackEvent("sign_up"). A separate Ads conversion would double-count the
  // same click. GA4 still gets the start_trial event for funnel analysis.
  start_trial: process.env.NEXT_PUBLIC_GOOGLE_ADS_TRIAL_LABEL || "",
  // begin_checkout has NO hardcoded default: unlike sign_up / subscribe, no
  // Google Ads conversion action exists for it yet. Create one (Goals ->
  // Conversions -> New conversion action -> Website -> Manual event,
  // SECONDARY so it doesn't compete with Subscribe for Smart Bidding) and set
  // NEXT_PUBLIC_GOOGLE_ADS_BEGIN_CHECKOUT_LABEL to its label. Until then the
  // label is empty and only GA4 receives the event — which is already the
  // whole point: begin_checkout is the missing middle of the funnel.
  begin_checkout: process.env.NEXT_PUBLIC_GOOGLE_ADS_BEGIN_CHECKOUT_LABEL || "",
};

type EventParams = Record<string, string | number | boolean>;

/**
 * Events fired before gtag.js finished loading. The loader is
 * `strategy="afterInteractive"`, so any event dispatched during hydration
 * (an OAuth `sign_up` on the onboarding page, a `view_ticker` on mount) used
 * to hit `typeof window.gtag !== "function"` and be silently dropped —
 * permanently losing the conversion. We now park them here and flush once
 * gtag appears.
 */
const pending: Array<[TapelineEvent, EventParams]> = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let flushAttempts = 0;
// ~10s of polling (40 × 250ms). Longer than any realistic gtag.js load, short
// enough that we stop burning timers on ad-blocked sessions where gtag will
// never arrive.
const MAX_FLUSH_ATTEMPTS = 40;
const FLUSH_INTERVAL_MS = 250;

function scheduleFlush(): void {
  if (flushTimer !== null) return;
  if (flushAttempts >= MAX_FLUSH_ATTEMPTS) {
    // gtag is never coming (ad blocker, blocked network). Drop the backlog so
    // it can't grow unbounded on a long-lived SPA session.
    pending.length = 0;
    return;
  }
  flushTimer = setTimeout(() => {
    flushTimer = null;
    flushAttempts += 1;
    if (typeof window !== "undefined" && typeof window.gtag === "function") {
      flushAttempts = 0;
      const queued = pending.splice(0, pending.length);
      for (const [event, params] of queued) dispatch(event, params);
      return;
    }
    if (pending.length > 0) scheduleFlush();
  }, FLUSH_INTERVAL_MS);
}

/** Actually hand an event to gtag. Caller guarantees gtag is a function. */
function dispatch(event: TapelineEvent, params: EventParams): void {
  try {
    window.gtag!("event", event, params);
    // Mirror conversion-worthy events to Google Ads (no-op unless an Ads ID +
    // matching label are configured). This is what makes paid-search clicks
    // attributable to real signups/subscriptions in the Ads dashboard.
    const adsLabel = ADS_CONVERSION_LABEL[event];
    if (GOOGLE_ADS_ID && adsLabel) {
      const conversion: Record<string, unknown> = {
        send_to: `${GOOGLE_ADS_ID}/${adsLabel}`,
      };
      // Pass a revenue value when the caller provides one (subscribe sends the
      // tier's first-charge price + currency). The matching Ads conversion
      // action must be set to "use different values" to read it. Value-less
      // conversions (sign_up, set to a fixed value in Ads) just omit these.
      if (typeof params?.value === "number") {
        conversion.value = params.value;
        if (typeof params.currency === "string") conversion.currency = params.currency;
      }
      // Forward the order id so Google Ads can drop server-side duplicates too
      // — belt and braces alongside the client-side one-shot guard in
      // trackEventOnce(). Ads dedupes conversions sharing a transaction_id.
      if (typeof params?.transaction_id === "string" && params.transaction_id) {
        conversion.transaction_id = params.transaction_id;
      }
      window.gtag!("event", "conversion", conversion);
    }
  } catch {
    // Analytics must never break the page.
  }
}

/**
 * Track a typed event. No-op on the server. If GA4 hasn't loaded yet the
 * event is QUEUED and flushed when gtag appears (see `pending` above) rather
 * than dropped — that silent drop used to lose OAuth signup conversions to a
 * script-load race. Never throws — fire and forget.
 *
 * Returns true when the event was handed to gtag or accepted into the queue,
 * false only when there is no browser to track in (SSR). Callers that persist
 * a "already fired" flag must key it off this return value, never fire it
 * blind before the call.
 */
export function trackEvent(
  event: TapelineEvent,
  params?: EventParams,
): boolean {
  if (typeof window === "undefined") return false;
  if (typeof window.gtag !== "function") {
    pending.push([event, params ?? {}]);
    scheduleFlush();
    return true;
  }
  dispatch(event, params ?? {});
  return true;
}

/**
 * Fire an event at most once per browser, keyed on `storageKey`.
 *
 * Order matters and is the whole point of this helper: the event is
 * dispatched FIRST, and the localStorage flag is written only after a
 * confirmed dispatch. Writing the flag first (the old pattern) meant a failed
 * or dropped dispatch permanently suppressed the event on that browser.
 *
 * Returns true if the event fired on this call, false if it was already
 * marked as fired (or the dispatch was refused, i.e. SSR).
 */
export function trackEventOnce(
  storageKey: string,
  event: TapelineEvent,
  params?: EventParams,
): boolean {
  if (typeof window === "undefined") return false;
  try {
    if (window.localStorage.getItem(storageKey) === "1") return false;
  } catch {
    // Storage unavailable (private mode / quota). Fall through and fire — an
    // occasional duplicate beats never counting the conversion at all.
  }
  const fired = trackEvent(event, params);
  if (!fired) return false;
  try {
    window.localStorage.setItem(storageKey, "1");
  } catch {
    // Storage unavailable — the event already fired, which is what matters.
  }
  return true;
}

/**
 * Dedupe key for the once-per-browser `first_ticker_added` activation event.
 * Exported so tests (and any future add surface) reference the same string —
 * a second key would double-count activation.
 */
export const FIRST_TICKER_ADDED_KEY = "tapeline_first_ticker_added";

/**
 * Activation signal: the user's first watchlist add, from ANY surface.
 *
 * Call this after a watchlist add succeeds on the scanner rows, the watchlist
 * page's own add box, and the ticker page's Add button. It used to live
 * inline in the scanner only, so adds from the other two surfaces never
 * counted and activation rate read low.
 *
 * @param surface which add path fired it — lets GA4 show WHERE activation happens.
 * @returns true if this was the first add on this browser (event fired).
 */
export function trackFirstTickerAdded(
  symbol: string,
  surface: "scanner" | "watchlist" | "ticker",
): boolean {
  return trackEventOnce(FIRST_TICKER_ADDED_KEY, "first_ticker_added", {
    symbol,
    surface,
  });
}

/**
 * The five metered free-tier caps. Mirrors backend CAP_NAMES
 * (backend/app/models/cap_events.py) so the client half of the funnel keys off
 * exactly the same vocabulary the durable server-side table records.
 */
export type CapName =
  | "scanner_rows"
  | "daily_lookups"
  | "watchlist_tickers"
  | "web_push_alerts"
  | "squeeze_preview";

/** Where in the app the funnel event fired — for GA4 segmentation. */
export type FunnelSurface =
  | "scanner"
  | "watchlist"
  | "ticker"
  | "squeeze"
  | "paywall";

/**
 * A free user was refused MORE of a metered cap and the client observed it (a
 * 402/403 limit response, or a server-reported capped view). The DURABLE record
 * is written server-side by cap_events.record_cap_hit; this is the client mirror
 * that opens the on-site funnel. Fire-and-forget.
 */
export function trackCapHit(cap: CapName, surface: FunnelSurface): boolean {
  return trackEvent("cap_hit", { cap, surface });
}

/**
 * A free user met a binary tier FEATURE gate (the Paywall lock rendered),
 * distinct from a count-cap `cap_hit`. Fired from the shared Paywall components.
 */
export function trackGateEncountered(
  feature: string,
  surface: FunnelSurface,
): boolean {
  return trackEvent("gate_encountered", { feature, surface });
}

/**
 * An upgrade prompt/paywall actually became visible. Fired on mount/open of the
 * shared Paywall components so every surface that renders one is counted the
 * same way — the middle of the free→paid funnel.
 */
export function trackUpgradePromptShown(
  surface: FunnelSurface,
  feature?: string,
): boolean {
  return trackEvent("upgrade_prompt_shown", feature ? { surface, feature } : { surface });
}

/**
 * The upgrade CTA on a visible prompt was clicked — the last step before
 * begin_checkout. Fired from the shared Paywall components' CTA handlers.
 */
export function trackUpgradePromptClicked(
  surface: FunnelSurface,
  feature?: string,
): boolean {
  return trackEvent(
    "upgrade_prompt_clicked",
    feature ? { surface, feature } : { surface },
  );
}
