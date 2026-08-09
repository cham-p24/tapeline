/**
 * Landing-PATH capture (lib/utm.ts) — "which page earned the signup".
 *
 * The UTM/gclid/referrer captures answer which CHANNEL brought a visitor.
 * With ~4,750 published SEO URLs that isn't actionable on its own — this
 * capture records WHICH page they first landed on. It must:
 *   - store the PATH ONLY (privacy — query strings can carry search terms or
 *     identifiers; they also explode aggregation cardinality)
 *   - normalise (lowercase, no trailing slash) so one page is one bucket
 *   - be first-touch: the page that pulled them in keeps credit over
 *     /signup, the page they merely converted on
 */
import { beforeEach, describe, expect, it } from "vitest";
import {
  captureLandingPathFromLocation,
  clearStoredLandingPath,
  getStoredLandingPath,
} from "@/lib/utm";

/** jsdom's window.location is read-only — redefine pathname per test. */
function setPathname(value: string): void {
  Object.defineProperty(window, "location", {
    value: { ...window.location, pathname: value, origin: "http://localhost:3000" },
    configurable: true,
    writable: true,
  });
}

describe("captureLandingPathFromLocation", () => {
  beforeEach(() => {
    window.localStorage.clear();
    setPathname("/");
  });

  it("stores the landing pathname", () => {
    setPathname("/glossary/rsi");
    expect(captureLandingPathFromLocation()).toEqual({
      signup_landing_path: "/glossary/rsi",
    });
    // Round-trips through storage the same way the signup page reads it.
    expect(getStoredLandingPath()).toEqual({
      signup_landing_path: "/glossary/rsi",
    });
  });

  it("captures the root path — a legitimate landing page", () => {
    setPathname("/");
    expect(captureLandingPathFromLocation()).toEqual({
      signup_landing_path: "/",
    });
  });

  it("normalises case and trailing slash so one page is one bucket", () => {
    setPathname("/Compare/Finviz/");
    expect(captureLandingPathFromLocation()).toEqual({
      signup_landing_path: "/compare/finviz",
    });
  });

  it("never persists a query string or hash", () => {
    // pathname excludes these by construction; the capture strips them anyway
    // so a full href handed in by a caller can't leak a search term.
    setPathname("/compare/finviz?q=stock%20scanner&utm_source=x#pricing");
    expect(captureLandingPathFromLocation()).toEqual({
      signup_landing_path: "/compare/finviz",
    });
    const raw = window.localStorage.getItem("tapeline_landing_path_v1")!;
    expect(raw).not.toContain("q=");
    expect(raw).not.toContain("utm_source");
    expect(raw).not.toContain("#pricing");
  });

  it("rejects a non-rooted or protocol-relative path", () => {
    setPathname("//evil.example.com/x");
    expect(captureLandingPathFromLocation()).toEqual({});
    expect(getStoredLandingPath()).toEqual({});
    setPathname("glossary/rsi");
    expect(captureLandingPathFromLocation()).toEqual({});
    expect(getStoredLandingPath()).toEqual({});
  });

  it("is first-touch: a later page view does not overwrite the capture", () => {
    setPathname("/glossary/rsi");
    captureLandingPathFromLocation();
    // The visitor browses on, then converts from /signup…
    setPathname("/pricing");
    expect(captureLandingPathFromLocation()).toEqual({
      signup_landing_path: "/glossary/rsi",
    });
    setPathname("/signup");
    expect(captureLandingPathFromLocation()).toEqual({
      signup_landing_path: "/glossary/rsi",
    });
    // …and the glossary page still gets the credit.
    expect(getStoredLandingPath()).toEqual({
      signup_landing_path: "/glossary/rsi",
    });
  });

  it("clearStoredLandingPath resets the capture", () => {
    setPathname("/sectors");
    captureLandingPathFromLocation();
    expect(getStoredLandingPath()).toEqual({ signup_landing_path: "/sectors" });
    clearStoredLandingPath();
    expect(getStoredLandingPath()).toEqual({});
  });
});
