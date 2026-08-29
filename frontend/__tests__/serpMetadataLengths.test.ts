/**
 * SERP title and description budgets.
 *
 * Audited 2026-08-29 across all 313 non-ticker pages: 300 descriptions were
 * over 165 chars (worst 413) and 70 titles over 65. `pageMeta`'s own docstring
 * had specified "150-160 chars" for description since it was written, so the
 * contract existed — nothing enforced it.
 *
 * Descriptions are now clamped mechanically in `pageMeta` (Google truncates
 * them either way; this only decides whether the cut lands on a word
 * boundary), so the test below is about the CLAMP behaving, not about 300
 * strings.
 *
 * Titles are NOT auto-truncated — cutting a headline mid-phrase is worse than
 * a long one — so those were shortened at the source and are pinned here per
 * data file.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { clampDescription, pageMeta, SERP_DESCRIPTION_MAX } from "../lib/seo";

const APP = join(__dirname, "..", "app");
const TITLE_MAX = 65;

describe("clampDescription", () => {
  it("leaves a short description untouched", () => {
    const s = "A short description.";
    expect(clampDescription(s)).toBe(s);
  });

  it("cuts on a word boundary, never mid-word", () => {
    const s = "word ".repeat(80).trim();
    const out = clampDescription(s);
    expect(out.length).toBeLessThanOrEqual(SERP_DESCRIPTION_MAX);
    expect(out.endsWith("word")).toBe(true);
  });

  it("does not leave dangling punctuation", () => {
    const s = `${"a".repeat(150)}, and then some more text here`;
    expect(clampDescription(s)).not.toMatch(/[\s,;:—–-]$/);
  });

  it("appends no ellipsis", () => {
    // Google adds its own when it truncates further; one we wrote would be
    // indistinguishable from content we lost.
    expect(clampDescription("x ".repeat(200))).not.toContain("…");
    expect(clampDescription("x ".repeat(200))).not.toMatch(/\.\.\.$/);
  });

  it("still returns something for a single over-long word", () => {
    const out = clampDescription("z".repeat(400));
    expect(out.length).toBeGreaterThan(0);
    expect(out.length).toBeLessThanOrEqual(SERP_DESCRIPTION_MAX);
  });
});

describe("pageMeta", () => {
  const long =
    "Tapeline vs Finviz Elite — one composite score per ticker, plain-English Why on every row, and a public next-day scorecard, none of which Finviz publishes. 9 categories Tapeline wins, 3 honest tradeoffs.";

  it("clamps the SERP description", () => {
    const m = pageMeta({ title: "T", description: long, path: "/x" });
    expect((m.description as string).length).toBeLessThanOrEqual(SERP_DESCRIPTION_MAX);
  });

  it("does NOT clamp the social card description", () => {
    // Different consumers, different limits — Facebook/LinkedIn/Slack show
    // appreciably more than Google, so clamping both would throw away copy
    // the card had room for.
    const m = pageMeta({ title: "T", description: long, path: "/x" });
    expect(m.openGraph?.description).toBe(long);
    expect(m.twitter?.description).toBe(long);
  });
});

/** Every `title: "..."` literal in a file, ignoring template literals. */
function titlesIn(relPath: string): string[] {
  const src = readFileSync(join(APP, relPath), "utf8");
  return [...src.matchAll(/(?:meta)?[Tt]itle:\s*"([^"]+)"/g)].map((m) => m[1]);
}

describe("title budgets at the source", () => {
  it("glossary terms fit", () => {
    const over = titlesIn(join("glossary", "terms.ts")).filter((t) => t.length > TITLE_MAX);
    expect(over, `over ${TITLE_MAX}: ${over.join(" | ")}`).toEqual([]);
  });

  it("best-stocks-for strategies fit", () => {
    const over = titlesIn(join("best-stocks-for", "[strategy]", "strategies.ts")).filter(
      (t) => t.length > TITLE_MAX,
    );
    expect(over, `over ${TITLE_MAX}: ${over.join(" | ")}`).toEqual([]);
  });

  it("every blog post has a SERP title that fits", () => {
    const src = readFileSync(join(APP, "blog", "posts.ts"), "utf8");
    // Pair each post's title with the metaTitle that follows it, if any.
    // \r?\n — posts.ts is CRLF in a Windows checkout.
    const posts = [
      ...src.matchAll(
        /\r?\n {4}title: "((?:[^"\\]|\\.)+)",\r?\n(?: {4}metaTitle: "((?:[^"\\]|\\.)+)",\r?\n)?/g,
      ),
    ];
    // Self-checking: one match per post entry. A regex that silently stopped
    // matching would otherwise make this test vacuously pass.
    const slugCount = (src.match(/^\s{4}slug:\s/gm) ?? []).length;
    expect(slugCount).toBeGreaterThan(0);
    expect(posts.length).toBe(slugCount);
    const over = posts
      .map(([, title, meta]) => (meta ?? title))
      .filter((t) => t.length > TITLE_MAX);
    expect(over, `over ${TITLE_MAX}: ${over.join(" | ")}`).toEqual([]);
  });
});
