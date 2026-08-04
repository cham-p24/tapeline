import { describe, it, expect } from "vitest";
import {
  parseMatchup,
  canonicalMatchup,
  allComparePairs,
  relatedMatchups,
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
});
