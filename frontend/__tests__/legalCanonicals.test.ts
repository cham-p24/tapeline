/**
 * Every indexable page must declare its OWN canonical URL.
 *
 * app/layout.tsx sets `alternates: { canonical: "/" }` on the ROOT layout, and
 * Next's metadata merge starts from a clone of the resolved parent metadata and
 * only overwrites keys physically present in the child. So a page that exports
 * a bare `{ title, description }` — with no `alternates` and without going
 * through lib/seo.pageMeta — silently inherits the HOMEPAGE canonical.
 *
 * app/legal/refund/page.tsx was doing exactly that. Verified in production:
 *
 *   curl -sL https://tapeline.io/legal/refund
 *     <link rel="canonical" href="https://tapeline.io"/>
 *     <meta property="og:url" content="https://tapeline.io"/>
 *
 * while its sibling /legal/terms correctly self-canonicalised. Because
 * sitemap.ts submits /legal/refund, GSC files it as "Duplicate, submitted URL
 * not selected as canonical" and folds it into the homepage — so the refund
 * policy never surfaces for "tapeline refund policy", and a Stripe dispute or
 * trust-page link previews the homepage card instead of the policy.
 *
 * This test sweeps every page with metadata rather than pinning the one file,
 * because the failure mode is silent: the page still renders, still has a
 * title, and only the canonical is wrong.
 */
import { describe, it, expect } from "vitest";
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

async function pageFiles(dir: string): Promise<string[]> {
  const out: string[] = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules") continue;
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await pageFiles(full)));
    else if (entry.name === "page.tsx") out.push(full.replace(/\\/g, "/"));
  }
  return out;
}

/** Routes deliberately excluded from the index, where a canonical is moot. */
function isNoindex(src: string): boolean {
  return /robots:\s*\{[^}]*index:\s*false/.test(src) || src.includes("noindex");
}

/**
 * Strip comments before looking for code.
 *
 * Without this the check matches its own documentation: a file explaining
 * *why* it must not rely on the root layout's `alternates` would satisfy a
 * naive `src.includes("alternates")` while the actual metadata export stayed
 * bare. Verified — the sweep below passed against a deliberately reverted
 * refund page until comments were stripped.
 */
function code(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

describe("canonical URLs", () => {
  it("no indexable page silently inherits the homepage canonical", async () => {
    const files = await pageFiles("app");
    const offenders: string[] = [];

    for (const path of files) {
      const src = code(await readFile(path, "utf-8"));
      const declaresMetadata =
        /export const metadata\s*=/.test(src) ||
        /export (async )?function generateMetadata/.test(src);
      if (!declaresMetadata) continue; // inherits by design (nested segments)
      if (isNoindex(src)) continue;

      // Self-canonical comes either from pageMeta() (lib/seo.ts) or an
      // explicit `alternates` block.
      const selfCanonical = src.includes("pageMeta(") || src.includes("alternates");
      if (!selfCanonical) offenders.push(path);
    }

    expect(
      offenders,
      "these indexable pages declare metadata but no canonical, so Next hands " +
        "them the root layout's `canonical: \"/\"` and Google folds them into " +
        "the homepage. Use pageMeta({ ..., path }) from lib/seo.ts:\n  " +
        offenders.join("\n  "),
    ).toEqual([]);
  });

  it("every legal page self-canonicalises", async () => {
    // The legal pages are linked from Stripe, the footer and dispute flows, so
    // they need to resolve to themselves, not the homepage.
    const files = (await pageFiles("app/legal")).sort();
    expect(files.length).toBeGreaterThan(3);
    for (const path of files) {
      const src = code(await readFile(path, "utf-8"));
      expect(
        src.includes("pageMeta(") || src.includes("alternates"),
        `${path} has no self-canonical`,
      ).toBe(true);
    }
  });

  it("/legal/refund canonicalises to itself", async () => {
    const src = code(await readFile("app/legal/refund/page.tsx", "utf-8"));
    expect(src).toContain("pageMeta(");
    expect(src).toContain('path: "/legal/refund"');
  });
});
