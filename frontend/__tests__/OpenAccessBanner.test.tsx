/**
 * Open-access month strip — the on-site surface of the backend promo
 * (tier.py `free_open_access()`): until 8 September 2026 a SIGNED-IN Free
 * account's scanner row cap lifts from the top 10 to the Pro cap (1,000).
 *
 * The copy contract this suite pins:
 *   - the strip states the factual end date and that the full list needs a
 *     signed-in account (the backend lift is authenticated-only — anonymous
 *     callers keep the top 10);
 *   - it carries no urgency or scarcity vocabulary (compliance Rule 6), and
 *     promises nothing about the account it cannot keep. Between 2026-08-22
 *     and #683 (2026-08-30) this list also banned every "no card" wording,
 *     because a new account met a card wall at first sign-in. The wall is
 *     gone: signing up is an email and a password and a free account really
 *     does reach the scanner, so card-free wording about SIGNUP is now simply
 *     accurate and is no longer policed here. The 14-day Premium trial still
 *     takes a card — but this strip is not about the trial;
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

  it("offers Sign in as the door — the promo lifts an account, not a session", () => {
    // The lift is authenticated-only, so the strip has to point somewhere an
    // account happens. It used to point at /signin *because* signup meant a
    // card wall; since #683 a signup link would be honest here too, so this
    // pins the door by HREF rather than forbidding a second one.
    render(<OpenAccessBanner now={DURING} />);
    const hrefs = screen
      .getAllByRole("link")
      .map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/signin");
  });

  it("carries no urgency/scarcity framing and promises nothing it can't keep", () => {
    render(<OpenAccessBanner now={DURING} />);
    const text = (
      screen.getByTestId("open-access-banner").textContent || ""
    ).toLowerCase();
    // Rule 6 vocabulary — a factual end date is permitted, pressure is not.
    expect(text).not.toMatch(
      /hurry|act now|last chance|limited time|countdown|ends in \d|only \d+ (left|remaining|spots?)/i,
    );
    // "no card" / "start free" were on this list from the 2026-08-22 card gate
    // until #683 removed the wall; both are now true of signing up, so banning
    // them here would be enforcing a claim that stopped being false. What is
    // still off-limits is the permanence promise ("free forever" — the free
    // tier is a product decision, not a covenant) and the banned marketing
    // phrase, which remains false of the trial this strip sits above.
    for (const banned of ["free forever", "no credit card required"]) {
      expect(text).not.toContain(banned);
    }
    // And nothing on a strip about the FREE tier may describe the trial as
    // card-free — the trial takes a card, unchanged by #683.
    expect(text).not.toMatch(/trial[^.;·]{0,30}(?:no|without a) (?:credit )?card/i);
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
