/**
 * The ranked SEO pages leave out what the scanner's default view leaves out.
 *
 * /api/scanner excludes leveraged/inverse funds (#761) and listings that are
 * not common stock (notes, preferreds, warrants: #875) by default. The ranked
 * SEO pages read /api/public/signals instead (see ssrScannerGating.test.ts),
 * which defaults both exclusions OFF for its breadth callers, so each ranked
 * page must ask for them. Found 2026-09-19: GREEL, a Greenidge senior note,
 * could top /signal/strong-setup.
 *
 * Driven through the pages themselves, not their source text: each page is
 * called with a stubbed fetch, for EVERY slug it serves, and the URL it
 * actually requests is checked.
 *
 * The breadth page /sectors must NOT ask for them (its counts describe every
 * scored row), but the one ticker it names as a sector's top must be one the
 * ranked view would show.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));

import SignalPage from "@/app/signal/[signal]/page";
import SectorPage from "@/app/sector/[sector]/page";
import BestStocksForStrategyPage from "@/app/best-stocks-for/[strategy]/page";
import SectorsIndexPage from "@/app/sectors/page";
import { SIGNALS } from "@/app/signal/signals";
import { SECTORS } from "@/app/sector/sectors";
import { STRATEGIES } from "@/app/best-stocks-for/[strategy]/strategies";

function stubFetch(items: object[] = []): string[] {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      urls.push(String(input));
      return {
        ok: true,
        status: 200,
        json: async () => ({ items, count: items.length }),
      } as unknown as Response;
    }),
  );
  return urls;
}

function publicSignalsParams(urls: string[]): URLSearchParams {
  const hit = urls.find((u) => u.includes("/api/public/signals?"));
  expect(hit, "the page never requested /api/public/signals").toBeDefined();
  return new URL(hit as string).searchParams;
}

function expectScannerExclusions(p: URLSearchParams) {
  expect(p.get("exclude_leveraged")).toBe("true");
  expect(p.get("exclude_non_common")).toBe("true");
}

afterEach(() => vi.unstubAllGlobals());

describe("ranked SEO pages ask for the scanner's exclusions", () => {
  for (const s of SIGNALS) {
    it(`/signal/${s.slug}`, async () => {
      const urls = stubFetch();
      await SignalPage({ params: Promise.resolve({ signal: s.slug }) });
      expectScannerExclusions(publicSignalsParams(urls));
    });
  }

  for (const s of SECTORS) {
    it(`/sector/${s.slug}`, async () => {
      const urls = stubFetch();
      await SectorPage({ params: Promise.resolve({ sector: s.slug }) });
      expectScannerExclusions(publicSignalsParams(urls));
    });
  }

  for (const s of STRATEGIES) {
    it(`/best-stocks-for/${s.slug}`, async () => {
      const urls = stubFetch();
      await BestStocksForStrategyPage({ params: Promise.resolve({ strategy: s.slug }) });
      expectScannerExclusions(publicSignalsParams(urls));
    });
  }
});

describe("/sectors keeps its breadth but names a rankable top ticker", () => {
  const sector = SECTORS[0].api;
  const row = (symbol: string, score: number, extra: object = {}) => ({
    symbol, name: symbol, sector, score, signal: "STRONG SETUP",
    is_leveraged: false, is_non_common: false, ...extra,
  });

  it("does not ask for the exclusions, so its counts cover every scored row", async () => {
    const urls = stubFetch();
    await SectorsIndexPage();
    const p = publicSignalsParams(urls);
    expect(p.get("exclude_leveraged")).toBeNull();
    expect(p.get("exclude_non_common")).toBeNull();
  });

  it("skips a note or a geared fund when naming the sector's top ticker", async () => {
    stubFetch([
      row("ZNOTE", 95, { is_non_common: true }),
      row("ZGEAR", 94, { is_leveraged: true }),
      row("ZSTCK", 80),
    ]);
    render(await SectorsIndexPage());
    const text = document.body.textContent ?? "";
    expect(text).toContain("ZSTCK");
    expect(text).not.toContain("ZNOTE");
    expect(text).not.toContain("ZGEAR");
    // The count still includes all three: it describes every scored row.
    expect(text).toContain("3 stocks scored");
  });
});
