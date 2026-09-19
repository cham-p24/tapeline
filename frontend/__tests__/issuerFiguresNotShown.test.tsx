/**
 * A note, preferred or warrant does not show its issuer's company figures.
 *
 * The backend blanks market cap, beta, P/E, EPS and dividend yield for such a
 * listing and ships `is_non_common` so the key-statistics card can say why;
 * the Financials endpoint answers `reason: "non_common"` instead of fetching
 * the issuer's financials. These pin the two pieces of copy that explain it,
 * and that a common stock shows neither. Descriptive only: no "risk", no
 * "avoid", no judgement of the listing.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const financialsMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { tickerFinancials: (s: string) => financialsMock(s) },
}));

import { FinancialsTab } from "@/components/FinancialsTab";
import { KeyStatistics } from "@/components/KeyStatistics";

const BANNED = ["risk", "avoid", "warning", "caution", "beware", "not suitable"];

beforeEach(() => financialsMock.mockReset());

describe("key statistics on a flagged listing", () => {
  it("says why the company-wide figures are empty", () => {
    render(<KeyStatistics stats={{ is_non_common: true, market_cap: null, pe_ttm: null }} />);
    const text = document.body.textContent ?? "";
    expect(text).toMatch(/not the company.s common stock/);
    expect(text).toMatch(/belong to the issuer, so they are not shown here/);
    for (const w of BANNED) expect(text.toLowerCase()).not.toContain(w);
  });

  it("says nothing of the kind on a common stock", () => {
    render(<KeyStatistics stats={{ is_non_common: false, market_cap: 1e9 }} />);
    expect(document.body.textContent ?? "").not.toMatch(/belong to the issuer/);
  });
});

describe("the Financials tab on a flagged listing", () => {
  it("explains instead of showing the issuer's financials", async () => {
    financialsMock.mockResolvedValue({
      symbol: "AGNCO", available: false, metrics: {}, reason: "non_common",
    });
    render(<FinancialsTab symbol="AGNCO" />);
    await waitFor(() =>
      expect(screen.getByText(/Not shown for AGNCO/)).toBeInTheDocument(),
    );
    const text = document.body.textContent ?? "";
    expect(text).toMatch(/are its issuer.s, not its own/);
    // Not the generic "no coverage" line, which blames ETFs and ADRs.
    expect(text).not.toMatch(/No fundamentals coverage/);
    for (const w of BANNED) expect(text.toLowerCase()).not.toContain(w);
  });

  it("keeps the no-coverage line for a listing with no reason", async () => {
    financialsMock.mockResolvedValue({ symbol: "SPY", available: false, metrics: {} });
    render(<FinancialsTab symbol="SPY" />);
    await waitFor(() =>
      expect(screen.getByText(/No fundamentals coverage for SPY/)).toBeInTheDocument(),
    );
  });
});
