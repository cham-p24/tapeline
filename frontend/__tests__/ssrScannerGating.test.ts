/**
 * Anonymous SSR must not read the TIER-GATED scanner for lists it publishes
 * as "top N".
 *
 * /api/scanner clamps row count by tier, and server-side rendering is an
 * anonymous caller — so it resolves the FREE cap (10). Three public SEO pages
 * asked for 30 rows and silently published 10:
 *
 *   /sector/{slug}          "Top {Sector} Stocks Ranked by Tapeline Score"
 *   /signal/{slug}          live tickers at that signal level
 *   /best-stocks-for/{s}    every strategy listicle (limit: 30 in apiParams)
 *
 * They now read /api/public/signals, which applies the same filters and the
 * same ORDER BY (backend services/ticker_ordering) with no row cap.
 *
 * Pages deliberately left on /api/scanner, because the Free cap IS the intent:
 *   /daily-picks, /feed.xml   — "Daily Top 10", they slice to 10 anyway
 *   components/ScannerPreview — a preview OF the free tier, limit=10
 *   /t/{symbol}               — sector-scoped, needs only 6 related cards
 */
import { describe, it, expect } from "vitest";
import { readFile } from "node:fs/promises";

/** Pages that publish a ranked list longer than the Free cap. */
const MUST_BE_UNGATED = [
  "app/sector/[sector]/page.tsx",
  "app/signal/[signal]/page.tsx",
  "app/best-stocks-for/[strategy]/page.tsx",
];

/** The Free scanner row cap — backend tier.py FREE_SCANNER_ROWS. */
const FREE_SCANNER_ROWS = 10;

describe("anonymous SSR list pages", () => {
  for (const path of MUST_BE_UNGATED) {
    it(`${path} does not fetch its list from the tier-gated scanner`, async () => {
      const src = await readFile(path, "utf-8");
      const gated = src.match(/\$\{API_BASE\}\/api\/scanner/g) ?? [];
      expect(
        gated.length,
        `${path} fetches /api/scanner. That endpoint tier-gates row count, and ` +
          `SSR is anonymous, so it silently returns ${FREE_SCANNER_ROWS} rows ` +
          `however many were requested. Use /api/public/signals.`,
      ).toBe(0);
      expect(src).toContain("/api/public/signals?");
    });

    it(`${path} keeps the scanner's liquidity floor after moving endpoints`, async () => {
      const src = await readFile(path, "utf-8");
      // /api/scanner defaults min_dollar_volume to SCANNER_MIN_DOLLAR_VOLUME;
      // /api/public/signals defaults it to 0 so its pre-existing callers are
      // unaffected. Moving endpoints therefore has to pass it explicitly, or
      // near-untradeable names quietly enter these ranked lists.
      // Match the PARAMETER, not the word: the surrounding comment also says
      // "min_dollar_volume", so a substring check would pass even if the param
      // itself were deleted.
      expect(
        /min_dollar_volume:\s*"\d+"/.test(src),
        `${path} must pass a min_dollar_volume VALUE — the public endpoint ` +
          `defaults it off, unlike the scanner it moved away from`,
      ).toBe(true);
    });
  }

  it("asks for more rows than the Free cap (otherwise the fix is pointless)", async () => {
    // /best-stocks-for declares its limit in the strategy table, not the page.
    const LIMIT_SOURCE: Record<string, string> = {
      "app/best-stocks-for/[strategy]/page.tsx":
        "app/best-stocks-for/[strategy]/strategies.ts",
    };
    for (const page of MUST_BE_UNGATED) {
      const path = LIMIT_SOURCE[page] ?? page;
      const src = await readFile(path, "utf-8");
      const limits = [...src.matchAll(/limit:\s*"?(\d+)"?/g)].map((m) => Number(m[1]));
      expect(limits.length, `${path}: no limit found`).toBeGreaterThan(0);
      expect(
        Math.max(...limits),
        `${path} requests <= ${FREE_SCANNER_ROWS} rows, so the gate was never ` +
          `what truncated it — re-check this test's premise`,
      ).toBeGreaterThan(FREE_SCANNER_ROWS);
    }
  });
});
