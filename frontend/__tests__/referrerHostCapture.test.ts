/**
 * Referrer-host capture (lib/utm.ts) — the "AI signups land as direct" fix.
 *
 * AI-assistant referrals (Copilot/ChatGPT/Perplexity) carry no utm_* params;
 * `document.referrer` is the only attribution trace. The capture must:
 *   - store the HOSTNAME ONLY (privacy — an AI-chat referrer path can carry
 *     the user's prompt text)
 *   - skip our own domain (tapeline.io + subdomains + the page's own host)
 *     and empty referrers (direct traffic)
 *   - be first-touch: never overwrite an earlier stored value
 */
import { beforeEach, describe, expect, it } from "vitest";
import {
  captureReferrerHostFromLocation,
  clearStoredReferrerHost,
  getStoredReferrerHost,
} from "@/lib/utm";

/** jsdom's document.referrer is read-only — redefine it per test. */
function setReferrer(value: string): void {
  Object.defineProperty(document, "referrer", {
    value,
    configurable: true,
  });
}

describe("captureReferrerHostFromLocation", () => {
  beforeEach(() => {
    window.localStorage.clear();
    setReferrer("");
  });

  it("stores the hostname of an external referrer — hostname only, never path/query", () => {
    setReferrer("https://copilot.microsoft.com/chat?q=stock%20scanner%20for%20AAPL");
    const captured = captureReferrerHostFromLocation();
    expect(captured).toEqual({ signup_referrer_host: "copilot.microsoft.com" });
    // Round-trips through storage the same way the signup page reads it.
    expect(getStoredReferrerHost()).toEqual({
      signup_referrer_host: "copilot.microsoft.com",
    });
    // Nothing beyond the hostname may be persisted (no path, no query).
    const raw = window.localStorage.getItem("tapeline_ref_host_v1")!;
    expect(raw).not.toContain("/chat");
    expect(raw).not.toContain("q=");
  });

  it("skips an empty referrer (direct traffic)", () => {
    setReferrer("");
    expect(captureReferrerHostFromLocation()).toEqual({});
    expect(getStoredReferrerHost()).toEqual({});
  });

  it("skips our own domain — internal navigation never claims attribution", () => {
    setReferrer("https://tapeline.io/pricing");
    expect(captureReferrerHostFromLocation()).toEqual({});
    setReferrer("https://www.tapeline.io/");
    expect(captureReferrerHostFromLocation()).toEqual({});
    // The page's own host (jsdom serves from localhost) is "own" too, so
    // dev navigation doesn't pollute attribution either.
    setReferrer(`${window.location.origin}/scorecard`);
    expect(captureReferrerHostFromLocation()).toEqual({});
    expect(getStoredReferrerHost()).toEqual({});
  });

  it("is first-touch: an earlier stored host is not overwritten", () => {
    setReferrer("https://copilot.microsoft.com/some/chat");
    captureReferrerHostFromLocation();
    // Later visit arrives from a different external site…
    setReferrer("https://www.reddit.com/r/stocks/comments/abc");
    const result = captureReferrerHostFromLocation();
    // …but the original host keeps credit.
    expect(result).toEqual({ signup_referrer_host: "copilot.microsoft.com" });
    expect(getStoredReferrerHost()).toEqual({
      signup_referrer_host: "copilot.microsoft.com",
    });
  });

  it("ignores an unparseable referrer without throwing", () => {
    setReferrer("not a url");
    expect(captureReferrerHostFromLocation()).toEqual({});
    expect(getStoredReferrerHost()).toEqual({});
  });

  it("clearStoredReferrerHost resets the capture", () => {
    setReferrer("https://chat.openai.com/");
    captureReferrerHostFromLocation();
    expect(getStoredReferrerHost()).toEqual({
      signup_referrer_host: "chat.openai.com",
    });
    clearStoredReferrerHost();
    expect(getStoredReferrerHost()).toEqual({});
  });
});
