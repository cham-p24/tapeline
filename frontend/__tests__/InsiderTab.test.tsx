/**
 * The Premium Insider tab on a ticker page.
 *
 * The backend caps the tab at 2,000 lines and says so with `truncated`
 * (backend/app/routers/ticker.py). Before, it cut at 500 with no flag while the
 * lock above counted every line (CRWV held 938), so the tab silently showed
 * fewer lines than the count promised.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", () => ({ api: { tickerInsider: vi.fn() } }));

import { InsiderTab } from "@/components/InsiderTab";
import { api } from "@/lib/api";

const mocked = api.tickerInsider as ReturnType<typeof vi.fn>;

function line(code: string, share_change: number) {
  return {
    filer_name: "DOE JANE", transaction_date: "2026-09-01",
    share_change, transaction_price: 10, code,
  };
}

describe("InsiderTab", () => {
  beforeEach(() => mocked.mockReset());

  it("says when the window held more lines than it lists", async () => {
    mocked.mockResolvedValue({
      symbol: "CRWV", days_back: 90, truncated: true,
      transactions: [line("S", -100), line("S", -200)],
    });
    render(<InsiderTab symbol="CRWV" />);
    const note = await waitFor(() => screen.getByTestId("insider-truncated"));
    expect(note.textContent).toMatch(/Showing the newest 2 Form 4\s+transactions for CRWV in the last 90 days/);
  });

  it("adds no note when every line is listed", async () => {
    mocked.mockResolvedValue({
      symbol: "AAPL", days_back: 90, truncated: false, transactions: [line("P", 100)],
    });
    render(<InsiderTab symbol="AAPL" />);
    await waitFor(() => screen.getByText("Buy (P)"));
    expect(screen.queryByTestId("insider-truncated")).toBeNull();
  });

  it("says a preferred or note never lists filings, rather than calling empty normal", async () => {
    // Since 2026-09-19 a company's filings are listed under every class of
    // its common stock (GOOG and GOOGL alike) and under none of its preferred
    // shares, notes or ETNs. #862's note - "listed under the ticker it names",
    // "may sit under another of its tickers" - became false with that change.
    mocked.mockResolvedValue({
      symbol: "STRK", days_back: 90, truncated: false, transactions: [],
    });
    render(<InsiderTab symbol="STRK" />);
    const note = await waitFor(() => screen.getByText(/No Form 4 filings for STRK/));
    expect(note.textContent).toMatch(/listed under every class of its common\s+stock/);
    expect(note.textContent).toMatch(/never under its preferred shares, notes, warrants, rights, units\s+or exchange-traded notes/);
    expect(note.textContent).not.toMatch(/the ticker it names/);
    expect(note.textContent).not.toMatch(/another of its tickers/);
    expect(note.textContent).not.toMatch(/Empty here is normal/);
  });

  it("does not call a code it has no label for a buy or a sale", async () => {
    mocked.mockResolvedValue({
      symbol: "AAPL", days_back: 90, truncated: false,
      transactions: [line("J", 300), line("D", -400)],
    });
    render(<InsiderTab symbol="AAPL" />);
    await waitFor(() => screen.getByText("Acquired"));
    expect(screen.getByText("Disposed")).toBeInTheDocument();
    expect(screen.queryByText("Buy")).toBeNull();
    expect(screen.queryByText("Sell")).toBeNull();
  });
});
