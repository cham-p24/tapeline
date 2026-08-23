/**
 * Open-access month strip — the on-site surface of the backend promo
 * (tier.py `free_open_access()`): until 8 September 2026 a SIGNED-IN Free
 * account's scanner row cap lifts from the top 10 to the Pro cap (1,000).
 *
 * The copy contract this suite pins:
 *   - the strip states the factual end date and that the full list needs a
 *     signed-in account (the backend lift is authenticated-only — anonymous
 *     callers keep the top 10);
 *   - it makes NO card-free-account claim (2026-08-22 card gate: a new
 *     account adds a card at first sign-in) and carries no urgency or
 *     scarcity vocabulary (compliance Rule 6);
 *   - it date-gates itself on the exact backend boundary (`d < UNTIL`:
 *     7 September is the last open day) so it auto-disappears with no deploy.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OpenAccessBanner } from "@/components/OpenAccessBanner";

const DURING = new Date("2026-08-23T12:00:00Z");
const LAST_OPEN_INSTANT = new Date("2026-09-07T23:59:59Z");
const CUTOFF = new Date("2026-09-08T00:00:00Z");

describe("OpenAccessBanner", () => {
  it("states the promo factually: end date, signed-in requirement, both row numbers", () => {
    render(<OpenAccessBanner now={DURING} />);
    const strip = screen.getByTestId("open-access-banner");
    const text = strip.textContent || "";
    expect(text).toMatch(/open-access month/i);
    expect(text).toMatch(/until 8 September/i);
    // The lift is for signed-in accounts; signed out you keep the top 10.
    expect(text).toMatch(/signed-in account/i);
    expect(text).toMatch(/signed out, you get the top 10/i);
    // The real numbers, mirroring tier.py: Pro cap 1,000 / Free cap 10.
    expect(text).toMatch(/1,000 rows/);
  });

  it("offers Sign in — not a card-free signup — as the door", () => {
    // Since the 2026-08-22 card gate a NEW account takes a card, so the only
    // honest CTA for the accounts this promo reaches is /signin.
    render(<OpenAccessBanner now={DURING} />);
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute(
      "href",
      "/signin",
    );
  });

  it("carries no urgency/scarcity framing and no card-free-account claim", () => {
    render(<OpenAccessBanner now={DURING} />);
    const text = (
      screen.getByTestId("open-access-banner").textContent || ""
    ).toLowerCase();
    // Rule 6 vocabulary — a factual end date is permitted, pressure is not.
    expect(text).not.toMatch(
      /hurry|act now|last chance|limited time|countdown|ends in \d|only \d+ (left|remaining|spots?)/i,
    );
    // Card-gate honesty — the phrases scrubbed sitewide by #548/#560/#563/#573.
    for (const banned of ["no card", "no credit card", "free forever", "start free"]) {
      expect(text).not.toContain(banned);
    }
  });

  it("renders through the last open instant and disappears at the backend cutoff", () => {
    // Backend is `d < PROMO_OPEN_ACCESS_UNTIL`: 7 Sep is the last open day.
    const { unmount } = render(<OpenAccessBanner now={LAST_OPEN_INSTANT} />);
    expect(screen.getByTestId("open-access-banner")).toBeInTheDocument();
    unmount();
    render(<OpenAccessBanner now={CUTOFF} />);
    expect(screen.queryByTestId("open-access-banner")).toBeNull();
  });
});
