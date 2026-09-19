import { describe, it, expect } from "vitest";
import {
  parseMatchup,
  canonicalMatchup,
  allComparePairs,
  relatedMatchups,
  comparePairsByGroup,
  normalizeSymbol,
  COMPARE_GROUPS,
  COMPARE_NAMES,
} from "@/lib/comparePairs";

describe("comparePairs", () => {
  it("canonicalMatchup sorts alphabetically and lowercases (one URL per pair)", () => {
    expect(canonicalMatchup("MSFT", "AAPL")).toBe("aapl-vs-msft");
    expect(canonicalMatchup("aapl", "msft")).toBe("aapl-vs-msft");
    // a-vs-b and b-vs-a collapse to the same canonical slug
    expect(canonicalMatchup("NVDA", "AMD")).toBe(canonicalMatchup("AMD", "NVDA"));
  });

  it("parseMatchup splits valid slugs and rejects malformed ones", () => {
    expect(parseMatchup("aapl-vs-msft")).toEqual({ a: "AAPL", b: "MSFT" });
    expect(parseMatchup("aapl-vs-aapl")).toBeNull(); // same symbol both sides
    expect(parseMatchup("aapl")).toBeNull(); // no separator
    expect(parseMatchup("a-vs-b-vs-c")).toBeNull(); // too many parts
    expect(parseMatchup("aapl-vs-")).toBeNull(); // empty side
  });

  it("allComparePairs is canonical, de-duped, and non-trivial", () => {
    const pairs = allComparePairs();
    expect(pairs.length).toBeGreaterThan(50);
    for (const p of pairs) expect(p.a <= p.b).toBe(true); // canonical order
    const keys = new Set(pairs.map((p) => `${p.a}-${p.b}`));
    expect(keys.size).toBe(pairs.length); // no duplicates (NVDA spans 2 groups)
    expect(pairs.some((p) => p.a === "AAPL" && p.b === "MSFT")).toBe(true);
  });

  it("relatedMatchups only returns pairs containing the symbol", () => {
    const r = relatedMatchups("AAPL", 3);
    expect(r.length).toBeGreaterThan(0);
    expect(r.length).toBeLessThanOrEqual(3);
    for (const p of r) expect(p.a === "AAPL" || p.b === "AAPL").toBe(true);
  });

  it("comparePairsByGroup partitions allComparePairs exactly — same set, same order", () => {
    // The /compare index prints pairs by theme; the sitemap emits
    // allComparePairs. If these ever diverge, a page is advertised but not
    // linked (or linked twice).
    const grouped = comparePairsByGroup();
    expect(grouped.map((g) => g.id)).toEqual(COMPARE_GROUPS.map((g) => g.id));
    expect(grouped.flatMap((g) => g.pairs)).toEqual(allComparePairs());
    for (const g of grouped) {
      for (const p of g.pairs) {
        expect(g.symbols).toContain(p.a);
        expect(g.symbols).toContain(p.b);
      }
    }
  });

  it("every theme has a unique anchor id and every curated symbol has a display name", () => {
    const ids = COMPARE_GROUPS.map((g) => g.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) expect(id).toMatch(/^[a-z0-9-]+$/);
    const missing = COMPARE_GROUPS.flatMap((g) => g.symbols).filter((s) => !COMPARE_NAMES[s]);
    expect(missing).toEqual([]);
  });

  it("normalizeSymbol keeps only what a matchup slug can carry", () => {
    expect(normalizeSymbol(" brk.b ")).toBe("BRK.B");
    expect(normalizeSymbol("$nvda")).toBe("NVDA");
    expect(normalizeSymbol("X:BTCUSD")).toBe("XBTCUSD");
    expect(normalizeSymbol("   ")).toBe("");
    // round-trips through the slug parser
    const slug = canonicalMatchup(normalizeSymbol("brk.b"), normalizeSymbol("aapl"));
    expect(parseMatchup(slug)).toEqual({ a: "AAPL", b: "BRK.B" });
  });
});
