/**
 * Every server-side call to our own API must identify itself as SSR.
 *
 * All server rendering leaves the one Fly egress IP, so it shares the backend's
 * per-IP limit_api bucket (120/min). Once drained the backend 429s its own
 * frontend — which is how the weekly SEO audit came to report "1534 URLs
 * returning non-2xx/3xx" for pages that served 200 to real visitors, and how
 * Googlebot crawling the ~8,400-page ticker sitemap gets served 500s.
 *
 * The fix is the `x-tapeline-internal` header (lib/ssrHeaders.ts). It only
 * works if EVERY server-side fetch sends it — one page that forgets keeps
 * draining the shared bucket for everyone. This test is that guarantee: a new
 * SSR page cannot silently omit it.
 */
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

// Windows path separator, built without a literal escape.
const SEP = String.fromCharCode(92);

/**
 * Deliberately exempt. /status is the public probe page — its entire job is to
 * measure what a real, unexempted visitor experiences. Giving it the bypass
 * would make the status page report better health than users actually get.
 */
const INTENTIONALLY_EXEMPT = new Set(["app/status/page.tsx"]);

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(tsx?|ts)$/.test(entry)) out.push(full);
  }
  return out;
}

describe("SSR internal-header coverage", () => {
  const files = walk("app");

  const serverApiFetchers = files.filter((f) => {
    const src = readFileSync(f, "utf8");
    if (src.split("\n").slice(0, 3).join("\n").includes('"use client"')) return false;
    if (!/await fetch\(/.test(src)) return false;
    return /API_BASE|NEXT_PUBLIC_API_URL/.test(src);
  });

  it("finds the server-side API callers (guards against a vacuous pass)", () => {
    // If this ever drops to ~0 the walk/filter broke and the real assertion
    // below would pass while checking nothing.
    expect(serverApiFetchers.length).toBeGreaterThan(10);
  });

  it("every server-side API fetch sends the SSR header", () => {
    // Count actual USE, not the import: a file can import the helper and still
    // forget it at a fetch site (and an earlier version of this test passed
    // vacuously for exactly that reason). Require one `headers:` per fetch, so
    // partially-covered files are caught too.
    const missing = serverApiFetchers
      .map((f) => f.split(SEP).join("/"))
      .filter((f) => !INTENTIONALLY_EXEMPT.has(f))
      .filter((f) => {
        const src = readFileSync(f, "utf8");
        const fetches = (src.match(/await fetch\(/g) || []).length;
        const headers = (src.match(/headers: ssrInternalHeaders\(\)/g) || []).length;
        return headers < fetches;
      });

    expect(
      missing,
      `These server components call our API without identifying as SSR, so they ` +
        `drain the shared per-IP rate-limit bucket and can be 429'd into 500s ` +
        `under crawl:\n  ${missing.join("\n  ")}\n` +
        `Add \`headers: ssrInternalHeaders()\` (see lib/ssrHeaders.ts), or add ` +
        `the file to INTENTIONALLY_EXEMPT with a reason.`,
    ).toEqual([]);
  });

  it("never exposes the token to the browser", () => {
    const src = readFileSync("lib/ssrHeaders.ts", "utf8");
    // NEXT_PUBLIC_* is inlined into the client bundle — reading the token from
    // one would hand every visitor a rate-limit bypass. Assert on actual USAGE,
    // not any mention: the file's own comment explains why we avoid it.
    expect(src).not.toMatch(/process\.env\.NEXT_PUBLIC_/);
    expect(src).toContain("process.env.INTERNAL_SSR_TOKEN");
    // Belt-and-braces guard so it cannot attach to a browser-side fetch.
    expect(src).toContain('typeof window !== "undefined"');
  });
});
