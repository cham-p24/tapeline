/**
 * Meta pixel scoping — it must never load on the logged-in product.
 *
 * The risk being guarded: Meta's fbevents.js reports the FULL current URL as
 * the `dl` parameter on its /tr/ beacon. `dl` is a payload field, not the
 * Referer header, so Referrer-Policy does not trim it — and because /tr/ is on
 * facebook.com, the browser may attach Facebook cookies it already holds. An
 * unscoped pixel therefore tells Meta which specific tickers a user researches,
 * linkable to their real Facebook account.
 *
 * Nothing is lost by scoping: every conversion is sent server-side by
 * services/meta_capi, which needs no browser.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

const mockPathname = vi.fn<() => string | null>();
vi.mock("next/navigation", () => ({ usePathname: () => mockPathname() }));

// next/script renders nothing useful in jsdom; stand in with a marker element
// so "did it render" is observable.
type ScriptStub = {
  id?: string;
  dangerouslySetInnerHTML?: { __html: string };
};

vi.mock("next/script", () => ({
  default: ({ id, dangerouslySetInnerHTML }: ScriptStub) => (
    <div data-testid="script" data-id={id}>
      {dangerouslySetInnerHTML?.__html ?? ""}
    </div>
  ),
}));

import { MetaPixel, isPixelAllowedPath } from "@/components/MetaPixel";

const PIXEL = "123456789";

beforeEach(() => mockPathname.mockReset());

describe("MetaPixel — path scoping", () => {
  it("does NOT render on the ticker page — the case that leaks the most", () => {
    mockPathname.mockReturnValue("/app/ticker/NVDA");
    const { queryByTestId } = render(<MetaPixel pixelId={PIXEL} />);
    expect(queryByTestId("script")).toBeNull();
  });

  it.each([
    "/app",
    "/app/scanner",
    "/app/holdings",
    "/app/billing",
    "/app/account",
    "/app/congress",
  ])("does NOT render on %s", (path) => {
    mockPathname.mockReturnValue(path);
    const { queryByTestId } = render(<MetaPixel pixelId={PIXEL} />);
    expect(queryByTestId("script")).toBeNull();
  });

  it.each(["/", "/pricing", "/signup", "/scorecard", "/how-it-works", "/blog/x"])(
    "DOES render on the marketing page %s — this is where attribution happens",
    (path) => {
      mockPathname.mockReturnValue(path);
      const { getByTestId } = render(<MetaPixel pixelId={PIXEL} />);
      expect(getByTestId("script").textContent).toContain(`fbq('init', '${PIXEL}')`);
    },
  );

  it("does not match a path that merely starts with the same letters", () => {
    // "/apply" must not be treated as being under "/app".
    mockPathname.mockReturnValue("/apply");
    const { queryByTestId } = render(<MetaPixel pixelId={PIXEL} />);
    expect(queryByTestId("script")).not.toBeNull();
  });

  it("renders nothing when no pixel id is set — the production state today", () => {
    mockPathname.mockReturnValue("/pricing");
    const { queryByTestId } = render(<MetaPixel pixelId="" />);
    expect(queryByTestId("script")).toBeNull();
  });

  it("fires PageView only — conversions are server-side", () => {
    mockPathname.mockReturnValue("/");
    const { getByTestId } = render(<MetaPixel pixelId={PIXEL} />);
    const src = getByTestId("script").textContent ?? "";
    expect(src).toContain("fbq('track', 'PageView')");
    // No conversion event may be fired from the browser: meta_capi owns those,
    // and a duplicate browser event would need event_id dedupe to stay honest.
    for (const ev of ["Purchase", "StartTrial", "CompleteRegistration"]) {
      expect(src).not.toContain(ev);
    }
  });

  it("passes no advanced-matching object to init", () => {
    // fbq('init', id) with a second argument would hand Meta user data from
    // our own code. (Automatic Advanced Matching is a dashboard toggle we
    // cannot control from here — see the component docstring.)
    mockPathname.mockReturnValue("/");
    const { getByTestId } = render(<MetaPixel pixelId={PIXEL} />);
    expect(getByTestId("script").textContent).toContain(`fbq('init', '${PIXEL}');`);
  });
});

describe("isPixelAllowedPath", () => {
  it("treats a null pathname as not allowed (fail closed)", () => {
    expect(isPixelAllowedPath(null)).toBe(false);
  });

  it("excludes /app and everything under it", () => {
    expect(isPixelAllowedPath("/app")).toBe(false);
    expect(isPixelAllowedPath("/app/")).toBe(false);
    expect(isPixelAllowedPath("/app/ticker/AAPL")).toBe(false);
  });

  it("allows public routes", () => {
    expect(isPixelAllowedPath("/")).toBe(true);
    expect(isPixelAllowedPath("/t/AAPL")).toBe(true);
  });
});
