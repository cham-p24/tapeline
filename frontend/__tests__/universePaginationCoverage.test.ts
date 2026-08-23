/**
 * The universe walk in app/sitemap.ts and app/stocks/page.tsx must not be able
 * to SKIP a ticker.
 *
 * Both walk `/api/public/signals?limit=2000&offset=N` in a loop. Each distinct
 * offset URL is its own `revalidate: 3600` Data Cache entry, so adjacent pages
 * are routinely served from snapshots up to an hour apart — while the worker
 * re-scores the entire universe every 60 seconds.
 *
 * With a stride equal to the page size the windows tile exactly, and a ticker
 * whose rank drifts across a boundary between the two snapshots lands in
 * NEITHER window:
 *
 *   page 0, read at T0      ranks    1..2000 as of T0   (DUK was 2100 → absent)
 *   page 1, read at T0+40m  ranks 2001..4000 as of T1   (DUK is now 1950 → absent)
 *
 * /t/DUK then disappears from sitemap.xml and from the /stocks directory — the
 * precise "Crawled - currently not indexed" failure the pagination was added to
 * fix. Both files already de-dupe, so duplicates are harmless; a SKIP is not
 * recoverable.
 *
 * The fix is to advance by less than a page so consecutive windows overlap.
 * These tests read the real constants out of both files and simulate the walk.
 */
import { describe, it, expect } from "vitest";
import { readFile } from "node:fs/promises";

const FILES = ["app/sitemap.ts", "app/stocks/page.tsx"];

async function constantsOf(path: string) {
  const src = await readFile(path, "utf-8");
  const num = (name: string) => {
    const m = src.match(new RegExp(`const ${name}\\s*=\\s*(\\d+)`));
    if (!m) throw new Error(`${path}: ${name} not found`);
    return Number(m[1]);
  };
  return {
    pageSize: num("UNIVERSE_PAGE_SIZE"),
    stride: num("UNIVERSE_STRIDE"),
    maxPages: num("UNIVERSE_MAX_PAGES"),
  };
}

/**
 * Simulate the walk. `rankAt(symbolIndex, page)` gives a symbol's rank in the
 * snapshot that page was read from, so drift between pages can be modelled.
 * Returns the set of symbol indices collected.
 */
function walk(
  universe: number,
  pageSize: number,
  stride: number,
  maxPages: number,
  rankAt: (symbol: number, page: number) => number,
): Set<number> {
  const seen = new Set<number>();
  for (let page = 0; page < maxPages; page++) {
    const offset = page * stride;
    // Rows this window returns, per that page's own snapshot.
    let returned = 0;
    for (let sym = 0; sym < universe; sym++) {
      const rank = rankAt(sym, page);
      if (rank >= offset && rank < offset + pageSize) {
        seen.add(sym);
        returned++;
      }
    }
    if (returned < pageSize) break;
  }
  return seen;
}

describe("universe pagination coverage", () => {
  for (const path of FILES) {
    it(`${path} overlaps its windows (stride < page size)`, async () => {
      const { pageSize, stride } = await constantsOf(path);
      expect(
        stride,
        `${path}: stride ${stride} >= page size ${pageSize}. Windows tile ` +
          `exactly, so a ticker whose rank drifts across a boundary between two ` +
          `independently-cached snapshots is silently dropped from the sitemap.`,
      ).toBeLessThan(pageSize);
    });

    it(`${path} still covers the whole universe with a stable ranking`, async () => {
      const { pageSize, stride, maxPages } = await constantsOf(path);
      const universe = 4600; // ~today's pool
      const stable = (sym: number) => sym; // rank == index, no drift
      const seen = walk(universe, pageSize, stride, maxPages, stable);
      expect(seen.size).toBe(universe);
    });

    it(`${path} survives rank drift up to the overlap width`, async () => {
      const { pageSize, stride, maxPages } = await constantsOf(path);
      const overlap = pageSize - stride;
      const universe = 4600;
      // Every symbol drifts UP by the full overlap on each later page — the
      // worst case, since drifting up is what carries a row past a boundary
      // that an earlier, staler page had not yet reached.
      const drifting = (sym: number, page: number) =>
        Math.max(0, sym - page * overlap);
      const seen = walk(universe, pageSize, stride, maxPages, drifting);
      const missing = [...Array(universe).keys()].filter((i) => !seen.has(i));
      expect(
        missing.length,
        `${missing.length} symbols skipped under ${overlap}-rank drift ` +
          `(first few: ${missing.slice(0, 5)})`,
      ).toBe(0);
    });

    it(`${path} would MISS rows if the stride were widened to the page size`, async () => {
      // Premise check: proves the overlap is what saves us, not the simulation
      // being too forgiving. With stride == pageSize the same drift loses rows.
      const { pageSize, maxPages } = await constantsOf(path);
      const universe = 4600;
      const overlap = 500;
      const drifting = (sym: number, page: number) =>
        Math.max(0, sym - page * overlap);
      const seen = walk(universe, pageSize, pageSize, maxPages, drifting);
      expect(seen.size).toBeLessThan(universe);
    });

    it(`${path} bounds the walk well past today's universe`, async () => {
      const { pageSize, stride, maxPages } = await constantsOf(path);
      const reach = (maxPages - 1) * stride + pageSize;
      expect(reach).toBeGreaterThan(10_000);
    });
  }

  it("sitemap and /stocks use identical constants", async () => {
    // app/stocks/page.tsx documents that it matches the sitemap "exactly"; if
    // they drift, the directory and the sitemap list different tickers.
    const [a, b] = await Promise.all(FILES.map(constantsOf));
    expect(a).toEqual(b);
  });
});
