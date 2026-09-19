/**
 * Public pages must survive the keyless response shape (2026-09-19).
 *
 * /api/public/heatmap and /api/public/signals serve prices and daily moves
 * only to a signed-in user or to our own SSR (INTERNAL_SSR_TOKEN). Anyone else,
 * including `next build` (which has no token) and a PR preview without the
 * secret, gets the same rows WITHOUT those fields. Two pages dereferenced them
 * unguarded: /stock-market-heatmap called change_pct_1d.toFixed (a TypeError at
 * build-time prerender, which fails `next build`), and /signals tested
 * `v === null`, which lets an absent (undefined) field through to .toFixed.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));
vi.mock("@/components/NewsletterCapture", () => ({ NewsletterCapture: () => null }));
vi.mock("@/components/AnonSignupNudge", () => ({ AnonSignupNudge: () => null }));
// /signals reads the session cookie (it is a per-request page); outside a
// request there is none, which is the keyless case this file is about.
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: () => undefined, has: () => false, getAll: () => [] }),
  headers: async () => new Headers(),
}));

import HeatmapPage from "@/app/stock-market-heatmap/page";
import SignalsPage from "@/app/signals/page";

afterEach(() => {
  vi.unstubAllGlobals();
});

function respond(body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })),
  );
}

describe("/stock-market-heatmap", () => {
  it("renders the labelled example, not a crash, on a keyless answer", async () => {
    respond({
      count: 2,
      sectors: [
        { sector: "Energy", ticker_count: 40 },
        { sector: "Utilities", ticker_count: 30 },
      ],
      prices_served: false,
    });
    const { container } = render(await HeatmapPage());
    expect(container.textContent).toContain("Snapshot example.");
    expect(container.textContent).not.toContain("undefined");
  });

  it("renders the served moves for our own SSR", async () => {
    respond({
      count: 1,
      sectors: [{ sector: "Energy", change_pct_1d: 1.23, ticker_count: 40 }],
      prices_served: true,
    });
    const { container } = render(await HeatmapPage());
    expect(container.textContent).toContain("+1.23%");
    expect(container.textContent).not.toContain("Snapshot example.");
  });

  it("is rendered per request, never prerendered at build without the token", async () => {
    const mod = await import("@/app/stock-market-heatmap/page");
    expect((mod as { dynamic?: string }).dynamic).toBe("force-dynamic");
  });
});

describe("/signals", () => {
  it("renders dashes, not a crash, when price fields are absent", async () => {
    const row = {
      symbol: "ZZZ",
      name: "Zed Corp",
      sector: "Energy",
      asset_class: "equity",
      score: 72.5,
      signal: "STRONG SETUP",
      confidence_pct: 80,
      sub_trend: 70,
      sub_rs: 70,
      sub_fundamentals: 70,
      sub_momentum: 70,
      sub_macro: 50,
      sub_smart_money: null,
      updated_at: "2026-09-19T00:00:00+00:00",
    };
    respond({ count: 1, limit: 1000, offset: 0, prices_served: false, items: [row] });
    const { container } = render(await SignalsPage());
    expect(container.textContent).toContain("ZZZ");
    expect(container.textContent).not.toContain("undefined");
    expect(container.textContent).not.toContain("NaN");
  });
});
