/**
 * The embed widget must stay iframe-able; everything else must not.
 *
 * app/embed/score/[symbol]/page.tsx exists solely to be iframed by third
 * parties — it is the backlink-acquisition asset ("Every blog, Substack,
 * GitHub README, or personal site that embeds this widget produces a dofollow
 * link back to https://tapeline.io/t/{TICKER}").
 *
 * next.config.js applied `X-Frame-Options: DENY` to `/:path*`, i.e. every
 * route. DENY forbids framing by ANY origin — including same-origin — so:
 *
 *   - a blogger who pasted the snippet from /embed saw an empty 480x140 box
 *   - the "Powered by Tapeline" dofollow link was never emitted, so the entire
 *     embed backlink channel produced zero links
 *   - the three live-preview iframes on /embed itself rendered blank to every
 *     visitor of the page that is supposed to sell the widget
 *   - trackEmbedImpression never fired, so the admin "Embed distribution"
 *     panel read zero — the failure looked like "nobody embedded it" rather
 *     than "embedding is impossible"
 *
 * Verified against production before the fix:
 *   curl -sI https://tapeline.io/embed/score/NVDA → `x-frame-options: DENY`
 *
 * These tests drive the real `headers()` from next.config.js, so they check the
 * shipped config rather than a copy of it.
 */
import { describe, it, expect } from "vitest";

type Header = { key: string; value: string };
type Rule = { source: string; headers: Header[] };

async function rules(): Promise<Rule[]> {
  // next.config.js is CommonJS; import it through the default interop.
  const mod = await import("../next.config.js");
  const config = (mod as { default?: unknown }).default ?? mod;
  const headersFn = (config as { headers?: () => Promise<Rule[]> }).headers;
  expect(typeof headersFn, "next.config.js exports no headers()").toBe("function");
  return await headersFn!.call(config);
}

/** The first rule whose source matches `path`, mimicking Next's precedence. */
function matching(all: Rule[], path: string): Rule[] {
  return all.filter((r) => {
    // Translate Next's `:path*` segment syntax into a regex; other sources in
    // this config are already regex-ish (negative lookahead).
    const pattern = r.source
      .replace(/\/:path\*/g, "(?:/.*)?")
      .replace(/\/:[A-Za-z]+\*/g, "(?:/.*)?");
    try {
      return new RegExp(`^${pattern}$`).test(path);
    } catch {
      return false;
    }
  });
}

function headerNames(rs: Rule[]): Set<string> {
  const out = new Set<string>();
  for (const r of rs) for (const h of r.headers) out.add(h.key.toLowerCase());
  return out;
}

describe("embed widget framing", () => {
  it("does not send X-Frame-Options on /embed/score/*", async () => {
    const all = await rules();
    const hit = matching(all, "/embed/score/NVDA");
    expect(hit.length, "no header rule matched /embed/score/NVDA").toBeGreaterThan(0);
    expect(
      headerNames(hit).has("x-frame-options"),
      "X-Frame-Options is still applied to the embed widget — DENY blocks " +
        "framing by every origin, so the widget can never paint and the embed " +
        "backlink channel produces zero links",
    ).toBe(false);
  });

  it("keeps every OTHER security header on the embed route", async () => {
    // Dropping the framing lock must not quietly drop the rest of the hardening.
    const all = await rules();
    const names = headerNames(matching(all, "/embed/score/NVDA"));
    for (const required of [
      "strict-transport-security",
      "x-content-type-options",
      "referrer-policy",
      "permissions-policy",
      "content-security-policy-report-only",
    ]) {
      expect(names.has(required), `embed route lost ${required}`).toBe(true);
    }
  });

  it("still denies framing everywhere else", async () => {
    const all = await rules();
    for (const path of ["/", "/pricing", "/embed", "/app/scanner", "/t/NVDA", "/scorecard"]) {
      const names = headerNames(matching(all, path));
      expect(
        names.has("x-frame-options"),
        `${path} lost its clickjacking protection`,
      ).toBe(true);
    }
  });

  it("the catch-all rule explicitly excludes the embed widget", async () => {
    // Belt and braces: if the exclusion were dropped from the catch-all, the
    // embed route would match BOTH rules and Next would apply DENY again.
    const all = await rules();
    const broad = all.find((r) => r.headers.some((h) => h.key === "X-Frame-Options"));
    expect(broad, "no rule sets X-Frame-Options at all").toBeTruthy();
    expect(
      broad!.source,
      "the X-Frame-Options rule does not exclude embed/score, so the embed " +
        "route still matches it",
    ).toContain("embed/score");
  });
});
