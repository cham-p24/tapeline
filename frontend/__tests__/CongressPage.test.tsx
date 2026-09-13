/**
 * Congressional trades: the honest "not available" state (T-02, 2026-09-14).
 *
 * No real congressional disclosure is being ingested today. Every
 * `congress_trades` row in production is mock-generator output, and
 * backend/app/services/congress_integrity.py already refuses to publish them.
 * Until this change the public /congressional-trades page showed five
 * hardcoded placeholder rows under an H1 reading "Live Tracker", and the
 * in-app /app/congress page described "every disclosed House and Senate
 * trade" synced "multiple times per day". The founder approved removing the
 * claim on 2026-09-14.
 *
 * The replaced suite asserted the Premium feed loaded and the Free preview
 * showed "REAL" rows. Both pinned a feed that does not exist. What is pinned
 * now: both pages say plainly the data is not available, render no rows of
 * any kind, fetch nothing, point to the SEC Form 4 page, and the public page
 * asks search engines not to index it.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => <nav /> }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => <footer /> }));

import PublicCongressPage, { metadata } from "@/app/congressional-trades/page";
import AppCongressPage from "@/app/app/congress/page";

const H1 = "Congressional trade data isn’t available";

afterEach(() => {
  vi.unstubAllGlobals();
});

function assertHonestState(container: HTMLElement) {
  expect(screen.getByRole("heading", { level: 1 }).textContent?.replace(/\s+/g, " ").trim()).toBe(H1);
  const text = (container.textContent ?? "").replace(/\s+/g, " ");
  expect(text).toMatch(/don’t currently have a real source of congressional trade disclosures/i);
  expect(text).toMatch(/so we don’t show any/i);
  // No rows of any kind: no table, no ticker links, none of the old
  // placeholder symbols or "N days ago" dates.
  expect(container.querySelector("table")).toBeNull();
  expect(container.querySelectorAll("tr")).toHaveLength(0);
  for (const sym of ["NVDA", "MSFT", "AAPL", "GOOGL", "META"]) {
    expect(text).not.toContain(sym);
  }
  expect(text).not.toMatch(/days? ago|weeks? ago|\blive\b|premium|senator|house \+ senate|upgrade/i);
  // The one real alternative: public SEC Form 4 filings.
  const link = screen.getByRole("link", { name: /insider buying page/i });
  expect(link.getAttribute("href")).toBe("/insider-buying");
  expect(text).toMatch(/SEC Form 4/);
}

describe("/congressional-trades (public)", () => {
  it("renders the honest not-available page with no rows", () => {
    const { container } = render(<PublicCongressPage />);
    assertHonestState(container);
  });

  it("is noindex", () => {
    expect(metadata.robots).toEqual({ index: false, follow: true });
    expect(String(metadata.title)).toMatch(/isn't available/i);
  });
});

describe("/app/congress (in-app)", () => {
  it("renders the same honest state and fetches nothing", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { container } = render(<AppCongressPage />);
    assertHonestState(container);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
