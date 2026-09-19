/**
 * /compare index — the stock-vs-stock hub.
 *
 * Contract pinned here:
 *   1. Every curated matchup (lib/comparePairs allComparePairs) is linked from
 *      the server render, exactly once in the by-theme directory. These are the
 *      cluster's SEO entry points; a redesign that drops one silently orphans
 *      a page the sitemap still advertises.
 *   2. The featured head-to-head shows ONLY numbers the ticker API returned.
 *      When the API fails, the preview is absent — no placeholder score, no
 *      "—/100" card, nothing.
 *   3. A pair whose read fails is dropped on its own; the rest still render.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));

import CompareIndexPage from "@/app/compare/page";
import { CompareFeatured } from "@/components/CompareFeatured";
import { allComparePairs, canonicalMatchup } from "@/lib/comparePairs";

type Payload = { score: number | null; name: string; breakdown?: Record<string, { value: number | null; label: string }> };

function tickerPayload(symbol: string, p: Payload) {
  return {
    symbol,
    name: p.name,
    sector: "Information Technology",
    price: 100,
    score: p.score,
    signal: "CONSTRUCTIVE",
    change_pct_1d: 0,
    reason: null,
    breakdown: p.breakdown ?? {
      trend: { value: 81, label: "Trend" },
      rs: { value: 47, label: "Relative strength" },
      fundamentals: { value: 73, label: "Fundamentals" },
      smart_money: { value: null, label: "Smart money" },
      macro: { value: 50, label: "Macro" },
      momentum: { value: 64, label: "Momentum" },
    },
  };
}

/**
 * Answers /api/ticker/{SYM} from `bySymbol`; a symbol missing from the map
 * gets a network error (the transient-failure path, retried then dropped).
 */
function stubTickerApi(bySymbol: Record<string, Payload>) {
  const fetchMock = vi.fn(async (url: string) => {
    const m = String(url).match(/\/api\/ticker\/([A-Z.]+)/);
    const sym = m?.[1];
    if (sym && bySymbol[sym]) {
      return { ok: true, status: 200, json: async () => tickerPayload(sym, bySymbol[sym]) } as unknown as Response;
    }
    throw new TypeError("fetch failed");
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function renderPage() {
  return render(await CompareIndexPage());
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("/compare index — matchup links", () => {
  it("links every curated pair exactly once in the by-theme directory", async () => {
    stubTickerApi({});
    await renderPage();

    const directory = screen.getByRole("region", { name: "Head-to-heads by theme" });
    const hrefs = within(directory)
      .getAllByRole("link")
      .map((a) => a.getAttribute("href") ?? "")
      .filter((h) => h.startsWith("/compare/"));

    const expected = allComparePairs().map(({ a, b }) => `/compare/${canonicalMatchup(a, b)}`);
    expect(expected.length).toBeGreaterThan(100); // guards a vacuous pass
    expect(new Set(hrefs)).toEqual(new Set(expected));
    expect(hrefs).toHaveLength(expected.length); // no pair printed twice
  });
});

describe("/compare index — featured head-to-head", () => {
  it("renders nothing — and no numbers — when the ticker API fails", async () => {
    const fetchMock = stubTickerApi({});
    const { container } = await renderPage();

    // The preview did try to read (so this is not passing by never fetching)…
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/api/ticker/"))).toBe(true);
    // …and, with every read failed, left no trace on the page.
    expect(screen.queryByTestId("compare-featured")).toBeNull();
    expect(screen.queryByText(/^composite score$/i)).toBeNull(); // the score-card label
    expect(screen.queryByText(/higher composite score/)).toBeNull();
    expect(container.textContent).not.toMatch(/\/100/);
  });

  it("the preview component itself renders nothing for an empty list", () => {
    // Belt and braces with the page's own guard: whatever calls it, no data
    // means no card — never a skeleton with placeholder figures.
    const { container } = render(<CompareFeatured matchups={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the API's own numbers when the read succeeds", async () => {
    stubTickerApi({
      AAPL: { score: 63.4, name: "Apple Inc." },
      MSFT: { score: 58.2, name: "Microsoft Corp." },
    });
    await renderPage();

    const featured = screen.getByTestId("compare-featured");
    expect(within(featured).getByText("63")).toBeInTheDocument();
    expect(within(featured).getByText("58")).toBeInTheDocument();
    expect(within(featured).getByText(/carries the higher composite score/)).toHaveTextContent(
      "AAPL carries the higher composite score today (63 vs 58).",
    );
    // A factor the API holds no reading for is an em-dash, never a 0.
    const table = within(featured).getByRole("table");
    const smartMoney = within(table).getByRole("row", { name: /Smart Money/ });
    expect(smartMoney).toHaveTextContent("Smart Money——");
    // Descriptive framing only.
    expect(featured.textContent).not.toMatch(/\b(buy|sell|winner|wins)\b/i);
    expect(within(featured).getByRole("link", { name: /Full AAPL vs MSFT breakdown/ })).toHaveAttribute(
      "href",
      "/compare/aapl-vs-msft",
    );
  });

  it("drops only the pair whose read failed, and a pair with a null composite", async () => {
    stubTickerApi({
      AAPL: { score: 63, name: "Apple Inc." },
      MSFT: { score: 58, name: "Microsoft Corp." },
      AMD: { score: 55, name: "Advanced Micro Devices" },
      // NVDA missing → network error → AMD vs NVDA dropped.
      BAC: { score: null, name: "Bank of America" }, // null composite → BAC vs JPM dropped
      JPM: { score: 57, name: "JPMorgan Chase" },
      KO: { score: 52, name: "Coca-Cola" },
      PEP: { score: 49, name: "PepsiCo" },
    });
    await renderPage();

    const tabs = within(screen.getByTestId("compare-featured")).getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(["AAPL · MSFT", "KO · PEP"]);
  });
});
