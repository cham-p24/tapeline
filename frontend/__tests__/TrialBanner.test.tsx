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
 *   3. The banner must tell the truth about the CARD, and the truth now has
 *      two shapes:
 *        - CARD ON FILE (the 2026-08 card-required trial): a real charge is
 *          scheduled, so the date of it and the one-click exit must be stated.
 *          "No card was taken" / "nothing to cancel" would be a lie, and
 *          "add a card" would nag someone who already gave us one.
 *        - NO CARD ON FILE (legacy auto-granted trial): trial end is not a
 *          billing event — nothing charged, nothing to cancel.
 *      The card state comes from the API, so there is also an UNKNOWN state,
 *      and the rule there is that the banner asserts NEITHER story.
 *
 * These tests changed with the card-required-trial work: the old file asserted
 * the no-card copy unconditionally, which is exactly the claim that can no
 * longer be made unconditionally.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// The banner switches to its START copy at TRIAL_DAYS - 1 days left, so
// "a trial that just began" is a function of the trial length, not the
// literal 14. These tests hardcoded 14 and silently stopped testing the
// start phase at all when the trial moved to 30 days.
import { TRIAL_DAYS } from "@/lib/trial";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));

import { TrialBanner, __resetCardOnFileCache } from "@/components/TrialBanner";
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

/** The banner's own date format, so assertions can't drift from the render. */
const endLabel = (daysLeft: number) =>
  new Date(Date.now() + (daysLeft - 0.5) * 86_400_000).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });

/** Tokens that signal alarm/urgency treatment in this design system. */
const ALARM_CLASS = /\b(?:bg|text|border|from|to|ring)-(?:down|warn|red|danger|destructive)/;
const MOTION_CLASS = /animate-(?:pulse|ping|bounce)/;

/**
 * Stub the card-state lookup. `null` leaves both endpoints answering an empty
 * object, which is what the component sees when the API can't tell it.
 */
function stubCardOnFile(value: boolean | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve(value === null ? {} : { has_card_on_file: value }),
      }),
    ),
  );
}

const render_ = (daysLeft: number) => {
  mockedUseUser.mockReturnValue(trialingUser(daysLeft));
  return render(<TrialBanner />);
};

beforeEach(() => {
  mockedUseUser.mockReset();
  __resetCardOnFileCache();
  stubCardOnFile(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
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

  it("keeps the SAME class list whether or not a card is on file", async () => {
    // A card on file must not buy the banner a louder treatment either.
    stubCardOnFile(false);
    const { unmount } = render_(3);
    await screen.findByText(/no card on file/i);
    const cardless = screen.getByTestId("trial-banner").className;
    unmount();

    __resetCardOnFileCache();
    stubCardOnFile(true);
    render_(3);
    await screen.findByText(/first charge is on/i);
    expect(screen.getByTestId("trial-banner").className).toBe(cardless);
  });

  it("never uses urgency or loss-aversion language, in any card state", async () => {
    for (const cardOnFile of [true, false, null] as const) {
      for (const daysLeft of [14, 3, 1]) {
        __resetCardOnFileCache();
        stubCardOnFile(cardOnFile);
        const { container, unmount } = render_(daysLeft);
        await waitFor(() =>
          expect(container.querySelector("[data-card-on-file]")).toHaveAttribute(
            "data-card-on-file",
            String(cardOnFile === null ? "unknown" : cardOnFile),
          ),
        );
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
    }
  });

  it("does not tick seconds — it states whole days remaining", () => {
    const { container } = render_(3);
    expect(container.textContent).toMatch(/3 days left/i);
    expect(container.textContent).not.toMatch(/\d+\s*(?:seconds?|minutes?|hours?)/i);
  });
});

// ── CARD ON FILE — the current, card-required trial ────────────────────────
// A charge really is coming. Honest disclosure is mandatory, and nagging for
// a card the user has already given is forbidden.

describe("TrialBanner — card on file", () => {
  beforeEach(() => {
    __resetCardOnFileCache();
    stubCardOnFile(true);
  });

  it("states nothing charged yet, the first-charge date, and the one-click exit", async () => {
    const { container } = render_(TRIAL_DAYS);
    await screen.findByText(/first charge is on/i);
    const text = container.textContent ?? "";
    expect(text).toMatch(/premium is active/i);
    expect(text).toMatch(/nothing has been charged/i);
    expect(text).toMatch(new RegExp(`first charge is on ${endLabel(TRIAL_DAYS)}`, "i"));
    expect(text).toMatch(/one click/i);
    expect(text).toMatch(/not charged at all/i);
  });

  it("keeps the same disclosure mid-trial, not only on day one", async () => {
    const { container } = render_(3);
    await screen.findByText(/first charge is on/i);
    const text = container.textContent ?? "";
    expect(text).toMatch(/3 days left/i);
    expect(text).toMatch(/nothing has been charged/i);
    expect(text).toMatch(new RegExp(`first charge is on ${endLabel(3)}`, "i"));
  });

  it("NEVER claims no card was taken or that there is nothing to cancel", async () => {
    for (const daysLeft of [14, 7, 1]) {
      __resetCardOnFileCache();
      stubCardOnFile(true);
      const { container, unmount } = render_(daysLeft);
      await screen.findByText(/first charge is on/i);
      const text = container.textContent ?? "";
      expect(text).not.toMatch(/no card (?:was taken|on file)/i);
      expect(text).not.toMatch(/nothing to cancel/i);
      unmount();
    }
  });

  it("never tells a card-on-file trialist to add a card", async () => {
    const { container } = render_(7);
    await screen.findByText(/first charge is on/i);
    expect(container.textContent ?? "").not.toMatch(/add(?:ing)? a card/i);
    // …and the action is management, not capture.
    expect(screen.getByRole("link").textContent).toMatch(/manage plan/i);
  });
});

// ── NO CARD ON FILE — the legacy auto-granted trial ────────────────────────

describe("TrialBanner — no card on file (legacy trial)", () => {
  beforeEach(() => {
    __resetCardOnFileCache();
    stubCardOnFile(false);
  });

  it("states that Premium is active, for the full trial, with no card taken", async () => {
    const { container } = render_(TRIAL_DAYS);
    await screen.findByText(/no card was taken/i);
    const text = container.textContent ?? "";
    expect(text).toMatch(/premium is active/i);
    expect(text).toMatch(new RegExp(`${TRIAL_DAYS} days`));
    expect(text).toMatch(/nothing to cancel/i);
  });

  it("keeps the no-card / nothing-charged reassurance mid-trial too", async () => {
    const { container } = render_(3);
    await screen.findByText(/no card on file/i);
    const text = container.textContent ?? "";
    expect(text).toMatch(/nothing is charged/i);
    expect(text).toMatch(/nothing to cancel/i);
  });

  it("never frames trial expiry as a billing event", async () => {
    for (const daysLeft of [14, 3, 1]) {
      __resetCardOnFileCache();
      stubCardOnFile(false);
      const { container, unmount } = render_(daysLeft);
      await waitFor(() =>
        expect(container.textContent ?? "").toMatch(/no card (?:was taken|on file)/i),
      );
      const text = container.textContent ?? "";
      expect(text).not.toMatch(/you (?:will|'ll) be (?:charged|billed)/i);
      expect(text).not.toMatch(/(?:card|payment method) (?:will be )?charged/i);
      unmount();
    }
  });
});

// ── UNKNOWN — the API could not answer ─────────────────────────────────────

describe("TrialBanner — unknown card state", () => {
  it("asserts NEITHER story rather than defaulting to the no-card copy", () => {
    const { container } = render_(TRIAL_DAYS);
    const text = container.textContent ?? "";
    // Only what the session payload proves.
    expect(text).toMatch(/premium is active/i);
    expect(text).toMatch(new RegExp(`${TRIAL_DAYS} days`));
    // No claim in either direction.
    expect(text).not.toMatch(/no card (?:was taken|on file)/i);
    expect(text).not.toMatch(/nothing to cancel/i);
    expect(text).not.toMatch(/first charge is on/i);
    expect(text).not.toMatch(/add(?:ing)? a card/i);
  });

  it("survives an API failure without throwing or asserting a card claim", async () => {
    __resetCardOnFileCache();
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
    const { container } = render_(6);
    await waitFor(() => expect(screen.getByTestId("trial-banner")).toBeInTheDocument());
    const text = container.textContent ?? "";
    expect(text).toMatch(/6 days left/i);
    expect(text).not.toMatch(/no card (?:was taken|on file)/i);
    expect(text).not.toMatch(/first charge is on/i);
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

  it("makes no network call when nobody is on a trial", () => {
    const fetchSpy = vi.fn(() =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) }),
    );
    vi.stubGlobal("fetch", fetchSpy);
    mockedUseUser.mockReturnValue({
      user: { id: "u_3", email: "f@example.com", name: null, tier: "free", created_at: null },
      loading: false,
      refresh: vi.fn(),
      signout: vi.fn(),
    });
    render(<TrialBanner />);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
