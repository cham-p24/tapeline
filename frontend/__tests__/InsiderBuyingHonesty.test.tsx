/**
 * /insider-buying — the public SEC Form 4 landing page.
 *
 * Two things are pinned here, both cases of the page stating something it does
 * not know:
 *
 * 1. INVENTED FILINGS. When the feed was unreachable the page fell back to five
 *    hardcoded rows — real tickers (BRK.B, ORCL, AMD, INTC, DIS), plausible
 *    insiders ("CEO", "CFO", "Director"), specific prices and "3 days ago"
 *    dates — under the label "Recent example". None of them was a filing. On a
 *    page whose H1 reads "Live SEC Form 4 Tracker", that asserts recent
 *    transactions by named public companies that never happened. There is now
 *    no fallback data at all: the page says the feed is unavailable.
 *
 * 2. FABRICATED ZEROS. transaction_price / transaction_value are NOT NULL with
 *    a 0 default in backend/app/models/insider_transaction.py, so a filing the
 *    vendor gave us no price for arrives as a real 0 and printed as "$0.00" /
 *    "$0". /app/holdings has guarded this for a while; this public page did not.
 *
 * The page is an async server component, so each case awaits it and renders the
 * returned tree. The SEO shell is stubbed to its children so the assertions are
 * about the data block, not the chrome.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/components/SeoFeaturePage", () => ({
  SeoFeaturePage: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  FEATURE_PAGES: [],
  STRATEGY_LINKS: [],
}));

import InsiderBuyingPage from "@/app/insider-buying/page";

/** The five invented rows that used to ship whenever the feed was down. */
const INVENTED_SYMBOLS = ["BRK.B", "ORCL", "AMD", "INTC", "DIS"];

type Row = Record<string, unknown>;

function mockFeed(result: "reject" | "http-error" | Row[]) {
  const fetchMock = vi.fn(async () => {
    if (result === "reject") throw new Error("ECONNREFUSED");
    if (result === "http-error") {
      return { ok: false, status: 503, json: async () => ({}) } as unknown as Response;
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({ count: result.length, items: result }),
    } as unknown as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function renderPage() {
  return render(await InsiderBuyingPage());
}

const realRow = {
  symbol: "TSTA",
  insider_name: "SMITH JANE",
  transaction_date: "2026-08-14",
  share_change: 4000,
  transaction_price: 25.5,
  transaction_value: 102000,
  code: "P",
};

describe("/insider-buying — no invented Form 4 filings", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each(["reject", "http-error"] as const)(
    "renders an honest unavailable state (%s), not a table of examples",
    async (mode) => {
      mockFeed(mode);
      const { container } = await renderPage();

      expect(screen.getByTestId("insider-feed-unavailable")).toBeInTheDocument();
      // No table at all — an empty table with headers would still look like a
      // feed that returned nothing, which is a different claim.
      expect(container.querySelector("table")).toBeNull();
      // The label must not call an absent feed a "Recent example".
      expect(container.textContent).not.toMatch(/recent example/i);
      expect(screen.getByTestId("feed-unavailable-label").textContent).toMatch(
        /unavailable/i,
      );
    },
  );

  it("never renders the old hardcoded rows, under any feed outcome", async () => {
    for (const mode of ["reject", "http-error"] as const) {
      mockFeed(mode);
      const { container, unmount } = await renderPage();
      for (const sym of INVENTED_SYMBOLS) {
        expect(container.textContent, `${mode} rendered ${sym}`).not.toContain(sym);
      }
      // The invented prices and relative dates that came with them.
      expect(container.textContent).not.toContain("480.12");
      expect(container.textContent).not.toContain("$24.01M");
      expect(container.textContent).not.toMatch(/\d+ (days|week|weeks) ago/);
      unmount();
    }
  });

  it("renders an empty feed as unavailable rather than as a live snapshot", async () => {
    mockFeed([]);
    const { container } = await renderPage();
    expect(screen.getByTestId("insider-feed-unavailable")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/live preview/i);
  });

  it("renders the real rows, and calls them live, when the feed answers", async () => {
    mockFeed([realRow]);
    const { container } = await renderPage();

    expect(screen.queryByTestId("insider-feed-unavailable")).toBeNull();
    expect(container.querySelector("table")).not.toBeNull();
    expect(container.textContent).toContain("TSTA");
    expect(container.textContent).toContain("SMITH JANE");
    expect(container.textContent).toContain("$25.50");
    expect(container.textContent).toContain("$102K");
    expect(container.textContent).toMatch(/live preview/i);
  });
});

describe("/insider-buying — an omitted figure is an em-dash, not $0.00", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("prints — for a price/value the filing did not give us", async () => {
    mockFeed([
      { ...realRow, symbol: "PRICED" },
      {
        ...realRow,
        symbol: "NOPRICE",
        // The NOT NULL column default standing in for "vendor sent nothing".
        transaction_price: 0,
        transaction_value: 0,
      },
    ]);
    const { container } = await renderPage();

    const rows = [...container.querySelectorAll("tbody tr")];
    expect(rows).toHaveLength(2);

    const priced = rows.find((r) => r.textContent?.includes("PRICED"))!;
    expect(priced.textContent).toContain("$25.50");
    expect(priced.textContent).toContain("$102K");

    const unpriced = rows.find((r) => r.textContent?.includes("NOPRICE"))!;
    // Cell order: ticker, insider, shares, price, value, filed.
    const tds = [...unpriced.querySelectorAll("td")];
    expect(tds[3].textContent).toBe("—");
    expect(tds[4].textContent).toBe("—");
    expect(unpriced.textContent).not.toContain("$0.00");
    expect(unpriced.textContent).not.toContain("$0");
  });

  it("survives a row with fields missing entirely instead of printing NaN", async () => {
    mockFeed([
      {
        symbol: "SPARSE",
        insider_name: "DOE JOHN",
        transaction_date: "2026-08-01",
        code: "P",
      },
    ]);
    const { container } = await renderPage();
    const row = container.querySelector("tbody tr")!;
    expect(row.textContent).toContain("SPARSE");
    expect(row.textContent).not.toContain("NaN");
    expect(row.textContent).not.toContain("undefined");
    const tds = [...row.querySelectorAll("td")];
    expect(tds[2].textContent).toBe("—"); // shares
    expect(tds[3].textContent).toBe("—"); // price
    expect(tds[4].textContent).toBe("—"); // value
  });
});

describe("/insider-buying — the stated refresh cadence matches the code", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not claim a 10-minute refresh on an hourly-revalidated page", async () => {
    mockFeed([realRow]);
    const { container } = await renderPage();
    // `export const revalidate = 3600` — and the upstream fetch uses the same
    // 3600s. "every 10 minutes" was a cadence the page never had.
    expect(container.textContent).not.toMatch(/every 10 minutes/i);
    expect(container.textContent).toMatch(/hourly/i);
  });
});
