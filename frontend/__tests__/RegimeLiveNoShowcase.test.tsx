/**
 * The live /market-regime card must never borrow the showcase's numbers.
 *
 * `fetchRegime` filled every missing field from SHOWCASE and still returned
 * `live: true`, so an API answer carrying a regime label but no VIX rendered
 * "17.26" beneath a heading that reads "Cached snapshot — refreshes hourly."
 * That figure is not a measurement of anything; it is placeholder copy written
 * to make the offline example look populated. The offline path is honest —
 * it says "Snapshot example" — but the live path made the same numbers a
 * claim about the market right now.
 *
 * These assert RENDERED OUTPUT for a partial API response: the showcase
 * constants must not appear anywhere on the page.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/components/SeoFeaturePage", () => ({
  SeoFeaturePage: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  FEATURE_PAGES: [],
  STRATEGY_LINKS: [],
}));

import MarketRegimePage from "@/app/market-regime/page";

/** Values that exist only in the offline SHOWCASE constant. */
const SHOWCASE_NUMBERS = ["17.26", "57.4", "4.47"];

function mockRegime(body: unknown | "reject") {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      if (body === "reject") throw new Error("ECONNREFUSED");
      return { ok: true, status: 200, json: async () => body } as unknown as Response;
    }),
  );
}

async function renderPage() {
  return render(await MarketRegimePage());
}

describe("/market-regime live path", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders an em-dash for every reading the API omitted", async () => {
    mockRegime({ available: true, regime: "BEAR" });
    const { container } = await renderPage();

    expect(screen.getByText("BEAR")).toBeInTheDocument();
    for (const n of SHOWCASE_NUMBERS) {
      expect(container.textContent ?? "").not.toContain(n);
    }
    // Four KPI tiles + the Fear & Greed figure + sector leaders, all absent.
    const dashes = (container.textContent ?? "").match(/—/g) ?? [];
    expect(dashes.length).toBeGreaterThanOrEqual(5);
  });

  it("does not colour a missing Fear & Greed as though it were a reading", async () => {
    mockRegime({ available: true, regime: "NEUTRAL" });
    const { container } = await renderPage();

    expect(screen.getByText("No reading held")).toBeInTheDocument();
    // text-down is the sub-25 "Extreme Fear" tone. A missing score is not
    // extreme fear — that is what `?? 0` upstream would have made it.
    expect(container.querySelectorAll(".text-down, .text-warn, .text-up").length).toBe(0);
  });

  it("still renders every reading the API did return", async () => {
    mockRegime({
      available: true,
      regime: "BULL",
      vix: 12.5,
      breadth_pct: 63.2,
      yield_10y: 4.1,
      rate_direction: "FALLING",
      fear_greed: { score: 80, label: "Extreme Greed" },
      sector_leaders: "Energy · Utilities",
    });
    const { container } = await renderPage();
    const text = container.textContent ?? "";

    expect(text).toContain("12.50");
    expect(text).toContain("63.2%");
    expect(text).toContain("4.10%");
    expect(text).toContain("FALLING");
    expect(text).toContain("Extreme Greed");
    expect(text).toContain("Energy · Utilities");
  });

  it("labels the advancer count for what it measures, not a 200DMA", async () => {
    mockRegime({ available: true, regime: "NEUTRAL", breadth_pct: 55.0 });
    const { container } = await renderPage();

    expect(container.textContent ?? "").toMatch(/Advancers today/i);
    expect(container.textContent ?? "").not.toMatch(/200\s*DMA|200-day/i);
  });

  it("keeps the showcase on the OFFLINE path, where the page calls it an example", async () => {
    mockRegime("reject");
    const { container } = await renderPage();

    // A worked example is honest as long as the page says that is what it is.
    expect(container.textContent ?? "").toContain("Snapshot example");
  });
});
