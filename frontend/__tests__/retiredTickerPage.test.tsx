/**
 * /t/{symbol} for a ticker retired as no longer trading.
 *
 * 2026-09-19. The backend now stamps `delisted_at` on a row a complete walk of
 * the vendor's active listings no longer lists, and /api/ticker answers 404
 * with a sentence that starts "No longer trading:". Before this the page was
 * built from the dead row like any other: GREE, renamed VIP on 24 Jul 2026,
 * rendered 75.8 STRONG SETUP beside its last price.
 *
 * Contract:
 *   1. The page shows the backend's sentence as is, on a noindex page.
 *   2. It fetches nothing beyond the one ticker request (no related tickers,
 *      no news): none of it describes a listing that still exists.
 *   3. Any other 404 is still Next's notFound().
 *   4. The change is on the public changelog (rule 1 of that log: a change to
 *      what may enter the record gets a dated scope entry).
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import path from "node:path";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));
vi.mock("@/components/NewsletterCapture", () => ({ NewsletterCapture: () => null }));
vi.mock("@/components/AnonSignupNudge", () => ({ AnonSignupNudge: () => null }));
vi.mock("@/components/ScoreSparkline", () => ({ ScoreSparkline: () => null }));

import PublicTickerPage, { generateMetadata } from "@/app/t/[symbol]/page";
import { RETIRED_PREFIX, retiredDetail } from "@/lib/retired";

const RETIRED =
  "No longer trading: GREE was not in our data vendor's list of active US " +
  "listings on 19 September 2026. Its last score is no longer updated.";

function stub404(detail: string) {
  const spy = vi.fn(async () => ({
    ok: false,
    status: 404,
    headers: new Headers(),
    json: async () => ({ detail }),
  }) as unknown as Response);
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("retiredDetail", () => {
  it("accepts only the retirement sentence", () => {
    expect(retiredDetail({ detail: RETIRED })).toBe(RETIRED);
    expect(retiredDetail({ detail: "Ticker GREE not in scanner universe" })).toBeNull();
    expect(retiredDetail(null)).toBeNull();
    expect(retiredDetail({ detail: 404 })).toBeNull();
    expect(RETIRED.startsWith(RETIRED_PREFIX)).toBe(true);
  });
});

describe("/t/{symbol} for a retired ticker", () => {
  it("renders the backend's sentence and fetches nothing else", async () => {
    const spy = stub404(RETIRED);
    const { container } = render(
      await PublicTickerPage({ params: Promise.resolve({ symbol: "gree" }) }),
    );
    expect(container.textContent).toContain(RETIRED);
    expect(container.querySelector("h1")?.textContent).toBe("GREE");
    const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/scorecard");
    // No score, no price, no label on the page.
    expect(container.textContent).not.toMatch(/STRONG SETUP|75\.8/);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(String((spy.mock.calls[0] as unknown[])[0])).toContain("/api/ticker/GREE");
  });

  it("is noindex", async () => {
    stub404(RETIRED);
    const meta = await generateMetadata({ params: Promise.resolve({ symbol: "GREE" }) });
    expect(meta.robots).toEqual({ index: false, follow: true });
    expect(meta.description).toBe(RETIRED);
    expect(String(meta.title)).toContain("No longer trading");
  });

  it("leaves any other 404 to notFound()", async () => {
    stub404("Ticker ZZZZ not in scanner universe");
    await expect(
      PublicTickerPage({ params: Promise.resolve({ symbol: "ZZZZ" }) }),
    ).rejects.toThrow();
  });
});

describe("the retirement scope change is on the changelog", () => {
  // Shipped copy only: comments stripped, so an explanatory comment cannot
  // satisfy the check.
  const src = readFileSync(path.resolve(__dirname, "..", "app/changelog/page.tsx"), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
  const title = 'title: "Tickers that stop trading are retired instead of staying ranked"';

  it("is a dated scope entry that names GREE and what leaves", () => {
    const at = src.indexOf(title);
    expect(at, "no changelog entry for the retirement change").toBeGreaterThan(-1);
    const e = src.slice(src.lastIndexOf("{", at), src.indexOf("},", at));
    expect(e).toMatch(/date: "2026-09-19"/);
    expect(e).toMatch(/kind: "scope"/);
    expect(e).toMatch(/GREE[^.]*renamed VIP on 24 July 2026/);
    expect(e).toMatch(/can no longer be listed on the daily record/);
    expect(e).toMatch(/known only after the first complete pass/);
    expect(e).toMatch(/No recorded entry was changed/);
    for (const banned of [/\blive\b/i, /real[\s-]?time/i, /no delay/i, /\bfrozen\b/i, /append[\s-]only/i]) {
      expect(e).not.toMatch(banned);
    }
  });
});
