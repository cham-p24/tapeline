/**
 * Landing page fold — the hero must pair the real-data scanner preview with
 * a zero-signup path into the product: the "See today's full Top 10 — no
 * signup →" link to /daily-picks, and no leftover "Live mock" framing from
 * the retired fabricated demo.
 *
 * It must also offer TWO first-class entry points, not one button plus a
 * ghost link. The fold previously demoted everything except /signup to
 * `btn-ghost` (borderless, muted text), so the no-card trial's terms and the
 * no-account browse path both read as footnotes. Both doors now carry equal
 * visual weight, and the trial is described plainly — no card, nothing
 * charged, and no deadline framing (compliance Rule 6).
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

  // ── Paired entry points ──────────────────────────────────────────────────

  it("offers BOTH hero CTAs: start the trial, and browse with no account", () => {
    render(<LandingPage />);
    expect(
      screen.getByRole("link", { name: /start the 14-day trial/i }),
    ).toHaveAttribute("href", "/signup");
    expect(
      screen.getByRole("link", { name: /browse without an account/i }),
    ).toHaveAttribute("href", "/daily-picks");
  });

  it("gives both hero CTAs equal visual weight (neither is a muted btn-ghost)", () => {
    render(<LandingPage />);
    const trial = screen.getByRole("link", { name: /start the 14-day trial/i });
    const browse = screen.getByRole("link", { name: /browse without an account/i });
    // Both are full pill buttons...
    expect(trial.className).toMatch(/\bbtn(-primary)?\b/);
    expect(browse.className).toMatch(/\bbtn\b/);
    // ...and neither is the borderless, muted treatment that buried the
    // secondary path before. `btn-ghost` here is the regression to catch.
    expect(trial.className).not.toMatch(/btn-ghost/);
    expect(browse.className).not.toMatch(/btn-ghost/);
    // The browse CTA carries a real border so it reads as a button, not text.
    expect(browse.className).toMatch(/border/);
  });

  it("states the trial terms plainly: no card, nothing charged, falls back to Free", () => {
    render(<LandingPage />);
    const terms = screen.getByText(
      /no credit card, no payment details, nothing charged/i,
    );
    expect(terms).toBeInTheDocument();
    expect(terms.textContent).toMatch(/14 days of Premium/i);
    expect(terms.textContent).toMatch(/stays on the Free tier/i);
  });

  it("keeps the trial CTA free of urgency and scarcity framing (Rule 6)", () => {
    const { container } = render(<LandingPage />);
    const text = container.textContent ?? "";
    // No deadline pricing, no countdown, no "N spots/seats left", no
    // "expires"/"ends soon" pressure anywhere in the fold copy.
    expect(text).not.toMatch(/only \d+ (left|remaining|spots?|seats?)/i);
    expect(text).not.toMatch(/countdown|hurry|act now|limited time|ends soon/i);
    expect(text).not.toMatch(/offer expires|last chance to/i);
  });
});
