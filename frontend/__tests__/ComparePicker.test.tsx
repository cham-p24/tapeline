/**
 * ComparePicker — the two-ticker tool at the top of /compare.
 *
 * Contract:
 *   - Compare routes to the ONE canonical matchup URL (alphabetical, lowercase),
 *     whatever order or case the tickers were typed in, so the visitor never
 *     takes the 308 hop from /compare/msft-vs-aapl.
 *   - Enter in a field submits; Enter on a highlighted suggestion picks it.
 *   - Same ticker twice, or a blank side, does not navigate.
 *   - The typeahead lists stocks before funds and never offers a crypto symbol
 *     (a namespaced "X:BTCUSD" cannot live in a slug).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const router = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/compare",
}));

const searchMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ api: { search: searchMock } }));

import { ComparePicker } from "@/components/ComparePicker";

function first() {
  return screen.getByRole("combobox", { name: "First ticker" });
}
function second() {
  return screen.getByRole("combobox", { name: "Second ticker" });
}

beforeEach(() => {
  router.push.mockReset();
  searchMock.mockReset();
  searchMock.mockResolvedValue({ results: [] });
});

describe("ComparePicker", () => {
  it("routes to the canonical slug regardless of typed order and case", async () => {
    const user = userEvent.setup();
    render(<ComparePicker suggestions={[]} />);
    await user.type(first(), "msft");
    await user.type(second(), " aapl ");
    await user.click(screen.getByRole("button", { name: /^Compare/ }));
    expect(router.push).toHaveBeenCalledTimes(1);
    expect(router.push).toHaveBeenCalledWith("/compare/aapl-vs-msft");
  });

  it("submits on Enter from a field", async () => {
    const user = userEvent.setup();
    render(<ComparePicker suggestions={[]} />);
    await user.type(first(), "XOM");
    await user.type(second(), "cvx{Enter}");
    expect(router.push).toHaveBeenCalledWith("/compare/cvx-vs-xom");
  });

  it("swaps the two fields", async () => {
    const user = userEvent.setup();
    render(<ComparePicker suggestions={[]} />);
    await user.type(first(), "KO");
    await user.type(second(), "PEP");
    await user.click(screen.getByRole("button", { name: "Swap the two tickers" }));
    expect(first()).toHaveValue("PEP");
    expect(second()).toHaveValue("KO");
  });

  it("does not navigate for the same ticker twice or a blank side", async () => {
    const user = userEvent.setup();
    render(<ComparePicker suggestions={[]} />);
    await user.type(first(), "NVDA");
    await user.click(screen.getByRole("button", { name: /^Compare/ }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter two tickers to compare.");
    await user.type(second(), "nvda");
    await user.click(screen.getByRole("button", { name: /^Compare/ }));
    expect(screen.getByRole("alert")).toHaveTextContent("Pick two different tickers.");
    expect(router.push).not.toHaveBeenCalled();
  });

  it("picks a suggestion with the keyboard, stocks ahead of funds, no crypto", async () => {
    searchMock.mockResolvedValue({
      results: [
        { symbol: "MSFX", name: "T-Rex 2X Long Microsoft Daily Target ETF", sector: "Funds & ETFs", score: 50, asset_class: "etf" },
        { symbol: "X:MSCUSD", name: "Micro Coin", sector: null, score: null, asset_class: "crypto", is_crypto: true },
        { symbol: "MSFT", name: "Microsoft Corp.", sector: "Information Technology", score: 62, asset_class: "equity" },
      ],
    });
    const user = userEvent.setup();
    render(<ComparePicker suggestions={[]} />);
    await user.type(first(), "micro");

    const options = await screen.findAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual([
      expect.stringContaining("MSFT"),
      expect.stringContaining("MSFX"),
    ]);

    await user.keyboard("{ArrowDown}{Enter}");
    expect(first()).toHaveValue("MSFT");
    expect(screen.getByText("Microsoft Corp.")).toBeInTheDocument(); // the pick's name hint
    expect(router.push).not.toHaveBeenCalled(); // Enter picked, it did not submit

    searchMock.mockResolvedValue({ results: [] });
    await user.type(second(), "aapl{Enter}");
    expect(router.push).toHaveBeenCalledWith("/compare/aapl-vs-msft");
  });

  it("links the suggested pairs to their canonical pages", () => {
    render(<ComparePicker suggestions={[{ a: "NVDA", b: "AMD" }]} />);
    expect(screen.getByRole("link", { name: /NVDA\s*vs\s*AMD/ })).toHaveAttribute("href", "/compare/amd-vs-nvda");
  });
});
