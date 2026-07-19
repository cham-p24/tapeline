/**
 * Regression tests for the ticker-prefix middleware patterns.
 *
 * The bug these exist to prevent: /scorecard/opengraph-image is a SINGLE
 * path segment under a ticker prefix, so TICKER_PREFIX_RE matched it, it
 * failed VALID_TICKER_RE, and middleware 308'd it to /search?q=opengraph-image.
 * Next never got to serve the generated PNG, so every share of /scorecard on
 * X, LinkedIn, Slack and Facebook rendered with no image — on the one page
 * the transparency pitch asks people to go and check.
 *
 * Verified against production before the fix:
 *   /opengraph-image              -> image/png            (fine)
 *   /how-it-works/opengraph-image -> image/png            (fine)
 *   /scorecard/opengraph-image    -> text/html, /search   (broken)
 *
 * These assert the DECISION, not the HTTP plumbing: whether a given path is
 * treated as a ticker to redirect, or falls through to Next.
 */
import { describe, expect, it } from "vitest";

import {
  METADATA_ROUTE_RE,
  TICKER_PREFIX_RE,
  VALID_TICKER_RE,
} from "../middleware";

/**
 * Mirrors handleTickerRoute's branch order. The ORDER matters: ticker shape is
 * tested before the metadata exemption, so a real symbol can never be shadowed
 * by a metadata name that happens to look like one.
 */
function decide(pathname: string): "fall-through" | "search" | "canonicalise" {
  const m = TICKER_PREFIX_RE.exec(pathname);
  if (!m) return "fall-through";
  const [, prefix, raw] = m;
  const upper = raw.toUpperCase();
  if (!VALID_TICKER_RE.test(upper)) {
    return METADATA_ROUTE_RE.test(raw) ? "fall-through" : "search";
  }
  return `/${prefix}/${upper}` === pathname ? "fall-through" : "canonicalise";
}

describe("metadata routes are never treated as tickers", () => {
  // The exact regression.
  it("serves /scorecard/opengraph-image instead of redirecting to search", () => {
    expect(decide("/scorecard/opengraph-image")).toBe("fall-through");
  });

  it.each([
    "/scorecard/opengraph-image",
    "/scorecard/twitter-image",
    "/t/opengraph-image",
    "/blog/ticker/opengraph-image",
    "/scorecard/apple-icon",
  ])("falls through: %s", (path) => {
    expect(decide(path)).toBe("fall-through");
  });

  it("tolerates Next's build-hash suffix", () => {
    expect(decide("/scorecard/opengraph-image-1a2b3c4d")).toBe("fall-through");
  });

  it("is case-insensitive", () => {
    expect(decide("/scorecard/OpenGraph-Image")).toBe("fall-through");
  });

  // Nested metadata routes were fixed earlier by the single-segment capture;
  // pin that too so a future greedy (.+) can't quietly reintroduce it.
  it("still ignores nested per-ticker metadata routes", () => {
    expect(decide("/t/AAPL/opengraph-image")).toBe("fall-through");
  });
});

describe("real ticker behaviour is unchanged", () => {
  it("canonicalises lowercase symbols", () => {
    expect(decide("/t/aapl")).toBe("canonicalise");
    expect(decide("/scorecard/nvda")).toBe("canonicalise");
  });

  it("leaves already-canonical symbols alone", () => {
    expect(decide("/t/AAPL")).toBe("fall-through");
    expect(decide("/scorecard/NVDA")).toBe("fall-through");
  });

  it("still sends non-ticker garbage to search", () => {
    expect(decide("/t/{search_term_string}")).toBe("search");
    expect(decide("/t/foo-bar")).toBe("search");
    expect(decide("/scorecard/some-marketing-slug")).toBe("search");
  });

  // The reason ticker shape is tested FIRST. "ICON" is a metadata route name
  // AND a valid 4-letter symbol; a real listed ICON must keep working, so the
  // exemption must never reach it. Same for its lowercase backlink form.
  it("never lets a metadata name shadow a real ticker", () => {
    expect(decide("/t/ICON")).toBe("fall-through"); // renders as a ticker
    expect(decide("/t/icon")).toBe("canonicalise"); // → /t/ICON, not exempted
    expect(decide("/scorecard/ICON")).toBe("fall-through");
    expect(decide("/t/ICONIC")).toBe("fall-through"); // 6 alpha, valid symbol
  });
});
