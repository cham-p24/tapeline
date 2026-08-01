/**
 * Regression test for the /badge/[symbol] reflected-XSS fix (round-4 audit #1).
 *
 * /badge/[symbol] serves a genuine top-level `image/svg+xml` document. An SVG
 * served as a top-level document executes inline <script> when opened directly
 * (and the site CSP is Report-Only, so it doesn't block). Both the `label`
 * query param and the error-branch `symbol` (raw decoded path) are
 * attacker-controlled and were interpolated into the SVG unescaped — a label
 * like `</text><script>…</script>` broke out of <text> and ran JS on the
 * tapeline.io origin, where the session cookie is domain-wide.
 *
 * These assert the values are XML-escaped in the response body.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "../app/badge/[symbol]/route";

// The route only reads `request.url`; a plain Request is a sufficient stand-in
// for NextRequest here.
function req(url: string): any {
  return new Request(url);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("/badge/[symbol] XSS escaping", () => {
  it("escapes a malicious label and symbol on the invalid-symbol error branch", async () => {
    const label = "</text><script>alert('xss')</script>";
    const url = `https://tapeline.io/badge/x?label=${encodeURIComponent(label)}`;
    // Symbol fails the ticker regex → synchronous error branch, no API fetch.
    const res = await GET(req(url), {
      params: Promise.resolve({ symbol: "<script>bad</script>" }),
    });
    const body = await res.text();

    expect(res.headers.get("Content-Type")).toContain("image/svg+xml");
    // Neither the lowercase label markup nor the uppercased symbol markup
    // may appear as live tags.
    expect(body).not.toContain("<script>");
    expect(body).not.toContain("<SCRIPT>");
    expect(body).not.toContain("</text><script>");
    // …they must be present, escaped.
    expect(body).toContain("&lt;script&gt;");
    expect(body).toContain("&lt;SCRIPT&gt;");
  });

  it("escapes a malicious label on the success path", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ symbol: "NVDA", score: 80, signal: "HIGH CONVICTION" }),
      })),
    );

    const label = "</text><script>alert(1)</script>";
    const url = `https://tapeline.io/badge/NVDA?label=${encodeURIComponent(label)}`;
    const res = await GET(req(url), { params: Promise.resolve({ symbol: "NVDA" }) });
    const body = await res.text();

    expect(body).not.toContain("<script>");
    expect(body).toContain("&lt;script&gt;");
    // The real ticker still renders.
    expect(body).toContain("NVDA");
  });
});
