/**
 * /t/[symbol] — the largest surface in the product, and the least quotable.
 *
 * ~3,516 of 3,875 sitemap URLs are per-ticker pages, and they produce ZERO
 * unbranded AI citations; eleven /best-stocks-for/ pages produce all of it.
 * Three things the sources that DO get cited have were missing here:
 *
 *   1. The h1 was the bare ticker. "AAPL" identifies nothing to a reader who
 *      searched for Apple, and the heading is the first string an answer
 *      engine reaches for when it attributes a figure.
 *   2. The score existed only as a numeral in a box. A model can quote a
 *      sentence; it cannot quote a layout.
 *   3. There was no freshness statement of any kind on the page, and the only
 *      machine-readable one — `article:modified_time` — was `new Date()`,
 *      i.e. a claim about our data derived from a fact about our ISR cache.
 *
 * Everything asserted here is pinned against the SCORE'S OWN `updated_at`.
 * The freshness half of this change is worthless if it can be satisfied by
 * render time, so the negative assertions matter as much as the positive ones:
 * no stamp on the row must produce no date anywhere, not today's date.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));
vi.mock("@/components/NewsletterCapture", () => ({ NewsletterCapture: () => null }));
vi.mock("@/components/AnonSignupNudge", () => ({ AnonSignupNudge: () => null }));
vi.mock("@/components/ScoreSparkline", () => ({ ScoreSparkline: () => null }));

import PublicTickerPage, { generateMetadata } from "@/app/t/[symbol]/page";
import { tickerDatasetJsonLd } from "@/lib/jsonld";

/** A fixed, unambiguous instant. Deliberately NOT near "now". */
const SCORED_AT = "2026-03-04T21:15:00+00:00";
const SCORED_DAY = "4 March 2026";

function tickerPayload(overrides: Record<string, unknown> = {}) {
  return {
    symbol: "CITECO",
    name: "Citable Industries Inc",
    sector: "Information Technology",
    asset_class: "stock",
    price: 44.5,
    score: 76.4,
    signal: "STRONG SETUP",
    confidence_pct: 71,
    change_pct_1d: 0.8,
    change_pct_5d: null,
    change_pct_1m: null,
    volume: 1_000_000,
    reason: "Trend and relative strength both read above their peer medians.",
    breakdown: {
      trend: { value: 81, label: "Trend" },
      rs: { value: 74, label: "Relative strength" },
      // Two null factors — the em-dash case the counted locks must never touch.
      fundamentals: { value: null, label: "Fundamentals" },
      smart_money: { value: null, label: "Smart money" },
      macro: { value: 55, label: "Macro" },
      momentum: { value: 60, label: "Momentum" },
    },
    key_stats: null,
    peer_percentiles: null,
    updated_at: SCORED_AT,
    gated_counts: { insider_form4: 0, insider_form4_window_days: 90 },
    ...overrides,
  };
}

function mockUpstream(payload: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (String(url).includes("/api/ticker/")) {
        return { ok: true, status: 200, json: async () => payload } as unknown as Response;
      }
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
  return render(await PublicTickerPage({ params: Promise.resolve({ symbol: "citeco" }) }));
}

/** The Dataset JSON-LD graph the page inlines, parsed back out of the DOM. */
function datasetGraph(container: HTMLElement): Record<string, unknown> {
  const scripts = Array.from(
    container.querySelectorAll('script[type="application/ld+json"]'),
  );
  for (const s of scripts) {
    const parsed = JSON.parse(s.innerHTML) as Record<string, unknown>;
    if (parsed["@type"] === "Dataset") return parsed;
  }
  throw new Error("no Dataset JSON-LD on the page");
}

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe("the heading names the company, not just the ticker", () => {
  it("puts the company name and the symbol in the h1", async () => {
    const { container } = await renderTicker(tickerPayload());
    const h1 = container.querySelector("h1")!;
    expect(h1.textContent).toContain("Citable Industries Inc");
    expect(h1.textContent).toContain("CITECO");
  });

  it("falls back to the bare symbol when the name is still a placeholder", async () => {
    // Discovery writes name = symbol for tickers the profile backfill hasn't
    // reached. "CITECO (CITECO)" would be worse than the bare ticker.
    const { container } = await renderTicker(tickerPayload({ name: "CITECO" }));
    expect(container.querySelector("h1")!.textContent!.trim()).toBe("CITECO");
  });
});

describe("the score is restated as a quotable sentence", () => {
  it("carries company, ticker, number, denominator, band and date in one passage", async () => {
    const { container } = await renderTicker(tickerPayload());
    const text = container.querySelector('[data-testid="score-restatement"]')!
      .textContent!;

    expect(text).toContain("Citable Industries Inc");
    expect(text).toContain("CITECO");
    expect(text).toContain("76 out of 100");
    expect(text).toContain("STRONG SETUP");
    // The band is explained, not just named — a quote of this sentence alone
    // has to survive without the rest of the page.
    expect(text).toContain("70 to 84");
    expect(text).toContain(SCORED_DAY);
  });

  it("stays descriptive — a measurement, never a judgement or expectation", async () => {
    const { container } = await renderTicker(tickerPayload());
    const text = container.querySelector('[data-testid="score-restatement"]')!
      .textContent!;

    expect(text).toMatch(/not investment advice/i);
    expect(text).not.toMatch(
      /\b(buy|sell|recommend\w*|should|outperform\w*|beat the market|winner|undervalued|poised|attractive|promising)\b/i,
    );
  });

  it("says we hold no score rather than restating a fabricated one", async () => {
    const { container } = await renderTicker(
      tickerPayload({ score: null, signal: null }),
    );
    const text = container.querySelector('[data-testid="score-restatement"]')!
      .textContent!;

    expect(text).toMatch(/no six-factor composite score/i);
    expect(text).not.toMatch(/\b0 out of 100\b/);
  });

  it("carries no date at all when the ticker row has no stamp", async () => {
    // Not today's date. This route is ISR'd hourly; a render-time date would
    // be a freshness claim about the cache.
    const { container } = await renderTicker(tickerPayload({ updated_at: null }));
    const text = container.querySelector('[data-testid="score-restatement"]')!
      .textContent!;

    expect(text).toContain("76 out of 100");
    expect(text).not.toMatch(/\bAs of\b/);
    const thisYear = String(new Date().getUTCFullYear());
    expect(text).not.toContain(thisYear);
  });
});

describe("freshness is stated once, from the score's own stamp", () => {
  it("renders a visible Updated line with a machine-readable datetime", async () => {
    const { container } = await renderTicker(tickerPayload());
    const time = container.querySelector("time[datetime]")!;

    expect(time.getAttribute("datetime")).toBe(SCORED_AT);
    expect(time.textContent).toBe(SCORED_DAY);
    expect(container.textContent).toContain(`Updated ${SCORED_DAY}`);
  });

  it("emits dateModified on the Dataset JSON-LD, equal to that same instant", async () => {
    const { container } = await renderTicker(tickerPayload());
    expect(datasetGraph(container).dateModified).toBe(SCORED_AT);
  });

  it("omits both halves when there is no stamp, rather than inventing one", async () => {
    const { container } = await renderTicker(tickerPayload({ updated_at: null }));

    expect(container.textContent).not.toContain("Updated ");
    expect(datasetGraph(container)).not.toHaveProperty("dateModified");
  });

  it("never emits a render-time article:modified_time", async () => {
    // The original bug: `new Date().toISOString()`, on every one of ~3,500
    // pages, whenever the ISR cache happened to turn over.
    mockUpstream(tickerPayload());
    const meta = await generateMetadata({
      params: Promise.resolve({ symbol: "citeco" }),
    });
    expect(meta.other?.["article:modified_time"]).toBe(SCORED_AT);

    mockUpstream(tickerPayload({ updated_at: null }));
    const bare = await generateMetadata({
      params: Promise.resolve({ symbol: "citeco" }),
    });
    expect(bare.other?.["article:modified_time"]).toBeUndefined();
  });
});

describe("tickerDatasetJsonLd only claims freshness it was given", () => {
  const base = {
    symbol: "CITECO",
    name: "Citable Industries Inc",
    url: "https://tapeline.io/t/CITECO",
    score: 76,
    signal: "STRONG SETUP",
    why: null,
  };

  it("emits dateModified when handed one", () => {
    expect(tickerDatasetJsonLd({ ...base, updatedAt: SCORED_AT }).dateModified).toBe(
      SCORED_AT,
    );
  });

  it("omits the key entirely when handed null", () => {
    expect(tickerDatasetJsonLd({ ...base, updatedAt: null })).not.toHaveProperty(
      "dateModified",
    );
  });
});
