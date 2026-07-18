/**
 * TrialBanner — the in-trial status strip. This component is the one place in
 * the product where a time-remaining statement is permitted at all
 * (docs/COMPLIANCE_COPY_RULES.md Rule 6, the trial-expiry exception), and the
 * exception is conditional on the presentation staying calm. These tests are
 * the guard rail:
 *
 *   1. NO alarm styling at low days-remaining. The banner previously swapped to
 *      the red loss token (`down`) at <= 3 days and amber (`warn`) at <= 7.
 *      The class list must be identical on day 14 and day 1.
 *   2. NO urgency language, ever.
 *   3. The trial is NEVER framed as a billing event — it takes no card, so
 *      nothing is charged and there is nothing to cancel.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));

import { TrialBanner } from "@/components/TrialBanner";
import { useUser } from "@/components/UserContext";

const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

const trialingUser = (daysLeft: number) => ({
  user: {
    id: "u_1",
    email: "t@example.com",
    name: null,
    tier: "premium",
    // + a few hours so Math.ceil lands on exactly `daysLeft`.
    trial_ends_at: new Date(Date.now() + (daysLeft - 0.5) * 86_400_000).toISOString(),
    created_at: null,
  },
  loading: false,
  refresh: vi.fn(),
  signout: vi.fn(),
});

/** Tokens that signal alarm/urgency treatment in this design system. */
const ALARM_CLASS = /\b(?:bg|text|border|from|to|ring)-(?:down|warn|red|danger|destructive)/;
const MOTION_CLASS = /animate-(?:pulse|ping|bounce)/;

const render_ = (daysLeft: number) => {
  mockedUseUser.mockReturnValue(trialingUser(daysLeft));
  return render(<TrialBanner />);
};

beforeEach(() => {
  mockedUseUser.mockReset();
});

describe("TrialBanner — Rule 6 calm styling", () => {
  it.each([14, 13, 7, 5, 3, 2, 1])(
    "uses no alarm or motion classes at %i day(s) left",
    (daysLeft) => {
      const { container } = render_(daysLeft);
      const html = container.innerHTML;
      expect(html).not.toMatch(ALARM_CLASS);
      expect(html).not.toMatch(MOTION_CLASS);
    },
  );

  it("keeps an identical class list from day 14 down to day 1", () => {
    const { unmount } = render_(14);
    const early = screen.getByTestId("trial-banner").className;
    unmount();
    render_(1);
    expect(screen.getByTestId("trial-banner").className).toBe(early);
  });

  it("never uses urgency or loss-aversion language", () => {
    for (const daysLeft of [14, 3, 1]) {
      const { container, unmount } = render_(daysLeft);
      const text = container.textContent ?? "";
      for (const phrase of [
        /hurry/i,
        /last chance/i,
        /act (?:now|fast)/i,
        /don'?t (?:lose|miss)/i,
        /before it'?s too late/i,
        /expir\w+ in \d+ (?:hour|minute|second)/i,
        /countdown/i,
        /final (?:day|hours?)/i,
      ]) {
        expect(text).not.toMatch(phrase);
      }
      unmount();
    }
  });

  it("does not tick seconds — it states whole days remaining", () => {
    const { container } = render_(3);
    expect(container.textContent).toMatch(/3 days left/i);
    expect(container.textContent).not.toMatch(/\d+\s*(?:seconds?|minutes?|hours?)/i);
  });
});

describe("TrialBanner — trial-start clarity", () => {
  it("states that Premium is active, for 14 days, with no card taken", () => {
    const { container } = render_(14);
    const text = container.textContent ?? "";
    expect(text).toMatch(/premium is active/i);
    expect(text).toMatch(/14 days/);
    expect(text).toMatch(/no card was taken/i);
    expect(text).toMatch(/nothing to cancel/i);
  });

  it("keeps the no-card / nothing-charged reassurance mid-trial too", () => {
    const { container } = render_(3);
    const text = container.textContent ?? "";
    expect(text).toMatch(/no card on file/i);
    expect(text).toMatch(/nothing is charged/i);
    expect(text).toMatch(/nothing to cancel/i);
  });

  it("never frames trial expiry as a billing event", () => {
    for (const daysLeft of [14, 3, 1]) {
      const { container, unmount } = render_(daysLeft);
      const text = container.textContent ?? "";
      expect(text).not.toMatch(/you (?:will|'ll) be (?:charged|billed)/i);
      expect(text).not.toMatch(/cancel (?:before|by|now)/i);
      expect(text).not.toMatch(/add a card to (?:keep|avoid)/i);
      expect(text).not.toMatch(/(?:card|payment method) (?:will be )?charged/i);
      unmount();
    }
  });
});

describe("TrialBanner — render conditions", () => {
  it("renders nothing without a trial", () => {
    mockedUseUser.mockReturnValue({
      user: { id: "u_2", email: "f@example.com", name: null, tier: "free", created_at: null },
      loading: false,
      refresh: vi.fn(),
      signout: vi.fn(),
    });
    const { container } = render(<TrialBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing once the trial has expired", () => {
    const { container } = render_(-2);
    expect(container).toBeEmptyDOMElement();
  });
});
