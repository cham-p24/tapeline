/**
 * /t/[symbol] — the public ticker page, for a ticker we hold NO composite for.
 *
 * The bug pinned here: `const score = data.score ?? 0` was declared for a tier
 * COLOUR and then leaked into the pre-filled "Share on X" text, so the share
 * link for a ticker with no score read "$SYM score: 0/100" — a specific,
 * quotable claim we never measured, published to a third party. The signed-in
 * /app/ticker/[symbol] page had already been fixed; this one had not.
 *
 * Contract:
 *   1. The share text carries an em-dash, never "0/100".
 *   2. The on-page composite is an em-dash (unchanged, guarded here so the two
 *      surfaces can't drift apart again).
 *   3. A real measured 0 still shares as "0/100" — zero is a measurement.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));
vi.mock("@/components/NewsletterCapture", () => ({ NewsletterCapture: () => null }));
vi.mock("@/components/AnonSignupNudge", () => ({ AnonSignupNudge: () => null }));
vi.mock("@/components/ScoreSparkline", () => ({ ScoreSparkline: () => null }));

import PublicTickerPage from "@/app/t/[symbol]/page";

function tickerPayload(overrides: Record<string, unknown> = {}) {
  return {
    symbol: "NULLCO",
    name: "Null Co",
    sector: "Information Technology",
    asset_class: "stock",
    price: null,
    score: null,
    signal: null,
    confidence_pct: null,
    change_pct_1d: null,
    change_pct_5d: null,
    change_pct_1m: null,
    volume: null,
    reason: null,
    breakdown: {},
    key_stats: null,
    peer_percentiles: null,
    ...overrides,
  };
}

/** Answers the ticker fetch; every other upstream call returns an empty set. */
function mockUpstream(payload: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (String(url).includes("/api/ticker/")) {
        return { ok: true, status: 200, json: async () => payload } as unknown as Response;
      }
      // Related tickers (/api/scanner) and news (/api/news).
      return {
        ok: true,
        status: 200,
        json: async () => ({ items: [], articles: [] }),
      } as unknown as Response;
    }),
  );
}

async function renderTicker(payload: Record<string, unknown>) {
  mockUpstream(payload);
  return render(await PublicTickerPage({ params: Promise.resolve({ symbol: "nullco" }) }));
}

/** The pre-filled tweet, decoded out of the intent URL. */
function shareText(container: HTMLElement): string {
  const link = container.querySelector<HTMLAnchorElement>(
    'a[href^="https://twitter.com/intent/tweet"]',
  )!;
  const params = new URLSearchParams(link.getAttribute("href")!.split("?")[1]);
  return params.get("text") ?? "";
}

describe("/t/[symbol] share text for a ticker with no score", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shares an em-dash, never a fabricated 0/100", async () => {
    const { container } = await renderTicker(tickerPayload());
    const text = shareText(container);

    expect(text).toContain("$NULLCO score: —/100");
    expect(text).not.toContain("0/100");
    // The signal is unknown too — it must not be asserted either.
    expect(text).toContain("(—)");
  });

  it("keeps the on-page composite as an em-dash, matching the share text", async () => {
    const { container } = await renderTicker(tickerPayload());
    // The big composite number (the "/ 100" denominator rides along in the
    // same block).
    const big = container.querySelector(".text-6xl")!;
    expect(big.textContent!.trim().startsWith("—")).toBe(true);
    expect(big.textContent).not.toMatch(/^\s*0/);
    expect(shareText(container)).toContain("—/100");
  });

  it("still shares a REAL measured 0 as 0/100", async () => {
    const { container } = await renderTicker(
      tickerPayload({ score: 0, signal: "AVOID" }),
    );
    const text = shareText(container);
    // Zero is a measurement; only the unknown becomes an em-dash.
    expect(text).toContain("$NULLCO score: 0/100");
    expect(text).toContain("(AVOID)");
  });

  it("shares the held score unchanged when we have one", async () => {
    const { container } = await renderTicker(
      tickerPayload({ score: 84.6, signal: "HIGH CONVICTION" }),
    );
    expect(shareText(container)).toContain("$NULLCO score: 85/100 (HIGH CONVICTION)");
  });
});
