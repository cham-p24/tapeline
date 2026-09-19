/**
 * /t/{SYMBOL} for a symbol outside the scored universe.
 *
 * It used to fall through to the site-wide "Not found" page with no way to
 * look up another ticker. It now says "Not covered", names the symbol, and
 * links to /search, while staying a 404 (the page still calls notFound()).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const pathname = vi.hoisted(() => ({ value: "/t/ZZZZQ" as string | null }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.value }));
vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));

import TickerNotCovered from "@/app/t/[symbol]/not-found";
import { requestedSymbol } from "@/components/NotCoveredSymbol";

describe("/t/{SYMBOL} not covered", () => {
  beforeEach(() => {
    pathname.value = "/t/ZZZZQ";
  });

  it("says plainly that the symbol is not covered", () => {
    render(<TickerNotCovered />);
    expect(screen.getByText("Not covered")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("ZZZZQ isn’t covered");
  });

  it("is not a dead end: it links to search and to the scored list", () => {
    render(<TickerNotCovered />);
    expect(screen.getByRole("link", { name: /search for a ticker/i })).toHaveAttribute("href", "/search");
    expect(screen.getByRole("link", { name: /browse scored stocks/i })).toHaveAttribute("href", "/signals");
  });

  it("never prefills the search, which would loop back here", () => {
    // /search 302s anything ticker-shaped to /t/{SYMBOL}.
    render(<TickerNotCovered />);
    for (const a of screen.getAllByRole("link")) {
      expect(a.getAttribute("href") ?? "", "a link carries the symbol back into /search").not.toMatch(/\/search\?/);
    }
  });

  it("makes no coverage count claim", () => {
    const { container } = render(<TickerNotCovered />);
    expect(container.textContent).not.toMatch(/\d[\d,]*\+?\s*(US|stocks|tickers)|\bevery\b/i);
  });

  it("stays a real 404: the ticker page still calls notFound() for a missing symbol", () => {
    const page = readFileSync(join(process.cwd(), "app/t/[symbol]/page.tsx"), "utf8");
    expect(page).toMatch(/result\.status === "missing"\)\s*notFound\(\)/);
  });
});

describe("requestedSymbol", () => {
  it("reads and upper-cases the last path segment", () => {
    expect(requestedSymbol("/t/zzzzq")).toBe("ZZZZQ");
    expect(requestedSymbol("/t/BRK.B")).toBe("BRK.B");
  });

  it("strips anything a ticker cannot hold, so a URL cannot write the heading", () => {
    expect(requestedSymbol("/t/%3Cb%3Ebuy%20now%3C%2Fb%3E")).toBe("BBUYNOWB");
    expect(requestedSymbol("/t/" + "A".repeat(40))).toHaveLength(12);
  });

  it("falls back when there is nothing usable", () => {
    expect(requestedSymbol(null)).toBeNull();
    pathname.value = "/t/%%%";
    render(<TickerNotCovered />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("This ticker isn’t covered");
  });
});
