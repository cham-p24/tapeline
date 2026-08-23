/**
 * Meta click-ID capture (lib/utm.ts) — gap G4.
 *
 * Attribution captured the whole Google click family and nothing from Meta.
 * Two things break without this (docs/PAID_ADS_METRICS_BIBLE.md §7.1):
 *   - Event Match Quality plateaus around 5-6, because the Conversions API
 *     has only a hashed email and a hashed user id to match on.
 *   - The fbclid -> User -> Stripe join cannot exist — and it is the ONLY
 *     honest Meta payer count, since a 14-day trial puts every first charge
 *     outside Meta's 7-day click window by construction.
 *
 * Same contract as the gclid / referrer-host / landing-path captures it
 * clones: first-touch, 30-day TTL, storage-failure-tolerant.
 *
 * `readFbpCookie` is separate on purpose: `_fbp` belongs to Meta's pixel, not
 * to us — we read it at submit and never persist it.
 */
import { beforeEach, describe, expect, it } from "vitest";
import {
  captureFbclidFromLocation,
  clearStoredFbclid,
  getStoredFbclid,
  readFbpCookie,
} from "@/lib/utm";

const KEY = "tapeline_fbclid_v1";

/** jsdom's window.location is read-only — redefine href per test. */
function setHref(value: string): void {
  Object.defineProperty(window, "location", {
    value: { ...window.location, href: value },
    configurable: true,
    writable: true,
  });
}

function setCookie(value: string): void {
  Object.defineProperty(document, "cookie", {
    value,
    configurable: true,
    writable: true,
  });
}

describe("captureFbclidFromLocation", () => {
  beforeEach(() => {
    window.localStorage.clear();
    setHref("http://localhost:3000/");
  });

  it("stores the fbclid from a Meta click", () => {
    setHref("http://localhost:3000/?fbclid=IwAR0-TeSt-FbCliD");
    expect(captureFbclidFromLocation()).toEqual({ fbclid: "IwAR0-TeSt-FbCliD" });
    // Round-trips through storage the way the signup page reads it back.
    expect(getStoredFbclid()).toEqual({ fbclid: "IwAR0-TeSt-FbCliD" });
  });

  it("stores the RAW click id, never the fb.1.<ts>.<id> wire format", () => {
    // The wire value is built server-side (meta_capi.fbc_value) so exactly
    // one place owns the format — including for events fired days later from
    // a Stripe webhook, where no browser exists to have built it.
    setHref("http://localhost:3000/?fbclid=abc123");
    expect(captureFbclidFromLocation().fbclid).toBe("abc123");
    expect(window.localStorage.getItem(KEY)).not.toContain("fb.1.");
  });

  it("captures nothing on organic traffic", () => {
    setHref("http://localhost:3000/scorecard");
    expect(captureFbclidFromLocation()).toEqual({});
    expect(getStoredFbclid()).toEqual({});
    expect(window.localStorage.getItem(KEY)).toBeNull();
  });

  it("is first-touch: a later visit does not overwrite the paid click", () => {
    setHref("http://localhost:3000/?fbclid=FIRST");
    captureFbclidFromLocation();
    // The visitor comes back directly the next day, then via a second ad…
    setHref("http://localhost:3000/pricing");
    expect(captureFbclidFromLocation()).toEqual({ fbclid: "FIRST" });
    setHref("http://localhost:3000/?fbclid=SECOND");
    expect(captureFbclidFromLocation()).toEqual({ fbclid: "FIRST" });
    // …and the click that actually brought them keeps the credit.
    expect(getStoredFbclid()).toEqual({ fbclid: "FIRST" });
  });

  it("truncates to the backing column width (200 chars)", () => {
    setHref(`http://localhost:3000/?fbclid=${"z".repeat(500)}`);
    expect(captureFbclidFromLocation().fbclid).toHaveLength(200);
  });

  it("drops an expired capture rather than crediting a 31-day-old click", () => {
    window.localStorage.setItem(
      KEY,
      JSON.stringify({
        fbclid: "STALE",
        captured_at: Date.now() - 31 * 24 * 60 * 60 * 1000,
      }),
    );
    expect(getStoredFbclid()).toEqual({});
    // …and it is cleared, so it can't resurface on a later read.
    expect(window.localStorage.getItem(KEY)).toBeNull();
  });

  it("survives a malformed stored value", () => {
    window.localStorage.setItem(KEY, "{not json");
    expect(getStoredFbclid()).toEqual({});
  });

  it("clearStoredFbclid resets the capture", () => {
    setHref("http://localhost:3000/?fbclid=abc");
    captureFbclidFromLocation();
    expect(getStoredFbclid()).toEqual({ fbclid: "abc" });
    clearStoredFbclid();
    expect(getStoredFbclid()).toEqual({});
  });
});

describe("readFbpCookie", () => {
  it("reads Meta's _fbp cookie when the pixel has written one", () => {
    setCookie("foo=bar; _fbp=fb.1.1755900000000.987654321; other=1");
    expect(readFbpCookie()).toBe("fb.1.1755900000000.987654321");
  });

  it("returns empty when the pixel never ran or was blocked", () => {
    // Common in this audience — ad-blocker usage runs well above web
    // average, and the event has to degrade silently rather than break.
    setCookie("foo=bar");
    expect(readFbpCookie()).toBe("");
    setCookie("");
    expect(readFbpCookie()).toBe("");
  });

  it("does not match a cookie that merely ends in _fbp", () => {
    setCookie("not_fbp=nope");
    expect(readFbpCookie()).toBe("");
  });
});
