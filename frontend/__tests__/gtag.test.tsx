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
