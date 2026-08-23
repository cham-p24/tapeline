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
  apexRedirectTarget,
  METADATA_ROUTE_RE,
  TICKER_PREFIX_RE,
  tickerRouteDecision,
  VALID_TICKER_RE,
} from "../middleware";

describe("canonical-host consolidation → bare tapeline.io", () => {
  it("308-redirects www.tapeline.io + .app hosts to the same path on bare .io, query preserved", () => {
    // www.io currently serves a 200 duplicate — redirect it to the apex.
    expect(apexRedirectTarget("www.tapeline.io", "/pricing", "")).toBe("https://tapeline.io/pricing");
    expect(apexRedirectTarget("www.tapeline.io", "/t/AAPL", "?ref=hn")).toBe(
      "https://tapeline.io/t/AAPL?ref=hn",
    );
    // Legacy .app domain.
    expect(apexRedirectTarget("tapeline.app", "/pricing", "")).toBe("https://tapeline.io/pricing");
    expect(apexRedirectTarget("www.tapeline.app", "/whats-new", "")).toBe(
      "https://tapeline.io/whats-new",
    );
    expect(apexRedirectTarget("TAPELINE.APP", "/whats-new", "")).toBe(
      "https://tapeline.io/whats-new",
    );
  });

  it("leaves the canonical bare host and everything else alone (no redirect loop)", () => {
    expect(apexRedirectTarget("tapeline.io", "/pricing", "")).toBeNull();
    expect(apexRedirectTarget("localhost:3000", "/", "")).toBeNull();
    expect(apexRedirectTarget("api.tapeline.io", "/x", "")).toBeNull();
    expect(apexRedirectTarget(null, "/x", "")).toBeNull();
  });
});

/**
 * Calls the REAL decision function out of middleware.ts.
 *
 * This used to be a local reimplementation that "mirrors handleTickerRoute's
 * branch order" — it imported the regexes but duplicated the branches. When the
 * real branch order changed (the metadata exemption had to move BEFORE the
 * ticker test, once hyphens became legal ticker characters), the copy kept
 * testing the old shape and reported a failure the real middleware did not
 * have. Never mirror the logic; call it.
 */
function decide(pathname: string): "fall-through" | "search" | "canonicalise" {
  const d = tickerRouteDecision(pathname);
  if (d.kind === "signals-root") return "canonicalise";
  return d.kind;
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
    // Longer than the backend's 12-char symbol limit, so still not a ticker.
    expect(decide("/scorecard/some-marketing-slug")).toBe("search");
    expect(decide("/t/this-is-far-too-long-to-be-a-symbol")).toBe("search");
    // Lowercase letters are not in the symbol class once uppercased? They are —
    // so shape, not content, is what disqualifies. Characters outside the
    // backend class still go to search:
    expect(decide("/t/foo_bar")).toBe("search");
    expect(decide("/t/hello world")).toBe("search");
  });

  it("treats a validly-SHAPED unknown symbol as a ticker, not as garbage", () => {
    // Behaviour change, deliberate. `foo-bar` uppercases to FOO-BAR, which is a
    // legal shape under the backend's VALID_SYMBOL_RE, so the middleware can no
    // longer claim to know it is garbage — only the ticker page can, and it
    // 404s unknown symbols. This already IS the behaviour for any validly
    // shaped unknown symbol; verified in production: /t/ZZZZZZ → 404 (it falls
    // through, it does not redirect to /search).
    //
    // The trade is deliberate: the narrow old regex sent real, servable symbols
    // (BRK-B, CL=F) to a robots-blocked /search. Losing the /search nicety for
    // hyphenated gibberish is worth keeping every real class share and futures
    // contract indexable.
    expect(decide("/t/FOO-BAR")).toBe("fall-through");
    expect(decide("/t/foo-bar")).toBe("canonicalise"); // → /t/FOO-BAR
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

/**
 * The backend's symbol shape is the single source of truth:
 *   VALID_SYMBOL_RE = ^[A-Z][A-Z0-9.=/^-]{0,11}$   (services/symbols.py)
 *
 * It admits class shares and continuous futures. (NOT leading-^ index
 * notation: the first character must be [A-Z], so "^GSPC" fails the BACKEND
 * regex too — the audit finding was wrong about that, and this suite caught it.)
 * ticker_freshness.py says these "must be kept" and backend tests assert BRK-B
 * and CL=F are real, servable symbols. The middleware's own regex was much
 * narrower (^[A-Z]{1,6}(\.[A-Z])?$), so it 308'd those real tickers to /search
 * — which robots.ts Disallows. sitemap.ts and /stocks meanwhile emitted and
 * linked to them, so each URL landed in GSC as "Page with redirect" onto a
 * target "Blocked by robots.txt": permanently unindexable.
 *
 * Verified in production before the fix:
 *   /t/BRK-B → 308 /search?q=BRK-B    while api /api/ticker/BRK-B → 200
 *   /t/CL=F  → 308 /search?q=CL%3DF   while api /api/ticker/CL=F  → 200
 */
describe("symbols the backend actually serves are never redirected away", () => {
  it.each([
    ["/t/BRK-B", "class share"],
    ["/t/RDS-A", "class share"],
    ["/t/CL=F", "continuous future"],
    ["/t/ZC=F", "continuous future"],
    ["/t/RB=F", "continuous future"],
    ["/t/BF-B", "class share"],
  ])("%s (%s) falls through to the ticker page", (path) => {
    expect(decide(path)).toBe("fall-through");
  });

  it("matches the backend's shape, not a narrower guess", () => {
    // Anything the backend would accept must pass here (minus '/', which can
    // never reach a single-segment capture).
    for (const sym of ["A", "NVDA", "BRK-B", "CL=F", "BRK.B", "ABCDEFGHIJKL"]) {
      expect(VALID_TICKER_RE.test(sym), `${sym} rejected`).toBe(true);
    }
    // 13 chars — one past the backend's limit.
    expect(VALID_TICKER_RE.test("ABCDEFGHIJKLM")).toBe(false);
    // Must start with a letter.
    expect(VALID_TICKER_RE.test("1NVDA")).toBe(false);
  });

  it("still serves each section's own metadata card", () => {
    // The regression guard that motivated this file in the first place, plus
    // apple-icon, which only became ambiguous once hyphens were legal.
    expect(decide("/scorecard/opengraph-image")).toBe("fall-through");
    expect(decide("/scorecard/twitter-image")).toBe("fall-through");
    expect(decide("/scorecard/apple-icon")).toBe("fall-through");
    expect(decide("/scorecard/apple-icon-1a2b3c4d")).toBe("fall-through");
    // ...while a real 4-letter symbol that collides with a metadata NAME is
    // still treated as a ticker, because that check is hyphen-gated.
    expect(decide("/t/ICON")).toBe("fall-through");
    expect(decide("/t/icon")).toBe("canonicalise");
  });
});

describe("frontend and backend agree on what a symbol looks like", () => {
  it("rejects exactly what the backend rejects", () => {
    // Backend: ^[A-Z][A-Z0-9.=/^-]{0,11}$ — the FIRST character must be a
    // letter, so a leading '^' is invalid there too. Anything the middleware
    // waves through still has to survive the ticker page's own 404 for an
    // unknown symbol; the point is only that the two layers agree on SHAPE.
    for (const bad of ["^GSPC", "1NVDA", "-NVDA", "=F", "ABCDEFGHIJKLM"]) {
      expect(VALID_TICKER_RE.test(bad), `${bad} should be rejected`).toBe(false);
    }
  });
});
