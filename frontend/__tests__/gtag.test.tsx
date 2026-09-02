/**
 * Guards the paid-search conversion pipeline (lib/gtag.ts).
 *
 * trackEvent() must mirror conversion-worthy events (sign_up / start_trial /
 * subscribe) to Google Ads as `gtag('event','conversion',{send_to})` — but
 * ONLY when the Ads id AND the matching per-event label env are set, and
 * never for other events. If this silently breaks, ad spend keeps running
 * with no conversion signal (Smart Bidding goes blind), so it's worth a guard.
 *
 * The Ads id + labels are captured at module load from
 * process.env.NEXT_PUBLIC_*, so each case stubs env, resets the module
 * registry, and re-imports a fresh copy of the module.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

type GtagSpy = ReturnType<typeof vi.fn>;

function installGtag(): GtagSpy {
  const spy = vi.fn();
  (window as unknown as { gtag?: GtagSpy }).gtag = spy;
  return spy;
}

describe("trackEvent → Google Ads conversion forwarding", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    delete (window as unknown as { gtag?: GtagSpy }).gtag;
  });

  it("forwards sign_up to Google Ads as a conversion when id + label are set", async () => {
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_ID", "AW-123456789");
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_SIGNUP_LABEL", "abcLABEL");
    const gtag = installGtag();
    const { trackEvent } = await import("@/lib/gtag");

    trackEvent("sign_up", { method: "email" });

    // GA4 event still fires …
    expect(gtag).toHaveBeenCalledWith("event", "sign_up", { method: "email" });
    // … plus the Google Ads conversion, joined as AW-XXXX/LABEL.
    expect(gtag).toHaveBeenCalledWith("event", "conversion", {
      send_to: "AW-123456789/abcLABEL",
    });
  });

  it("forwards sign_up using the hardcoded production default label when the label env is unset", async () => {
    // Pin the id deterministically; intentionally do NOT stub the label env so
    // the hardcoded default in lib/gtag.ts is exercised. This guards the live
    // Google Ads "Sign-up" conversion label — a typo there = signups silently
    // stop counting as conversions and Smart Bidding goes blind.
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_ID", "AW-18169833652");
    const gtag = installGtag();
    const { trackEvent } = await import("@/lib/gtag");

    trackEvent("sign_up", { method: "email" });

    expect(gtag).toHaveBeenCalledWith("event", "conversion", {
      send_to: "AW-18169833652/PLnpCJvM8LgcELTRhthD",
    });
  });

  it("forwards subscribe with value + currency when the caller supplies them", async () => {
    // subscribe carries a revenue value (the tier's first-charge price). The
    // Ads "Subscribe" action is set to "use different values", so the snippet
    // must include value + currency for value-based / ROAS bidding.
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_ID", "AW-123456789");
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_SUBSCRIBE_LABEL", "subLABEL");
    const gtag = installGtag();
    const { trackEvent } = await import("@/lib/gtag");

    trackEvent("subscribe", {
      tier: "pro",
      billing_period: "annual",
      value: 99,
      currency: "USD",
    });

    expect(gtag).toHaveBeenCalledWith("event", "conversion", {
      send_to: "AW-123456789/subLABEL",
      value: 99,
      currency: "USD",
    });
  });

  it("forwards subscribe using the hardcoded production default label", async () => {
    // Pin the id; do NOT stub the label so the hardcoded default is exercised.
    // Guards the live "Subscribe" revenue conversion label — a typo there =
    // paying customers stop counting and value-based bidding goes blind.
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_ID", "AW-18169833652");
    const gtag = installGtag();
    const { trackEvent } = await import("@/lib/gtag");

    trackEvent("subscribe", {
      tier: "premium",
      billing_period: "monthly",
      value: 19.99,
      currency: "USD",
    });

    expect(gtag).toHaveBeenCalledWith("event", "conversion", {
      send_to: "AW-18169833652/1GH_CIT50rkcELTRhthD",
      value: 19.99,
      currency: "USD",
    });
  });

  it("fires NO Ads conversion when the Ads id is unset (GA4 event still fires)", async () => {
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_ID", "");
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_SIGNUP_LABEL", "");
    const gtag = installGtag();
    const { trackEvent } = await import("@/lib/gtag");

    trackEvent("sign_up");

    expect(gtag).toHaveBeenCalledWith("event", "sign_up", {});
    expect(gtag).not.toHaveBeenCalledWith("event", "conversion", expect.anything());
  });

  it("fires NO Ads conversion for a non-conversion event even with id set", async () => {
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_ID", "AW-123456789");
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_SIGNUP_LABEL", "abcLABEL");
    const gtag = installGtag();
    const { trackEvent } = await import("@/lib/gtag");

    trackEvent("view_ticker", { symbol: "AAPL" });

    expect(gtag).toHaveBeenCalledWith("event", "view_ticker", { symbol: "AAPL" });
    expect(gtag).not.toHaveBeenCalledWith("event", "conversion", expect.anything());
  });

  it("never throws when gtag has not loaded (ad blocker / SSR)", async () => {
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_ID", "AW-123456789");
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_SIGNUP_LABEL", "abcLABEL");
    // intentionally do NOT install window.gtag
    const { trackEvent } = await import("@/lib/gtag");

    expect(() => trackEvent("sign_up")).not.toThrow();
  });
});


/**
 * The once-per-browser flag must follow a REAL dispatch.
 *
 * `trackEventOnce` writes a localStorage flag so an activation event is
 * counted once per browser. It took `trackEvent`'s return value as proof the
 * event had been sent — but `trackEvent` returns true when it merely QUEUES
 * the event because gtag has not loaded yet, which is the normal case for an
 * event fired from a mount effect (both scripts in app/layout.tsx are
 * `afterInteractive`).
 *
 * If gtag then never arrives, `scheduleFlush` drops the backlog while the
 * flag is already written, and the event can never fire on that browser
 * again. Caught in a real browser: `/app/scanner` left
 * `tapeline_scanner_first_use = "1"` in localStorage with no
 * `scanner_first_use` anywhere in `dataLayer`.
 */
describe("trackEventOnce — the flag must not outrun the dispatch", () => {
  const KEY = "tapeline_test_once_key";

  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.useFakeTimers();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    window.localStorage.clear();
    delete (window as unknown as { gtag?: GtagSpy }).gtag;
  });

  it("sets the flag immediately when gtag is already present", async () => {
    const gtag = installGtag();
    const { trackEventOnce } = await import("@/lib/gtag");

    expect(trackEventOnce(KEY, "scanner_first_use")).toBe(true);

    expect(gtag).toHaveBeenCalledWith("event", "scanner_first_use", {});
    expect(window.localStorage.getItem(KEY)).toBe("1");
  });

  it("does NOT set the flag while the event is only queued", async () => {
    delete (window as unknown as { gtag?: GtagSpy }).gtag;
    const { trackEventOnce } = await import("@/lib/gtag");

    trackEventOnce(KEY, "scanner_first_use");

    expect(window.localStorage.getItem(KEY)).toBeNull();
  });

  it("sets the flag once the queued event actually reaches gtag", async () => {
    delete (window as unknown as { gtag?: GtagSpy }).gtag;
    const { trackEventOnce } = await import("@/lib/gtag");

    trackEventOnce(KEY, "scanner_first_use");
    expect(window.localStorage.getItem(KEY)).toBeNull();

    const gtag = installGtag();
    await vi.advanceTimersByTimeAsync(1000);

    expect(gtag).toHaveBeenCalledWith("event", "scanner_first_use", {});
    expect(window.localStorage.getItem(KEY)).toBe("1");
  });

  it("leaves the flag UNSET when gtag never arrives, so the next visit retries", async () => {
    delete (window as unknown as { gtag?: GtagSpy }).gtag;
    const { trackEventOnce } = await import("@/lib/gtag");

    trackEventOnce(KEY, "scanner_first_use");
    // Past the whole flush window (40 x 250ms), after which the backlog is
    // dropped. This is the permanent-suppression case.
    await vi.advanceTimersByTimeAsync(20_000);

    expect(window.localStorage.getItem(KEY)).toBeNull();

    // ...and a later visit, with gtag present, still counts the activation.
    const gtag = installGtag();
    expect(trackEventOnce(KEY, "scanner_first_use")).toBe(true);
    expect(gtag).toHaveBeenCalledWith("event", "scanner_first_use", {});
    expect(window.localStorage.getItem(KEY)).toBe("1");
  });

  it("still refuses a second fire once the flag is genuinely set", async () => {
    const gtag = installGtag();
    const { trackEventOnce } = await import("@/lib/gtag");

    trackEventOnce(KEY, "scanner_first_use");
    gtag.mockClear();

    expect(trackEventOnce(KEY, "scanner_first_use")).toBe(false);
    expect(gtag).not.toHaveBeenCalled();
  });
});
