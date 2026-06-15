/**
 * Unit tests for the pure filter/search helpers in lib/filters.ts.
 *
 * These back the consistent filter bar + search box added across the
 * live-monitor pages (scanner, squeeze, congress, news, earnings, IPOs,
 * watchlist). The page components just wire these predicates to React state,
 * so covering the predicates here gives us confidence the actual filtering
 * rules behave the same everywhere without rendering every page.
 */
import { describe, it, expect } from "vitest";
import {
  matchesQuery,
  inRange,
  matchesSelect,
  assetBucket,
  matchesAssetBucket,
} from "@/lib/filters";

describe("matchesQuery", () => {
  it("matches everything when the query is empty or whitespace", () => {
    expect(matchesQuery("", ["AAPL"])).toBe(true);
    expect(matchesQuery("   ", ["AAPL"])).toBe(true);
  });

  it("is case-insensitive and matches substrings", () => {
    expect(matchesQuery("nvd", ["NVDA"])).toBe(true);
    expect(matchesQuery("APPLE", ["Apple Inc"])).toBe(true);
  });

  it("matches across multiple fields (ticker OR name)", () => {
    expect(matchesQuery("tesla", ["TSLA", "Tesla Inc"])).toBe(true);
    expect(matchesQuery("tsla", ["TSLA", "Tesla Inc"])).toBe(true);
  });

  it("returns false when no field contains the needle", () => {
    expect(matchesQuery("zzz", ["AAPL", "Apple Inc"])).toBe(false);
  });

  it("skips null/undefined fields without throwing", () => {
    expect(matchesQuery("aapl", [null, undefined, "AAPL"])).toBe(true);
    expect(matchesQuery("x", [null, undefined])).toBe(false);
  });
});

describe("inRange", () => {
  it("passes everything when both bounds are absent", () => {
    expect(inRange(50, null, null)).toBe(true);
    expect(inRange(null, undefined, undefined)).toBe(true);
  });

  it("respects an inclusive minimum", () => {
    expect(inRange(70, 70, null)).toBe(true);
    expect(inRange(69, 70, null)).toBe(false);
  });

  it("respects an inclusive maximum", () => {
    expect(inRange(80, null, 80)).toBe(true);
    expect(inRange(81, null, 80)).toBe(false);
  });

  it("respects both bounds together", () => {
    expect(inRange(50, 40, 60)).toBe(true);
    expect(inRange(39, 40, 60)).toBe(false);
    expect(inRange(61, 40, 60)).toBe(false);
  });

  it("drops null values only when a bound is actually set", () => {
    expect(inRange(null, 10, null)).toBe(false);
    expect(inRange(null, null, null)).toBe(true);
  });
});

describe("matchesSelect", () => {
  it("matches everything when nothing is selected", () => {
    expect(matchesSelect("", "BUY")).toBe(true);
    expect(matchesSelect("", null)).toBe(true);
  });

  it("matches case-insensitively", () => {
    expect(matchesSelect("buy", "BUY")).toBe(true);
    expect(matchesSelect("Senate", "senate")).toBe(true);
  });

  it("returns false on a mismatch or null row value", () => {
    expect(matchesSelect("BUY", "SELL")).toBe(false);
    expect(matchesSelect("BUY", null)).toBe(false);
  });
});

describe("assetBucket / matchesAssetBucket", () => {
  it("collapses fine-grained asset classes into coarse buckets", () => {
    expect(assetBucket("equity")).toBe("equity");
    expect(assetBucket("stock")).toBe("equity");
    expect(assetBucket("etf")).toBe("etf");
    expect(assetBucket("fund")).toBe("etf");
    expect(assetBucket("future")).toBe("other");
    expect(assetBucket(null)).toBe("");
  });

  it("matches everything when no bucket is selected", () => {
    expect(matchesAssetBucket("", "future")).toBe(true);
  });

  it("filters to the selected bucket", () => {
    expect(matchesAssetBucket("equity", "stock")).toBe(true);
    expect(matchesAssetBucket("equity", "etf")).toBe(false);
    expect(matchesAssetBucket("etf", "fund")).toBe(true);
    expect(matchesAssetBucket("other", "future")).toBe(true);
  });
});
