/**
 * /short-squeeze-scanner must never show invented squeeze rows.
 *
 * Production (2026-09-14) held 15 squeeze rows written by a mock tick on
 * 2026-07-18 — FCX 92, BKNG 91, SO 88, T 88, DUK 84 were the public top five —
 * and the page labelled them "Live preview · top 5". When the API returned
 * nothing it fell back to a hardcoded SHOWCASE_ROWS table (AMD, PLTR, NVDA,
 * META, INTC). The backend now serves only publishable rows, and this page
 * renders an honest empty state for an empty list, an HTTP error or a network
 * failure alike.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import ShortSqueezeScannerPage, { metadata } from "@/app/short-squeeze-scanner/page";

const EMPTY =
  "No squeeze data right now. We don't have a live source for this list, so we aren't showing one.";

const INVENTED_TICKERS = ["FCX", "BKNG", "DUK", "AMD", "PLTR", "NVDA", "META", "INTC"];

function mockFetch(result: { ok: boolean; body?: unknown } | "reject") {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      if (result === "reject") throw new Error("ECONNREFUSED");
      return {
        ok: result.ok,
        status: result.ok ? 200 : 503,
        json: async () => result.body,
      } as unknown as Response;
    }),
  );
}

async function renderPage() {
  return render(await ShortSqueezeScannerPage());
}

describe("/short-squeeze-scanner", () => {
  afterEach(() => vi.unstubAllGlobals());

  it.each([
    ["an empty list", { ok: true, body: { count: 0, items: [] } }],
    ["an HTTP error", { ok: false, body: {} }],
    ["a network failure", "reject"],
  ] as const)("renders the empty state for %s, with no invented rows", async (_label, result) => {
    mockFetch(result as { ok: boolean; body?: unknown } | "reject");
    const { container } = await renderPage();
    const text = container.textContent ?? "";

    expect(screen.getByTestId("squeeze-empty-state")).toHaveTextContent(EMPTY);
    expect(container.querySelector("table")).toBeNull();
    for (const t of INVENTED_TICKERS) {
      expect(text).not.toMatch(new RegExp(String.raw`\b${t}\b`));
    }
    expect(text).not.toMatch(/Live preview/i);
    expect(text).not.toMatch(/\blive snapshot\b/i);
    expect(text).not.toMatch(/refreshed every 5 minutes/i);
    expect(text).not.toContain("6,900");
    expect(text).not.toMatch(/congress/i);
    expect(text).not.toMatch(/\$\d/);
  });

  it("renders a real row with its write time and no Live label", async () => {
    mockFetch({
      ok: true,
      body: {
        count: 1,
        items: [
          {
            symbol: "REALX",
            spike_score: 81.4,
            squeeze_days: 6,
            volume_multiple: 1.7,
            obv_trend: "RISING",
            breakout_type: "bullish",
            reason: "Tight range.",
            updated_at: "2026-09-14T13:05:00+00:00",
          },
        ],
      },
    });
    const { container } = await renderPage();
    const text = container.textContent ?? "";

    expect(screen.getByText("REALX")).toBeInTheDocument();
    // en-GB renders the month as "Sep" or "Sept" depending on the ICU version.
    expect(text).toMatch(/updated 14 Sept? 2026, 13:05 UTC/);
    expect(screen.queryByTestId("squeeze-empty-state")).toBeNull();
    expect(text).not.toMatch(/Live preview/i);
  });

  it("is noindex while no data source exists", () => {
    const robots = metadata.robots as { index?: boolean; googleBot?: { index?: boolean } };
    expect(robots.index).toBe(false);
    expect(robots.googleBot?.index).toBe(false);
  });
});
