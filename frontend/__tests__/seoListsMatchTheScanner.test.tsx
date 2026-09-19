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
 * scored row, so it also pages through the whole universe), but the one
 * ticker it names as a sector's top is rank 1 of that sector's ranked page.
 * /signals' anonymous top 10 leaves them out too.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));
// No session cookie: /signals renders its anonymous preview.
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => undefined }) }));

import SignalPage from "@/app/signal/[signal]/page";
import SectorPage from "@/app/sector/[sector]/page";
import BestStocksForStrategyPage from "@/app/best-stocks-for/[strategy]/page";
import SectorsIndexPage from "@/app/sectors/page";
import SignalsPage from "@/app/signals/page";
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

describe("/sectors counts every scored row and names each sector's ranked #1", () => {
  const sector = SECTORS[0].api;
  const row = (symbol: string, score: number, extra: object = {}) => ({
    symbol, name: symbol, sector, score, signal: "STRONG SETUP",
    is_leveraged: false, is_non_common: false, ...extra,
  });

  /** Answers the breadth pages and the ranked read differently. */
  function stubSectors(breadth: object[][], ranked: object[]): string[] {
    const urls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const u = String(input);
        urls.push(u);
        const p = new URL(u).searchParams;
        const items = p.get("exclude_non_common")
          ? ranked
          : breadth[Math.round(Number(p.get("offset") ?? 0) / 1500)] ?? [];
        return { ok: true, status: 200, json: async () => ({ items }) } as unknown as Response;
      }),
    );
    return urls;
  }

  it("pages through the whole universe for its counts, with no exclusions", async () => {
    // A full first page means there is more: the next window must be read.
    const full = Array.from({ length: 2000 }, (_, i) => row(`ZP${i}`, 50));
    const urls = stubSectors([full, [row("ZLAST", 40)]], []);
    render(await SectorsIndexPage());
    const breadth = urls.filter((u) => !new URL(u).searchParams.get("exclude_non_common"));
    expect(breadth.length).toBeGreaterThanOrEqual(2);
    for (const u of breadth) {
      const p = new URL(u).searchParams;
      expect(p.get("exclude_leveraged")).toBeNull();
      expect(p.get("min_dollar_volume")).toBeNull();
    }
    expect(document.body.textContent ?? "").toContain("2001 stocks scored");
  });

  it("names the ranked read's first row, not the highest breadth score", async () => {
    const urls = stubSectors(
      [[
        row("ZNOTE", 95, { is_non_common: true }),
        row("ZTHIN", 94), // unflagged but below the $50k floor: absent from the ranked read
        row("ZSTCK", 80),
      ]],
      [row("ZSTCK", 80)],
    );
    render(await SectorsIndexPage());
    const ranked = urls.find((u) => new URL(u).searchParams.get("exclude_non_common"));
    expect(ranked, "no ranked read for the top tickers").toBeDefined();
    const p = new URL(ranked as string).searchParams;
    expectScannerExclusions(p);
    expect(p.get("min_dollar_volume")).toBe("50000");
    const text = document.body.textContent ?? "";
    expect(text).toContain("ZSTCK");
    expect(text).not.toContain("ZNOTE");
    expect(text).not.toContain("ZTHIN");
    expect(text).toContain("3 stocks scored");
  });
});

describe("/signals' anonymous top 10 leaves out what the scanner's does", () => {
  it("skips a note and a geared fund in the preview", async () => {
    const row = (symbol: string, score: number, extra: object = {}) => ({
      symbol, name: symbol, sector: "Energy", asset_class: "equity", score,
      signal: "STRONG SETUP", price: 10, change_pct_1d: 0, change_pct_5d: 0,
      change_pct_1m: 0, confidence_pct: 70, sub_trend: 70, sub_rs: 70,
      sub_fundamentals: null, sub_momentum: 70, sub_macro: 50, sub_smart_money: null,
      is_leveraged: false, is_non_common: false, ...extra,
    });
    stubFetch([
      row("ZNOTE", 99, { is_non_common: true }),
      row("ZGEAR", 98, { is_leveraged: true }),
      row("ZSTCK", 80),
    ]);
    render(await SignalsPage());
    const text = document.body.textContent ?? "";
    expect(text).toContain("ZSTCK");
    expect(text).not.toContain("ZNOTE");
    expect(text).not.toContain("ZGEAR");
  });
});
