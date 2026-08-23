/**
 * FinancialsTab metric hints must describe the fallback chain the backend
 * actually reads.
 *
 * finnhub_feed.fetch_metrics (backend/app/services/finnhub_feed.py:691-692):
 *
 *   "pe":     metric["peNormalizedAnnual"]     or metric["peTTM"]
 *   "margin": metric["netProfitMarginAnnual"]  or metric["netProfitMarginTTM"]
 *
 * The hints said "Price ÷ trailing EPS" and "Net income ÷ revenue, TTM" — both
 * named the FALLBACK as though it were the primary. For most covered tickers
 * the annual field is present, so the number on screen was the annual one
 * under a TTM label. Fixed to the "X, falls back to Y" phrasing the EPS-growth
 * and revenue-growth hints two lines below already use.
 *
 * The hint is rendered as the tile's `title` attribute, so these assert on the
 * DOM, not on source text.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const financialsMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { tickerFinancials: (s: string) => financialsMock(s) },
}));

import { FinancialsTab } from "@/components/FinancialsTab";

const METRICS = {
  pe: 28.4,
  margin: 24.1,
  roe: 31.2,
  eps_growth: 12.5,
  revenue_growth: 8.3,
  debt_to_equity: 1.42,
};

/** The tile whose visible label is `label`. */
function tile(label: string): HTMLElement {
  const el = screen.getByText(label).closest("[title]");
  if (!el) throw new Error(`no titled tile for ${label}`);
  return el as HTMLElement;
}

beforeEach(() => {
  financialsMock.mockReset();
  financialsMock.mockResolvedValue({ available: true, metrics: METRICS });
});

describe("FinancialsTab hints", () => {
  it("describes P/E as normalized-annual first, TTM as the fallback", async () => {
    render(<FinancialsTab symbol="AAPL" />);
    await waitFor(() => expect(screen.getByText("P/E")).toBeInTheDocument());

    const hint = tile("P/E").getAttribute("title") ?? "";
    expect(hint).toMatch(/normalized annual/i);
    expect(hint).toMatch(/falls back to TTM/i);
    // The old hint claimed the trailing figure was what we show.
    expect(hint).not.toBe("Price ÷ trailing EPS");
    expect(hint).not.toMatch(/trailing EPS/i);
  });

  it("describes net margin as annual first, TTM as the fallback", async () => {
    render(<FinancialsTab symbol="AAPL" />);
    await waitFor(() => expect(screen.getByText("Net margin")).toBeInTheDocument());

    const hint = tile("Net margin").getAttribute("title") ?? "";
    expect(hint).toMatch(/annual/i);
    expect(hint).toMatch(/falls back to TTM/i);
    // Must not label an annual number as TTM outright.
    expect(hint).not.toBe("Net income ÷ revenue, TTM");
  });

  it("leaves the already-correct growth hints alone", async () => {
    render(<FinancialsTab symbol="AAPL" />);
    await waitFor(() => expect(screen.getByText("EPS growth")).toBeInTheDocument());

    expect(tile("EPS growth").getAttribute("title")).toBe(
      "5-year CAGR, falls back to TTM YoY",
    );
    expect(tile("Revenue growth").getAttribute("title")).toBe(
      "5-year CAGR, falls back to TTM YoY",
    );
  });

  it("renders an em-dash for a missing metric, never a zero", async () => {
    financialsMock.mockResolvedValue({
      available: true,
      metrics: { ...METRICS, pe: null, margin: null },
    });
    render(<FinancialsTab symbol="AAPL" />);
    await waitFor(() => expect(screen.getByText("P/E")).toBeInTheDocument());

    // A null P/E is "we don't know", not 0 / 0.00 / 0.0%.
    expect(tile("P/E").textContent).toContain("—");
    expect(tile("P/E").textContent).not.toMatch(/0\.00|0\.0%/);
    expect(tile("Net margin").textContent).toContain("—");
    expect(tile("Net margin").textContent).not.toMatch(/\+?0\.0%/);
  });
});
