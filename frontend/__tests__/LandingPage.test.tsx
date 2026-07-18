/**
 * Landing page fold — the hero must pair the real-data scanner preview with
 * a zero-signup path into the product: the "See today's full Top 10 — no
 * signup →" link to /daily-picks, and no leftover "Live mock" framing from
 * the retired fabricated demo.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// ScannerPreview is an async server component (server-fetches the real
// anonymous top-10) — RTL/jsdom can't render async components, so stub it.
// Its own contract is covered in ScannerPreview.test.tsx.
vi.mock("@/components/ScannerPreview", () => ({
  ScannerPreview: () =>
    require("react").createElement("div", { "data-testid": "scanner-preview" }),
}));
// Client widgets with their own timers/fetch loops — out of scope here.
vi.mock("@/components/LiveCounters", () => ({ LiveCounters: () => null }));
vi.mock("@/components/ExitIntentModal", () => ({ ExitIntentModal: () => null }));
// FadeIn mounts an IntersectionObserver, which jsdom doesn't implement —
// pass children straight through.
vi.mock("@/components/FadeIn", () => ({
  FadeIn: ({ children }: { children: unknown }) => children,
}));

import LandingPage from "@/app/page";

describe("LandingPage hero fold", () => {
  it("links the fold to the zero-signup /daily-picks Top 10", () => {
    render(<LandingPage />);
    const link = screen.getByRole("link", {
      name: /see today.s full top 10 — no signup/i,
    });
    expect(link).toHaveAttribute("href", "/daily-picks");
  });

  it("retires the 'Live mock' framing from the fold", () => {
    render(<LandingPage />);
    expect(screen.queryByText(/live mock/i)).toBeNull();
  });
});
